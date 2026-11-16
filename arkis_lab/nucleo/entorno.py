"""Entorno: une motor, percepción, recompensa, ciclos y evolución en un episodio.

No contiene ningún algoritmo de aprendizaje. Los modelos reciben `Percepcion` y devuelven
una `Accion`; cada uno decide qué hace con la `Transicion` según su metodología.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import evolucion
from .ciclos import ConfigCiclos, DetectorCiclos, EvaluacionCiclo
from .config import (SEGUNDOS_CICLO, VELOCIDAD_MOVIMIENTO_POR_DEFECTO, Dificultad,
                     obtener_dificultad)
from .motor import CICLO, LIMITE_TECNICO, Accion, ErrorPartida, Partida
from .percepcion import Percepcion, percibir
from .recompensas import ConfigRecompensa, Recompensa, calcular_recompensa
from .reloj import RelojSimulacion


@dataclass(frozen=True)
class ConfigEntorno:
    velocidad_movimiento: float = VELOCIDAD_MOVIMIENTO_POR_DEFECTO
    segundos_ciclo: float = SEGUNDOS_CICLO
    # Seguridad: pasos sin manzana = factor · casillas. Causa de fin distinta del ciclo.
    factor_limite_tecnico: int = 100
    recompensa: ConfigRecompensa = field(default_factory=ConfigRecompensa)
    ciclos: ConfigCiclos = field(default_factory=ConfigCiclos)


@dataclass(frozen=True)
class Transicion:
    accion: Accion
    percepcion: Percepcion          # estado siguiente
    recompensa: Recompensa
    terminada: bool
    causa_fin: str | None
    comio: bool
    nivel: int
    ciclo: EvaluacionCiclo | None
    pasos_en_ciclo: int


@dataclass(frozen=True)
class ResumenEpisodio:
    dificultad: str
    semilla: int
    pasos: int
    manzanas: int
    longitud_max: int
    ocupacion_max: float
    nivel: int
    victoria: bool
    causa_fin: str | None
    retorno: float
    retorno_por_componente: dict
    tiempo_juego_s: float


def _manhattan(a, b):
    return None if b is None else abs(a[0] - b[0]) + abs(a[1] - b[1])


class Entorno:
    def __init__(self, dificultad: str | Dificultad, config: ConfigEntorno | None = None):
        self.dificultad = obtener_dificultad(dificultad)
        self.config = config or ConfigEntorno()
        self.reloj = RelojSimulacion(self.config.velocidad_movimiento)
        self.limite_ciclo = self.reloj.pasos_para(self.config.segundos_ciclo)
        self.limite_tecnico = self.config.factor_limite_tecnico * self.dificultad.casillas
        self.partida: Partida | None = None

    def reiniciar(self, semilla: int, partida: Partida | None = None) -> Percepcion:
        self.partida = partida if partida is not None else Partida(self.dificultad, semilla)
        self._detector = DetectorCiclos(self.dificultad.casillas, self.config.ciclos)
        self._detector.reiniciar(self.partida.segmentos, self.partida.manzana)
        self.pasos_en_ciclo = 0
        self.pasos_sin_manzana = 0
        self.nivel_max = 0
        self._retorno = 0.0
        self._componentes: dict[str, float] = {}
        self._percepcion = percibir(self.partida)
        return self._percepcion

    @property
    def percepcion(self) -> Percepcion:
        return self._percepcion

    @property
    def terminado(self) -> bool:
        return self.partida is None or not self.partida.en_curso

    def paso(self, accion: Accion) -> Transicion:
        if self.partida is None:
            raise ErrorPartida("Llama a reiniciar() antes de paso()")
        p = self.partida
        d_ant = _manhattan(p.cabeza, p.manzana)
        res = p.paso(accion)
        evaluacion = None

        if res.terminada:
            self.pasos_en_ciclo = 0
        elif res.comio:
            self.pasos_sin_manzana = 0
            self.pasos_en_ciclo = 0
            self._detector.reiniciar(p.segmentos, p.manzana)
        else:
            self.pasos_sin_manzana += 1
            evaluacion = self._detector.registrar(p.segmentos, p.manzana, accion)
            self.pasos_en_ciclo = self.pasos_en_ciclo + 1 if evaluacion.en_ciclo else 0
            if self.pasos_en_ciclo >= self.limite_ciclo:
                p.terminar(CICLO)
            elif self.pasos_sin_manzana >= self.limite_tecnico:
                p.terminar(LIMITE_TECNICO)

        r = calcular_recompensa(
            self.config.recompensa,
            d_anterior=d_ant, d_actual=_manhattan(p.cabeza, p.manzana),
            comio=res.comio, colision=res.colision is not None, victoria=res.victoria,
            estado_repetido=bool(evaluacion and evaluacion.configuracion_repetida),
            casilla_nueva=bool(evaluacion and evaluacion.casilla_nueva),
            fin_por_ciclo=p.causa_fin == CICLO,
        )
        self._retorno += r.total
        for k, v in r.componentes.items():
            self._componentes[k] = self._componentes.get(k, 0.0) + v

        n = evolucion.nivel(p.longitud, p.casillas, p.manzanas)
        self.nivel_max = max(self.nivel_max, n)
        self._percepcion = percibir(p)
        return Transicion(accion, self._percepcion, r, not p.en_curso, p.causa_fin,
                          res.comio, n, evaluacion, self.pasos_en_ciclo)

    def resumen(self) -> ResumenEpisodio:
        p = self.partida
        return ResumenEpisodio(
            dificultad=self.dificultad.clave, semilla=p.semilla, pasos=p.pasos,
            manzanas=p.manzanas, longitud_max=p.longitud,
            ocupacion_max=evolucion.ocupacion(p.longitud, p.casillas),
            nivel=self.nivel_max, victoria=p.causa_fin == "victoria", causa_fin=p.causa_fin,
            retorno=self._retorno, retorno_por_componente=dict(self._componentes),
            tiempo_juego_s=self.reloj.segundos(p.pasos),
        )
