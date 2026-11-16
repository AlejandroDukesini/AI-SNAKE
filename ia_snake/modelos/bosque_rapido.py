"""Evaluación directa de un RandomForestClassifier entrenado, para predecir pocas filas.

`predict_proba` de scikit-learn tarda ~50 ms por llamada por la sobrecarga de coordinar
los árboles, aunque la predicción en sí sea trivial. Esto recorre los mismos árboles con
los mismos umbrales y promedia las mismas probabilidades de hoja: el resultado es idéntico
(lo verifica tests/test_clark.py::test_bosque_rapido_identico_a_sklearn). El modelo de
scikit-learn sigue siendo el artefacto guardado; esto es solo una vista de lectura.
"""
from __future__ import annotations

import numpy as np


class BosqueRapido:
    def __init__(self, bosque):
        self.classes_ = bosque.classes_
        self._arboles = []
        n_clases = len(bosque.classes_)
        for est in bosque.estimators_:
            t = est.tree_
            valores = t.value[:, 0, :n_clases].astype(np.float64)
            sumas = valores.sum(axis=1, keepdims=True)
            sumas[sumas == 0] = 1.0
            self._arboles.append((t.children_left.tolist(), t.children_right.tolist(),
                                  t.feature.tolist(), t.threshold.tolist(),
                                  (valores / sumas).tolist()))
        self._n = len(self._arboles)
        self._k = n_clases

    def predict_proba(self, X) -> np.ndarray:
        # scikit-learn convierte X a float32 antes de comparar con los umbrales: redondeamos
        # igual una sola vez; después la comparación en float64 es exacta.
        filas = np.asarray(X, dtype=np.float32).astype(np.float64).tolist()
        acum = [[0.0] * self._k for _ in filas]
        for izq, der, rasgo, umbral, valor in self._arboles:
            for i, x in enumerate(filas):
                nodo = 0
                while izq[nodo] != -1:
                    nodo = izq[nodo] if x[rasgo[nodo]] <= umbral[nodo] else der[nodo]
                v = valor[nodo]
                a = acum[i]
                for k in range(self._k):
                    a[k] += v[k]
        return np.asarray(acum) / self._n
