"""Vector de características de ARKIS (27 valores), calculado solo desde la percepción común.

Por cada acción absoluta (arriba, abajo, izquierda, derecha), 6 rasgos:
  colision, espacio (fracción de casillas libres alcanzables), cola_alcanzable,
  acerca (+1 reduce la distancia a la manzana, −1 la aumenta), muro (distancia normalizada
  al límite en esa dirección), recto (es la dirección actual).
Globales: dx y dy normalizados hacia la manzana y ocupación del tablero.
"""
from __future__ import annotations

import numpy as np

from ...nucleo.motor import ACCIONES
from ...nucleo.percepcion import Percepcion

RASGOS_ACCION = ("colision", "espacio", "cola_alcanzable", "acerca", "muro", "recto")
NOMBRES = [f"{r}_{a.etiqueta}" for a in ACCIONES for r in RASGOS_ACCION] + [
    "manzana_dx", "manzana_dy", "ocupacion"]


def caracteristicas(p: Percepcion) -> np.ndarray:
    c, m, mu = p.cuerpo, p.manzana, p.muros
    libres = max(1, c.casillas_libres)
    lado_x, lado_y = max(1, p.ancho - 1), max(1, p.alto - 1)
    v = []
    for a in ACCIONES:
        if m is None:
            acerca = 0.0
        else:
            d = abs(m.dx - a.dx) + abs(m.dy - a.dy)
            acerca = float(np.sign(m.manhattan - d))
        lado = lado_x if a.dx else lado_y
        v += [
            float(c.colision_por_accion[a] is not None),
            c.espacio_por_accion[a] / libres,
            float(c.cola_alcanzable_por_accion[a]),
            acerca,
            mu.distancia(a) / lado,
            float(a is c.direccion),
        ]
    v += [
        0.0 if m is None else m.dx / lado_x,
        0.0 if m is None else m.dy / lado_y,
        c.longitud / (p.ancho * p.alto),
    ]
    return np.asarray(v, dtype=np.float64)
