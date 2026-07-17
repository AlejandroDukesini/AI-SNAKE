# -*- coding: utf-8 -*-
"""
================================================================================
  SNAKE IA - PERSISTENCIA LOCAL
================================================================================
  Cada especimen vive en su propia CARPETA dentro de `historial/`:

      historial/
        Serpiente_Pro_v1/
          modelo.json     -> identidad + mejor linaje (pesos y sesgos optimos)
          sesiones.json   -> historico de scores, un registro por entrenamiento
        Cobra-Core-V51/
          ...

  La carpeta ES la identidad del especimen: entrenar con un nombre que ya existe
  CONTINUA ese linaje (hereda sus pesos y le suma generaciones); con un nombre
  nuevo, nace un especimen desde cero. Eso es justo lo que hace el selector de
  "abrir / crear carpeta" de la pantalla de entrenamiento.

  Aqui no hay nada de machine learning: eso vive en `snake_neuroevolution.py`.
================================================================================
"""

import os
import re
import json
import shutil
import datetime

import snake_neuroevolution as ml

# =============================================================================
#  RUTAS
# =============================================================================
SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
HISTORY_DIR   = os.path.join(SCRIPT_DIR, "historial")
CONFIG_FILE   = os.path.join(SCRIPT_DIR, "config.json")

MODEL_FILE    = "modelo.json"
SESSIONS_FILE = "sesiones.json"

# Temas de la interfaz (los nombres los comparten React y Python)
THEMES        = ("oscura", "minimalista", "verde")
DEFAULT_THEME = "oscura"


# =============================================================================
#  NOMBRES Y CARPETAS
# =============================================================================
def slugify(nombre):
    """Convierte el nombre del especimen en un nombre de carpeta seguro.

    Es la unica barrera entre un nombre escrito por el usuario y el sistema de
    ficheros: sin esto, un nombre como '../../algo' escribiria fuera de
    `historial/`. Se permiten solo letras, numeros, guion y guion bajo.
    """
    nombre = str(nombre or "").strip()
    nombre = re.sub(r"\s+", "_", nombre)             # Espacios -> guion bajo
    nombre = re.sub(r"[^A-Za-z0-9_\-]", "", nombre)  # Fuera todo lo demas
    nombre = nombre.strip("._-")[:40]                # Sin puntos guia; max 40
    return nombre or ml.random_name()


def model_dir(carpeta):
    """Ruta absoluta de la carpeta de un especimen."""
    return os.path.join(HISTORY_DIR, carpeta)


def exists(carpeta):
    """True si ese especimen ya tiene carpeta con modelo guardado."""
    return os.path.isfile(os.path.join(model_dir(carpeta), MODEL_FILE))


def _ensure_history_dir():
    """Crea `historial/` si aun no existe."""
    os.makedirs(HISTORY_DIR, exist_ok=True)


def _now():
    """Marca de tiempo legible, en formato estable para ordenar."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# =============================================================================
#  LECTURA
# =============================================================================
def _read_json(path, default):
    """Lee un JSON; ante cualquier problema devuelve `default` en vez de reventar.
    Los ficheros del historial son editables a mano y pueden estar corruptos."""
    if not os.path.isfile(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def _write_json(path, datos):
    """Escribe un JSON creando la carpeta si hace falta. True si se guardo."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
        return True
    except OSError:
        return False


def load_model(carpeta):
    """Carga el modelo completo (con pesos) de un especimen. None si no existe."""
    datos = _read_json(os.path.join(model_dir(carpeta), MODEL_FILE), None)
    if not isinstance(datos, dict) or "pesos" not in datos:
        return None
    datos["carpeta"] = carpeta          # La carpeta manda sobre lo que diga el JSON
    datos.setdefault("favorito", False)
    return datos


def load_sessions(carpeta):
    """Historico de scores de un especimen: un registro por entrenamiento."""
    datos = _read_json(os.path.join(model_dir(carpeta), SESSIONS_FILE), [])
    return datos if isinstance(datos, list) else []


def model_summary(m):
    """Version ligera de un especimen: todo menos los pesos.

    La lista del historial no necesita los ~150 numeros de la red, y enviarlos
    en cada refresco multiplicaria por mil el tamano de la respuesta.

    Ademas deriva SIEMPRE el nivel de inteligencia de su cobertura (longitud /
    area del tablero), de modo que hasta los especimenes antiguos -que se
    guardaron antes de existir el sistema de niveles- muestran el suyo.
    """
    resumen = {k: v for k, v in m.items() if k != "pesos"}
    length = resumen.get("length")
    grid   = resumen.get("grid")
    if isinstance(length, int) and isinstance(grid, int) and grid > 0:
        info = ml.nivel_de_cobertura(ml.cobertura(length, grid))
        resumen["cobertura"]      = info["cobertura"]
        resumen["nivel"]          = info["nivel"]
        resumen["nivel_etiqueta"] = info["etiqueta"]
    return resumen


def list_models():
    """Todos los especimenes guardados, ordenados por fitness (mejor primero)."""
    _ensure_history_dir()
    modelos = []
    for carpeta in sorted(os.listdir(HISTORY_DIR)):
        if not os.path.isdir(model_dir(carpeta)):
            continue
        m = load_model(carpeta)
        if m is None:
            continue
        resumen = model_summary(m)
        resumen["sesiones"] = load_sessions(carpeta)
        modelos.append(resumen)
    modelos.sort(key=lambda m: m.get("fitness", 0), reverse=True)
    return modelos


