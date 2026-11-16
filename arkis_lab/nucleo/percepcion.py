"""Los tres sentidos: cuerpo, manzana y muros.

`percibir(partida)` devuelve una instantánea inmutable: no guarda referencia a la partida.
La matriz del cuerpo se deriva de la lista ordenada de segmentos en el mismo momento, y
`verificar_sincronia` comprueba que ambas representaciones coinciden.

Los cálculos caros (espacio alcanzable y cola alcanzable por acción) son perezosos: solo
se calculan si un modelo los consulta.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property, lru_cache

import numpy as np

from .motor import ACCIONES, Accion, Casilla, Partida, resolver_movimiento


@lru_cache(maxsize=None)
def _vecinos(ancho: int, alto: int) -> tuple[tuple[int, ...], ...]:
    """Tabla de vecinos ortogonales por índice plano i = y·ancho + x."""
    out = []
    for y in range(alto):
        for x in range(ancho):
            v = []
            if y > 0: v.append(x + (y - 1) * ancho)
            if y < alto - 1: v.append(x + (y + 1) * ancho)
            if x > 0: v.append(x - 1 + y * ancho)
            if x < ancho - 1: v.append(x + 1 + y * ancho)
            out.append(tuple(v))
    return tuple(out)


def _alcanzables(inicio: Casilla, obstaculos, ancho: int, alto: int,
                 objetivo: Casilla | None = None) -> tuple[int, bool]:
    """BFS desde `inicio`. Devuelve (casillas alcanzables sin contar el inicio, objetivo alcanzado).
    El objetivo cuenta como alcanzado si es adyacente a la región, aunque sea un obstáculo."""
    vec = _vecinos(ancho, alto)
    bloqueado = bytearray(ancho * alto)
    for x, y in obstaculos:
        bloqueado[x + y * ancho] = 1
    ini = inicio[0] + inicio[1] * ancho
    obj = -1 if objetivo is None else objetivo[0] + objetivo[1] * ancho
    alcanzado = obj == ini
    bloqueado[ini] = 1
    pila = [ini]
    n = 0
    while pila:
        i = pila.pop()
        for j in vec[i]:
            if j == obj:
                alcanzado = True
            if not bloqueado[j]:
                bloqueado[j] = 1
                n += 1
                pila.append(j)
    return n, alcanzado


class SentidoCuerpo:
    """Sentido 1. Matriz binaria (0 libre, 1 ocupada) + segmentos ordenados cabeza→cola."""

    def __init__(self, segmentos: tuple[Casilla, ...], direccion: Accion,
                 ancho: int, alto: int, manzana: Casilla | None):
        self.segmentos = segmentos
        self.direccion = direccion
        self.ancho = ancho
        self.alto = alto
        self._manzana = manzana
        self._ocupadas = frozenset(segmentos)
        m = np.zeros((alto, ancho), dtype=np.uint8)
        for x, y in segmentos:
            m[y, x] = 1
        m.setflags(write=False)
        self.matriz = m   # indexada [y, x]

    @property
    def cabeza(self) -> Casilla:
        return self.segmentos[0]

    @property
    def cola(self) -> Casilla:
        return self.segmentos[-1]

    @property
    def longitud(self) -> int:
        return len(self.segmentos)

    @property
    def casillas_libres(self) -> int:
        return self.ancho * self.alto - self.longitud

    def ocupada(self, casilla: Casilla) -> bool:
        return casilla in self._ocupadas

    @cached_property
    def acciones_disponibles(self) -> tuple[Accion, ...]:
        if self.longitud < 2:
            return ACCIONES
        return tuple(a for a in ACCIONES if a.desde(self.cabeza) != self.segmentos[1])

    @cached_property
    def colision_por_accion(self) -> dict[Accion, str | None]:
        """Para cada acción: 'limite', 'cuerpo' o None (movimiento seguro este paso)."""
        return {a: self._mov(a).colision for a in ACCIONES}

    @cached_property
    def espacio_por_accion(self) -> dict[Accion, int]:
        """Casillas libres alcanzables desde la nueva cabeza tras la acción (0 si colisiona)."""
        out = {}
        for a in ACCIONES:
            cuerpo = self._cuerpo_tras(a)
            out[a] = 0 if cuerpo is None else _alcanzables(
                cuerpo[0], set(cuerpo[1:]), self.ancho, self.alto)[0]
        return out

    @cached_property
    def cola_alcanzable_por_accion(self) -> dict[Accion, bool]:
        """Si tras la acción la cabeza puede llegar a su cola (señal de no quedar encerrada)."""
        out = {}
        for a in ACCIONES:
            cuerpo = self._cuerpo_tras(a)
            if cuerpo is None:
                out[a] = False
            elif len(cuerpo) == 1:
                out[a] = True
            else:
                out[a] = _alcanzables(cuerpo[0], set(cuerpo[1:-1]), self.ancho,
                                      self.alto, objetivo=cuerpo[-1])[1]
        return out

    def _mov(self, a: Accion):
        return resolver_movimiento(self.segmentos, self._ocupadas, self.ancho, self.alto,
                                   self._manzana, a)

    def _cuerpo_tras(self, a: Accion) -> tuple[Casilla, ...] | None:
        mov = self._mov(a)
        if mov.colision is not None:
            return None
        resto = self.segmentos if mov.come else self.segmentos[:-1]
        return (mov.destino,) + resto


@dataclass(frozen=True)
class SentidoManzana:
    """Sentido 2. La manzana es visible: coordenadas, diferencias y distancia Manhattan."""
    x: int
    y: int
    dx: int          # x_manzana - x_cabeza (positivo = a la derecha)
    dy: int          # y_manzana - y_cabeza (positivo = abajo)
    manhattan: int

    @property
    def horizontal(self) -> str:
        return "derecha" if self.dx > 0 else "izquierda" if self.dx < 0 else "alineada"

    @property
    def vertical(self) -> str:
        return "abajo" if self.dy > 0 else "arriba" if self.dy < 0 else "alineada"

    @property
    def direccion_relativa(self) -> tuple[str, str]:
        return (self.vertical, self.horizontal)

    @property
    def acciones_que_acercan(self) -> tuple[Accion, ...]:
        out = []
        if self.dy < 0: out.append(Accion.ARRIBA)
        if self.dy > 0: out.append(Accion.ABAJO)
        if self.dx < 0: out.append(Accion.IZQUIERDA)
        if self.dx > 0: out.append(Accion.DERECHA)
        return tuple(out)


@dataclass(frozen=True)
class SentidoMuros:
    """Sentido 3. Distancia (casillas libres hasta el borde) a cada límite."""
    arriba: int
    abajo: int
    izquierda: int
    derecha: int
    colision_limite_por_accion: dict
    espacio_libre: int

    def distancia(self, accion: Accion) -> int:
        return getattr(self, accion.etiqueta)


@dataclass(frozen=True)
class Percepcion:
    cuerpo: SentidoCuerpo
    manzana: SentidoManzana | None   # None tras la victoria
    muros: SentidoMuros
    ancho: int
    alto: int
    pasos: int
    manzanas: int

    def a_dict(self, completa: bool = False) -> dict:
        c = self.cuerpo
        d = {
            "cuerpo": {
                "matriz": c.matriz.tolist(),
                "segmentos": [list(s) for s in c.segmentos],
                "cabeza": list(c.cabeza), "cola": list(c.cola),
                "longitud": c.longitud, "direccion": c.direccion.etiqueta,
                "casillas_libres": c.casillas_libres,
                "acciones_disponibles": [a.etiqueta for a in c.acciones_disponibles],
                "colision_por_accion": {a.etiqueta: v for a, v in c.colision_por_accion.items()},
            },
            "manzana": None if self.manzana is None else {
                "x": self.manzana.x, "y": self.manzana.y,
                "dx": self.manzana.dx, "dy": self.manzana.dy,
                "manhattan": self.manzana.manhattan,
                "direccion_relativa": list(self.manzana.direccion_relativa),
            },
            "muros": {
                "arriba": self.muros.arriba, "abajo": self.muros.abajo,
                "izquierda": self.muros.izquierda, "derecha": self.muros.derecha,
                "colision_limite_por_accion": {a.etiqueta: v for a, v in
                                               self.muros.colision_limite_por_accion.items()},
                "espacio_libre": self.muros.espacio_libre,
            },
        }
        if completa:
            d["cuerpo"]["espacio_por_accion"] = {a.etiqueta: v for a, v in c.espacio_por_accion.items()}
            d["cuerpo"]["cola_alcanzable_por_accion"] = {
                a.etiqueta: v for a, v in c.cola_alcanzable_por_accion.items()}
        return d


def percibir(partida: Partida) -> Percepcion:
    segs = partida.segmentos
    hx, hy = segs[0]
    ancho, alto = partida.ancho, partida.alto
    cuerpo = SentidoCuerpo(segs, partida.direccion, ancho, alto, partida.manzana)
    manzana = None
    if partida.manzana is not None:
        mx, my = partida.manzana
        manzana = SentidoManzana(mx, my, mx - hx, my - hy, abs(mx - hx) + abs(my - hy))
    muros = SentidoMuros(
        arriba=hy, abajo=alto - 1 - hy, izquierda=hx, derecha=ancho - 1 - hx,
        colision_limite_por_accion={
            a: not (0 <= hx + a.dx < ancho and 0 <= hy + a.dy < alto) for a in ACCIONES},
        espacio_libre=ancho * alto - len(segs),
    )
    return Percepcion(cuerpo, manzana, muros, ancho, alto, partida.pasos, partida.manzanas)


def verificar_sincronia(cuerpo: SentidoCuerpo) -> bool:
    """La matriz y la secuencia ordenada describen exactamente el mismo cuerpo contiguo."""
    segs = cuerpo.segmentos
    if len(set(segs)) != len(segs) or int(cuerpo.matriz.sum()) != len(segs):
        return False
    if any(cuerpo.matriz[y, x] != 1 for x, y in segs):
        return False
    return all(abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1 for a, b in zip(segs, segs[1:]))
