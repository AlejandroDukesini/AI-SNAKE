"""Servicio de LERK. Cada cambio de conocimiento crea una versión nueva (historial completo
de modificaciones y posibilidad de volver a cualquier estado anterior)."""
from __future__ import annotations

import json
import random
import uuid

from ...evaluacion.protocolo import semillas
from ...nucleo.entorno import Entorno
from ...persistencia.almacen import a_json
from .. import base as estados
from ..ejemplos import Dataset
from ..servicio import Cancelado, ServicioModelo
from ..situacion import situacion_de
from . import aprendizaje
from .conocimiento import BaseConocimiento, LerkAgente, Regla
from .predicados import PREDICADOS, hechos

MAX_EXPERIENCIA = 30_000


class ServicioLerk(ServicioModelo):
    clave = "lerk"
    nombre = "LERK"
    metodologia = "Aprendizaje simbólico"
    descripcion = ("Reglas explícitas con excepciones, inducidas de ejemplos y de la experiencia, "
                   "y corregibles por ti. Cada decisión se explica con su cadena de inferencia.")

    def cargar(self) -> None:
        self.casos = Dataset(self.almacen.leer_datos("casos.json"))
        self.experiencia: list = self.almacen.leer_datos("experiencia.json", [])
        cargado = self.almacen.cargar_version()
        if cargado is None:
            self.version, self.base = None, BaseConocimiento()
        else:
            self.version, archivos = cargado
            self.base = BaseConocimiento.desde_lista(json.loads(archivos["base.json"]))

    def agente(self) -> LerkAgente:
        return LerkAgente(self.base)

    def _guardar(self, motivo: str, metricas: dict | None = None) -> str:
        estado = estados.ENTRENADO if self.base.reglas else estados.SIN_ENTRENAR
        self.version = self.almacen.guardar_version(
            {"base.json": a_json(self.base.a_lista())}, motivo, estado,
            {"reglas": len(self.base.reglas), **(metricas or {})})
        return self.version

    # --- Edición directa por el usuario ----------------------------------------
    def crear_regla(self, datos: dict) -> dict:
        with self.lock:
            r = Regla(condiciones=datos.get("condiciones", []), conclusion=datos["conclusion"],
                      accion=datos.get("accion") or None, prioridad=int(datos.get("prioridad", 0)),
                      padre=datos.get("padre") or None, origen="usuario", nota=datos.get("nota", ""))
            r = self.base.agregar(r)
            self._guardar(f"regla creada por el usuario: {r.texto()}")
            return r.a_dict()

    def modificar_regla(self, id_: str, cambios: dict) -> dict:
        with self.lock:
            r = self.base.buscar(id_)
            datos = r.a_dict()
            for k in ("condiciones", "conclusion", "accion", "prioridad", "activa", "nota"):
                if k in cambios:
                    datos[k] = cambios[k]
            nueva = Regla.desde_dict(datos)          # valida
            self.base.reglas[self.base.reglas.index(r)] = nueva
            self._guardar(f"regla modificada: {nueva.texto()}")
            return nueva.a_dict()

    def eliminar_regla(self, id_: str) -> list[str]:
        with self.lock:
            ids = self.base.eliminar(id_)
            self._guardar(f"reglas eliminadas: {', '.join(ids)}")
            return ids

    # --- Casos (ejemplos del usuario) -------------------------------------------
    def agregar_caso(self, situacion: dict, etiqueta: str, episodio: str = "manual",
                     origen: str = "demostracion") -> dict:
        with self.lock:
            e = self.casos.agregar(situacion, etiqueta, origen, episodio)
            self.casos.aprobar([e["id"]])
            self.almacen.escribir_datos("casos.json", self.casos.a_dict())
            return e

    def corregir(self, situacion: dict, correcta: str, condiciones: list[str] | None = None) -> dict:
        with self.lock:
            cambios = aprendizaje.corregir(self.base, situacion, correcta, condiciones)
            if not cambios.get("sin_cambios"):
                self.agregar_caso(situacion, correcta, "correcciones", "correccion")
                self._guardar(f"corrección: '{cambios['elegida_antes']}' → '{correcta}'")
            return cambios

    def diferencias(self, situacion: dict) -> dict:
        """Para la interfaz: hechos de cada acción y lista de diferencias propuesta."""
        from ..situacion import percepcion_de
        perc = percepcion_de(situacion)
        h = hechos(perc)
        elegida, exp = self.base.inferir(perc, random.Random(0))
        prop = []
        if exp["ganadora"]:
            prop = aprendizaje.lista_diferencias(self.base.buscar(exp["ganadora"]), h[elegida])
        return {"elegida": elegida.etiqueta, "explicacion": exp, "propuesta": prop,
                "hechos": {a.etiqueta: sorted(v) for a, v in h.items()}}

    # --- Aprendizaje -------------------------------------------------------------
    def inducir(self, **kw) -> dict:
        with self.lock:
            nuevas = aprendizaje.inducir_de_casos(self.base, self.casos.aprobados(), **kw)
            self._guardar(f"inducción desde {len(self.casos.aprobados())} casos: {len(nuevas)} reglas",
                          {"inducidas": len(nuevas)})
            return {"reglas": [r.a_dict() for r in nuevas]}

    def generalizar(self, tolerancia: float = 0.0) -> dict:
        with self.lock:
            cambios = aprendizaje.generalizar(self.base, self.casos.aprobados(), tolerancia)
            if cambios:
                self._guardar(f"generalización: {len(cambios)} reglas simplificadas")
            return {"cambios": cambios}

    def validar(self) -> dict:
        with self.lock:
            rep = aprendizaje.validar(self.base, self.casos.aprobados())
            if rep["casos"]:
                self._guardar(f"validación en {rep['casos']} casos", {
                    "exactitud": rep["exactitud"], "cobertura": rep["cobertura"]})
            return rep

    def conflictos(self) -> list[dict]:
        return aprendizaje.conflictos(self.base, self.casos.aprobados())

    def entrenamiento_automatico(self, dificultad: str, episodios: int = 50, epsilon: float = 0.2,
                                 semilla: int = 0, bloque: int = 10, progreso=None,
                                 cancelar=None) -> dict:
        """LERK juega, el simulador aporta los resultados y se inducen reglas de experiencia
        cada `bloque` episodios. ε = probabilidad de explorar una acción al azar."""
        ent = Entorno(dificultad)
        rng = random.Random(semilla)
        id_ = f"auto-{uuid.uuid4().hex[:8]}"
        v0 = self.version
        resumenes, ultimo = [], {}
        lista = [s + semilla * 100_000 for s in semillas("entrenamiento", episodios)]
        for i, s in enumerate(lista):
            if cancelar and cancelar():
                break
            perc = ent.reiniciar(s)
            pasos = []
            ag = self.agente()
            while not ent.terminado:
                h = hechos(perc)
                if rng.random() < epsilon:
                    a = rng.choice(perc.cuerpo.acciones_disponibles)
                else:
                    a = ag.decidir(perc, rng).accion
                t = ent.paso(a)
                pasos.append({"verdaderos": sorted(h[a]), "accion": a.etiqueta, "comio": t.comio})
                perc = t.percepcion
            r = ent.resumen()
            self.experiencia += aprendizaje.etiquetar_episodio(pasos, r.causa_fin)
            self.experiencia = self.experiencia[-MAX_EXPERIENCIA:]
            self.almacen.registrar_episodio(r, self.version, "entrenamiento", id_, {"epsilon": epsilon})
            resumenes.append(r)
            if (i + 1) % bloque == 0 or i + 1 == len(lista):
                with self.lock:
                    ultimo = aprendizaje.aprender_de_experiencia(self.base, self.experiencia)
                    self.almacen.escribir_datos("experiencia.json", self.experiencia)
                    self._guardar(f"experiencia: {i + 1} episodios ({id_})", ultimo)
            if progreso:
                progreso(i + 1, len(lista), r)
        res = {"sesion": id_, "episodios": len(resumenes), "aprendizaje": ultimo,
               "manzanas_media": sum(r.manzanas for r in resumenes) / max(1, len(resumenes))}
        self.almacen.registrar_sesion(id_, "entrenamiento_automatico", v0, self.version,
                                      {"dificultad": dificultad, "episodios": episodios,
                                       "epsilon": epsilon, "semilla": semilla}, res)
        return res

    def detalle_entrenamiento(self) -> dict:
        origenes: dict = {}
        for r in self.base.reglas:
            origenes[r.origen] = origenes.get(r.origen, 0) + 1
        return {"reglas": self.base.a_lista(), "por_origen": origenes,
                "casos": self.casos.estadisticas(), "experiencia": len(self.experiencia),
                "predicados": PREDICADOS}
