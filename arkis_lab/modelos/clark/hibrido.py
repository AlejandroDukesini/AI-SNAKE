"""CLARK: sistema híbrido de referencia con tres componentes independientes.

A · Machine Learning: Random Forest que estima P(acción buena | rasgos de la acción).
    Aprende de resultados objetivos de su propia experiencia (no morir en ≤ K pasos y
    comer o acercarse) y de las correcciones del usuario.
B · Simbólico: base de reglas propia (inducción por experiencia + correcciones RDR).
    Aporta vetos (prohibiciones) y preferencias.
C · Refuerzo: tabla Q propia, actualizada con la recompensa común durante sus episodios.

Integración (fija y documentada; es la referencia):
  1. B veta las acciones prohibidas. Si las veta todas, se ignoran los vetos (conflicto).
  1b. Si alguna regla del usuario o corrección suya prefiere acciones permitidas, la
     elección se restringe a ellas: el conocimiento explícito del director prevalece
     sobre las estimaciones aprendidas.
  2. Puntuación = w_A · P_A(a) + w_B · pref_B(a) + w_C · softmax_τ(Q(s,·))(a)
     · P_A = 0,5 si A no está entrenado; pref_B = confianza de la mejor preferencia de B
       sobre a (0 si ninguna); softmax uniforme si el estado no está en la tabla.
  3. Gana la acción permitida de mayor puntuación. Se registra qué componente estaba de
     acuerdo con la decisión final y si hubo conflicto entre sus elecciones.
CLARK reutiliza el CÓDIGO de los algoritmos de LERK y BORK, nunca sus instancias,
reglas, tablas ni datos.
"""
from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass

import numpy as np
from sklearn.ensemble import RandomForestClassifier

from ...nucleo.motor import ACCIONES, Accion
from ...nucleo.percepcion import Percepcion
from ..base import Agente, Decision
from ..bork.qlearning import TablaQ, estado
from ..bosque_rapido import BosqueRapido
from ..lerk.conocimiento import BaseConocimiento
from ..lerk.predicados import hechos

RASGOS = ("colision", "espacio", "cola_alcanzable", "acerca", "muro", "recto", "ocupacion",
          "manhattan")


def rasgos_accion(p: Percepcion, a: Accion) -> list[float]:
    c, m = p.cuerpo, p.manzana
    libres = max(1, c.casillas_libres)
    if m is None:
        acerca, dist = 0.0, 0.0
    else:
        d = abs(m.dx - a.dx) + abs(m.dy - a.dy)
        acerca = float(np.sign(m.manhattan - d))
        dist = m.manhattan / (p.ancho + p.alto)
    lado = max(1, (p.ancho if a.dx else p.alto) - 1)
    return [float(c.colision_por_accion[a] is not None), c.espacio_por_accion[a] / libres,
            float(c.cola_alcanzable_por_accion[a]), acerca, p.muros.distancia(a) / lado,
            float(a is c.direccion), c.longitud / (p.ancho * p.alto), dist]


@dataclass
class ConfigClark:
    peso_ml: float = 0.4
    peso_simbolico: float = 0.2
    peso_refuerzo: float = 0.4
    temperatura: float = 1.0           # τ del softmax sobre Q
    alfa: float = 0.1
    gamma: float = 0.9
    epsilon_inicial: float = 0.5
    epsilon_final: float = 0.02
    decaimiento: float = 0.99

    def __post_init__(self):
        pesos = (self.peso_ml, self.peso_simbolico, self.peso_refuerzo)
        if min(pesos) < 0 or sum(pesos) <= 0:
            raise ValueError("Los pesos deben ser ≥ 0 y no todos 0")
        if self.temperatura <= 0:
            raise ValueError("τ debe ser positiva")
        if not 0 < self.alfa <= 1 or not 0 <= self.gamma <= 1:
            raise ValueError("α ∈ (0,1], γ ∈ [0,1]")
        if not 0 <= self.epsilon_final <= self.epsilon_inicial <= 1:
            raise ValueError("Se requiere 0 ≤ ε_final ≤ ε_inicial ≤ 1")

    def epsilon(self, episodio: int) -> float:
        return max(self.epsilon_final, self.epsilon_inicial * self.decaimiento ** episodio)


class Componentes:
    """Los tres componentes de UNA instancia de CLARK."""

    def __init__(self, ml: RandomForestClassifier | None, simbolico: BaseConocimiento,
                 refuerzo: TablaQ):
        self.ml = ml
        self.simbolico = simbolico
        self.refuerzo = refuerzo

    @property
    def ml(self):
        return self._ml

    @ml.setter
    def ml(self, modelo):
        self._ml = modelo
        self.ml_rapido = BosqueRapido(modelo) if modelo is not None else None


