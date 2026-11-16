"""Hechos simbólicos de LERK, calculados desde la percepción común.

Cada predicado se evalúa para una acción candidata X: p.ej. libre(X), acerca(X), encierro(X).
Las reglas usan la variable X, así una regla aprendida en una dirección vale en todas
(generalización simbólica).
"""
from __future__ import annotations

from ...nucleo.motor import ACCIONES, Accion
from ...nucleo.percepcion import Percepcion

PREDICADOS: dict[str, str] = {
    "libre": "la casilla destino no provoca colisión",
    "choque_limite": "el movimiento sale del tablero",
    "choque_cuerpo": "el movimiento choca con el cuerpo",
    "come": "la casilla destino tiene la manzana",
    "acerca": "reduce la distancia Manhattan a la manzana",
    "aleja": "aumenta la distancia Manhattan a la manzana",
    "encierro": "tras moverse quedan menos casillas alcanzables que la longitud del cuerpo",
    "cola_alcanzable": "tras moverse la cabeza puede llegar a su cola",
    "recto": "continúa en la dirección actual",
    "borde": "la casilla destino está junto al límite del tablero",
}


def hechos(p: Percepcion) -> dict[Accion, frozenset[str]]:
    """Para cada acción, el conjunto de predicados verdaderos."""
    c, m = p.cuerpo, p.manzana
    hx, hy = c.cabeza
    out = {}
    for a in ACCIONES:
        col = c.colision_por_accion[a]
        h = set()
        if col is None:
            h.add("libre")
            if c.espacio_por_accion[a] < c.longitud:
                h.add("encierro")
            if c.cola_alcanzable_por_accion[a]:
                h.add("cola_alcanzable")
            nx, ny = hx + a.dx, hy + a.dy
            if nx in (0, p.ancho - 1) or ny in (0, p.alto - 1):
                h.add("borde")
        elif col == "limite":
            h.add("choque_limite")
        else:
            h.add("choque_cuerpo")
        if m is not None:
            d = abs(m.dx - a.dx) + abs(m.dy - a.dy)
            if d == 0:
                h.add("come")
            if d < m.manhattan:
                h.add("acerca")
            elif d > m.manhattan:
                h.add("aleja")
        if a is c.direccion:
            h.add("recto")
        out[a] = frozenset(h)
    return out


def literales() -> list[str]:
    """Literales posibles en una condición: 'p' o '!p'."""
    return [x for p in PREDICADOS for x in (p, "!" + p)]


def cumple(literal: str, verdaderos: frozenset[str]) -> bool:
    if literal.startswith("!"):
        return literal[1:] not in verdaderos
    return literal in verdaderos


def validar_literal(literal: str) -> str:
    nombre = literal[1:] if literal.startswith("!") else literal
    if nombre not in PREDICADOS:
        raise ValueError(f"Predicado desconocido: {nombre}")
    return literal


def texto_literal(literal: str) -> str:
    return f"NO {literal[1:]}(X)" if literal.startswith("!") else f"{literal}(X)"
