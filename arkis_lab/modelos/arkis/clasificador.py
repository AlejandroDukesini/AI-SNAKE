"""ARKIS: Random Forest entrenado con ejemplos etiquetados por el usuario.

Validación sin fugas: GroupKFold por episodio (pasos consecutivos son casi idénticos).
El aumento por simetrías se aplica SOLO dentro de la parte de entrenamiento de cada pliegue.
Métricas fuera de pliegue: accuracy, precision, recall, F1 (macro y por clase), matriz de
confusión y lista de errores.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import GroupKFold
from sklearn.tree import DecisionTreeClassifier, export_text

from ...nucleo.motor import ACCIONES
from ..base import Agente, Decision
from ..bosque_rapido import BosqueRapido
from ..situacion import SIMETRIAS, percepcion_de, transformar_accion
from .caracteristicas import NOMBRES, caracteristicas, transformar_caracteristicas

CLASES = [a.etiqueta for a in ACCIONES]


class ErrorEntrenamiento(ValueError):
    pass


def _accion(nombre):
    return ACCIONES[CLASES.index(nombre)]


def _filas(ejemplos: list[dict], aumentar: bool) -> list[tuple[list, list]]:
    """Por ejemplo: (filas X, etiquetas y). La primera fila es siempre la original; con
    aumento le siguen las 7 simetrías, aplicadas al vector y a la etiqueta."""
    out = []
    for e in ejemplos:
        x = caracteristicas(percepcion_de(e["situacion"]))
        if aumentar:
            sims = list(SIMETRIAS)
            out.append(([transformar_caracteristicas(x, s) for s in sims],
                        [transformar_accion(_accion(e["etiqueta"]), s).etiqueta for s in sims]))
        else:
            out.append(([x], [e["etiqueta"]]))
    return out


def _apilar(filas, indices) -> tuple[np.ndarray, np.ndarray]:
    X = [x for i in indices for x in filas[i][0]]
    y = [et for i in indices for et in filas[i][1]]
    return np.array(X), np.array(y)


def _crear_bosque(semilla: int, n_arboles: int) -> RandomForestClassifier:
    return RandomForestClassifier(n_estimators=n_arboles, class_weight="balanced",
                                  random_state=semilla, n_jobs=1)


def predecir_enmascarado(modelo, X: np.ndarray, disponibles: list[list[str]]) -> list[str]:
    proba = modelo.predict_proba(X)
    clases = list(modelo.classes_)
    out = []
    for fila, disp in zip(proba, disponibles):
        validas = [(fila[clases.index(c)] if c in clases else 0.0, c) for c in disp]
        out.append(max(validas)[1])
    return out


@dataclass
class ResultadoEntrenamiento:
    modelo: RandomForestClassifier
    metricas: dict
    arbol_explicativo: str


def entrenar(ejemplos: list[dict], semilla: int = 0, aumentar: bool = True,
             n_arboles: int = 100) -> ResultadoEntrenamiento:
    if len(ejemplos) < 2:
        raise ErrorEntrenamiento("Se necesitan al menos 2 ejemplos aprobados")
    if len({e["etiqueta"] for e in ejemplos}) < 2:
        raise ErrorEntrenamiento("Se necesitan ejemplos de al menos 2 acciones distintas")

    grupos = np.array([e["episodio"] for e in ejemplos])
    n_grupos = len(set(grupos))
    metricas: dict = {"ejemplos": len(ejemplos), "episodios": n_grupos, "aumento": aumentar,
                      "semilla": semilla, "n_arboles": n_arboles}

    filas = _filas(ejemplos, aumentar)
    if n_grupos >= 2:
        k = min(5, n_grupos)
        reales, predichas, ids = [], [], []
        for tr, te in GroupKFold(n_splits=k).split(np.zeros(len(ejemplos)), groups=grupos):
            X, y = _apilar(filas, tr)
            if len(set(y)) < 2:
                continue
            m = _crear_bosque(semilla, n_arboles).fit(X, y)
            prueba = [ejemplos[i] for i in te]
            Xt = np.array([filas[i][0][0] for i in te])
            disp = [[a.etiqueta for a in percepcion_de(e["situacion"]).cuerpo.acciones_disponibles]
                    for e in prueba]
            reales += [e["etiqueta"] for e in prueba]
            predichas += predecir_enmascarado(m, Xt, disp)
            ids += [e["id"] for e in prueba]
        if reales:
            p, r, f, s = precision_recall_fscore_support(reales, predichas, labels=CLASES,
                                                         zero_division=0)
            pm, rm, fm, _ = precision_recall_fscore_support(reales, predichas, labels=CLASES,
                                                            average="macro", zero_division=0)
            metricas["validacion"] = {
                "metodo": f"GroupKFold por episodio, k={k}",
                "n": len(reales),
                "accuracy": accuracy_score(reales, predichas),
                "precision_macro": pm, "recall_macro": rm, "f1_macro": fm,
                "por_clase": {c: {"precision": p[i], "recall": r[i], "f1": f[i], "soporte": int(s[i])}
                              for i, c in enumerate(CLASES)},
                "matriz_confusion": {"clases": CLASES,
                                     "valores": confusion_matrix(reales, predichas, labels=CLASES).tolist()},
                "errores": [{"id": i, "real": a, "predicha": b}
                            for i, a, b in zip(ids, reales, predichas) if a != b][:200],
            }
    if "validacion" not in metricas:
        metricas["validacion"] = None
        metricas["aviso"] = ("Sin validación: hacen falta ejemplos de al menos 2 episodios "
                             "distintos para evaluar sin fuga de datos.")

    X, y = _apilar(filas, range(len(ejemplos)))
    modelo = _crear_bosque(semilla, n_arboles).fit(X, y)
    metricas["filas_entrenamiento"] = int(len(y))
    metricas["importancias"] = sorted(
        ({"rasgo": n, "importancia": float(v)} for n, v in zip(NOMBRES, modelo.feature_importances_)),
        key=lambda d: -d["importancia"])[:12]
    arbol = DecisionTreeClassifier(max_depth=4, random_state=semilla, class_weight="balanced").fit(X, y)
    return ResultadoEntrenamiento(modelo, metricas, export_text(arbol, feature_names=NOMBRES))


class ArkisAgente(Agente):
    clave = "arkis"
    nombre = "ARKIS"
    metodologia = "Machine Learning supervisado (Random Forest)"

    def __init__(self, modelo: RandomForestClassifier | None = None):
        self.modelo = modelo
        self._rapido = BosqueRapido(modelo) if modelo is not None else None

    def decidir(self, percepcion, rng=None) -> Decision:
        disp = percepcion.cuerpo.acciones_disponibles
        if self.modelo is None:
            a = (rng or random).choice(disp)
            return Decision(a, {}, {"tipo": "sin_entrenar",
                                    "texto": "ARKIS no tiene modelo entrenado: acción al azar."})
        x = caracteristicas(percepcion).reshape(1, -1)
        fila = self._rapido.predict_proba(x)[0]
        clases = list(self.modelo.classes_)
        punt = {a: float(fila[clases.index(a.etiqueta)]) if a.etiqueta in clases else 0.0
                for a in ACCIONES}
        a = max(disp, key=lambda b: punt[b])
        return Decision(a, punt, {
            "tipo": "probabilidades",
            "texto": f"Probabilidad de que '{a.etiqueta}' sea la acción que elegirías: {punt[a]:.0%}",
            "confianza": punt[a],
            "enmascaradas": [b.etiqueta for b in ACCIONES if b not in disp],
        })
