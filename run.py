# -*- coding: utf-8 -*-
"""
================================================================================
  SNAKE IA - ORQUESTADOR
================================================================================
  Levanta el proyecto entero con un solo comando:

      npm run dev     -> python run.py            (desarrollo)
      npm start       -> python run.py --prod     (web ya compilada)

  En DESARROLLO arranca dos procesos en paralelo:
      1. El servidor de la IA  (uvicorn -> ai_server.py)  en el puerto 8000
      2. El servidor de Vite   (npm run vite)             en el puerto 5173

  Se abre el navegador en Vite (5173), que hace de proxy hacia el 8000 para
  /api y /ws (ver vite.config.js). Asi el frontend usa rutas relativas y el
  mismo codigo vale en desarrollo y en produccion, sin URLs hardcodeadas.

  En PRODUCCION (--prod) solo arranca el servidor de la IA, que sirve `dist/`:
  un unico proceso y un unico puerto para el hosting.

  Ctrl+C cierra los dos procesos de forma ordenada.
================================================================================
"""

import os
import sys
import time
import signal
import shutil
import socket
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR   = os.path.join(SCRIPT_DIR, "dist")

API_PORT  = int(os.environ.get("PORT", 8000))
VITE_PORT = 5173

# Los procesos vivos, para poder cerrarlos todos al salir.
procesos = []


def log(quien, mensaje):
    """Mensajes del orquestador, con prefijo para distinguirlos de los hijos."""
    print(f"[{quien}] {mensaje}", flush=True)


def npm_cmd():
    """Ruta del ejecutable de npm.

    En Windows npm es `npm.cmd`, no `npm`: sin esto, subprocess falla con
    FileNotFoundError aunque npm este perfectamente instalado.
    """
    for nombre in ("npm.cmd", "npm") if os.name == "nt" else ("npm",):
        ruta = shutil.which(nombre)
        if ruta:
            return ruta
    return None


def puerto_ocupado(puerto):
    """True si algo ya escucha en ese puerto de localhost.

    Se prueban TODAS las direcciones de localhost, no solo 127.0.0.1: Vite
    escucha en ::1 (IPv6) y una comprobacion solo IPv4 no lo veria nunca.
    """
    try:
        infos = socket.getaddrinfo("localhost", puerto, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False
    for familia, tipo, proto, _, direccion in infos:
        with socket.socket(familia, tipo, proto) as s:
            s.settimeout(0.4)
            if s.connect_ex(direccion) == 0:
                return True
    return False


def comprobar_puertos(prod):
    """Avisa ANTES de arrancar si los puertos ya estan ocupados.

    Sin esto, uvicorn falla al atar el puerto con un error de winsock que no le
    dice nada a nadie. La causa casi siempre es otro `npm run dev` abierto, o
    uno anterior que dejo procesos huerfanos.
    """
    ocupados = [p for p in ([API_PORT] if prod else [API_PORT, VITE_PORT])
                if puerto_ocupado(p)]
    if not ocupados:
        return True

    for p in ocupados:
        log("ERROR", f"El puerto {p} ya esta ocupado.")
    log("ERROR", "Seguramente tengas otro 'npm run dev' abierto, o quedaron")
    log("ERROR", "procesos de un arranque anterior. Cierralos y vuelve a probar:")
    if os.name == "nt":
        log("ERROR", '  netstat -ano | findstr ":8000 :5173"   ->  taskkill /F /PID <pid>')
    else:
        log("ERROR", "  lsof -ti:8000,5173 | xargs kill")
    return False


def comprobar_dependencias(prod):
    """Verifica lo imprescindible antes de arrancar y explica como arreglarlo.

    Fallar aqui con un mensaje claro es mucho mejor que arrancar a medias y
    dejar al usuario mirando una pantalla en blanco.
    """
    try:
        import fastapi, uvicorn, numpy       # noqa: F401
    except ImportError as exc:
        log("ERROR", f"Falta una dependencia de Python: {exc.name}")
        log("ERROR", "Instalala con:  pip install -r requirements.txt")
        return False

    if prod:
        if not os.path.isfile(os.path.join(DIST_DIR, "index.html")):
            log("ERROR", "No existe dist/. Compila la web antes:  npm run build")
            return False
        return True

    if npm_cmd() is None:
        log("ERROR", "No se encuentra npm. Instala Node.js: https://nodejs.org")
        return False

    if not os.path.isdir(os.path.join(SCRIPT_DIR, "node_modules")):
        log("ERROR", "Faltan las dependencias de Node. Instalalas con:  npm install")
        return False

    return True


def lanzar_api():
    """Arranca el servidor de la IA (uvicorn) como proceso hijo."""
    # `sys.executable` en vez de "python": asi se usa el MISMO interprete que
    # ejecuta run.py, que es el que tiene numpy y fastapi instalados.
    cmd = [sys.executable, "-m", "uvicorn", "ai_server:app",
           "--host", "127.0.0.1", "--port", str(API_PORT)]
    log("orquestador", f"IA        -> http://127.0.0.1:{API_PORT}")
    return subprocess.Popen(cmd, cwd=SCRIPT_DIR)


def lanzar_vite():
    """Arranca el servidor de desarrollo de Vite como proceso hijo."""
    # Se llama a `npm run vite`, NO a `npm run dev`: dev es este mismo script y
    # se llamaria a si mismo en bucle infinito.
    cmd = [npm_cmd(), "run", "vite"]
    log("orquestador", f"Interfaz  -> http://localhost:{VITE_PORT}")
    return subprocess.Popen(cmd, cwd=SCRIPT_DIR)


def _matar_arbol(p):
    """Mata un proceso Y toda su descendencia.

    Hace falta porque `npm run vite` es en realidad npm -> node: al terminar
    solo npm, el node se queda huerfano ocupando el puerto 5173, y el siguiente
    `npm run dev` falla al arrancar sin explicar por que. En Windows la unica
    forma fiable de cortar el arbol es taskkill /T.
    """
    if p.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                       capture_output=True)
    else:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        except (OSError, ProcessLookupError):
            p.terminate()


