"""Líneas base SIN aprendizaje, para situar a los modelos. No son modelos del laboratorio.

- azar: acción disponible al azar.
- voraz: entre las acciones sin colisión inmediata, la que más reduce la distancia a la
  manzana (desempate por espacio alcanzable). No planifica: puede encerrarse.
"""
from __future__ import annotations

import random

from ..nucleo.motor import Accion
from ..nucleo.percepcion import Percepcion


def politica_azar(percepcion: Percepcion, rng: random.Random) -> Accion:
    return rng.choice(percepcion.cuerpo.acciones_disponibles)


def politica_voraz(percepcion: Percepcion, rng: random.Random) -> Accion:
    c = percepcion.cuerpo
    seguras = [a for a in c.acciones_disponibles if c.colision_por_accion[a] is None]
    if not seguras:
        return c.acciones_disponibles[0]
    m = percepcion.manzana
    hx, hy = c.cabeza

    def clave(a: Accion):
        d = 0 if m is None else abs(m.x - (hx + a.dx)) + abs(m.y - (hy + a.dy))
        return (d, -c.espacio_por_accion[a])

    return min(seguras, key=clave)


LINEAS_BASE = {"azar": politica_azar, "voraz": politica_voraz}
