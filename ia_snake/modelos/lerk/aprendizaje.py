"""Mecanismos de adquisición de conocimiento de LERK.

1. Inducción por cobertura secuencial (familia CN2/RIPPER): aprende reglas a partir de
   instancias (hechos de la acción X, positivo/negativo), añadiendo literales que
   maximizan la precisión de Laplace y retirando los positivos cubiertos.
2. Aprendizaje por experiencia: LERK juega y el SIMULADOR aporta los resultados objetivos
   (morir en ≤ K pasos, comer, acercarse y sobrevivir). Con ellos se inducen reglas de
   prohibición y de preferencia. Nunca se usan las predicciones de LERK como verdad.
3. Corrección con Ripple-Down Rules: cuando el usuario corrige una inferencia, se crea una
   excepción a la regla responsable con las condiciones que distinguen el caso.
4. Generalización: se eliminan condiciones de una regla mientras su precisión en los
   casos no empeore (dropping conditions).
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from ...nucleo.motor import ACCIONES, Accion
from ..situacion import accion_por_nombre, percepcion_de
from .conocimiento import BaseConocimiento, Regla
from .predicados import cumple, hechos, literales

HORIZONTE_FRACASO = 4      # K: morir en ≤ K pasos tras la acción = fracaso


def laplace(p: int, n: int) -> float:
    return (p + 1) / (p + n + 2)


@dataclass(frozen=True)
class Instancia:
    verdaderos: frozenset
    positivo: bool


# --- 1. Inducción por cobertura secuencial -----------------------------------
def inducir(instancias: list[Instancia], conclusion: str, origen: str, min_soporte: int = 3,
            min_confianza: float = 0.75, max_reglas: int = 12, max_condiciones: int = 4,
            prioridad: int = 0) -> list[Regla]:
    pos = [i for i in instancias if i.positivo]
    neg = [i for i in instancias if not i.positivo]
    reglas: list[Regla] = []
    candidatos = literales()
    while pos and len(reglas) < max_reglas:
        conds: list[str] = []
        cp, cn = pos, neg
        while cn and len(conds) < max_condiciones:
            mejor, mejor_val = None, laplace(len(cp), len(cn))
            for lit in candidatos:
                if lit in conds or ("!" + lit) in conds or lit.lstrip("!") in conds:
                    continue
                p = sum(1 for i in cp if cumple(lit, i.verdaderos))
                if p < min_soporte:
                    continue
                n = sum(1 for i in cn if cumple(lit, i.verdaderos))
                val = laplace(p, n)
                if val > mejor_val + 1e-12:
                    mejor, mejor_val = lit, val
            if mejor is None:
                break
            conds.append(mejor)
            cp = [i for i in cp if cumple(mejor, i.verdaderos)]
            cn = [i for i in cn if cumple(mejor, i.verdaderos)]
        if not conds or len(cp) < min_soporte or laplace(len(cp), len(cn)) < min_confianza:
            break
        reglas.append(Regla(conds, conclusion, origen=origen, prioridad=prioridad,
                            soporte=len(cp) + len(cn), aciertos=len(cp)))
        cubiertos = set(map(id, cp))
        pos = [i for i in pos if id(i) not in cubiertos]
    return reglas


def instancias_de_casos(casos: list[dict]) -> list[Instancia]:
    """Casos etiquetados por el usuario → instancia positiva para la acción elegida y
    negativas para las demás disponibles."""
    out = []
    for c in casos:
        perc = percepcion_de(c["situacion"])
        h = hechos(perc)
        for a in perc.cuerpo.acciones_disponibles:
            out.append(Instancia(h[a], a.etiqueta == c["etiqueta"]))
    return out


def inducir_de_casos(base: BaseConocimiento, casos: list[dict], **kw) -> list[Regla]:
    """Sustituye las reglas inducidas de casos anteriores por las nuevas."""
    nuevas = inducir(instancias_de_casos(casos), "preferir", "induccion", **kw)
    _reemplazar_origen(base, "induccion", nuevas)
    return nuevas


# --- 2. Aprendizaje por experiencia ------------------------------------------
def etiquetar_episodio(pasos: list[dict], causa_fin: str | None) -> list[dict]:
    """pasos: [{'verdaderos', 'accion', 'comio'}] en orden. Añade los resultados objetivos."""
    total = len(pasos)
    murio = causa_fin in ("limite", "cuerpo")
    for i, p in enumerate(pasos):
        restantes = total - 1 - i
        p["fracaso"] = murio and restantes < HORIZONTE_FRACASO
        p["progreso"] = (not p["fracaso"]) and (p["comio"] or "acerca" in p["verdaderos"])
    return pasos


def aprender_de_experiencia(base: BaseConocimiento, experiencia: list[dict], **kw) -> dict:
    """Induce prohibiciones (de los fracasos) y preferencias (de los progresos) y sustituye
    las reglas de experiencia anteriores. Las reglas del usuario y las correcciones no se tocan."""
    inst_f = [Instancia(frozenset(e["verdaderos"]), e["fracaso"]) for e in experiencia]
    inst_p = [Instancia(frozenset(e["verdaderos"]), e["progreso"]) for e in experiencia]
    prohib = inducir(inst_f, "prohibir", "experiencia", prioridad=1, **kw)
    prefer = inducir(inst_p, "preferir", "experiencia", **kw)
    _reemplazar_origen(base, "experiencia", prohib + prefer)
    return {"prohibiciones": len(prohib), "preferencias": len(prefer),
            "instancias": len(experiencia),
            "fracasos": sum(e["fracaso"] for e in experiencia),
            "progresos": sum(e["progreso"] for e in experiencia)}


def _reemplazar_origen(base: BaseConocimiento, origen: str, nuevas: list[Regla]) -> None:
    viejas = [r.id for r in base.reglas if r.origen == origen and r.padre is None]
    for id_ in viejas:
        if any(r.id == id_ for r in base.reglas):
            base.eliminar(id_)
    for r in nuevas:
        base.agregar(r)


# --- 3. Corrección con Ripple-Down Rules -------------------------------------
def lista_diferencias(regla: Regla, verdaderos_ahora: frozenset) -> list[str]:
    """Literales que distinguen el caso actual del caso que originó la regla."""
    if regla.caso_origen:
        antes = frozenset(regla.caso_origen.get("verdaderos", []))
        dif = [p for p in sorted(verdaderos_ahora - antes)]
        dif += ["!" + p for p in sorted(antes - verdaderos_ahora)]
        if dif:
            return dif
    return [p for p in sorted(verdaderos_ahora) if p not in regla.condiciones]


def corregir(base: BaseConocimiento, situacion: dict, correcta: str,
             condiciones: list[str] | None = None, rng=None) -> dict:
    perc = percepcion_de(situacion)
    h = hechos(perc)
    acc_ok = accion_por_nombre(correcta)
    if acc_ok not in perc.cuerpo.acciones_disponibles:
        raise ValueError(f"'{correcta}' no es una acción disponible")
    elegida, exp = base.inferir(perc, rng or random.Random(0))
    cambios = {"elegida_antes": elegida.etiqueta, "excepcion": None, "regla_nueva": None}
    if elegida is acc_ok:
        cambios["sin_cambios"] = True
        return cambios

    if exp["ganadora"]:
        responsable = base.buscar(exp["ganadora"])
        conds = condiciones or lista_diferencias(responsable, h[elegida])
        exc = Regla(conds, "anular", padre=responsable.id, origen="correccion",
                    caso_origen={"situacion": situacion, "accion": elegida.etiqueta,
                                 "verdaderos": sorted(h[elegida])},
                    nota=f"corrección: en este caso no era '{elegida.etiqueta}'")
        base.agregar(exc)
        cambios["excepcion"] = exc.a_dict()

    nuevo_elegido, _ = base.inferir(perc, rng or random.Random(0))
    if nuevo_elegido is not acc_ok:
        conds = condiciones if (condiciones and not exp["ganadora"]) else sorted(h[acc_ok])
        regla = Regla(conds, "preferir", origen="correccion", prioridad=1,
                      caso_origen={"situacion": situacion, "accion": correcta,
                                   "verdaderos": sorted(h[acc_ok])},
                      nota=f"corrección: aquí la acción correcta es '{correcta}'")
        base.agregar(regla)
        cambios["regla_nueva"] = regla.a_dict()
    cambios["elegida_despues"] = base.inferir(perc, rng or random.Random(0))[0].etiqueta
    return cambios


# --- 4. Validación, conflictos y generalización -------------------------------
def _evaluaciones(base: BaseConocimiento, casos: list[dict]):
    for c in casos:
        perc = percepcion_de(c["situacion"])
        h = hechos(perc)
        yield c, perc, h


def validar(base: BaseConocimiento, casos: list[dict], actualizar: bool = True) -> dict:
    stats = {r.id: [0, 0] for r in base.reglas}
    correctas = cubiertos = 0
    for c, perc, h in _evaluaciones(base, casos):
        disp = perc.cuerpo.acciones_disponibles
        ok = accion_por_nombre(c["etiqueta"])
        for d in base.disparos(h, disp):
            r = d.excepcion or d.regla
            stats[r.id][0] += 1
            acierta = (d.accion is ok) == (d.conclusion == "preferir")
            stats[r.id][1] += int(acierta)
        elegida, exp = base.inferir(perc, random.Random(0))
        correctas += int(elegida is ok)
        cubiertos += int(not exp["sin_conocimiento"])
    if actualizar:
        for r in base.reglas:
            if stats[r.id][0]:
                r.soporte, r.aciertos = stats[r.id]
    n = len(casos)
    return {"casos": n, "exactitud": correctas / n if n else None,
            "cobertura": cubiertos / n if n else None,
            "por_regla": {k: {"soporte": v[0], "aciertos": v[1]} for k, v in stats.items()}}


def conflictos(base: BaseConocimiento, casos: list[dict]) -> list[dict]:
    """Pares de reglas que, en algún caso, concluyen cosas incompatibles."""
    vistos: dict = {}
    for c, perc, h in _evaluaciones(base, casos):
        ds = base.disparos(h, perc.cuerpo.acciones_disponibles)
        for i, a in enumerate(ds):
            for b in ds[i + 1:]:
                ra, rb = a.excepcion or a.regla, b.excepcion or b.regla
                tipo = None
                if a.accion is b.accion and {a.conclusion, b.conclusion} == {"preferir", "prohibir"}:
                    tipo = "preferir_vs_prohibir"
                elif (a.accion is not b.accion and a.conclusion == b.conclusion == "preferir"
                      and a.fuerza() == b.fuerza()):
                    tipo = "empate_de_preferencias"
                if tipo:
                    k = (min(ra.id, rb.id), max(ra.id, rb.id), tipo)
                    vistos.setdefault(k, {"reglas": [ra.texto(), rb.texto()], "ids": [ra.id, rb.id],
                                          "tipo": tipo, "casos": 0})["casos"] += 1
    return sorted(vistos.values(), key=lambda d: -d["casos"])


def generalizar(base: BaseConocimiento, casos: list[dict], tolerancia: float = 0.0) -> list[dict]:
    """Elimina condiciones mientras la precisión de Laplace de la regla en los casos no baje
    más de `tolerancia`. Devuelve los cambios realizados."""
    inst = instancias_de_casos(casos)
    if not inst:
        return []
    cambios = []
    for r in [r for r in base.reglas if r.padre is None and r.conclusion in ("preferir", "prohibir")
              and r.accion is None and len(r.condiciones) > 1]:
        pos_es = (lambda i: i.positivo) if r.conclusion == "preferir" else (lambda i: not i.positivo)

        def precision(conds):
            cub = [i for i in inst if all(cumple(c, i.verdaderos) for c in conds)]
            p = sum(1 for i in cub if pos_es(i))
            return laplace(p, len(cub) - p), len(cub)

        actual, cobertura = precision(r.condiciones)
        mejorado = True
        antes = list(r.condiciones)
        while mejorado and len(r.condiciones) > 1:
            mejorado = False
            for c in list(r.condiciones):
                resto = [x for x in r.condiciones if x != c]
                prec, cob = precision(resto)
                if prec >= actual - tolerancia and cob > cobertura:
                    r.condiciones, actual, cobertura, mejorado = resto, prec, cob, True
                    break
        if r.condiciones != antes:
            cambios.append({"regla": r.id, "antes": antes, "despues": list(r.condiciones),
                            "precision": round(actual, 4), "cobertura": cobertura})
    return cambios