# =============================================================================
#  ESCRITURA
# =============================================================================
def save_training(nombre, resultado):
    """Guarda el resultado de un entrenamiento en la carpeta del especimen.

    Si la carpeta ya existe se CONTINUA el linaje: las generaciones se acumulan
    y el mejor linaje (pesos) solo se sustituye si esta tanda supero el record.
    La evolucion tiene azar, asi que una tanda peor no debe degradar al mejor
    especimen que el usuario ya tenia: seguir entrenando nunca empeora tu IA.

    Devuelve el resumen del modelo guardado (sin pesos).
    """
    carpeta = slugify(nombre)
    previo = load_model(carpeta)
    ahora = _now()

    if previo is None:
        modelo = {
            "carpeta":             carpeta,
            "nombre":              str(nombre or carpeta).strip()[:40] or carpeta,
            "fecha_creacion":      ahora,
            "fecha_actualizacion": ahora,
            "generaciones":        int(resultado["generaciones"]),
            "fitness":             int(resultado["fitness"]),
            "frutas":              int(resultado["frutas"]),
            "pasos":               int(resultado["pasos"]),
            "length":              int(resultado["length"]),
            "grid":                int(resultado["grid"]),
            "favorito":            False,
            "pesos":               resultado["brain"].to_dict(),
        }
    else:
        modelo = previo
        modelo["generaciones"] = int(modelo.get("generaciones", 0)) + int(resultado["generaciones"])
        modelo["fecha_actualizacion"] = ahora
        if int(resultado["fitness"]) > int(modelo.get("fitness", -1)):
            modelo["fitness"] = int(resultado["fitness"])
            modelo["frutas"]  = int(resultado["frutas"])
            modelo["pasos"]   = int(resultado["pasos"])
            modelo["length"]  = int(resultado["length"])
            modelo["grid"]    = int(resultado["grid"])
            modelo["pesos"]   = resultado["brain"].to_dict()

    _write_json(os.path.join(model_dir(carpeta), MODEL_FILE), modelo)

    # Historico de scores: se anade SIEMPRE, aunque la tanda no batiera el record.
    # Asi la grafica del historial refleja la evolucion real del entrenamiento.
    sesiones = load_sessions(carpeta)
    # El nivel de cada sesion es el de SU propio resultado (no el record del
    # especimen): asi el historico muestra como fue subiendo de nivel tanda a
    # tanda. `train` ya lo calcula; si faltara, se deriva de longitud y tablero.
    info_sesion = ml.nivel_de_cobertura(
        resultado.get("cobertura", ml.cobertura(int(resultado["length"]), int(resultado["grid"]))))
    sesiones.append({
        "fecha":          ahora,
        "generaciones":   int(resultado["generaciones"]),
        "fitness":        int(resultado["fitness"]),
        "frutas":         int(resultado["frutas"]),
        "pasos":          int(resultado["pasos"]),
        "length":         int(resultado["length"]),
        "grid":           int(resultado["grid"]),
        "cobertura":      info_sesion["cobertura"],
        "nivel":          info_sesion["nivel"],
        "nivel_etiqueta": info_sesion["etiqueta"],
        "record":         int(resultado["fitness"]) >= int(modelo["fitness"]),
    })
    _write_json(os.path.join(model_dir(carpeta), SESSIONS_FILE), sesiones)

    resumen = model_summary(modelo)
    resumen["sesiones"] = sesiones
    return resumen


def set_favorite(carpeta, favorito):
    """Marca o desmarca un especimen como favorito. None si no existe."""
    modelo = load_model(carpeta)
    if modelo is None:
        return None
    modelo["favorito"] = bool(favorito)
    _write_json(os.path.join(model_dir(carpeta), MODEL_FILE), modelo)
    return model_summary(modelo)


def delete_model(carpeta):
    """Borra la carpeta entera de un especimen. True si existia."""
    ruta = model_dir(carpeta)
    if not os.path.isdir(ruta):
        return False
    shutil.rmtree(ruta, ignore_errors=True)
    return not os.path.isdir(ruta)


def clear_history(keep_favorites=True):
    """Vacia el historial. Por defecto CONSERVA los favoritos: son justo lo que
    el usuario marco para no perder. Devuelve cuantos especimenes se borraron."""
    borrados = 0
    for m in list_models():
        if keep_favorites and m.get("favorito"):
            continue
        if delete_model(m["carpeta"]):
            borrados += 1
    return borrados


# =============================================================================
#  CONFIGURACION
# =============================================================================
def default_config():
    """Configuracion de fabrica."""
    return {
        "theme":       DEFAULT_THEME,
        "generations": ml.DEFAULT_GENERATIONS,
        "grid":        ml.DEFAULT_GRID,
    }


def load_config():
    """Lee config.json validando SIEMPRE los valores: el fichero es editable a
    mano y un valor absurdo no debe llegar al algoritmo."""
    cfg = default_config()
    datos = _read_json(CONFIG_FILE, None)
    if not isinstance(datos, dict):
        return cfg
    if datos.get("theme") in THEMES:
        cfg["theme"] = datos["theme"]
    if "generations" in datos:
        cfg["generations"] = ml.clamp_generations(datos["generations"])
    if "grid" in datos:
        cfg["grid"] = ml.clamp_grid(datos["grid"])
    return cfg


def save_config(patch):
    """Guarda solo los campos presentes y devuelve la configuracion efectiva."""
    cfg = load_config()
    if patch.get("theme") in THEMES:
        cfg["theme"] = patch["theme"]
    if patch.get("generations") is not None:
        cfg["generations"] = ml.clamp_generations(patch["generations"])
    if patch.get("grid") is not None:
        cfg["grid"] = ml.clamp_grid(patch["grid"])
    _write_json(CONFIG_FILE, cfg)
    return cfg
