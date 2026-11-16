"""Conjunto de ejemplos etiquetados (ARKIS y casos de LERK). Las etiquetas SOLO las pone el usuario.

Ejemplo:
  id, situacion (tablero serializado), etiqueta (acción o None si solo se recopiló),
  origen ('demostracion' = el usuario jugó y eligió | 'captura' = situación guardada para
  etiquetar después | 'correccion' = el usuario corrigió una predicción),
  episodio (grupo para validar sin fugas), aprobado, fecha, historial de cambios.
Eliminar mueve a la papelera; nada se borra físicamente sin una acción explícita.
"""
from __future__ import annotations

import time
import uuid
from collections import Counter

from ..nucleo.motor import Accion
from .situacion import accion_por_nombre, percepcion_de

ORIGENES = ("demostracion", "captura", "correccion")


class ErrorDataset(ValueError):
    pass


def _ahora():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class Dataset:
    def __init__(self, datos: dict | None = None):
        datos = datos or {}
        self.ejemplos: list[dict] = datos.get("ejemplos", [])
        self.papelera: list[dict] = datos.get("papelera", [])
        self.revision: int = datos.get("revision", 0)

    def a_dict(self) -> dict:
        return {"ejemplos": self.ejemplos, "papelera": self.papelera, "revision": self.revision}

    def _buscar(self, id_: str) -> dict:
        for e in self.ejemplos:
            if e["id"] == id_:
                return e
        raise ErrorDataset(f"No existe el ejemplo {id_}")

    def agregar(self, situacion: dict, etiqueta: str | None, origen: str, episodio: str,
                paso: int = 0) -> dict:
        if origen not in ORIGENES:
            raise ErrorDataset(f"Origen inválido: {origen}")
        if etiqueta is not None:
            self._validar_etiqueta(situacion, etiqueta)
        e = {"id": uuid.uuid4().hex[:12], "situacion": situacion, "etiqueta": etiqueta,
             "origen": origen, "episodio": episodio, "paso": paso, "aprobado": False,
             "fecha": _ahora(), "historial": []}
        self.ejemplos.append(e)
        self.revision += 1
        return e

    @staticmethod
    def _validar_etiqueta(situacion: dict, etiqueta: str) -> None:
        a = accion_por_nombre(etiqueta)
        if a not in percepcion_de(situacion).cuerpo.acciones_disponibles:
            raise ErrorDataset(f"'{etiqueta}' no es una acción disponible en esa situación")

    def etiquetar(self, id_: str, etiqueta: str) -> dict:
        """Etiquetar o corregir. La etiqueta anterior queda en el historial y el ejemplo
        vuelve a requerir aprobación."""
        e = self._buscar(id_)
        self._validar_etiqueta(e["situacion"], etiqueta)
        if e["etiqueta"] != etiqueta:
            e["historial"].append({"fecha": _ahora(), "etiqueta_anterior": e["etiqueta"],
                                   "aprobado_anterior": e["aprobado"]})
            e["etiqueta"] = etiqueta
            e["aprobado"] = False
            self.revision += 1
        return e

    def aprobar(self, ids: list[str], aprobado: bool = True) -> int:
        n = 0
        for id_ in ids:
            e = self._buscar(id_)
            if aprobado and e["etiqueta"] is None:
                raise ErrorDataset(f"El ejemplo {id_} no tiene etiqueta")
            if e["aprobado"] != aprobado:
                e["aprobado"] = aprobado
                n += 1
        self.revision += 1
        return n

    def eliminar(self, id_: str) -> None:
        e = self._buscar(id_)
        self.ejemplos.remove(e)
        e["eliminado"] = _ahora()
        self.papelera.append(e)
        self.revision += 1

    def restaurar(self, id_: str) -> None:
        for e in self.papelera:
            if e["id"] == id_:
                self.papelera.remove(e)
                e.pop("eliminado", None)
                self.ejemplos.append(e)
                self.revision += 1
                return
        raise ErrorDataset(f"No está en la papelera: {id_}")

    def aprobados(self) -> list[dict]:
        return [e for e in self.ejemplos if e["aprobado"] and e["etiqueta"] is not None]

    def estadisticas(self) -> dict:
        etiquetados = [e for e in self.ejemplos if e["etiqueta"] is not None]
        return {
            "recopilados": len(self.ejemplos),
            "etiquetados": len(etiquetados),
            "aprobados": len(self.aprobados()),
            "sin_etiqueta": len(self.ejemplos) - len(etiquetados),
            "episodios": len({e["episodio"] for e in self.ejemplos}),
            "distribucion": dict(Counter(e["etiqueta"] for e in etiquetados)),
            "distribucion_aprobados": dict(Counter(e["etiqueta"] for e in self.aprobados())),
            "por_origen": dict(Counter(e["origen"] for e in self.ejemplos)),
            "en_papelera": len(self.papelera),
            "revision": self.revision,
        }
