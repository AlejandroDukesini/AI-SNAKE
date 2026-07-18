# -*- coding: utf-8 -*-
"""
================================================================================
  SNAKE IA - SERVIDOR DE LA IA (FastAPI: WebSocket + REST)
================================================================================
  Une el frontend React con el cerebro NumPy. No renderiza nada: el navegador
  dibuja, y aqui se aplican las reglas y se evoluciona la poblacion.

  Servidor AUTORITATIVO: el estado del juego vive en Python. El cliente nunca
  calcula reglas, asi que React no puede desincronizarse del algoritmo.

    REST  /api/config             tema, generaciones y tamano de tablero
    REST  /api/models             especimenes guardados (carpetas)
    WS    /ws/play                partida manual
    WS    /ws/train               entrenamiento en vivo
    WS    /ws/demo/{carpeta}      ver jugar a un especimen guardado

  En desarrollo lo levanta `run.py` junto a Vite (que hace de proxy hacia aqui).
  En produccion, si existe `dist/`, este mismo proceso sirve la web ya compilada.

  Ejecucion:  python ai_server.py       (o `npm run server`)
================================================================================
"""

import os
import queue
import asyncio
import threading

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import snake_neuroevolution as ml
import storage

# =============================================================================
#  CONFIGURACION DEL SERVIDOR
# =============================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR   = os.path.join(SCRIPT_DIR, "dist")

FPS_PLAY   = 12      # Velocidad jugable (manual y demo)
STREAM_FPS = 20      # Refrescos por segundo enviados durante el entrenamiento

app = FastAPI(title="Snake IA - Neuroevolucion")


# =============================================================================
#  API REST: CONFIGURACION
# =============================================================================
class ConfigIn(BaseModel):
    """Cuerpo de PUT /api/config. Todos los campos son opcionales: se puede
    cambiar solo el tema, solo las generaciones o solo el tablero."""
    theme:       str | None = None
    generations: int | None = None
    grid:        int | None = None


@app.get("/api/config")
def get_config():
    """Configuracion persistida + los limites y opciones que la UI necesita para
    construir sus controles sin duplicar constantes."""
    return {
        "config": storage.load_config(),
        "themes": list(storage.THEMES),
        "grids":  list(ml.GRID_SIZES),
        "limits": {
            "min_generations": ml.MIN_GENERATIONS,
            "max_generations": ml.MAX_GENERATIONS,
        },
        "pop_size": ml.POP_SIZE,
    }


@app.put("/api/config")
def put_config(cfg: ConfigIn):
    """Guarda la configuracion y devuelve la version efectiva (ya validada)."""
    return {"config": storage.save_config(cfg.model_dump())}


# =============================================================================
#  API REST: ESPECIMENES (carpetas del historial)
# =============================================================================
class FavoriteIn(BaseModel):
    favorito: bool


class RenameIn(BaseModel):
    nombre: str


@app.get("/api/models")
def get_models(favorites: bool = False):
    """Lista los especimenes guardados, sin los pesos de la red."""
    modelos = storage.list_models()
    if favorites:
        modelos = [m for m in modelos if m["favorito"]]
    return {"models": modelos}


@app.get("/api/models/{carpeta}")
def get_model(carpeta: str):
    """Detalle de un especimen, con su historico de scores."""
    modelo = storage.load_model(storage.slugify(carpeta))
    if modelo is None:
        raise HTTPException(status_code=404, detail="Especimen no encontrado")
    resumen = storage.model_summary(modelo)
    resumen["sesiones"] = storage.load_sessions(modelo["carpeta"])
    return {"model": resumen}


@app.get("/api/exists/{nombre}")
def check_exists(nombre: str):
    """Dice si un nombre ya tiene carpeta. Lo usa el selector de entrenamiento
    para avisar de si va a CREAR un especimen o CONTINUAR uno existente."""
    carpeta = storage.slugify(nombre)
    modelo = storage.load_model(carpeta)
    return {
        "carpeta": carpeta,
        "existe":  modelo is not None,
        "model":   storage.model_summary(modelo) if modelo else None,
    }


@app.put("/api/models/{carpeta}/favorite")
def put_favorite(carpeta: str, body: FavoriteIn):
    """Marca o desmarca un especimen como favorito."""
    resumen = storage.set_favorite(storage.slugify(carpeta), body.favorito)
    if resumen is None:
        raise HTTPException(status_code=404, detail="Especimen no encontrado")
    return {"model": resumen}


