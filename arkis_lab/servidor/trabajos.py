"""Trabajos en segundo plano (entrenamientos y evaluaciones largas), uno por modelo a la vez."""
from __future__ import annotations

import threading
import time
import traceback
import uuid
from dataclasses import asdict, is_dataclass


def _serializable(r):
    if r is None:
        return None
    if is_dataclass(r):
        d = asdict(r)
        d.pop("episodios", None)
        return d
    return r


class Trabajo:
    def __init__(self, modelo: str, tipo: str, parametros: dict):
        self.id = uuid.uuid4().hex[:10]
        self.modelo = modelo
        self.tipo = tipo
        self.parametros = parametros
        self.estado = "en_curso"
        self.hechos = 0
        self.total = 0
        self.ultimo: dict | None = None
        self.resultado = None
        self.error: str | None = None
        self.inicio = time.time()
        self.fin: float | None = None
        self._cancelar = threading.Event()

    def progreso(self, hechos: int, total: int, resumen=None) -> None:
        self.hechos, self.total = hechos, total
        if resumen is not None:
            self.ultimo = {"manzanas": resumen.manzanas, "pasos": resumen.pasos,
                           "nivel": resumen.nivel, "causa_fin": resumen.causa_fin,
                           "retorno": round(resumen.retorno, 3)}

    def cancelado(self) -> bool:
        return self._cancelar.is_set()

    def cancelar(self) -> None:
        self._cancelar.set()

    def a_dict(self) -> dict:
        return {"id": self.id, "modelo": self.modelo, "tipo": self.tipo,
                "parametros": self.parametros, "estado": self.estado, "hechos": self.hechos,
                "total": self.total, "ultimo": self.ultimo, "resultado": self.resultado,
                "error": self.error, "segundos": round((self.fin or time.time()) - self.inicio, 1)}


class GestorTrabajos:
    def __init__(self):
        self._trabajos: dict[str, Trabajo] = {}
        self._lock = threading.Lock()

    def activo(self, modelo: str) -> Trabajo | None:
        for t in self._trabajos.values():
            if t.modelo == modelo and t.estado == "en_curso":
                return t
        return None

    def lanzar(self, modelo: str, tipo: str, parametros: dict, funcion) -> Trabajo:
        """`funcion(trabajo)` hace el trabajo y devuelve el resultado."""
        with self._lock:
            if self.activo(modelo):
                raise RuntimeError(f"{modelo} ya tiene un trabajo en curso")
            t = Trabajo(modelo, tipo, parametros)
            self._trabajos[t.id] = t

        def correr():
            try:
                t.resultado = _serializable(funcion(t))
                t.estado = "cancelado" if t.cancelado() else "terminado"
            except Exception as e:                     # se informa en la interfaz
                t.estado = "cancelado" if type(e).__name__ == "Cancelado" else "error"
                t.error = f"{type(e).__name__}: {e}"
                if t.estado == "error":
                    traceback.print_exc()
            finally:
                t.fin = time.time()

        threading.Thread(target=correr, daemon=True, name=f"trabajo-{t.id}").start()
        return t

    def obtener(self, id_: str) -> Trabajo:
        return self._trabajos[id_]

    def lista(self) -> list[dict]:
        return [t.a_dict() for t in sorted(self._trabajos.values(), key=lambda t: -t.inicio)[:30]]
