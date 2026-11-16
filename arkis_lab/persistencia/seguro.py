"""Serialización segura de modelos scikit-learn con skops (sin pickle).

skops marca `sklearn.tree._tree.Tree` como no confiable: un archivo manipulado podría
provocar lecturas fuera de rango al predecir. Política del laboratorio:
- Artefactos propios: se confía en Tree solo si el hash SHA-256 coincide con el registrado
  en el meta.json de la versión (lo garantiza AlmacenModelo.cargar_version).
- Artefactos importados: el usuario debe confirmarlo explícitamente (`confiar_importados`).
"""
from __future__ import annotations

import skops.io as sio

TIPOS_REVISADOS = ["sklearn.tree._tree.Tree"]


class ErrorSeguridad(RuntimeError):
    pass


def volcar(modelo) -> bytes:
    return sio.dumps(modelo)


def cargar(datos: bytes, importado: bool = False, confiar_importados: bool = False):
    if importado and not confiar_importados:
        raise ErrorSeguridad("Artefacto importado: confirma que confías en su origen para cargarlo")
    desconocidos = set(sio.get_untrusted_types(data=datos)) - set(TIPOS_REVISADOS)
    if desconocidos:
        raise ErrorSeguridad(f"Tipos no revisados en el artefacto: {sorted(desconocidos)}")
    return sio.loads(datos, trusted=TIPOS_REVISADOS)
