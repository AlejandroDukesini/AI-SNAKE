"""Servicio de BORK: configuración, entrenamiento por episodios, curva y versiones de la tabla Q."""
from __future__ import annotations

import json
import random
import uuid
from dataclasses import asdict

from ...evaluacion.protocolo import semillas
from ...nucleo.entorno import ConfigEntorno, Entorno
from ...persistencia.almacen import a_json
from .. import base as estados
from ..servicio import ServicioModelo
from .qlearning import REPRESENTACIONES, BorkAgente, ConfigBork, TablaQ, entrenar_episodio

MAX_CURVA = 20_000


class ServicioBork(ServicioModelo):
    clave = "bork"
    nombre = "BORK"
    metodologia = "Aprendizaje por refuerzo"
    descripcion = ("Q-Learning tabular sobre un estado compacto. Aprende solo de recompensas y "
                   "penalizaciones; tú configuras α, γ, ε y las recompensas.")

    def cargar(self) -> None:
        self.curva: list = self.almacen.leer_datos("curva.json", [])
        cargado = self.almacen.cargar_version()
        if cargado is None:
            self.version, self.tabla, self.episodios_totales = None, TablaQ(), 0
            self.config = ConfigBork(**(self.almacen.leer_datos("config.json") or {}))
            return
        self.version, archivos = cargado
        d = json.loads(archivos["qtabla.json"])
        self.tabla = TablaQ(d["q"], d["visitas"])
        meta = json.loads(archivos["config.json"])
        self.config = ConfigBork(**meta["config"])
        self.episodios_totales = meta["episodios_totales"]

    def agente(self) -> BorkAgente:
        return BorkAgente(self.tabla, self.config.representacion)

    def configurar(self, cambios: dict) -> dict:
        """Cambia la configuración. Cambiar la representación del estado exige empezar una
        tabla nueva (las claves de estado no son compatibles): se rechaza si ya hay tabla."""
        with self.lock:
            datos = asdict(self.config)
            if "recompensa" in cambios:
                datos["recompensa"] = {**datos["recompensa"], **cambios.pop("recompensa")}
            datos.update(cambios)
            nueva = ConfigBork(**datos)
            if nueva.representacion != self.config.representacion and self.tabla.q:
                raise ValueError("La tabla actual usa otra representación; reiníciala para cambiarla")
            self.config = nueva
            self.almacen.escribir_datos("config.json", asdict(nueva))
            return asdict(nueva)

    def reiniciar_tabla(self) -> None:
        """Empieza de cero SIN borrar nada: las versiones anteriores siguen disponibles."""
        with self.lock:
            self.tabla, self.episodios_totales = TablaQ(), 0
            self._guardar("tabla reiniciada (versiones anteriores conservadas)", estados.SIN_ENTRENAR)

    def _guardar(self, motivo: str, estado=estados.ENTRENADO, metricas=None) -> str:
        self.version = self.almacen.guardar_version(
            {"qtabla.json": a_json(self.tabla.a_dict()),
             "config.json": a_json({"config": asdict(self.config),
                                    "episodios_totales": self.episodios_totales})},
            motivo, estado, {"estados": len(self.tabla.q), "episodios_totales": self.episodios_totales,
                             **(metricas or {})})
        return self.version

    def entrenar(self, dificultad: str, episodios: int = 500, semilla: int = 0,
                 velocidad_movimiento: float | None = None, guardar_cada: int = 0,
                 progreso=None, cancelar=None, observador=None) -> dict:
        cfg = self.config
        ent = Entorno(dificultad, ConfigEntorno(
            velocidad_movimiento=velocidad_movimiento or ConfigEntorno().velocidad_movimiento,
            recompensa=cfg.config_recompensa()))
        rng = random.Random(semilla)
        id_ = f"q-{uuid.uuid4().hex[:8]}"
        v0 = self.version
        lista = [s + semilla * 100_000 for s in semillas("entrenamiento", episodios)]
        hechos = 0
        for i, s in enumerate(lista):
            if cancelar and cancelar():
                break
            eps = cfg.epsilon(self.episodios_totales)
            if observador is not None:
                observador.nuevo_episodio(self.episodios_totales + 1, len(lista), s,
                                          {"epsilon": round(eps, 4), "dificultad": dificultad})
            with self.lock:
                r, extra = entrenar_episodio(ent, self.tabla, cfg, eps, s, rng, observador)
            self.episodios_totales += 1
            hechos += 1
            punto = {"episodio": self.episodios_totales, "dificultad": dificultad,
                     "manzanas": r.manzanas, "pasos": r.pasos, "retorno": round(r.retorno, 3),
                     "componentes": {k: round(v, 3) for k, v in r.retorno_por_componente.items()},
                     "causa_fin": r.causa_fin, "nivel": r.nivel, "epsilon": round(eps, 4),
                     "estados": len(self.tabla.q), **extra}
            self.curva.append(punto)
            if observador is not None:
                observador.fin_episodio(r, {"epsilon": round(eps, 4), "estados": len(self.tabla.q),
                                            "td_medio": round(extra["td_medio"], 4)})
            self.almacen.registrar_episodio(r, self.version, "entrenamiento", id_,
                                            {"epsilon": eps, **extra})
            if guardar_cada and hechos % guardar_cada == 0:
                self._guardar(f"autoguardado: episodio {self.episodios_totales}")
            if progreso:
                progreso(i + 1, len(lista), r)
        self.curva = self.curva[-MAX_CURVA:]
        self.almacen.escribir_datos("curva.json", self.curva)
        v = self._guardar(f"Q-Learning: {hechos} episodios en {dificultad} ({id_})",
                          metricas={"aliasing": self.tabla.aliasing()})
        res = {"sesion": id_, "episodios": hechos, "estados": len(self.tabla.q),
               "cobertura_estados": len(self.tabla.q) / REPRESENTACIONES[cfg.representacion],
               "aliasing": self.tabla.aliasing(),
               "epsilon_final": cfg.epsilon(self.episodios_totales),
               "manzanas_media_ultimos": _media([p["manzanas"] for p in self.curva[-100:]])}
        self.almacen.registrar_sesion(id_, "q_learning", v0, v,
                                      {"dificultad": dificultad, "episodios": episodios,
                                       "semilla": semilla, "config": asdict(cfg)}, res)
        return res

    def inspeccionar(self, limite: int = 40) -> list[dict]:
        filas = sorted(self.tabla.visitas.items(), key=lambda kv: -sum(kv[1]))[:limite]
        return [{"estado": s, "visitas": v, "q": [round(x, 3) for x in self.tabla.q[s]]}
                for s, v in filas]

    def detalle_entrenamiento(self) -> dict:
        return {"config": asdict(self.config), "episodios_totales": self.episodios_totales,
                "estados": len(self.tabla.q),
                "estados_posibles": REPRESENTACIONES[self.config.representacion],
                "epsilon_actual": self.config.epsilon(self.episodios_totales),
                "curva": self.curva[-2000:]}


def _media(v):
    return sum(v) / len(v) if v else None
