"""Interfaz común de los modelos: solo la forma de ACTUAR. Cada modelo aprende a su manera
(no hay un método `entrenar` común a propósito: la especificación prohíbe un entrenamiento
universal)."""
from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..nucleo.motor import Accion
from ..nucleo.percepcion import Percepcion

class NoEncontrado(LookupError):
    """El recurso pedido no existe (la API lo traduce a 404)."""

    def __str__(self):
        return str(self.args[0]) if self.args else "No encontrado"


# Estados con evidencia (docs/ia-snake/ETAPA-1-ANALISIS.md §6.3)
SIN_ENTRENAR = "sin_entrenar"
ENTRENADO = "entrenado"
EVALUADO = "evaluado"
VALIDADO = "validado"
PREENTRENADO = "preentrenado"
EXPERIMENTACION = "experimentacion"


@dataclass
class Decision:
    accion: Accion
    puntuaciones: dict = field(default_factory=dict)   # Accion -> float (escala propia del modelo)
    explicacion: dict = field(default_factory=dict)    # estructura propia de cada metodología

    def a_dict(self) -> dict:
        return {
            "accion": self.accion.etiqueta,
            "puntuaciones": {a.etiqueta: round(float(v), 4) for a, v in self.puntuaciones.items()},
            "explicacion": self.explicacion,
        }


class Agente(ABC):
    clave: str = ""
    nombre: str = ""
    metodologia: str = ""

    @abstractmethod
    def decidir(self, percepcion: Percepcion, rng: random.Random | None = None) -> Decision:
        ...

    def politica(self):
        """Adaptador a (percepcion, rng) -> Accion para el protocolo de evaluación."""
        return lambda perc, rng: self.decidir(perc, rng).accion
