# -*- coding: utf-8 -*-
"""
================================================================================
  MIGRACION: mejores_ias.json  ->  historial/<especimen>/
================================================================================
  Convierte el historial antiguo (un unico JSON con todas las IAs) a la nueva
  estructura de una carpeta por especimen. Conserva pesos, fitness, fechas y
  favoritos.

  Es idempotente y NO destructivo:
    - No pisa una carpeta que ya exista.
    - No borra `mejores_ias.json`: se queda como copia de seguridad.

  Uso:  python migrar_historial.py          (migra)
        python migrar_historial.py --dry    (solo muestra que haria)
================================================================================
"""

import os
import sys
import json

import storage
import snake_neuroevolution as ml

VIEJO = os.path.join(storage.SCRIPT_DIR, "mejores_ias.json")

# El historial antiguo se entreno siempre en 8x8: era una constante del codigo.
GRID_ANTIGUO = 8


def cargar_antiguo():
    """Lee el JSON antiguo. Devuelve [] si no existe o esta corrupto."""
    if not os.path.isfile(VIEJO):
        return []
    try:
        with open(VIEJO, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    return [d for d in datos if isinstance(d, dict) and "pesos" in d] \
        if isinstance(datos, list) else []


def migrar(dry=False):
    """Crea una carpeta por cada IA del JSON antiguo."""
    antiguos = cargar_antiguo()
    if not antiguos:
        print("No hay nada que migrar: no existe mejores_ias.json o esta vacio.")
        return 0

    print(f"Encontradas {len(antiguos)} IAs en mejores_ias.json\n")
    migradas = saltadas = 0

    for viejo in antiguos:
        nombre = viejo.get("nombre") or ml.random_name()
        carpeta = storage.slugify(nombre)

        if storage.exists(carpeta):
            print(f"  [saltada]  {nombre:24s} -> historial/{carpeta}/ ya existe")
            saltadas += 1
            continue

        # `fecha` era el unico campo temporal del formato antiguo.
        fecha = viejo.get("fecha_creacion") or viejo.get("fecha") or ""
        # La red antigua tiene 9 entradas; from_dict le anade la columna de
        # ceros del sensor de tamano, dejando su comportamiento intacto.
        brain = ml.NeuralNetwork.from_dict(viejo["pesos"])

        modelo = {
            "carpeta":             carpeta,
            "nombre":              nombre,
            "fecha_creacion":      fecha,
            "fecha_actualizacion": viejo.get("fecha_actualizacion") or fecha,
            # El formato antiguo no registro las generaciones y no se pueden
            # deducir (el limite ya era configurable): se marca desconocido en
            # vez de inventar una cifra.
            "generaciones":        viejo.get("generaciones"),
            "fitness":             int(viejo.get("fitness", 0)),
            "frutas":              int(viejo.get("frutas", 0)),
            "pasos":               int(viejo.get("pasos", 0)),
            "length":              ml.INITIAL_LENGTH + int(viejo.get("frutas", 0)),
            "grid":                GRID_ANTIGUO,
            "favorito":            bool(viejo.get("favorito", False)),
            "pesos":               brain.to_dict(),
        }

        estrella = " *FAV*" if modelo["favorito"] else ""
        print(f"  [migrada]  {nombre:24s} -> historial/{carpeta}/  "
              f"fitness={modelo['fitness']}{estrella}")

        if not dry:
            storage._write_json(
                os.path.join(storage.model_dir(carpeta), storage.MODEL_FILE), modelo)
            # Sesion sintetica: no sabemos como fue aquel entrenamiento, pero si
            # su resultado. Marcada para no confundirla con una sesion real.
            storage._write_json(
                os.path.join(storage.model_dir(carpeta), storage.SESSIONS_FILE),
                [{
                    "fecha":        fecha,
                    "generaciones": viejo.get("generaciones"),
                    "fitness":      modelo["fitness"],
                    "frutas":       modelo["frutas"],
                    "pasos":        modelo["pasos"],
                    "length":       modelo["length"],
                    "grid":         GRID_ANTIGUO,
                    "record":       True,
                    "importada":    True,
                }])
        migradas += 1

    print()
    print(f"Migradas: {migradas} | Saltadas (ya existian): {saltadas}")
    if dry:
        print("\n(--dry: no se ha escrito nada)")
    else:
        print(f"\nmejores_ias.json se conserva intacto como copia de seguridad.")
    return migradas


def migrar_config(dry=False):
    """Traduce el config.json antiguo al formato nuevo.

    Cambiaron los dos campos:
      - Los temas se llamaban tech/friendly/retro y ahora oscura/minimalista/verde.
      - `max_gen` era el INDICE de la ultima generacion contando desde 0, asi que
        `max_gen: 4` significaba 5 generaciones. Ahora `generations` es la
        cantidad directa, sin trampa: por eso se suma 1.
    """
    ruta = storage.CONFIG_FILE
    if not os.path.isfile(ruta):
        return

    try:
        with open(ruta, "r", encoding="utf-8") as f:
            viejo = json.load(f)
    except (json.JSONDecodeError, OSError):
        return
    if not isinstance(viejo, dict) or "max_gen" not in viejo:
        return          # Ya esta en el formato nuevo

    TEMAS = {"tech": "oscura", "friendly": "minimalista", "retro": "verde"}
    nuevo = {
        "theme":       TEMAS.get(viejo.get("theme"), storage.DEFAULT_THEME),
        "generations": ml.clamp_generations(int(viejo.get("max_gen", 4)) + 1),
        "grid":        ml.DEFAULT_GRID,   # Antes el tablero era fijo 8x8
    }
    print(f"\nConfiguracion: {viejo}  ->  {nuevo}")
    if not dry:
        storage._write_json(ruta, nuevo)


if __name__ == "__main__":
    seco = "--dry" in sys.argv
    migrar(dry=seco)
    migrar_config(dry=seco)
