"""Configuración fija del entorno: dificultades, velocidades y versión del motor.

Decisiones aprobadas (docs/ia-snake/DECISIONES.md):
- Difícil es 16×16 (256 casillas): tablero par, admite ciclo hamiltoniano y E8 es demostrable.
- Fácil (4×4) empieza con longitud 1; Medio y Difícil con longitud 3 (cabeza, cuerpo y cola).
- La regla de los 30 s se mide en tiempo de juego: pasos / velocidad de movimiento.
"""
from __future__ import annotations

from dataclasses import dataclass

VERSION_MOTOR = "1.0.0"

VELOCIDAD_MOVIMIENTO_POR_DEFECTO = 10.0   # movimientos por segundo de juego
SEGUNDOS_CICLO = 30.0                     # regla de los 30 segundos


@dataclass(frozen=True)
class Dificultad:
    clave: str
    nombre: str
    ancho: int
    alto: int
    longitud_inicial: int

    @property
    def casillas(self) -> int:
        return self.ancho * self.alto


DIFICULTADES: dict[str, Dificultad] = {
    "facil": Dificultad("facil", "Fácil", 4, 4, 1),
    "medio": Dificultad("medio", "Medio", 8, 8, 3),
    "dificil": Dificultad("dificil", "Difícil", 16, 16, 3),
}


def obtener_dificultad(clave: str | Dificultad) -> Dificultad:
    if isinstance(clave, Dificultad):
        return clave
    try:
        return DIFICULTADES[clave]
    except KeyError:
        raise ValueError(
            f"Dificultad desconocida: {clave!r}. Opciones: {', '.join(DIFICULTADES)}"
        ) from None
