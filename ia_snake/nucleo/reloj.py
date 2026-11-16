"""Relojes.

- RelojSimulacion: tiempo de juego = pasos / velocidad de movimiento. Es el que usa la
  regla de los 30 s: determinista, independiente del hardware, del renderizado y de
  acelerar el entrenamiento.
- RelojSesion: tiempo real activo medido con un reloj monotónico, sin contar las pausas.
  Solo se muestra e informa; no interviene en las reglas.
"""
from __future__ import annotations

import math
import time


class RelojSimulacion:
    def __init__(self, velocidad_movimiento: float):
        if velocidad_movimiento <= 0:
            raise ValueError("La velocidad de movimiento debe ser positiva")
        self.velocidad = float(velocidad_movimiento)

    def segundos(self, pasos: int) -> float:
        return pasos / self.velocidad

    def pasos_para(self, segundos: float) -> int:
        return max(1, math.ceil(segundos * self.velocidad - 1e-9))


class RelojSesion:
    def __init__(self, fuente=time.monotonic):
        self._fuente = fuente
        self._acumulado = 0.0
        self._desde: float | None = None

    @property
    def corriendo(self) -> bool:
        return self._desde is not None

    def iniciar(self) -> None:
        if self._desde is None:
            self._desde = self._fuente()

    reanudar = iniciar

    def pausar(self) -> None:
        if self._desde is not None:
            self._acumulado += self._fuente() - self._desde
            self._desde = None

    def transcurrido(self) -> float:
        extra = self._fuente() - self._desde if self._desde is not None else 0.0
        return self._acumulado + extra
