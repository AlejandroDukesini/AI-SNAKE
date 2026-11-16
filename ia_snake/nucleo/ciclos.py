"""Detector de ciclos improductivos.

Evalúa el comportamiento repetitivo desde la última manzana:
- configuración repetida (cuerpo completo + manzana ya vistos);
- posiciones repetidas: ventana llena sin casillas nuevas y pocas casillas distintas;
- secuencia de acciones periódica, también sin casillas nuevas en la ventana.

Recorrer casillas nuevas cuenta como progreso: no comer durante un rato no es un ciclo.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

CONFIGURACION_REPETIDA = "configuracion_repetida"
POSICIONES_REPETIDAS = "posiciones_repetidas"
SECUENCIA_PERIODICA = "secuencia_periodica"


@dataclass(frozen=True)
class ConfigCiclos:
    ventana: int | None = None        # None = número de casillas del tablero (mín. 16)
    umbral_unicas: float = 0.5        # proporción de casillas distintas en la ventana
    periodo_maximo: int = 8
    repeticiones_periodo: int = 3


@dataclass(frozen=True)
class EvaluacionCiclo:
    en_ciclo: bool
    motivos: tuple[str, ...]
    configuracion_repetida: bool
    casilla_nueva: bool


class DetectorCiclos:
    def __init__(self, casillas: int, config: ConfigCiclos = ConfigCiclos()):
        self.config = config
        self.ventana = config.ventana or max(16, casillas)
        self.reiniciar()

    def reiniciar(self, segmentos=None, manzana=None) -> None:
        """Al empezar y tras cada manzana (progreso efectivo)."""
        self._configs: set = set()
        self._visitadas: set = set()
        self._pos: deque = deque(maxlen=self.ventana)
        self._nuevas: deque = deque(maxlen=self.ventana)
        self._acciones: deque = deque(
            maxlen=self.config.periodo_maximo * self.config.repeticiones_periodo)
        if segmentos is not None:
            self._configs.add((tuple(segmentos), manzana))
            self._visitadas.add(segmentos[0])

    def registrar(self, segmentos, manzana, accion) -> EvaluacionCiclo:
        clave = (tuple(segmentos), manzana)
        repetida = clave in self._configs
        self._configs.add(clave)
        cabeza = segmentos[0]
        nueva = cabeza not in self._visitadas
        self._visitadas.add(cabeza)
        self._pos.append(cabeza)
        self._nuevas.append(nueva)
        self._acciones.append(accion)

        motivos = []
        if repetida:
            motivos.append(CONFIGURACION_REPETIDA)
        if len(self._pos) == self.ventana and not any(self._nuevas):
            if len(set(self._pos)) / self.ventana < self.config.umbral_unicas:
                motivos.append(POSICIONES_REPETIDAS)
            if self._periodica():
                motivos.append(SECUENCIA_PERIODICA)
        return EvaluacionCiclo(bool(motivos), tuple(motivos), repetida, nueva)

    def _periodica(self) -> bool:
        acc = list(self._acciones)
        k = self.config.repeticiones_periodo
        for p in range(1, self.config.periodo_maximo + 1):
            if len(acc) < p * k:
                break
            cola = acc[-p * k:]
            bloque = cola[:p]
            if all(cola[i] == bloque[i % p] for i in range(p * k)):
                return True
        return False
