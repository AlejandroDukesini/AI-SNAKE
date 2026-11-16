"""Protocolo de evaluación reproducible: semillas disjuntas y estadísticos con IC 95 %.

Una `politica` es cualquier función (percepcion, rng) -> Accion. El rng de la política se
deriva de la semilla del episodio, así la evaluación completa es reproducible.
"""
from __future__ import annotations

import math
import random
import statistics
from collections import Counter
from dataclasses import dataclass

from ..nucleo.config import Dificultad
from ..nucleo.entorno import ConfigEntorno, Entorno, ResumenEpisodio

# Rangos disjuntos: ninguna semilla de prueba se usa jamás para entrenar.
_BASES = {"entrenamiento": 0, "validacion": 1_000_000, "prueba": 2_000_000}


def semillas(conjunto: str, n: int) -> list[int]:
    if conjunto not in _BASES:
        raise ValueError(f"Conjunto desconocido: {conjunto}")
    return [_BASES[conjunto] + i for i in range(n)]


def rng_episodio(semilla: int) -> random.Random:
    return random.Random(semilla * 7919 + 1)


def jugar_episodio(entorno: Entorno, politica, semilla: int) -> ResumenEpisodio:
    rng = rng_episodio(semilla)
    perc = entorno.reiniciar(semilla)
    while not entorno.terminado:
        perc = entorno.paso(politica(perc, rng)).percepcion
    return entorno.resumen()


def jugar_episodio_observado(entorno: Entorno, agente, semilla: int, observador) -> ResumenEpisodio:
    """Igual que jugar_episodio (mismo RNG, mismas llamadas a decidir) pero entrega cada
    decisión real y su resultado al observador."""
    rng = rng_episodio(semilla)
    perc = entorno.reiniciar(semilla)
    while not entorno.terminado:
        d = agente.decidir(perc, rng)
        cabeza, manzana = entorno.partida.cabeza, entorno.partida.manzana
        t = entorno.paso(d.accion)
        observador.paso(cabeza, manzana, t, d.a_dict(), entorno)
        perc = t.percepcion
    return entorno.resumen()


# Valores críticos t de Student (bilateral 95 %) para gl 1..30; después ≈ normal.
_T95 = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228,
        2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086,
        2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042]


@dataclass(frozen=True)
class Estadistico:
    n: int
    media: float
    mediana: float
    sd: float
    ic95: tuple[float, float]


def estadistico(valores) -> Estadistico:
    v = [float(x) for x in valores]
    n = len(v)
    media = statistics.fmean(v)
    sd = statistics.stdev(v) if n > 1 else 0.0
    t = _T95[n - 2] if 2 <= n <= 31 else 1.96
    h = t * sd / math.sqrt(n) if n > 1 else 0.0
    return Estadistico(n, media, statistics.median(v), sd, (media - h, media + h))


@dataclass(frozen=True)
class Evaluacion:
    dificultad: str
    episodios: list
    manzanas: Estadistico
    ocupacion_max: Estadistico
    nivel: Estadistico
    pasos: Estadistico
    victorias: int
    causas_fin: dict
    mejor_nivel: int


def evaluar(politica, dificultad: str | Dificultad, lista_semillas,
            config: ConfigEntorno | None = None) -> Evaluacion:
    entorno = Entorno(dificultad, config)
    eps = [jugar_episodio(entorno, politica, s) for s in lista_semillas]
    return Evaluacion(
        dificultad=entorno.dificultad.clave, episodios=eps,
        manzanas=estadistico(e.manzanas for e in eps),
        ocupacion_max=estadistico(e.ocupacion_max for e in eps),
        nivel=estadistico(e.nivel for e in eps),
        pasos=estadistico(e.pasos for e in eps),
        victorias=sum(e.victoria for e in eps),
        causas_fin=dict(Counter(e.causa_fin for e in eps)),
        mejor_nivel=max(e.nivel for e in eps),
    )
