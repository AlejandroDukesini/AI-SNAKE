"""Observación del entrenamiento REAL, paso a paso.

Los bucles de entrenamiento y evaluación llaman a `Observador.paso(...)` con la decisión
efectiva del modelo y la transición que devolvió el motor. Nada aquí decide ni calcula
resultados: solo copia lo que ya ocurrió.

- Último fotograma: se sobrescribe (no se encola); la interfaz lo lee al ritmo que quiera,
  así visualizar más lento o más rápido no frena ni altera el entrenamiento.
- Ritmo (pasos por segundo, 0 = máximo) y pausa: solo AÑADEN ESPERAS entre pasos. No tocan
  generadores aleatorios ni cálculos, así que el resultado del entrenamiento es idéntico
  (lo verifica tests/test_observacion.py).
"""
from __future__ import annotations

import threading
import time

from ..nucleo import evolucion

MAX_EPISODIOS = 2000


def _manhattan(a, b):
    return None if b is None else abs(a[0] - b[0]) + abs(a[1] - b[1])


class Observador:
    def __init__(self, pasos_por_segundo: float = 0.0, cancelar=None):
        self._lock = threading.Lock()
        self._reanudar = threading.Event()
        self._reanudar.set()
        self.pasos_por_segundo = float(pasos_por_segundo or 0)
        self._cancelar = cancelar or (lambda: False)
        self._ultimo = 0.0
        self.fotograma: dict | None = None
        self.episodios: list[dict] = []
        self.secuencia = 0
        self.fase = "preparando"
        self.contexto: dict = {}           # información estática de la sesión (p. ej. datos usados)
        self._acum = self._acumulado_vacio()

    # --- Control ------------------------------------------------------------
    @property
    def pausado(self) -> bool:
        return not self._reanudar.is_set()

    def pausar(self) -> None:
        self._reanudar.clear()

    def reanudar(self) -> None:
        self._reanudar.set()

    def fijar_ritmo(self, pasos_por_segundo: float) -> None:
        self.pasos_por_segundo = max(0.0, float(pasos_por_segundo or 0))

    def _esperar(self) -> None:
        while not self._reanudar.wait(0.1):
            if self._cancelar():
                return
        if self.pasos_por_segundo > 0:
            espera = self._ultimo + 1.0 / self.pasos_por_segundo - time.monotonic()
            if espera > 0:
                time.sleep(espera)
        self._ultimo = time.monotonic()

    # --- Registro -----------------------------------------------------------
    @staticmethod
    def _acumulado_vacio():
        return {"acerca": 0, "aleja": 0, "come": 0, "pasos": 0, "retorno": 0.0,
                "componentes": {}, "acuerdo": {}, "decisiones_integradas": 0, "exploracion": 0}

    def nuevo_episodio(self, episodio: int, total: int, semilla: int, extra: dict | None = None) -> None:
        with self._lock:
            self._acum = self._acumulado_vacio()
            self.contexto_episodio = {"episodio": episodio, "total": total, "semilla": semilla,
                                      **(extra or {})}

    def paso(self, cabeza_antes, manzana_antes, transicion, decision: dict, entorno,
             extra: dict | None = None) -> None:
        """`decision`: lo que el modelo usó realmente para elegir (dict serializable)."""
        p = entorno.partida
        d_antes = _manhattan(cabeza_antes, manzana_antes)
        d_despues = None if transicion.comio else _manhattan(p.cabeza, manzana_antes)
        if transicion.comio:
            mov = "come"
        elif transicion.causa_fin in ("limite", "cuerpo"):
            mov = "colision"
        elif d_antes is not None and d_despues is not None:
            mov = "acerca" if d_despues < d_antes else "aleja" if d_despues > d_antes else "igual"
        else:
            mov = "igual"
        r = transicion.recompensa
        with self._lock:
            a = self._acum
            a["pasos"] += 1
            if mov in ("acerca", "aleja", "come"):
                a[mov] += 1
            a["retorno"] += r.total
            for k, v in r.componentes.items():
                a["componentes"][k] = a["componentes"].get(k, 0.0) + v
            exp = decision.get("explicacion", {}) if isinstance(decision, dict) else {}
            if exp.get("modo") == "exploracion":
                a["exploracion"] += 1
            if exp.get("tipo") == "hibrido" and exp.get("modo") == "integracion":
                a["decisiones_integradas"] += 1
                for k, v in exp.get("acuerdo", {}).items():
                    a["acuerdo"][k] = a["acuerdo"].get(k, 0) + int(v)
            self.secuencia += 1
            self.fase = "jugando"
            self.fotograma = {
                "secuencia": self.secuencia,
                **getattr(self, "contexto_episodio", {}),
                "partida": p.instantanea(),
                "decision": decision,
                "transicion": {
                    "accion": transicion.accion.etiqueta, "movimiento": mov,
                    "distancia_antes": d_antes, "distancia_despues": d_despues,
                    "comio": transicion.comio, "causa_fin": transicion.causa_fin,
                    "terminada": transicion.terminada,
                    "recompensa": round(r.total, 4),
                    "componentes": {k: round(v, 4) for k, v in r.componentes.items() if v},
                    "en_ciclo": bool(transicion.ciclo and transicion.ciclo.en_ciclo),
                    "pasos_en_ciclo": transicion.pasos_en_ciclo,
                },
                "evolucion": {"nivel": transicion.nivel, "nivel_max": entorno.nivel_max,
                              "ocupacion": round(evolucion.ocupacion(p.longitud, p.casillas), 2),
                              "umbrales": list(evolucion.tabla_umbrales(p.casillas))},
                "episodio_actual": {k: (round(v, 3) if isinstance(v, float) else v)
                                    for k, v in a.items() if k != "componentes"}
                | {"componentes": {k: round(v, 3) for k, v in a["componentes"].items()}},
                "extra": extra or {},
            }
        self._esperar()

    def fin_episodio(self, resumen, extra: dict | None = None) -> None:
        with self._lock:
            a = self._acum
            fila = {"episodio": getattr(self, "contexto_episodio", {}).get("episodio"),
                    "manzanas": resumen.manzanas, "pasos": resumen.pasos,
                    "longitud": resumen.longitud_max, "ocupacion": round(resumen.ocupacion_max, 2),
                    "nivel": resumen.nivel, "causa_fin": resumen.causa_fin,
                    "retorno": round(resumen.retorno, 3), "acerca": a["acerca"], "aleja": a["aleja"],
                    "exploracion": a["exploracion"], **(extra or {})}
            if a["decisiones_integradas"]:
                fila["acuerdo"] = {k: round(v / a["decisiones_integradas"], 3)
                                   for k, v in a["acuerdo"].items()}
            self.episodios.append(fila)
            self.episodios = self.episodios[-MAX_EPISODIOS:]

    def estado(self) -> dict:
        with self._lock:
            return {"fase": self.fase, "pausado": self.pausado,
                    "pasos_por_segundo": self.pasos_por_segundo, "contexto": self.contexto,
                    "fotograma": self.fotograma, "episodios": self.episodios[-300:],
                    "total_episodios": len(self.episodios)}
