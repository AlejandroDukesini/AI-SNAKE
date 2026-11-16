"""Base de conocimiento de LERK y motor de inferencia.

Regla:  SI cond_1(X) Y ... [Y X = acción] ENTONCES preferir X | prohibir X
Excepción (Ripple-Down Rules): regla hija ligada a una regla padre. Si el padre se cumple
para X y la excepción también, prevalece la conclusión de la excepción ('anular',
'prohibir' o 'preferir').

Resolución de conflictos (documentada):
1. Para cada acción disponible X se evalúan las reglas raíz y sus excepciones.
2. Una prohibición elimina X, salvo que una preferencia sobre X tenga prioridad
   estrictamente mayor que todas sus prohibiciones.
3. Entre las acciones permitidas gana la preferencia más fuerte:
   (prioridad, especificidad = nº de condiciones, confianza de Laplace).
4. Si todas están prohibidas, se elige la de prohibición más débil (conflicto registrado).
5. Si ninguna regla de preferencia se cumple, LERK no sabe: elige al azar entre las
   permitidas y lo dice.
"""
from __future__ import annotations

import random
import time
import uuid
from dataclasses import asdict, dataclass, field

from ...nucleo.motor import ACCIONES, Accion
from ...nucleo.percepcion import Percepcion
from ..base import Agente, Decision
from .predicados import cumple, hechos, texto_literal, validar_literal

CONCLUSIONES = ("preferir", "prohibir", "anular")
ORIGENES = ("usuario", "induccion", "correccion", "experiencia", "generalizacion")


@dataclass
class Regla:
    condiciones: list[str]
    conclusion: str
    accion: str | None = None          # constante opcional: la regla solo vale para esa acción
    prioridad: int = 0
    origen: str = "usuario"
    padre: str | None = None           # si es excepción, id de la regla padre
    activa: bool = True
    soporte: int = 0                   # casos en los que se cumplió (validación/inducción)
    aciertos: int = 0                  # de ellos, en cuántos su conclusión fue correcta
    caso_origen: dict | None = None    # caso que la motivó (cornerstone en RDR)
    nota: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    creada: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))

    def __post_init__(self):
        if self.conclusion not in CONCLUSIONES:
            raise ValueError(f"Conclusión inválida: {self.conclusion}")
        if self.conclusion == "anular" and self.padre is None:
            raise ValueError("'anular' solo tiene sentido en una excepción")
        if self.origen not in ORIGENES:
            raise ValueError(f"Origen inválido: {self.origen}")
        if self.accion is not None and self.accion not in [a.etiqueta for a in ACCIONES]:
            raise ValueError(f"Acción inválida: {self.accion}")
        self.condiciones = [validar_literal(c) for c in self.condiciones]

    @property
    def confianza(self) -> float:
        return (self.aciertos + 1) / (self.soporte + 2)     # estimación de Laplace

    @property
    def especificidad(self) -> int:
        return len(self.condiciones) + (1 if self.accion else 0)

    def se_cumple(self, accion: Accion, verdaderos: frozenset[str]) -> bool:
        if self.accion is not None and self.accion != accion.etiqueta:
            return False
        return all(cumple(c, verdaderos) for c in self.condiciones)

    def texto(self) -> str:
        partes = [texto_literal(c) for c in self.condiciones]
        if self.accion:
            partes.append(f"X = {self.accion}")
        si = " Y ".join(partes) if partes else "SIEMPRE"
        pref = "EXCEPCIÓN: " if self.padre else ""
        return f"{pref}SI {si} ENTONCES {self.conclusion} X"

    def a_dict(self) -> dict:
        d = asdict(self)
        d["texto"] = self.texto()
        d["confianza"] = round(self.confianza, 4)
        return d

    @classmethod
    def desde_dict(cls, d: dict) -> "Regla":
        campos = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**campos)


@dataclass
class Disparo:
    regla: Regla
    accion: Accion
    conclusion: str
    excepcion: Regla | None = None

    def fuerza(self):
        r = self.excepcion or self.regla
        return (r.prioridad, r.especificidad, r.confianza)


