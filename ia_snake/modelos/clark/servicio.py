"""Servicio de CLARK. Empieza SIN ENTRENAR (decisión D4). En su entrenamiento automático
cada componente aprende con su propio mecanismo:
  A · reentrena el Random Forest con los resultados objetivos de la experiencia,
  B · induce reglas de experiencia (prohibiciones y preferencias),
  C · actualiza la tabla Q paso a paso con la recompensa común.
"""
from __future__ import annotations

import json
import random
import uuid
from dataclasses import asdict

import numpy as np

from ...evaluacion.protocolo import semillas
from ...nucleo.entorno import Entorno
from ...nucleo.motor import Accion
from ...persistencia import seguro
from ...persistencia.almacen import a_json
from .. import base as estados
from ..bork.qlearning import TablaQ, estado
from ..lerk import aprendizaje as simbolico
from ..lerk.conocimiento import BaseConocimiento
from ..lerk.predicados import hechos
from ..servicio import ServicioModelo
from ..situacion import accion_por_nombre, percepcion_de, situacion_de
from .hibrido import ClarkAgente, Componentes, ConfigClark, rasgos_accion

MAX_EXPERIENCIA = 40_000


class ServicioClark(ServicioModelo):
    clave = "clark"
    nombre = "CLARK"
    metodologia = "Híbrido: ML + simbólico + refuerzo"
    descripcion = ("Modelo de referencia. Tres componentes propios —Random Forest, reglas y "
                   "tabla Q— integrados con vetos y pesos documentados.")

    def cargar(self) -> None:
        self.experiencia: list = self.almacen.leer_datos("experiencia.json", [])
        self.bloqueado = None
        cargado = self.almacen.cargar_version()
        if cargado is None:
            self.version, self.episodios_totales = None, 0
            self.config = ConfigClark(**(self.almacen.leer_datos("config.json") or {}))
            self.comp = Componentes(None, BaseConocimiento(), TablaQ())
            return
        self.version, archivos = cargado
        meta = self.almacen.meta(self.version)
        cfg = json.loads(archivos["config.json"])
        self.config = ConfigClark(**cfg["config"])
        self.episodios_totales = cfg["episodios_totales"]
        ml = None
        if "ml.skops" in archivos:
            try:
                ml = seguro.cargar(archivos["ml.skops"], meta.get("importada", False),
                                   meta.get("confiado", False))
            except seguro.ErrorSeguridad as e:
                self.bloqueado = str(e)
        q = json.loads(archivos["qtabla.json"])
        self.comp = Componentes(ml, BaseConocimiento.desde_lista(json.loads(archivos["base.json"])),
                                TablaQ(q["q"], q["visitas"]))

    def agente(self, epsilon: float = 0.0) -> ClarkAgente:
        return ClarkAgente(self.comp, self.config, epsilon)

    def configurar(self, cambios: dict) -> dict:
        with self.lock:
            self.config = ConfigClark(**{**asdict(self.config), **cambios})
            self.almacen.escribir_datos("config.json", asdict(self.config))
            return asdict(self.config)

    def _guardar(self, motivo: str, metricas: dict | None = None) -> str:
        archivos = {
            "base.json": a_json(self.comp.simbolico.a_lista()),
            "qtabla.json": a_json(self.comp.refuerzo.a_dict()),
            "config.json": a_json({"config": asdict(self.config),
                                   "episodios_totales": self.episodios_totales}),
        }
        if self.comp.ml is not None:
            archivos["ml.skops"] = seguro.volcar(self.comp.ml)
        self.version = self.almacen.guardar_version(
            archivos, motivo, estados.ENTRENADO,
            {"reglas": len(self.comp.simbolico.reglas), "estados_q": len(self.comp.refuerzo.q),
             "ml_entrenado": self.comp.ml is not None, **(metricas or {})})
        return self.version

    # --- Aprendizaje de cada componente --------------------------------------
    def _entrenar_ml(self, semilla: int) -> dict:
        datos = [e for e in self.experiencia if "rasgos" in e]
        y = np.array([int(e["progreso"]) for e in datos])
        if len(datos) < 20 or len(set(y)) < 2:
            return {"entrenado": False, "motivo": "faltan datos de ambas clases"}
        from sklearn.ensemble import RandomForestClassifier
        X = np.array([e["rasgos"] for e in datos])
        self.comp.ml = RandomForestClassifier(n_estimators=60, min_samples_leaf=3,
                                              class_weight="balanced", random_state=semilla,
                                              n_jobs=1).fit(X, y)
        return {"entrenado": True, "instancias": len(datos), "positivas": int(y.sum())}

    def entrenamiento_automatico(self, dificultad: str, episodios: int = 200, semilla: int = 0,
                                 bloque: int = 25, progreso=None, cancelar=None,
                                 observador=None) -> dict:
        ent = Entorno(dificultad)
        rng = random.Random(semilla)
        id_ = f"auto-{uuid.uuid4().hex[:8]}"
        v0 = self.version
        cfg = self.config
        lista = [s + semilla * 100_000 for s in semillas("entrenamiento", episodios)]
        hechos_ep, info = 0, {}
        acuerdos = {"ml": 0, "simbolico": 0, "refuerzo": 0}
        decisiones = vetos = 0
        for i, s in enumerate(lista):
            if cancelar and cancelar():
                break
            eps = cfg.epsilon(self.episodios_totales)
            ag = self.agente(eps)
            perc = ent.reiniciar(s)
            pasos = []
            choques_comp = {"ml": 0, "simbolico": 0, "refuerzo": 0}
            if observador is not None:
                observador.nuevo_episodio(self.episodios_totales + 1, len(lista), s, {
                    "epsilon": round(eps, 4), "dificultad": dificultad,
                    "pesos": {"ml": cfg.peso_ml, "simbolico": cfg.peso_simbolico,
                              "refuerzo": cfg.peso_refuerzo}})
            with self.lock:
                while not ent.terminado:
                    d = ag.decidir(perc, rng)
                    a = d.accion
                    if observador is not None:
                        # Rendimiento por componente con datos reales: ¿la acción favorita de
                        # cada componente habría chocado de inmediato según el motor?
                        fav, choque = {}, {}
                        for k, v in d.explicacion["componentes"].items():
                            f = max(v, key=v.get)
                            fav[k] = f
                            choque[k] = perc.cuerpo.colision_por_accion[Accion[f.upper()]] is not None
                            choques_comp[k] += choque[k]
                        cabeza, manzana = ent.partida.cabeza, ent.partida.manzana
                    if d.explicacion["modo"] == "integracion":
                        decisiones += 1
                        vetos += bool(d.explicacion["vetos"])
                        for k, v in d.explicacion["acuerdo"].items():
                            acuerdos[k] += v
                    sq = estado(perc)
                    h = hechos(perc)[a]
                    rs = rasgos_accion(perc, a)
                    t = ent.paso(a)
                    # C · Q-Learning con la recompensa común
                    if t.terminada and t.causa_fin != "limite_tecnico":
                        obj = t.recompensa.total
                    else:
                        obj = t.recompensa.total + cfg.gamma * self.comp.refuerzo.max_q(
                            estado(t.percepcion), t.percepcion.cuerpo.acciones_disponibles)
                    self.comp.refuerzo.actualizar(sq, a, obj, cfg.alfa)
                    pasos.append({"verdaderos": sorted(h), "accion": a.etiqueta, "comio": t.comio,
                                  "rasgos": [round(x, 5) for x in rs]})
                    if observador is not None:
                        observador.paso(cabeza, manzana, t, d.a_dict(), ent, {
                            "favorita_por_componente": fav, "chocaria_por_componente": choque,
                            "estados_q": len(self.comp.refuerzo.q),
                            "reglas": len(self.comp.simbolico.reglas),
                            "ml_entrenado": self.comp.ml is not None})
                    perc = t.percepcion
            r = ent.resumen()
            self.episodios_totales += 1
            hechos_ep += 1
            self.experiencia += simbolico.etiquetar_episodio(pasos, r.causa_fin)
            self.experiencia = self.experiencia[-MAX_EXPERIENCIA:]
            self.almacen.registrar_episodio(r, self.version, "entrenamiento", id_, {"epsilon": eps})
            if observador is not None:
                observador.fin_episodio(r, {"epsilon": round(eps, 4),
                                            "choques_evitables_por_componente": dict(choques_comp)})
            if (i + 1) % bloque == 0 or i + 1 == len(lista):
                if observador is not None:
                    observador.fase = "aprendiendo"
                with self.lock:
                    info = {"ml": self._entrenar_ml(semilla),
                            "simbolico": simbolico.aprender_de_experiencia(self.comp.simbolico,
                                                                            self.experiencia)}
                    self.almacen.escribir_datos("experiencia.json", self.experiencia)
                    self._guardar(f"automático: {self.episodios_totales} episodios ({id_})", info)
                if observador is not None:
                    observador.contexto.setdefault("aprendizajes", []).append({
                        "tras_episodio": i + 1, "version": self.version, **info,
                        "reglas_total": len(self.comp.simbolico.reglas),
                        "estados_q": len(self.comp.refuerzo.q)})
            if progreso:
                progreso(i + 1, len(lista), r)
        res = {"sesion": id_, "episodios": hechos_ep, "componentes": info,
               "acuerdo_con_final": {k: v / max(1, decisiones) for k, v in acuerdos.items()},
               "decisiones_con_veto": vetos / max(1, decisiones),
               "estados_q": len(self.comp.refuerzo.q)}
        self.almacen.registrar_sesion(id_, "entrenamiento_automatico", v0, self.version,
                                      {"dificultad": dificultad, "episodios": episodios,
                                       "semilla": semilla, "config": asdict(cfg)}, res)
        return res

    def corregir(self, situacion: dict, correcta: str) -> dict:
        """Entrenamiento manual: la corrección llega a A (instancias etiquetadas por el
        usuario) y a B (excepción RDR). C solo aprende de recompensas: no se toca."""
        with self.lock:
            perc = percepcion_de(situacion)
            ok = accion_por_nombre(correcta)
            elegida = self.agente().decidir(perc, random.Random(0)).accion
            h = hechos(perc)
            self.experiencia.append({"verdaderos": sorted(h[ok]), "accion": ok.etiqueta,
                                     "comio": False, "rasgos": rasgos_accion(perc, ok),
                                     "fracaso": False, "progreso": True, "origen": "usuario"})
            if elegida is not ok:
                self.experiencia.append({"verdaderos": sorted(h[elegida]), "accion": elegida.etiqueta,
                                         "comio": False, "rasgos": rasgos_accion(perc, elegida),
                                         "fracaso": False, "progreso": False, "origen": "usuario"})
            cambios = simbolico.corregir(self.comp.simbolico, situacion, correcta)
            ml = self._entrenar_ml(0)
            self.almacen.escribir_datos("experiencia.json", self.experiencia)
            self._guardar(f"corrección del usuario: '{elegida.etiqueta}' → '{correcta}'")
            return {"simbolico": cambios, "ml": ml, "elegida_antes": elegida.etiqueta,
                    "elegida_despues": self.agente().decidir(perc, random.Random(0)).accion.etiqueta}

    def detalle_entrenamiento(self) -> dict:
        return {"config": asdict(self.config), "episodios_totales": self.episodios_totales,
                "reglas": self.comp.simbolico.a_lista(), "estados_q": len(self.comp.refuerzo.q),
                "ml_entrenado": self.comp.ml is not None, "experiencia": len(self.experiencia),
                "epsilon_actual": self.config.epsilon(self.episodios_totales),
                "bloqueado": self.bloqueado}
