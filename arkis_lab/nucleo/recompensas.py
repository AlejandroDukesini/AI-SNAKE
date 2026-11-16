"""Función de recompensa común (la usan solo los componentes de refuerzo: BORK, CLARK-RL, MABU-RL).

Base: Δd = d_anterior - d_actual (positivo = se acercó). Con factor pequeño frente a la
colisión y la repetición, la distancia nunca es el único criterio. Cada componente se
devuelve por separado para poder registrarlo.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ConfigRecompensa:
    manzana: float = 10.0
    colision: float = -10.0
    factor_distancia: float = 0.1     # recompensa = factor · Δd
    supervivencia: float = -0.01      # por paso vivo
    repeticion: float = -0.5          # configuración ya vista desde la última manzana
    exploracion: float = 0.02         # casilla nueva desde la última manzana
    victoria: float = 50.0
    fin_por_ciclo: float = -5.0       # fin por la regla de los 30 s

    def a_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Recompensa:
    total: float
    componentes: dict = field(default_factory=dict)


def calcular_recompensa(cfg: ConfigRecompensa, *, d_anterior: int | None, d_actual: int | None,
                        comio: bool, colision: bool, victoria: bool, estado_repetido: bool,
                        casilla_nueva: bool, fin_por_ciclo: bool) -> Recompensa:
    c = {
        "manzana": cfg.manzana if comio else 0.0,
        "colision": cfg.colision if colision else 0.0,
        "distancia": 0.0,
        "supervivencia": 0.0 if colision else cfg.supervivencia,
        "repeticion": cfg.repeticion if estado_repetido else 0.0,
        "exploracion": cfg.exploracion if casilla_nueva else 0.0,
        "victoria": cfg.victoria if victoria else 0.0,
        "fin_por_ciclo": cfg.fin_por_ciclo if fin_por_ciclo else 0.0,
    }
    # Tras comer, la distancia se mide a una manzana nueva: Δd no es comparable.
    if not comio and not colision and d_anterior is not None and d_actual is not None:
        c["distancia"] = cfg.factor_distancia * (d_anterior - d_actual)
    return Recompensa(sum(c.values()), c)