@app.patch("/api/models/{carpeta}")
def patch_model(carpeta: str, body: RenameIn):
    """Renombra un especimen sin perder su entrenamiento. Si el nombre nuevo
    choca con otra carpeta existente se rechaza (409): fusionar dos linajes
    borraria el aprendizaje de uno de ellos."""
    resumen, error = storage.rename_model(storage.slugify(carpeta), body.nombre)
    if error == "no_encontrado":
        raise HTTPException(status_code=404, detail="Especimen no encontrado")
    if error == "nombre_vacio":
        raise HTTPException(status_code=400, detail="El nombre no puede estar vacío")
    if error == "ya_existe":
        raise HTTPException(status_code=409, detail="Ya existe una IA con ese nombre")
    return {"model": resumen}


@app.delete("/api/models/{carpeta}")
def delete_model(carpeta: str):
    """Borra la carpeta entera de un especimen."""
    if not storage.delete_model(storage.slugify(carpeta)):
        raise HTTPException(status_code=404, detail="Especimen no encontrado")
    return {"deleted": carpeta}


@app.delete("/api/models")
def clear_history(keep_favorites: bool = True):
    """Vacia el historial. Por defecto conserva los favoritos."""
    return {"deleted": storage.clear_history(keep_favorites=keep_favorites)}


# =============================================================================
#  WEBSOCKET: ENTRENAMIENTO
# =============================================================================
@app.websocket("/ws/train")
async def ws_train(ws: WebSocket):
    """Ejecuta la neuroevolucion y retransmite su progreso en vivo.

    El entrenamiento es CPU intensivo y bloquearia el bucle de asyncio, asi que
    corre en un hilo aparte. La comunicacion entre ese hilo y el WebSocket usa:
      - `ultimo`: casilla con el ultimo turno simulado. Se SOBRESCRIBE, no se
        encola: el nucleo produce miles de pasos por segundo y encolarlos todos
        agotaria la memoria y saturaria la red. Al cliente solo le importa el
        fotograma mas reciente.
      - `eventos`: cola real para 'gen' y 'done', que NO se pueden perder.
    """
    await ws.accept()

    cancelar = threading.Event()
    ultimo   = {"step": None}
    eventos  = queue.Queue()
    fin      = threading.Event()

    try:
        peticion = await ws.receive_json()
    except (WebSocketDisconnect, ValueError):
        return

    cfg = storage.load_config()
    generations = ml.clamp_generations(peticion.get("generations", cfg["generations"]))
    grid        = ml.clamp_grid(peticion.get("grid", cfg["grid"]))
    nombre      = peticion.get("nombre") or ml.random_name()
    carpeta     = storage.slugify(nombre)

    # Si la carpeta ya existe se HEREDA su linaje; si no, nace de cero.
    previo = storage.load_model(carpeta)
    seed_brain = ml.NeuralNetwork.from_dict(previo["pesos"]) if previo else None

    await ws.send_json({
        "type":     "info",
        "carpeta":  carpeta,
        "nombre":   nombre,
        "continua": previo is not None,
        "grid":     grid,
        "generations": generations,
    })

    def on_event(tipo, datos):
        """Callback invocado por el nucleo desde el hilo de entrenamiento."""
        if cancelar.is_set():
            return False        # Cancela la neuroevolucion
        if tipo == "step":
            ultimo["step"] = datos
        else:
            eventos.put({"type": tipo, **datos})
        return True

    def trabajo():
        """Hilo: entrena, guarda el mejor linaje en su carpeta y avisa.

        Guardar aqui (y no dentro de `train`) es lo que permite decidir entre
        crear un especimen o sumarle generaciones a uno existente.
        """
        try:
            resultado = ml.train(generations=generations, grid=grid,
                                 pop_size=ml.POP_SIZE, seed_brain=seed_brain,
                                 on_event=on_event)
            if resultado is None:
                return          # Cancelado: no se guarda nada
            resumen = storage.save_training(nombre, resultado)
            eventos.put({"type": "done", "model": resumen, "continua": previo is not None})
        except Exception as exc:            # No dejar el hilo morir en silencio
            eventos.put({"type": "error", "detail": str(exc)})
        finally:
            fin.set()

    hilo = threading.Thread(target=trabajo, daemon=True)
    hilo.start()

    async def escuchar_cancelacion():
        """Atiende {'action':'cancel'} y la desconexion del navegador. Si el
        usuario cierra la pestana hay que parar el hilo, o el servidor seguiria
        quemando CPU para nadie."""
        try:
            while not fin.is_set():
                msg = await ws.receive_json()
                if msg.get("action") == "cancel":
                    cancelar.set()
                    return
        except (WebSocketDisconnect, ValueError, RuntimeError):
            cancelar.set()

    escucha = asyncio.create_task(escuchar_cancelacion())

    try:
        # Bucle emisor: ritmo fijo, independiente de lo rapido que simule el hilo.
        while True:
            await asyncio.sleep(1.0 / STREAM_FPS)

            while not eventos.empty():
                await ws.send_json(eventos.get())

            if ultimo["step"] is not None:
                await ws.send_json({"type": "step", **ultimo["step"]})
                ultimo["step"] = None

            if fin.is_set() and eventos.empty():
                break

        if cancelar.is_set():
            await ws.send_json({"type": "cancelled"})
    except (WebSocketDisconnect, RuntimeError):
        cancelar.set()
    finally:
        cancelar.set()
        escucha.cancel()
        hilo.join(timeout=2.0)