class ClarkAgente(Agente):
    clave = "clark"
    nombre = "CLARK"
    metodologia = "Híbrido: ML + simbólico + refuerzo"

    def __init__(self, comp: Componentes, config: ConfigClark, epsilon: float = 0.0):
        self.comp = comp
        self.config = config
        self.epsilon = epsilon

    def opiniones(self, p: Percepcion) -> dict:
        disp = list(p.cuerpo.acciones_disponibles)
        cfg = self.config
        # A · ML
        if self.comp.ml is not None:
            X = np.array([rasgos_accion(p, a) for a in disp])
            proba = self.comp.ml_rapido.predict_proba(X)
            clases = list(self.comp.ml.classes_)
            pa = {a: float(proba[i][clases.index(1)]) if 1 in clases else 0.0
                  for i, a in enumerate(disp)}
        else:
            pa = {a: 0.5 for a in disp}
        # B · simbólico
        h = hechos(p)
        disparos = self.comp.simbolico.disparos(h, disp)
        vetos = sorted({d.accion for d in disparos if d.conclusion == "prohibir"},
                       key=lambda a: a.etiqueta)
        pb = {a: 0.0 for a in disp}
        del_usuario = set()
        for d in disparos:
            if d.conclusion == "preferir":
                r = d.excepcion or d.regla
                pb[d.accion] = max(pb[d.accion], r.confianza)
                if r.origen in ("usuario", "correccion"):
                    del_usuario.add(d.accion)
        # C · refuerzo
        s = estado(p)
        fila = self.comp.refuerzo.q.get(s)
        if fila is None:
            pc = {a: 1 / len(disp) for a in disp}
        else:
            idx = {a: i for i, a in enumerate(ACCIONES)}
            vals = [fila[idx[a]] / cfg.temperatura for a in disp]
            mx = max(vals)
            ex = [math.exp(v - mx) for v in vals]
            pc = {a: e / sum(ex) for a, e in zip(disp, ex)}
        return {"disponibles": disp, "ml": pa, "simbolico": pb, "refuerzo": pc, "vetos": vetos,
                "preferidas_usuario": del_usuario,
                "estado_q": s, "estado_conocido": fila is not None,
                "disparos": [(d.excepcion or d.regla).texto() + f" [{d.accion.etiqueta}]"
                             for d in disparos]}

    def decidir(self, p: Percepcion, rng=None) -> Decision:
        rng = rng or random.Random()
        cfg = self.config
        o = self.opiniones(p)
        disp = o["disponibles"]
        permitidas = [a for a in disp if a not in o["vetos"]]
        conflictos = []
        if not permitidas:
            permitidas = disp
            conflictos.append("el componente simbólico veta todas las acciones: se ignoran los vetos")
        usuario = [a for a in permitidas if a in o["preferidas_usuario"]]
        if usuario:
            permitidas = usuario
        total = cfg.peso_ml + cfg.peso_simbolico + cfg.peso_refuerzo
        punt = {a: (cfg.peso_ml * o["ml"][a] + cfg.peso_simbolico * o["simbolico"][a]
                    + cfg.peso_refuerzo * o["refuerzo"][a]) / total for a in disp}
        explorar = self.epsilon and rng.random() < self.epsilon
        if explorar:
            final = rng.choice(disp)
        else:
            mejor = max(punt[a] for a in permitidas)
            final = rng.choice([a for a in permitidas if punt[a] == mejor])

        def favorita(d):                  # favorita de cada componente entre TODAS las disponibles
            m = max(d[a] for a in disp)
            return {a for a in disp if d[a] == m}
        fav = {"ml": favorita(o["ml"]), "simbolico": favorita(o["simbolico"]),
               "refuerzo": favorita(o["refuerzo"])}
        acuerdo = {k: final in v for k, v in fav.items()}
        if len({frozenset(v) for v in fav.values()}) > 1:
            conflictos.append("los componentes prefieren acciones distintas")
        return Decision(final, punt, {
            "tipo": "hibrido",
            "modo": "exploracion" if explorar else "integracion",
            "pesos": {"ml": cfg.peso_ml, "simbolico": cfg.peso_simbolico, "refuerzo": cfg.peso_refuerzo},
            "componentes": {k: {a.etiqueta: round(v, 4) for a, v in o[k].items()}
                            for k in ("ml", "simbolico", "refuerzo")},
            "vetos": [a.etiqueta for a in o["vetos"]],
            "restriccion_usuario": [a.etiqueta for a in usuario],
            "reglas_disparadas": o["disparos"],
            "estado_q": o["estado_q"], "estado_conocido": o["estado_conocido"],
            "acuerdo": acuerdo, "conflictos": conflictos,
            "ml_entrenado": self.comp.ml is not None,
            "texto": (f"Final: {final.etiqueta}. De acuerdo: "
                      + (", ".join(k for k, v in acuerdo.items() if v) or "ninguno")),
        })


def config_dict(c: ConfigClark) -> dict:
    return asdict(c)
