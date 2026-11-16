"""Base de los servicios de modelo: almacenamiento, evaluación con evidencia y resumen.

La evaluación es común (mide jugando con semillas fijas); el aprendizaje NO lo es: cada
servicio implementa sus propios métodos de entrenamiento.
"""
from __future__ import annotations

import random
import threading
import uuid

from ..evaluacion.lineas_base import politica_azar
from ..evaluacion.protocolo import estadistico, jugar_episodio, jugar_episodio_observado, semillas
from ..nucleo.entorno import ConfigEntorno, Entorno
from ..persistencia.almacen import AlmacenModelo
from . import base

CONJUNTOS = ("validacion", "prueba")


class Cancelado(Exception):
    pass


class ServicioModelo:
    clave = ""
    nombre = ""
    metodologia = ""
    descripcion = ""

    def __init__(self, raiz=None):
        self.almacen = AlmacenModelo(self.clave, raiz)
        self.lock = threading.RLock()
        self.version: str | None = None
        self.cargar()

    # A implementar por cada modelo
    def cargar(self) -> None:
        raise NotImplementedError

    def agente(self) -> base.Agente:
        raise NotImplementedError

    def detalle_entrenamiento(self) -> dict:
        return {}

    # --- Evaluación ----------------------------------------------------------
    def evaluar(self, dificultad: str, episodios: int = 30, conjunto: str = "validacion",
                config: ConfigEntorno | None = None, progreso=None, cancelar=None,
                observador=None) -> dict:
        """Juega `episodios` partidas con semillas fijas del conjunto indicado, las registra y
        compara con el azar en las MISMAS semillas. Cambia el estado según la evidencia."""
        if conjunto not in CONJUNTOS:
            raise ValueError("Solo se evalúa con semillas de validación o prueba")
        lista = semillas(conjunto, episodios)
        ag = self.agente()
        pol = ag.politica()
        ent = Entorno(dificultad, config)
        id_ = f"eval-{uuid.uuid4().hex[:8]}"
        eps = []
        for i, s in enumerate(lista):
            if cancelar and cancelar():
                raise Cancelado()
            if observador is not None:
                observador.nuevo_episodio(i + 1, episodios, s, {"dificultad": dificultad,
                                                                "fase": "evaluacion", "version": self.version})
                r = jugar_episodio_observado(ent, ag, s, observador)
                observador.fin_episodio(r)
            else:
                r = jugar_episodio(ent, pol, s)
            self.almacen.registrar_episodio(r, self.version, "evaluacion", id_)
            eps.append(r)
            if progreso:
                progreso(i + 1, episodios, r)
        azar = [jugar_episodio(ent, politica_azar, s) for s in lista]
        m = estadistico([e.manzanas for e in eps])
        ma = estadistico([e.manzanas for e in azar])
        supera = bool(m.ic95[0] > ma.ic95[1])
        res = {
            "id": id_, "dificultad": dificultad, "conjunto": conjunto, "episodios": episodios,
            "semillas": [lista[0], lista[-1]], "version": self.version,
            "manzanas": m.__dict__, "azar": ma.__dict__,
            "ocupacion_max": estadistico([e.ocupacion_max for e in eps]).__dict__,
            "nivel_medio": estadistico([e.nivel for e in eps]).media,
            "mejor_nivel": max(e.nivel for e in eps),
            "victorias": sum(e.victoria for e in eps),
            "causas_fin": _contar(e.causa_fin for e in eps),
            "supera_azar": supera,
        }
        evals = self.almacen.leer_datos("evaluaciones.json", [])
        evals.append(res)
        self.almacen.escribir_datos("evaluaciones.json", evals[-200:])
        if self.version:
            estado = base.VALIDADO if supera else base.EVALUADO
            if self.almacen.manifiesto().get("estado") != base.PREENTRENADO:
                self.almacen.actualizar_estado(estado)
        self.almacen.registrar_sesion(id_, "evaluacion", self.version, self.version,
                                      {"dificultad": dificultad, "episodios": episodios,
                                       "conjunto": conjunto}, res)
        return res

    # --- Resumen para la interfaz -------------------------------------------
    def resumen(self) -> dict:
        m = self.almacen.manifiesto()
        return {
            "clave": self.clave, "nombre": self.nombre, "metodologia": self.metodologia,
            "descripcion": self.descripcion,
            "estado": m.get("estado", base.SIN_ENTRENAR),
            "version": m.get("version_actual"),
            "versiones": m.get("versiones", [])[-30:],
            "records": self.almacen.records(),
            "episodios": self.almacen.resumen_episodios(),
            "ultima_evaluacion": (self.almacen.leer_datos("evaluaciones.json", []) or [None])[-1],
            "entrenamiento": self.detalle_entrenamiento(),
        }


def _contar(it):
    out: dict = {}
    for x in it:
        out[x] = out.get(x, 0) + 1
    return out


def rng_de(semilla: int | None) -> random.Random:
    return random.Random(semilla)
