"""BORK: Q-Learning tabular.

    Q(s,a) ← Q(s,a) + α [ r + γ · max_a' Q(s',a') − Q(s,a) ]

Estado compacto (no se tabula el tablero completo):
  - 'completa': por cada acción absoluta, peligro (colisión inmediata), encierro (espacio
    alcanzable < longitud) y cola alcanzable → 12 bits; más la dirección de la manzana
    (signo de Δx y Δy) → 9 valores. 2^12 · 9 = 36 864 estados posibles.
  - 'basica': solo peligro + dirección de la manzana (2^4 · 9 = 144). Sirve como ablación
    para medir cuánto aporta la información de encierro y cola.
Riesgo de compresión (aliasing): tableros distintos comparten celda. Se mide con la
varianza de los retornos observados dentro de cada par (s, a).
"""
from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, field

from ...nucleo.motor import ACCIONES, Accion
from ...nucleo.percepcion import Percepcion
from ...nucleo.recompensas import ConfigRecompensa
from ..base import Agente, Decision

REPRESENTACIONES = {"completa": 2 ** 12 * 9, "basica": 2 ** 4 * 9}
_IDX = {a: i for i, a in enumerate(ACCIONES)}


def _signo(v: int) -> str:
    return "+" if v > 0 else "-" if v < 0 else "0"


def estado(p: Percepcion, representacion: str = "completa") -> str:
    c = p.cuerpo
    peligro = "".join("1" if c.colision_por_accion[a] else "0" for a in ACCIONES)
    m = p.manzana
    manz = "xx" if m is None else _signo(m.dx) + _signo(m.dy)
    if representacion == "basica":
        return f"{peligro}|{manz}"
    encierro = "".join("1" if (c.colision_por_accion[a] is None and
                               c.espacio_por_accion[a] < c.longitud) else "0" for a in ACCIONES)
    cola = "".join("1" if c.cola_alcanzable_por_accion[a] else "0" for a in ACCIONES)
    return f"{peligro}|{encierro}|{cola}|{manz}"


@dataclass
class ConfigBork:
    alfa: float = 0.1
    gamma: float = 0.9
    epsilon_inicial: float = 1.0
    epsilon_final: float = 0.02
    decaimiento: float = 0.99          # ε_e = max(ε_final, ε_inicial · decaimiento^e)
    representacion: str = "completa"
    recompensa: dict = field(default_factory=lambda: asdict(ConfigRecompensa()))

    def __post_init__(self):
        if not 0 < self.alfa <= 1:
            raise ValueError("α debe estar en (0, 1]")
        if not 0 <= self.gamma <= 1:
            raise ValueError("γ debe estar en [0, 1]")
        if not 0 <= self.epsilon_final <= self.epsilon_inicial <= 1:
            raise ValueError("Se requiere 0 ≤ ε_final ≤ ε_inicial ≤ 1")
        if not 0 < self.decaimiento <= 1:
            raise ValueError("El decaimiento debe estar en (0, 1]")
        if self.representacion not in REPRESENTACIONES:
            raise ValueError(f"Representación desconocida: {self.representacion}")
        ConfigRecompensa(**self.recompensa)   # valida claves

    def config_recompensa(self) -> ConfigRecompensa:
        return ConfigRecompensa(**self.recompensa)

    def epsilon(self, episodio: int) -> float:
        return max(self.epsilon_final, self.epsilon_inicial * self.decaimiento ** episodio)


class TablaQ:
    def __init__(self, valores: dict | None = None, visitas: dict | None = None):
        self.q: dict[str, list[float]] = {k: list(v) for k, v in (valores or {}).items()}
        self.visitas: dict[str, list[int]] = {k: list(v) for k, v in (visitas or {}).items()}
        # Estadística de retornos por (s,a) para medir aliasing: [n, media, M2] (Welford)
        self.retornos: dict[str, list] = {}

    def fila(self, s: str) -> list[float]:
        f = self.q.get(s)
        if f is None:
            f = self.q[s] = [0.0, 0.0, 0.0, 0.0]
            self.visitas[s] = [0, 0, 0, 0]
        return f

    def mejor(self, s: str, disponibles, rng: random.Random) -> Accion:
        f = self.q.get(s)
        if f is None:
            return rng.choice(list(disponibles))
        top = max(f[_IDX[a]] for a in disponibles)
        return rng.choice([a for a in disponibles if f[_IDX[a]] == top])

    def max_q(self, s: str, disponibles) -> float:
        f = self.q.get(s)
        return 0.0 if f is None else max(f[_IDX[a]] for a in disponibles)

    def actualizar(self, s: str, a: Accion, objetivo: float, alfa: float) -> float:
        f = self.fila(s)
        i = _IDX[a]
        td = objetivo - f[i]
        f[i] += alfa * td
        self.visitas[s][i] += 1
        return td

    def registrar_retorno(self, s: str, a: Accion, g: float) -> None:
        k = f"{s}#{a.etiqueta}"
        n, media, m2 = self.retornos.get(k, (0, 0.0, 0.0))
        n += 1
        d = g - media
        media += d / n
        m2 += d * (g - media)
        self.retornos[k] = [n, media, m2]

    def aliasing(self, minimo: int = 5) -> dict:
        sds = [math.sqrt(m2 / (n - 1)) for n, _, m2 in self.retornos.values() if n >= minimo]
        return {"pares_medidos": len(sds),
                "sd_media_retorno_en_celda": (sum(sds) / len(sds)) if sds else None,
                "sd_maxima": max(sds) if sds else None}

    def a_dict(self) -> dict:
        return {"q": self.q, "visitas": self.visitas}


