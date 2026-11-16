"""Motor de Snake: reglas puras y deterministas, sin ningún conocimiento de los modelos.

Coordenadas (x, y) con origen arriba a la izquierda; y crece hacia abajo.
Toda la aleatoriedad (posición de la manzana) usa un `random.Random` propio de la partida:
misma semilla + mismas acciones = misma partida.
"""
from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .config import Dificultad, obtener_dificultad

Casilla = tuple[int, int]


class Accion(Enum):
    ARRIBA = (0, -1)
    ABAJO = (0, 1)
    IZQUIERDA = (-1, 0)
    DERECHA = (1, 0)

    def __init__(self, dx: int, dy: int):
        # Atributos directos: el acceso vía propiedad de Enum es ~10× más lento.
        self.dx = dx
        self.dy = dy

    @property
    def opuesta(self) -> "Accion":
        return _OPUESTAS[self]

    @property
    def etiqueta(self) -> str:
        return self.name.lower()

    def desde(self, casilla: Casilla) -> Casilla:
        return (casilla[0] + self.dx, casilla[1] + self.dy)


ACCIONES: tuple[Accion, ...] = (Accion.ARRIBA, Accion.ABAJO, Accion.IZQUIERDA, Accion.DERECHA)
_OPUESTAS = {
    Accion.ARRIBA: Accion.ABAJO, Accion.ABAJO: Accion.ARRIBA,
    Accion.IZQUIERDA: Accion.DERECHA, Accion.DERECHA: Accion.IZQUIERDA,
}


class EstadoPartida(Enum):
    EN_CURSO = "en_curso"
    VICTORIA = "victoria"
    DERROTA = "derrota"
    INTERRUMPIDA = "interrumpida"   # fin externo: ciclo, límite técnico, usuario


# Causas de fin
LIMITE = "limite"
CUERPO = "cuerpo"
VICTORIA = "victoria"
CICLO = "ciclo"
LIMITE_TECNICO = "limite_tecnico"
MANUAL = "manual"


class ErrorPartida(RuntimeError):
    pass


@dataclass(frozen=True)
class Movimiento:
    """Resultado de resolver una acción sobre un estado, sin modificarlo."""
    destino: Casilla
    colision: str | None   # LIMITE | CUERPO | None
    come: bool


def resolver_movimiento(segmentos, ocupadas, ancho: int, alto: int,
                        manzana: Casilla | None, accion: Accion) -> Movimiento:
    """Única definición de las reglas de colisión. La usan el motor y la percepción.

    - Salir del tablero: colisión con el límite.
    - Entrar en el cuello (giro de 180° con longitud ≥ 2): colisión con el cuerpo.
    - Entrar en el cuerpo: colisión, salvo en la cola cuando no se come (la cola se mueve).
    """
    cabeza = segmentos[0]
    destino = accion.desde(cabeza)
    x, y = destino
    if not (0 <= x < ancho and 0 <= y < alto):
        return Movimiento(destino, LIMITE, False)
    if len(segmentos) >= 2 and destino == segmentos[1]:
        return Movimiento(destino, CUERPO, False)
    come = destino == manzana
    if destino in ocupadas and not (destino == segmentos[-1] and not come):
        return Movimiento(destino, CUERPO, False)
    return Movimiento(destino, None, come)


@dataclass(frozen=True)
class ResultadoPaso:
    accion: Accion
    cabeza_anterior: Casilla
    cabeza: Casilla
    comio: bool
    colision: str | None
    victoria: bool
    terminada: bool