# =============================================================================
#  WEBSOCKET: JUEGO MANUAL
# =============================================================================
@app.websocket("/ws/play")
async def ws_play(ws: WebSocket):
    """Partida manual con el servidor como autoridad.

    La serpiente arranca DETENIDA y no se mueve hasta recibir {'action':'start'},
    que React envia al terminar su cuenta atras (3, 2, 1). Sin esa espera el
    jugador perdia antes de poder reaccionar. La autoridad sigue siendo del
    servidor: aunque el cliente no cuente, sin 'start' no hay movimiento.
    """
    await ws.accept()
    grid = ml.clamp_grid(storage.load_config()["grid"])
    snake = ml.Snake(grid=grid, use_energy=False)   # Sin inanicion en manual
    pendiente = {"dir": None}
    jugando = {"on": False}

    async def escuchar():
        """Recibe las teclas sin bloquear el avance del juego."""
        nonlocal snake, grid
        while True:
            msg = await ws.receive_json()
            accion = msg.get("action")
            if accion == "dir":
                d = msg.get("dir")
                if isinstance(d, int) and 0 <= d <= 3:
                    pendiente["dir"] = d
            elif accion == "start":
                jugando["on"] = True        # La cuenta atras del cliente termino
            elif accion == "restart":
                pendiente["restart"] = True

    escucha = asyncio.create_task(escuchar())

    try:
        while True:
            await asyncio.sleep(1.0 / FPS_PLAY)

            if pendiente.pop("restart", False):
                # Se relee el tablero: el usuario puede haberlo cambiado en
                # Configuracion entre una partida y la siguiente.
                grid = ml.clamp_grid(storage.load_config()["grid"])
                snake = ml.Snake(grid=grid, use_energy=False)
                pendiente["dir"] = None
                jugando["on"] = False       # Cada partida nueva vuelve a contar

            if jugando["on"] and snake.alive:
                if pendiente["dir"] is not None:
                    snake.set_absolute_direction(pendiente["dir"])
                    pendiente["dir"] = None
                snake.advance()

            if not snake.alive:
                jugando["on"] = False

            await ws.send_json({
                "type": "state",
                "snake": snake.to_state(),
                "jugando": jugando["on"],
            })
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        escucha.cancel()


# =============================================================================
#  WEBSOCKET: DEMO DE UN ESPECIMEN
# =============================================================================
@app.websocket("/ws/demo/{carpeta}")
async def ws_demo(ws: WebSocket, carpeta: str):
    """Reproduce en bucle la partida de un especimen guardado.

    Carga sus pesos exactos, de modo que se ve jugar a esa IA concreta. El
    tablero es el de la configuracion actual, no el del entrenamiento: los
    sensores estan normalizados, asi que una red entrenada en 8x8 tambien juega
    en 15x15 (peor, pero juega).
    """
    await ws.accept()
    modelo = storage.load_model(storage.slugify(carpeta))
    if modelo is None:
        await ws.send_json({"type": "error", "detail": "Especimen no encontrado"})
        await ws.close()
        return

    grid = ml.clamp_grid(storage.load_config()["grid"])
    brain = ml.NeuralNetwork.from_dict(modelo["pesos"])
    snake = ml.Snake(brain=brain.clone(), grid=grid)

    try:
        await ws.send_json({"type": "info", "model": storage.model_summary(modelo)})
        while True:
            await asyncio.sleep(1.0 / FPS_PLAY)
            if snake.alive:
                snake.step_ai()
            else:
                await asyncio.sleep(0.7)                       # Pausa breve
                snake = ml.Snake(brain=brain.clone(), grid=grid)  # Reinicia
            await ws.send_json({"type": "state", "snake": snake.to_state()})
    except (WebSocketDisconnect, RuntimeError):
        pass


# =============================================================================
#  WEB COMPILADA (produccion)
# =============================================================================
#  En desarrollo la web la sirve Vite y estas rutas no se montan. Tras
#  `npm run build`, este mismo proceso sirve `dist/`: un solo comando y un solo
#  puerto para el hosting.
# =============================================================================
if os.path.isdir(DIST_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST_DIR, "assets")),
              name="assets")

    @app.get("/")
    def index():
        """Sirve la aplicacion React compilada."""
        return FileResponse(os.path.join(DIST_DIR, "index.html"))


if __name__ == "__main__":
    import uvicorn
    # El hosting suele inyectar el puerto por variable de entorno.
    puerto = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=puerto)
