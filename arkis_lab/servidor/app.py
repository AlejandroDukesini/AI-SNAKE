"""Servidor de ARKIS AI LAB (FastAPI). Única autoridad del juego y de los modelos.

Arranque:  python run.py   (o: uvicorn arkis_lab.servidor.app:app --port 8000)
"""
from __future__ import annotations

import base64
import os
from dataclasses import asdict
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..evaluacion.lineas_base import LINEAS_BASE
from ..evaluacion.protocolo import evaluar, semillas
from ..modelos.arkis.servicio import ServicioArkis
from ..modelos.bork.servicio import ServicioBork
from ..modelos.clark.servicio import ServicioClark
from ..modelos.lerk.predicados import PREDICADOS
from ..modelos.lerk.servicio import ServicioLerk
from ..nucleo import evolucion
from ..nucleo.config import (DIFICULTADES, SEGUNDOS_CICLO, VELOCIDAD_MOVIMIENTO_POR_DEFECTO,
                             VERSION_MOTOR)
from ..nucleo.recompensas import ConfigRecompensa
from .sesiones import GestorSesiones
from .trabajos import GestorTrabajos

RAIZ_DATOS = os.environ.get("ARKIS_LAB_DATOS")
DIST = Path(__file__).resolve().parents[2] / "dist"

app = FastAPI(title="ARKIS AI LAB", version=VERSION_MOTOR)
servicios = {
    "arkis": ServicioArkis(RAIZ_DATOS),
    "lerk": ServicioLerk(RAIZ_DATOS),
    "bork": ServicioBork(RAIZ_DATOS),
    "clark": ServicioClark(RAIZ_DATOS),
}
trabajos = GestorTrabajos()
sesiones = GestorSesiones()

MABU = {
    "clave": "mabu", "nombre": "MABU", "metodologia": "Híbrido preentrenado: ML + simbólico + refuerzo",
    "descripcion": ("Modelo experimental principal. Pendiente: su arquitectura se presentará para "
                    "aprobación en la Etapa 5 y su preentrenamiento se hará al final."),
    "estado": "pendiente", "version": None, "records": {}, "episodios": {}, "pendiente": True,
}


def svc(clave: str):
    if clave not in servicios:
        raise HTTPException(404, f"Modelo desconocido: {clave}")
    return servicios[clave]


def _error(e: Exception):
    raise HTTPException(400, str(e))


# --- Configuración general ----------------------------------------------------
@app.get("/api/salud")
def salud():
    return {"ok": True, "motor": VERSION_MOTOR}


@app.get("/api/config")
def config():
    return {
        "motor": VERSION_MOTOR,
        "dificultades": {k: {**asdict(d), "casillas": d.casillas,
                             "umbrales": list(evolucion.tabla_umbrales(d.casillas))}
                         for k, d in DIFICULTADES.items()},
        "velocidad_por_defecto": VELOCIDAD_MOVIMIENTO_POR_DEFECTO,
        "segundos_ciclo": SEGUNDOS_CICLO,
        "recompensa": ConfigRecompensa().a_dict(),
        "predicados": PREDICADOS,
    }


# --- Modelos ---------------------------------------------------------------------
@app.get("/api/modelos")
def modelos():
    out = []
    for s in servicios.values():
        r = s.resumen()
        r.pop("entrenamiento", None)
        r["trabajo"] = (t.a_dict() if (t := trabajos.activo(s.clave)) else None)
        out.append(r)
    return out + [MABU]


@app.get("/api/modelos/{clave}")
def modelo(clave: str):
    s = svc(clave)
    r = s.resumen()
    r["trabajo"] = (t.a_dict() if (t := trabajos.activo(clave)) else None)
    r["sesiones"] = s.almacen.sesiones(20)
    r["evaluaciones"] = s.almacen.leer_datos("evaluaciones.json", [])[-20:]
    return r


@app.get("/api/modelos/{clave}/episodios")
def episodios(clave: str, limite: int = 300, dificultad: str | None = None):
    return svc(clave).almacen.episodios(limite, dificultad)


class Restaurar(BaseModel):
    version: str


