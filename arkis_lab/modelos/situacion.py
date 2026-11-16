"""Situación: estado del tablero serializable (para guardar ejemplos y casos) y las 8
simetrías del cuadrado. Lo usan los modelos que aprenden de ejemplos (ARKIS, LERK, CLARK).

Una simetría transforma el tablero y la acción de forma geométricamente exacta: no inventa
etiquetas, solo describe la misma decisión vista girada o reflejada.
"""
from __future__ import annotations

from ..nucleo.motor import ACCIONES, Accion, Partida
from ..nucleo.percepcion import Percepcion, percibir

# Matrices enteras 2×2 (a, b, c, d): (x, y) -> (a·x + b·y, c·x + d·y)
SIMETRIAS: dict[str, tuple[int, int, int, int]] = {
    "identidad": (1, 0, 0, 1),
    "rot90": (0, -1, 1, 0),
    "rot180": (-1, 0, 0, -1),
    "rot270": (0, 1, -1, 0),
    "espejo_h": (-1, 0, 0, 1),
    "espejo_v": (1, 0, 0, -1),
    "transpuesta": (0, 1, 1, 0),
    "antitranspuesta": (0, -1, -1, 0),
}


def situacion_de(partida: Partida) -> dict:
    return {
        "dificultad": partida.dificultad.clave,
        "segmentos": [list(s) for s in partida.segmentos],
        "direccion": partida.direccion.etiqueta,
        "manzana": list(partida.manzana) if partida.manzana else None,
    }


def partida_de(situacion: dict, semilla: int = 0) -> Partida:
    return Partida.desde_estado(
        situacion["dificultad"], semilla, [tuple(s) for s in situacion["segmentos"]],
        Accion[situacion["direccion"].upper()],
        tuple(situacion["manzana"]) if situacion["manzana"] else None)


def percepcion_de(situacion: dict) -> Percepcion:
    return percibir(partida_de(situacion))


def accion_por_nombre(nombre: str) -> Accion:
    return Accion[nombre.upper()]


def _aplicar(m, vx, vy):
    a, b, c, d = m
    return a * vx + b * vy, c * vx + d * vy


def transformar_accion(accion: Accion, nombre_simetria: str) -> Accion:
    v = _aplicar(SIMETRIAS[nombre_simetria], accion.dx, accion.dy)
    return next(a for a in ACCIONES if (a.dx, a.dy) == v)


def transformar_situacion(situacion: dict, nombre_simetria: str, lado: int) -> dict:
    """Solo para tableros cuadrados. p' = M·p + (I − M)·c, con 2c = lado − 1 (siempre entero)."""
    m = SIMETRIAS[nombre_simetria]
    k = lado - 1

    def punto(p):
        x, y = _aplicar(m, p[0], p[1])
        ox, oy = _aplicar(m, k, k)
        # (I − M)·c = (k − ox, k − oy) / 2, exacto porque ox, oy ∈ {k, −k}
        return [x + (k - ox) // 2, y + (k - oy) // 2]

    return {
        "dificultad": situacion["dificultad"],
        "segmentos": [punto(s) for s in situacion["segmentos"]],
        "direccion": transformar_accion(Accion[situacion["direccion"].upper()],
                                        nombre_simetria).etiqueta,
        "manzana": punto(situacion["manzana"]) if situacion["manzana"] else None,
    }