class BorkAgente(Agente):
    clave = "bork"
    nombre = "BORK"
    metodologia = "Aprendizaje por refuerzo (Q-Learning tabular)"

    def __init__(self, tabla: TablaQ, representacion: str = "completa", epsilon: float = 0.0):
        self.tabla = tabla
        self.representacion = representacion
        self.epsilon = epsilon

    def decidir(self, percepcion, rng=None) -> Decision:
        rng = rng or random.Random()
        s = estado(percepcion, self.representacion)
        disp = percepcion.cuerpo.acciones_disponibles
        conocido = s in self.tabla.q
        if self.epsilon and rng.random() < self.epsilon:
            a, modo = rng.choice(disp), "exploracion"
        else:
            a, modo = self.tabla.mejor(s, disp, rng), "explotacion"
        f = self.tabla.q.get(s, [0.0] * 4)
        return Decision(a, {b: f[_IDX[b]] for b in ACCIONES}, {
            "tipo": "valores_q", "estado": s, "estado_conocido": conocido, "modo": modo,
            "visitas": self.tabla.visitas.get(s, [0] * 4),
            "texto": (f"Estado {s}: {modo}, Q({a.etiqueta}) = {f[_IDX[a]]:.3f}" if conocido
                      else f"Estado {s} nunca visto: acción al azar"),
        })


def entrenar_episodio(entorno, tabla: TablaQ, cfg: ConfigBork, epsilon: float, semilla: int,
                      rng: random.Random, observador=None) -> tuple:
    """Un episodio de Q-Learning. Devuelve (resumen, estadísticas del episodio).
    `observador` (opcional) recibe cada paso real: estado, Q antes/después y recompensa."""
    perc = entorno.reiniciar(semilla)
    s = estado(perc, cfg.representacion)
    nuevos = 0
    traza = []
    td_abs = 0.0
    while not entorno.terminado:
        disp = perc.cuerpo.acciones_disponibles
        conocido = s in tabla.q
        if not conocido:
            nuevos += 1
        explora = rng.random() < epsilon            # mismo orden de consumo del RNG que antes
        a = rng.choice(disp) if explora else tabla.mejor(s, disp, rng)
        if observador is not None:
            cabeza, manzana = entorno.partida.cabeza, entorno.partida.manzana
            q_antes = list(tabla.q.get(s, [0.0] * 4))
        t = entorno.paso(a)
        r = t.recompensa.total
        if t.terminada and t.causa_fin != "limite_tecnico":
            objetivo = r                                    # estado terminal
            s2 = None
        else:
            s2 = estado(t.percepcion, cfg.representacion)
            objetivo = r + cfg.gamma * tabla.max_q(s2, t.percepcion.cuerpo.acciones_disponibles)
        td = tabla.actualizar(s, a, objetivo, cfg.alfa)
        td_abs += abs(td)
        if observador is not None:
            observador.paso(cabeza, manzana, t, {
                "accion": a.etiqueta,
                "puntuaciones": {b.etiqueta: round(q, 4) for b, q in zip(ACCIONES, q_antes)},
                "explicacion": {
                    "tipo": "valores_q", "estado": s, "estado_conocido": conocido,
                    "modo": "exploracion" if explora else "explotacion", "epsilon": round(epsilon, 4),
                    "visitas": list(tabla.visitas.get(s, [0] * 4)),
                    "q_antes": [round(q, 4) for q in q_antes],
                    "q_despues": [round(q, 4) for q in tabla.q[s]],
                    "objetivo": round(objetivo, 4), "error_td": round(td, 4),
                    "texto": (f"{'Exploración (ε)' if explora else 'Explotación'}: Q(s,{a.etiqueta}) "
                              f"{q_antes[_IDX[a]]:.3f} → {tabla.q[s][_IDX[a]]:.3f}"),
                }}, entorno, {"estados_tabla": len(tabla.q)})
        traza.append((s, a, r))
        perc = t.percepcion
        if s2 is not None:
            s = s2
    g = 0.0
    for s_, a_, r_ in reversed(traza):
        g = r_ + cfg.gamma * g
        tabla.registrar_retorno(s_, a_, g)
    return entorno.resumen(), {"estados_nuevos": nuevos, "td_medio": td_abs / max(1, len(traza))}
