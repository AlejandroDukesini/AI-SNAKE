"""Sesiones de simulación en vivo. El servidor es la única autoridad: el navegador pide
pasos y dibuja lo que recibe.

Modos:
- 'observar': el modelo decide cada paso y explica su decisión.
- 'demostrar': tú eliges cada acción; cada elección se guarda como ejemplo etiquetado del
  modelo destino (ARKIS: ejemplo pendiente de aprobar; LERK: caso).
- 'jugar': tú juegas sin guardar ejemplos (para probar el entorno).
El tiempo de la regla de 30 s es tiempo de juego; el reloj monotónico solo mide el
tiempo real activo (las pausas no cuentan).
"""
from __future__ import annotations

import random
import time
import uuid
from collections import OrderedDict

from ..nucleo import evolucion
from ..nucleo.entorno import Entorno
from ..nucleo.motor import Accion
from ..nucleo.reloj import RelojSesion
from ..modelos.situacion import situacion_de

MODOS = ("observar", "demostrar", "jugar")
MAX_SESIONES = 20


class Sesion:
    def __init__(self, servicio, dificultad: str, semilla: int | None, modo: str,
                 destino: str | None, velocidad: float):
        if modo not in MODOS:
            raise ValueError(f"Modo inválido: {modo}")
        self.id = uuid.uuid4().hex[:10]
        self.servicio = servicio            # None en 'jugar'
        self.dificultad = dificultad
        self.semilla = semilla if semilla is not None else random.randrange(3_000_000, 9_000_000)
        self.modo = modo
        self.destino = destino
        from ..nucleo.entorno import ConfigEntorno
        self.entorno = Entorno(dificultad, ConfigEntorno(velocidad_movimiento=velocidad))
        self.entorno.reiniciar(self.semilla)
        self.rng = random.Random(self.semilla)
        self.reloj = RelojSesion()
        self.reloj.iniciar()
        self.pausada = False
        self.ultima = None
        self.registrado = False
        self.ejemplos_guardados = 0
        self.decision = None
        self.visto = time.time()

    def _decision(self):
        if self.servicio is None or self.entorno.terminado:
            return None
        return self.servicio.agente().decidir(self.entorno.percepcion, self.rng)

    def paso(self, accion: str | None) -> None:
        if self.entorno.terminado:
            return
        perc = self.entorno.percepcion
        if accion is None:
            if self.modo != "observar":
                raise ValueError("En este modo tienes que elegir la acción")
            a = (self.decision or self._decision()).accion
        else:
            a = Accion[accion.upper()]
            if self.modo == "observar":
                raise ValueError("En modo observar decide el modelo")
            if a not in perc.cuerpo.acciones_disponibles:
                raise ValueError(f"'{accion}' no está disponible (giro de 180°)")
            if self.modo == "demostrar":
                self._guardar_ejemplo(a)
        self.ultima = self.entorno.paso(a)
        self.decision = None
        if self.entorno.terminado and not self.registrado and self.servicio is not None:
            self.registrado = True
            modo = "observacion" if self.modo == "observar" else "demostracion"
            self.servicio.almacen.registrar_episodio(self.entorno.resumen(), self.servicio.version,
                                                     modo, self.id)

    def _guardar_ejemplo(self, a: Accion) -> None:
        sit = situacion_de(self.entorno.partida)
        if self.destino == "arkis":
            svc = self.servicio
            with svc.lock:
                svc.dataset.agregar(sit, a.etiqueta, "demostracion", self.id, self.entorno.partida.pasos)
                svc.guardar_dataset()
        elif self.destino == "lerk":
            self.servicio.agregar_caso(sit, a.etiqueta, self.id)
        self.ejemplos_guardados += 1

    def pausar(self, pausada: bool) -> None:
        self.pausada = pausada
        self.reloj.pausar() if pausada else self.reloj.reanudar()

    def fotograma(self) -> dict:
        self.visto = time.time()
        ent, p = self.entorno, self.entorno.partida
        if self.decision is None and self.modo != "jugar":
            self.decision = self._decision()
        u = self.ultima
        casillas = p.casillas
        return {
            "id": self.id, "modo": self.modo, "destino": self.destino,
            "modelo": None if self.servicio is None else self.servicio.clave,
            "version": None if self.servicio is None else self.servicio.version,
            "partida": p.instantanea(),
            "percepcion": ent.percepcion.a_dict(completa=True),
            "decision": None if self.decision is None else self.decision.a_dict(),
            "ultima": None if u is None else {
                "accion": u.accion.etiqueta, "comio": u.comio, "causa_fin": u.causa_fin,
                "recompensa": round(u.recompensa.total, 4),
                "componentes": {k: round(v, 4) for k, v in u.recompensa.componentes.items()},
                "ciclo": None if u.ciclo is None else {"en_ciclo": u.ciclo.en_ciclo,
                                                       "motivos": list(u.ciclo.motivos)},
            },
            "evolucion": {
                "nivel": evolucion.nivel(p.longitud, casillas, p.manzanas),
                "nivel_max_partida": ent.nivel_max,
                "ocupacion": round(evolucion.ocupacion(p.longitud, casillas), 2),
                "umbrales": list(evolucion.tabla_umbrales(casillas)),
                "record": None if self.servicio is None else
                self.servicio.almacen.records().get(self.dificultad),
            },
            "tiempo": {
                "juego_s": round(ent.reloj.segundos(p.pasos), 2),
                "real_activo_s": round(self.reloj.transcurrido(), 2),
                "pasos_en_ciclo": ent.pasos_en_ciclo, "limite_ciclo": ent.limite_ciclo,
                "segundos_en_ciclo": round(ent.reloj.segundos(ent.pasos_en_ciclo), 2),
                "velocidad": ent.reloj.velocidad,
            },
            "pausada": self.pausada, "terminada": ent.terminado,
            "ejemplos_guardados": self.ejemplos_guardados,
        }


class GestorSesiones:
    def __init__(self):
        self._s: OrderedDict[str, Sesion] = OrderedDict()

    def crear(self, *args, **kw) -> Sesion:
        s = Sesion(*args, **kw)
        self._s[s.id] = s
        while len(self._s) > MAX_SESIONES:
            self._s.popitem(last=False)
        return s

    def obtener(self, id_: str) -> Sesion:
        s = self._s[id_]
        self._s.move_to_end(id_)
        return s

    def eliminar(self, id_: str) -> None:
        self._s.pop(id_, None)
