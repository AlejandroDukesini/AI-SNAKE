"""Servicio de ARKIS: conjunto de ejemplos, entrenamiento, versiones y recopilación."""
from __future__ import annotations

import json
import random
import uuid

from ...evaluacion.protocolo import semillas
from ...nucleo.entorno import Entorno
from ...persistencia.almacen import a_json
from ...persistencia import seguro
from .. import base
from ..servicio import ServicioModelo
from ..situacion import situacion_de
from .clasificador import ArkisAgente, entrenar
from ..ejemplos import Dataset


class ServicioArkis(ServicioModelo):
    clave = "arkis"
    nombre = "ARKIS"
    metodologia = "Machine Learning supervisado"
    descripcion = ("Random Forest que aprende de las acciones que tú etiquetas. "
                   "Sin redes neuronales ni refuerzo.")

    def cargar(self) -> None:
        self.dataset = Dataset(self.almacen.leer_datos("dataset.json"))
        self._agente = ArkisAgente(None)
        self.metricas: dict | None = None
        self.arbol: str | None = None
        self.bloqueado: str | None = None
        cargado = self.almacen.cargar_version()
        if cargado is None:
            self.version = None
            return
        self.version, archivos = cargado
        meta = self.almacen.meta(self.version)
        try:
            modelo = seguro.cargar(archivos["modelo.skops"], importado=meta.get("importada", False),
                                   confiar_importados=meta.get("confiado", False))
            self._agente = ArkisAgente(modelo)
        except seguro.ErrorSeguridad as e:
            self.bloqueado = str(e)
        self.metricas = json.loads(archivos["metricas.json"])
        self.arbol = archivos["arbol.txt"].decode("utf-8")

    def agente(self) -> ArkisAgente:
        return self._agente

    def guardar_dataset(self) -> None:
        self.almacen.escribir_datos("dataset.json", self.dataset.a_dict())

    # --- Entrenamiento manual: el usuario aporta ejemplos; aquí se ajusta el bosque ---
    def entrenar(self, semilla: int = 0, aumentar: bool = True, n_arboles: int = 100) -> dict:
        with self.lock:
            aprobados = self.dataset.aprobados()
            res = entrenar(aprobados, semilla, aumentar, n_arboles)
            res.metricas["revision_dataset"] = self.dataset.revision
            v = self.almacen.guardar_version(
                {"modelo.skops": seguro.volcar(res.modelo),
                 "metricas.json": a_json(res.metricas),
                 "arbol.txt": res.arbol_explicativo.encode("utf-8"),
                 "dataset.json": a_json(aprobados)},
                f"entrenado con {len(aprobados)} ejemplos aprobados", base.ENTRENADO,
                {k: res.metricas[k] for k in ("ejemplos", "episodios")})
            self.almacen.registrar_sesion(f"ent-{v}", "entrenamiento", self.version, v,
                                          {"semilla": semilla, "aumentar": aumentar,
                                           "n_arboles": n_arboles}, res.metricas)
            self.cargar()
            return res.metricas

    def entrenamiento_automatico(self, dificultad: str, episodios: int = 30, semilla: int = 0,
                                 aumentar: bool = True, progreso=None, cancelar=None,
                                 observador=None) -> dict:
        """Modo automático de ARKIS: reentrena con los conjuntos YA APROBADOS y se evalúa
        jugando. Nunca genera etiquetas por su cuenta."""
        if observador is not None:
            observador.fase = "entrenando"
            observador.contexto["datos"] = self.dataset.estadisticas()
        metricas = self.entrenar(semilla, aumentar)
        if observador is not None:
            observador.contexto["metricas"] = _resumen_metricas(metricas)
            observador.contexto["historial_metricas"] = self.historial_metricas()
            observador.fase = "evaluando"
        evaluacion = self.evaluar(dificultad, episodios, progreso=progreso, cancelar=cancelar,
                                  observador=observador)
        return {"metricas": metricas, "evaluacion": evaluacion}

    def recopilar(self, dificultad: str, episodios: int = 5, umbral: float = 0.6,
                  maximo: int = 50, semilla: int = 0) -> int:
        """Aprendizaje activo: ARKIS juega y guarda SIN ETIQUETA las situaciones en las que
        duda (confianza < umbral). Tú decides después la etiqueta."""
        ent = Entorno(dificultad)
        rng = random.Random(semilla)
        ag = self.agente()
        n = 0
        for s in semillas("entrenamiento", episodios):
            s += semilla * 10_000
            perc = ent.reiniciar(s)
            grupo = f"captura-{uuid.uuid4().hex[:8]}"
            while not ent.terminado and n < maximo:
                d = ag.decidir(perc, rng)
                if d.explicacion.get("confianza", 0.0) < umbral:
                    self.dataset.agregar(situacion_de(ent.partida), None, "captura", grupo,
                                         ent.partida.pasos)
                    n += 1
                perc = ent.paso(d.accion).percepcion
        self.guardar_dataset()
        return n

    def confiar_version_importada(self) -> None:
        """El usuario confirma que confía en el origen del artefacto importado."""
        meta = self.almacen.meta(self.version)
        ruta = self.almacen.dir / "versiones" / self.version / "meta.json"
        meta["confiado"] = True
        from ...persistencia.almacen import escribir_atomico
        escribir_atomico(ruta, a_json(meta))
        self.almacen.evento("confianza", f"{self.version} marcada como confiable por el usuario")
        self.cargar()

    def historial_metricas(self) -> list[dict]:
        """Métricas de validación de cada versión entrenada (evolución del modelo)."""
        out = []
        for v in self.almacen.manifiesto().get("versiones", []):
            try:
                ruta = self.almacen.dir / "versiones" / v["version"] / "metricas.json"
                m = json.loads(ruta.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            out.append({"version": v["version"], "fecha": v["fecha"], **_resumen_metricas(m)})
        return out

    def detalle_entrenamiento(self) -> dict:
        return {"dataset": self.dataset.estadisticas(), "metricas": self.metricas,
                "bloqueado": self.bloqueado, "historial_metricas": self.historial_metricas()}


def _resumen_metricas(m: dict) -> dict:
    val = m.get("validacion") or {}
    return {"ejemplos": m.get("ejemplos"), "episodios": m.get("episodios"),
            "filas_entrenamiento": m.get("filas_entrenamiento"),
            "accuracy": val.get("accuracy"), "f1_macro": val.get("f1_macro"),
            "precision_macro": val.get("precision_macro"), "recall_macro": val.get("recall_macro")}