class BaseConocimiento:
    def __init__(self, reglas: list[Regla] | None = None):
        self.reglas: list[Regla] = list(reglas or [])

    # --- Gestión -------------------------------------------------------------
    def buscar(self, id_: str) -> Regla:
        for r in self.reglas:
            if r.id == id_:
                return r
        raise KeyError(f"No existe la regla {id_}")

    def agregar(self, regla: Regla) -> Regla:
        if regla.padre is not None:
            self.buscar(regla.padre)
        for r in self.reglas:
            if (r.activa and r.padre == regla.padre and r.accion == regla.accion
                    and r.conclusion == regla.conclusion
                    and set(r.condiciones) == set(regla.condiciones)):
                return r                    # ya existe: no se duplica
        self.reglas.append(regla)
        return regla

    def eliminar(self, id_: str) -> list[str]:
        """Elimina la regla y, en cascada, sus excepciones. Devuelve los ids eliminados."""
        ids = {id_}
        cambio = True
        while cambio:
            nuevos = {r.id for r in self.reglas if r.padre in ids} - ids
            cambio = bool(nuevos)
            ids |= nuevos
        self.buscar(id_)
        self.reglas = [r for r in self.reglas if r.id not in ids]
        return sorted(ids)

    def raices(self) -> list[Regla]:
        return [r for r in self.reglas if r.padre is None and r.activa]

    def excepciones_de(self, regla: Regla) -> list[Regla]:
        return [r for r in self.reglas if r.padre == regla.id and r.activa]

    def a_lista(self) -> list[dict]:
        return [r.a_dict() for r in self.reglas]

    @classmethod
    def desde_lista(cls, datos: list[dict]) -> "BaseConocimiento":
        return cls([Regla.desde_dict(d) for d in datos or []])

    # --- Inferencia ----------------------------------------------------------
    def _evaluar(self, regla: Regla, accion: Accion, verdaderos) -> Disparo | None:
        if not regla.se_cumple(accion, verdaderos):
            return None
        for e in self.excepciones_de(regla):
            sub = self._evaluar(e, accion, verdaderos)
            if sub is not None:
                return Disparo(regla, accion, sub.conclusion, sub.excepcion or e)
        return Disparo(regla, accion, regla.conclusion)

    def disparos(self, verdaderos_por_accion: dict, acciones) -> list[Disparo]:
        out = []
        for a in acciones:
            for r in self.raices():
                d = self._evaluar(r, a, verdaderos_por_accion[a])
                if d is not None:
                    out.append(d)
        return out

    def inferir(self, p: Percepcion, rng: random.Random | None = None) -> tuple[Accion, dict]:
        disp = list(p.cuerpo.acciones_disponibles)
        h = hechos(p)
        ds = self.disparos(h, disp)
        prohib = {a: [d for d in ds if d.accion is a and d.conclusion == "prohibir"] for a in disp}
        prefer = {a: [d for d in ds if d.accion is a and d.conclusion == "preferir"] for a in disp}
        conflictos = []

        permitidas = []
        for a in disp:
            if not prohib[a]:
                permitidas.append(a)
                continue
            fp = max((d.fuerza()[0] for d in prohib[a]))
            if prefer[a] and max(d.fuerza()[0] for d in prefer[a]) > fp:
                permitidas.append(a)
                conflictos.append(f"{a.etiqueta}: preferencia de mayor prioridad anula la prohibición")
            elif prefer[a]:
                conflictos.append(f"{a.etiqueta}: prohibición y preferencia a la vez; gana la prohibición")
        if not permitidas:
            debil = min(disp, key=lambda a: max(d.fuerza() for d in prohib[a]))
            permitidas = [debil]
            conflictos.append("todas las acciones están prohibidas: se elige la prohibición más débil")

        con_pref = [a for a in permitidas if prefer[a]]
        if con_pref:
            fuerza = {a: max(d.fuerza() for d in prefer[a]) for a in con_pref}
            mejor = max(fuerza.values())
            empatadas = [a for a in con_pref if fuerza[a] == mejor]
            if len(empatadas) > 1:
                conflictos.append("empate entre " + ", ".join(a.etiqueta for a in empatadas)
                                  + ": se desempata al azar")
            elegida = (rng or random).choice(empatadas)
            ganadora = max(prefer[elegida], key=Disparo.fuerza)
            motivo = f"regla ganadora: {(ganadora.excepcion or ganadora.regla).texto()}"
            sin_conocimiento = False
        else:
            elegida = (rng or random).choice(permitidas)
            ganadora = None
            motivo = "ninguna regla de preferencia se cumple: acción al azar entre las permitidas"
            sin_conocimiento = True

        explicacion = {
            "tipo": "cadena_inferencia",
            "hechos": {a.etiqueta: sorted(h[a]) for a in disp},
            "disparos": [{"regla": d.regla.id, "texto": d.regla.texto(), "accion": d.accion.etiqueta,
                          "conclusion": d.conclusion,
                          "excepcion": d.excepcion.texto() if d.excepcion else None} for d in ds],
            "prohibidas": [a.etiqueta for a in disp if a not in permitidas],
            "conflictos": conflictos,
            "ganadora": None if ganadora is None else (ganadora.excepcion or ganadora.regla).id,
            "texto": motivo,
            "sin_conocimiento": sin_conocimiento,
        }
        return elegida, explicacion


class LerkAgente(Agente):
    clave = "lerk"
    nombre = "LERK"
    metodologia = "Aprendizaje simbólico"

    def __init__(self, base: BaseConocimiento):
        self.base = base

    def decidir(self, percepcion, rng=None) -> Decision:
        a, exp = self.base.inferir(percepcion, rng)
        punt = {b: 0.0 for b in ACCIONES}
        punt[a] = 1.0
        return Decision(a, punt, exp)