class Partida:
    """Una partida de Snake. No sabe nada de modelos, recompensas ni tiempo."""

    def __init__(self, dificultad: str | Dificultad, semilla: int):
        self.dificultad = obtener_dificultad(dificultad)
        self.semilla = int(semilla)
        self._rng = random.Random(self.semilla)
        cx, cy = self.ancho // 2, self.alto // 2
        self._inicializar(
            [(cx - i, cy) for i in range(self.dificultad.longitud_inicial)],
            Accion.DERECHA,
        )
        self.manzana: Casilla | None = self._generar_manzana()

    @classmethod
    def desde_estado(cls, dificultad: str | Dificultad, semilla: int,
                     segmentos: Iterable[Casilla], direccion: Accion,
                     manzana: Casilla | None) -> "Partida":
        """Construye una situación concreta (pruebas, escenarios de etiquetado)."""
        p = cls.__new__(cls)
        p.dificultad = obtener_dificultad(dificultad)
        p.semilla = int(semilla)
        p._rng = random.Random(p.semilla)
        segs = [tuple(s) for s in segmentos]
        p._inicializar(segs, direccion)
        p._validar_estado()
        if manzana is not None:
            manzana = tuple(manzana)
            if manzana in p._ocupadas or not p._dentro(manzana):
                raise ErrorPartida(f"Manzana inválida: {manzana}")
        p.manzana = manzana
        return p

    def _inicializar(self, segmentos, direccion: Accion) -> None:
        self._segmentos: deque[Casilla] = deque(segmentos)
        self._ocupadas: set[Casilla] = set(self._segmentos)
        self.direccion = direccion
        self.estado = EstadoPartida.EN_CURSO
        self.causa_fin: str | None = None
        self.pasos = 0
        self.manzanas = 0

    def _validar_estado(self) -> None:
        segs = list(self._segmentos)
        if not segs:
            raise ErrorPartida("La serpiente necesita al menos un segmento")
        if len(set(segs)) != len(segs):
            raise ErrorPartida("Segmentos repetidos")
        for s in segs:
            if not self._dentro(s):
                raise ErrorPartida(f"Segmento fuera del tablero: {s}")
        for a, b in zip(segs, segs[1:]):
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1:
                raise ErrorPartida(f"Segmentos no contiguos: {a} {b}")

    # --- Consultas ---------------------------------------------------------
    @property
    def ancho(self) -> int:
        return self.dificultad.ancho

    @property
    def alto(self) -> int:
        return self.dificultad.alto

    @property
    def casillas(self) -> int:
        return self.dificultad.casillas

    @property
    def segmentos(self) -> tuple[Casilla, ...]:
        return tuple(self._segmentos)

    @property
    def cabeza(self) -> Casilla:
        return self._segmentos[0]

    @property
    def cola(self) -> Casilla:
        return self._segmentos[-1]

    @property
    def longitud(self) -> int:
        return len(self._segmentos)

    @property
    def en_curso(self) -> bool:
        return self.estado is EstadoPartida.EN_CURSO

    def ocupada(self, casilla: Casilla) -> bool:
        return casilla in self._ocupadas

    def _dentro(self, c: Casilla) -> bool:
        return 0 <= c[0] < self.ancho and 0 <= c[1] < self.alto

    def acciones_disponibles(self) -> tuple[Accion, ...]:
        """Acciones físicamente posibles: todas salvo volver sobre el cuello."""
        if len(self._segmentos) < 2:
            return ACCIONES
        cuello = self._segmentos[1]
        return tuple(a for a in ACCIONES if a.desde(self.cabeza) != cuello)

    def resolver(self, accion: Accion) -> Movimiento:
        return resolver_movimiento(self._segmentos, self._ocupadas, self.ancho,
                                   self.alto, self.manzana, accion)

    # --- Dinámica ----------------------------------------------------------
    def paso(self, accion: Accion) -> ResultadoPaso:
        if not self.en_curso:
            raise ErrorPartida(f"La partida ya terminó ({self.causa_fin})")
        if not isinstance(accion, Accion):
            raise TypeError(f"Se esperaba Accion, llegó {accion!r}")
        anterior = self.cabeza
        mov = self.resolver(accion)
        self.pasos += 1
        if mov.colision is not None:
            self.estado = EstadoPartida.DERROTA
            self.causa_fin = mov.colision
            return ResultadoPaso(accion, anterior, anterior, False, mov.colision, False, True)

        if not mov.come:
            self._ocupadas.discard(self._segmentos.pop())
        self._segmentos.appendleft(mov.destino)
        self._ocupadas.add(mov.destino)
        self.direccion = accion

        victoria = False
        if mov.come:
            self.manzanas += 1
            if self.longitud == self.casillas:
                victoria = True
                self.estado = EstadoPartida.VICTORIA
                self.causa_fin = VICTORIA
                self.manzana = None          # E8: no se genera otra manzana
            else:
                self.manzana = self._generar_manzana()
        return ResultadoPaso(accion, anterior, mov.destino, mov.come, None, victoria, victoria)

    def terminar(self, causa: str) -> None:
        """Fin externo (ciclo, límite técnico, usuario)."""
        if self.en_curso:
            self.estado = EstadoPartida.INTERRUMPIDA
            self.causa_fin = causa

    def _generar_manzana(self) -> Casilla | None:
        libres = [(x, y) for y in range(self.alto) for x in range(self.ancho)
                  if (x, y) not in self._ocupadas]
        return self._rng.choice(libres) if libres else None

    # --- Copias y serialización -------------------------------------------
    def clonar(self) -> "Partida":
        p = Partida.__new__(Partida)
        p.dificultad = self.dificultad
        p.semilla = self.semilla
        p._rng = random.Random()
        p._rng.setstate(self._rng.getstate())
        p._segmentos = deque(self._segmentos)
        p._ocupadas = set(self._ocupadas)
        p.direccion = self.direccion
        p.estado = self.estado
        p.causa_fin = self.causa_fin
        p.pasos = self.pasos
        p.manzanas = self.manzanas
        p.manzana = self.manzana
        return p

    def instantanea(self) -> dict:
        return {
            "dificultad": self.dificultad.clave,
            "ancho": self.ancho,
            "alto": self.alto,
            "semilla": self.semilla,
            "segmentos": [list(s) for s in self._segmentos],
            "direccion": self.direccion.etiqueta,
            "manzana": list(self.manzana) if self.manzana else None,
            "pasos": self.pasos,
            "manzanas": self.manzanas,
            "longitud": self.longitud,
            "estado": self.estado.value,
            "causa_fin": self.causa_fin,
        }