def cerrar_todo(*_):
    """Cierra los procesos hijo de forma ordenada; mata a los que se resistan."""
    for p in procesos:
        if p.poll() is None:
            try:
                p.terminate()
            except OSError:
                pass

    plazo = time.time() + 4
    for p in procesos:
        restante = max(0, plazo - time.time())
        try:
            p.wait(timeout=restante)
        except subprocess.TimeoutExpired:
            _matar_arbol(p)     # No se rindio por las buenas
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
    print()
    log("orquestador", "Todo cerrado. Hasta luego.")


def main():
    """Punto de entrada: arranca, vigila y cierra."""
    prod = "--prod" in sys.argv

    print()
    print("=" * 64)
    print("  SNAKE IA - Neuroevolucion" + ("  [produccion]" if prod else "  [desarrollo]"))
    print("=" * 64)

    if not comprobar_dependencias(prod) or not comprobar_puertos(prod):
        sys.exit(1)

    # Cerrar los hijos pase lo que pase:
    #   SIGINT   -> el Ctrl+C del usuario
    #   SIGTERM  -> gestores de procesos y Docker al parar el contenedor
    #   SIGBREAK -> Ctrl+Break, solo en Windows
    # Sin esto el script muere sin limpiar y deja uvicorn (y node) huerfanos
    # ocupando los puertos, de modo que el siguiente arranque falla.
    #
    # Aviso: en Windows no existe un SIGTERM de verdad. Si a este proceso lo
    # matan con TerminateProcess (por ejemplo `taskkill /F` o el Administrador
    # de tareas), NINGUN manejador llega a ejecutarse y los hijos sobreviven.
    # Es una limitacion del sistema, no del script: por eso `comprobar_puertos`
    # detecta esos restos al arrancar y explica como quitarlos.
    def salir(*_):
        cerrar_todo()
        sys.exit(0)

    signal.signal(signal.SIGINT, salir)
    signal.signal(signal.SIGTERM, salir)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, salir)

    if prod:
        log("orquestador", f"Sirviendo la web compilada en http://127.0.0.1:{API_PORT}")
        procesos.append(lanzar_api())
    else:
        procesos.append(lanzar_api())
        time.sleep(1.0)          # Margen para que uvicorn ate el puerto
        procesos.append(lanzar_vite())
        print()
        log("orquestador", f"Abre  ->  http://localhost:{VITE_PORT}")
        log("orquestador", "Ctrl+C para parar los dos procesos.")
    print()

    try:
        # Si CUALQUIERA de los dos muere, se cierra el otro: dejar medio proyecto
        # vivo solo confunde (la web cargaria pero sin IA detras, o al reves).
        while True:
            for p in procesos:
                codigo = p.poll()
                if codigo is not None:
                    log("orquestador", f"Un proceso termino (codigo {codigo}). Cerrando el resto.")
                    cerrar_todo()
                    sys.exit(codigo or 0)
            time.sleep(0.4)
    except KeyboardInterrupt:
        cerrar_todo()


if __name__ == "__main__":
    main()