@app.post("/api/modelos/{clave}/restaurar")
def restaurar(clave: str, cuerpo: Restaurar):
    s = svc(clave)
    if trabajos.activo(clave):
        raise HTTPException(409, "Hay un trabajo en curso")
    try:
        with s.lock:
            s.almacen.restaurar(cuerpo.version)
            s.cargar()
    except Exception as e:
        _error(e)
    return {"version": s.version}


@app.get("/api/modelos/{clave}/exportar")
def exportar(clave: str):
    datos = svc(clave).almacen.exportar()
    return Response(datos, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{clave}.zip"'})


class Importar(BaseModel):
    zip_base64: str


@app.post("/api/modelos/{clave}/importar")
def importar(clave: str, cuerpo: Importar):
    s = svc(clave)
    try:
        with s.lock:
            vs = s.almacen.importar(base64.b64decode(cuerpo.zip_base64))
            s.cargar()
    except Exception as e:
        _error(e)
    return {"importadas": vs, "version": s.version,
            "bloqueado": getattr(s, "bloqueado", None)}


@app.post("/api/modelos/{clave}/confiar")
def confiar(clave: str):
    s = svc(clave)
    if not hasattr(s, "confiar_version_importada"):
        meta_ruta = s.almacen.dir / "versiones" / s.version / "meta.json"
        import json
        from ..persistencia.almacen import a_json, escribir_atomico
        meta = json.loads(meta_ruta.read_text(encoding="utf-8"))
        meta["confiado"] = True
        escribir_atomico(meta_ruta, a_json(meta))
        s.cargar()
    else:
        s.confiar_version_importada()
    return {"ok": True}


@app.post("/api/modelos/{clave}/copia")
def copia(clave: str):
    return {"ruta": str(svc(clave).almacen.copia_de_seguridad())}


# --- Trabajos -----------------------------------------------------------------
TIPOS = {
    "arkis": ("entrenar", "automatico", "evaluar", "recopilar"),
    "lerk": ("automatico", "evaluar"),
    "bork": ("entrenar", "evaluar"),
    "clark": ("automatico", "evaluar"),
}


class NuevoTrabajo(BaseModel):
    tipo: str
    parametros: dict = {}


@app.post("/api/modelos/{clave}/trabajos")
def nuevo_trabajo(clave: str, cuerpo: NuevoTrabajo):
    s = svc(clave)
    if cuerpo.tipo not in TIPOS[clave]:
        raise HTTPException(400, f"{clave} no admite '{cuerpo.tipo}'. Opciones: {TIPOS[clave]}")
    p = dict(cuerpo.parametros)
    dif = p.get("dificultad", "medio")
    if dif not in DIFICULTADES:
        raise HTTPException(400, "Dificultad inválida")

    def funcion(t):
        kw = {"progreso": t.progreso, "cancelar": t.cancelado}
        if cuerpo.tipo == "evaluar":
            return s.evaluar(dif, int(p.get("episodios", 30)), p.get("conjunto", "validacion"), **kw)
        if clave == "arkis":
            if cuerpo.tipo == "entrenar":
                return s.entrenar(int(p.get("semilla", 0)), bool(p.get("aumentar", True)),
                                  int(p.get("n_arboles", 100)))
            if cuerpo.tipo == "recopilar":
                return {"capturadas": s.recopilar(dif, int(p.get("episodios", 5)),
                                                  float(p.get("umbral", 0.6)),
                                                  int(p.get("maximo", 50)), int(p.get("semilla", 0)))}
            return s.entrenamiento_automatico(dif, int(p.get("episodios", 30)),
                                              int(p.get("semilla", 0)), bool(p.get("aumentar", True)), **kw)
        if clave == "lerk":
            return s.entrenamiento_automatico(dif, int(p.get("episodios", 50)),
                                              float(p.get("epsilon", 0.2)), int(p.get("semilla", 0)),
                                              int(p.get("bloque", 10)), **kw)
        if clave == "bork":
            return s.entrenar(dif, int(p.get("episodios", 500)), int(p.get("semilla", 0)),
                              float(p["velocidad"]) if p.get("velocidad") else None,
                              int(p.get("guardar_cada", 0)), **kw)
        return s.entrenamiento_automatico(dif, int(p.get("episodios", 200)), int(p.get("semilla", 0)),
                                          int(p.get("bloque", 25)), **kw)

    try:
        return trabajos.lanzar(clave, cuerpo.tipo, p, funcion).a_dict()
    except RuntimeError as e:
        raise HTTPException(409, str(e))


@app.get("/api/trabajos")
def lista_trabajos():
    return trabajos.lista()


@app.get("/api/trabajos/{id_}")
def trabajo(id_: str):
    try:
        return trabajos.obtener(id_).a_dict()
    except KeyError:
        raise HTTPException(404, "No existe el trabajo")


@app.post("/api/trabajos/{id_}/cancelar")
def cancelar(id_: str):
    trabajos.obtener(id_).cancelar()
    return {"ok": True}


# --- Comparación ------------------------------------------------------------
class Comparar(BaseModel):
    dificultad: str = "medio"
    episodios: int = 30


@app.post("/api/comparar")
def comparar(cuerpo: Comparar):
    """Todos los modelos y las líneas base en las MISMAS semillas de prueba. Solo métricas
    de juego: las recompensas de algoritmos distintos no son comparables."""
    if cuerpo.dificultad not in DIFICULTADES:
        raise HTTPException(400, "Dificultad inválida")

    def funcion(t):
        filas = []
        lista = semillas("prueba", cuerpo.episodios)
        candidatos = [(k, s.nombre, s.agente().politica(), s.version) for k, s in servicios.items()]
        candidatos += [(f"base_{k}", f"Línea base: {k}", f, None) for k, f in LINEAS_BASE.items()]
        for i, (k, nombre, pol, version) in enumerate(candidatos):
            if t.cancelado():
                break
            ev = evaluar(pol, cuerpo.dificultad, lista)
            filas.append({"clave": k, "nombre": nombre, "version": version,
                          "manzanas": ev.manzanas.__dict__, "ocupacion_max": ev.ocupacion_max.__dict__,
                          "pasos": ev.pasos.__dict__, "nivel_medio": ev.nivel.media,
                          "mejor_nivel": ev.mejor_nivel, "victorias": ev.victorias,
                          "causas_fin": ev.causas_fin})
            t.progreso(i + 1, len(candidatos))
        return {"dificultad": cuerpo.dificultad, "episodios": cuerpo.episodios,
                "semillas": [lista[0], lista[-1]], "filas": filas}

    try:
        return trabajos.lanzar("comparacion", "comparar", cuerpo.model_dump(), funcion).a_dict()
    except RuntimeError as e:
        raise HTTPException(409, str(e))


# --- Sesiones de simulación ------------------------------------------------------
class NuevaSesion(BaseModel):
    modelo: str | None = None
    dificultad: str = "medio"
    semilla: int | None = None
    modo: str = "observar"
    velocidad: float = VELOCIDAD_MOVIMIENTO_POR_DEFECTO


@app.post("/api/sesiones")
def nueva_sesion(c: NuevaSesion):
    if c.dificultad not in DIFICULTADES:
        raise HTTPException(400, "Dificultad inválida")
    if c.modo in ("observar", "demostrar") and not c.modelo:
        raise HTTPException(400, "Elige un modelo")
    if c.modo == "demostrar" and c.modelo not in ("arkis", "lerk"):
        raise HTTPException(400, "Las demostraciones etiquetadas son para ARKIS o LERK")
    s = svc(c.modelo) if c.modelo else None
    try:
        sesion = sesiones.crear(s, c.dificultad, c.semilla, c.modo,
                                c.modelo if c.modo == "demostrar" else None, c.velocidad)
    except ValueError as e:
        _error(e)
    return sesion.fotograma()


def _sesion(id_):
    try:
        return sesiones.obtener(id_)
    except KeyError:
        raise HTTPException(404, "La sesión no existe o caducó")


@app.get("/api/sesiones/{id_}")
def ver_sesion(id_: str):
    return _sesion(id_).fotograma()


class Paso(BaseModel):
    accion: str | None = None
    pasos: int = 1


@app.post("/api/sesiones/{id_}/paso")
def paso(id_: str, c: Paso):
    s = _sesion(id_)
    try:
        for _ in range(max(1, min(c.pasos, 50))):
            if s.entorno.terminado:
                break
            s.paso(c.accion)
    except ValueError as e:
        _error(e)
    return s.fotograma()


class Pausa(BaseModel):
    pausada: bool


@app.post("/api/sesiones/{id_}/pausa")
def pausa(id_: str, c: Pausa):
    s = _sesion(id_)
    s.pausar(c.pausada)
    return s.fotograma()


@app.post("/api/sesiones/{id_}/capturar")
def capturar(id_: str):
    """Guarda la situación actual SIN etiqueta en el conjunto de ARKIS, para etiquetarla después."""
    from ..modelos.situacion import situacion_de
    s = _sesion(id_)
    a = servicios["arkis"]
    with a.lock:
        e = a.dataset.agregar(situacion_de(s.entorno.partida), None, "captura", f"captura-{s.id}",
                              s.entorno.partida.pasos)
        a.guardar_dataset()
    return e


@app.get("/api/sesiones/{id_}/situacion")
def situacion_sesion(id_: str):
    from ..modelos.situacion import situacion_de
    return situacion_de(_sesion(id_).entorno.partida)


# --- ARKIS ------------------------------------------------------------------------
@app.get("/api/arkis/ejemplos")
def arkis_ejemplos(filtro: str = "todos", offset: int = 0, limite: int = 50):
    a = servicios["arkis"]
    ej = a.dataset.ejemplos
    if filtro == "sin_etiqueta":
        ej = [e for e in ej if e["etiqueta"] is None]
    elif filtro == "pendientes":
        ej = [e for e in ej if e["etiqueta"] is not None and not e["aprobado"]]
    elif filtro == "aprobados":
        ej = [e for e in ej if e["aprobado"]]
    elif filtro == "papelera":
        ej = a.dataset.papelera
    ej = list(reversed(ej))
    errores = {x["id"]: x["predicha"] for x in
               ((a.metricas or {}).get("validacion") or {}).get("errores", [])}
    pagina = [{**e, "error_validacion": errores.get(e["id"])} for e in ej[offset:offset + limite]]
    return {"total": len(ej), "ejemplos": pagina, "estadisticas": a.dataset.estadisticas()}


class Etiqueta(BaseModel):
    etiqueta: str


class NuevoEjemplo(BaseModel):
    situacion: dict
    etiqueta: str
    origen: str = "correccion"


@app.post("/api/arkis/ejemplos")
def arkis_agregar(c: NuevoEjemplo):
    """Corrección desde el simulador: tu etiqueta queda pendiente de aprobación."""
    a = servicios["arkis"]
    try:
        with a.lock:
            e = a.dataset.agregar(c.situacion, c.etiqueta, c.origen, "correcciones")
            a.guardar_dataset()
    except ValueError as e:
        _error(e)
    return e


@app.patch("/api/arkis/ejemplos/{id_}")
def arkis_etiquetar(id_: str, c: Etiqueta):
    a = servicios["arkis"]
    try:
        with a.lock:
            e = a.dataset.etiquetar(id_, c.etiqueta)
            a.guardar_dataset()
    except ValueError as e:
        _error(e)
    return e


class Aprobar(BaseModel):
    ids: list[str] | None = None
    todos_pendientes: bool = False
    aprobado: bool = True


@app.post("/api/arkis/ejemplos/aprobar")
def arkis_aprobar(c: Aprobar):
    a = servicios["arkis"]
    with a.lock:
        ids = c.ids or []
        if c.todos_pendientes:
            ids = [e["id"] for e in a.dataset.ejemplos if e["etiqueta"] and not e["aprobado"]]
        try:
            n = a.dataset.aprobar(ids, c.aprobado)
        except ValueError as e:
            _error(e)
        a.guardar_dataset()
    return {"cambiados": n, "estadisticas": a.dataset.estadisticas()}


@app.delete("/api/arkis/ejemplos/{id_}")
def arkis_eliminar(id_: str):
    a = servicios["arkis"]
    with a.lock:
        a.dataset.eliminar(id_)
        a.guardar_dataset()
    return {"ok": True}


@app.post("/api/arkis/ejemplos/{id_}/restaurar")
def arkis_restaurar_ejemplo(id_: str):
    a = servicios["arkis"]
    with a.lock:
        a.dataset.restaurar(id_)
        a.guardar_dataset()
    return {"ok": True}


@app.post("/api/arkis/predecir")
def arkis_predecir(situacion: dict = Body(...)):
    from ..modelos.situacion import percepcion_de
    import random as _r
    return servicios["arkis"].agente().decidir(percepcion_de(situacion), _r.Random(0)).a_dict()


@app.get("/api/arkis/arbol")
def arkis_arbol():
    return {"arbol": servicios["arkis"].arbol}


# --- LERK -------------------------------------------------------------------
@app.post("/api/lerk/reglas")
def lerk_crear(datos: dict = Body(...)):
    try:
        return servicios["lerk"].crear_regla(datos)
    except (ValueError, KeyError) as e:
        _error(e)


@app.patch("/api/lerk/reglas/{id_}")
def lerk_modificar(id_: str, cambios: dict = Body(...)):
    try:
        return servicios["lerk"].modificar_regla(id_, cambios)
    except (ValueError, KeyError) as e:
        _error(e)


@app.delete("/api/lerk/reglas/{id_}")
def lerk_eliminar(id_: str):
    try:
        return {"eliminadas": servicios["lerk"].eliminar_regla(id_)}
    except KeyError as e:
        _error(e)


@app.post("/api/lerk/inducir")
def lerk_inducir():
    return servicios["lerk"].inducir()


@app.post("/api/lerk/generalizar")
def lerk_generalizar(tolerancia: float = 0.0):
    return servicios["lerk"].generalizar(tolerancia)


@app.post("/api/lerk/validar")
def lerk_validar():
    return servicios["lerk"].validar()


@app.get("/api/lerk/conflictos")
def lerk_conflictos():
    return servicios["lerk"].conflictos()


class Correccion(BaseModel):
    situacion: dict
    correcta: str
    condiciones: list[str] | None = None


@app.post("/api/lerk/corregir")
def lerk_corregir(c: Correccion):
    try:
        return servicios["lerk"].corregir(c.situacion, c.correcta, c.condiciones)
    except ValueError as e:
        _error(e)


@app.post("/api/lerk/diferencias")
def lerk_diferencias(situacion: dict = Body(...)):
    return servicios["lerk"].diferencias(situacion)


# --- BORK y CLARK ---------------------------------------------------------------
@app.post("/api/bork/config")
def bork_config(cambios: dict = Body(...)):
    try:
        return servicios["bork"].configurar(cambios)
    except (ValueError, TypeError) as e:
        _error(e)


@app.post("/api/bork/reiniciar")
def bork_reiniciar():
    if trabajos.activo("bork"):
        raise HTTPException(409, "Hay un trabajo en curso")
    servicios["bork"].reiniciar_tabla()
    return {"ok": True}


@app.get("/api/bork/tabla")
def bork_tabla(limite: int = 40):
    return servicios["bork"].inspeccionar(limite)


@app.post("/api/clark/config")
def clark_config(cambios: dict = Body(...)):
    try:
        return servicios["clark"].configurar(cambios)
    except (ValueError, TypeError) as e:
        _error(e)


class CorreccionClark(BaseModel):
    situacion: dict
    correcta: str


@app.post("/api/clark/corregir")
def clark_corregir(c: CorreccionClark):
    try:
        return servicios["clark"].corregir(c.situacion, c.correcta)
    except ValueError as e:
        _error(e)


# --- Web compilada (producción) ---------------------------------------------------
if (DIST / "index.html").is_file():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{ruta:path}")
    def spa(ruta: str):
        f = DIST / ruta
        if ruta and f.is_file() and DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
