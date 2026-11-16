import random

import pytest

from arkis_lab.evaluacion.lineas_base import politica_azar, politica_voraz
from arkis_lab.evaluacion.protocolo import evaluar, semillas
from arkis_lab.modelos.lerk import aprendizaje
from arkis_lab.modelos.lerk.conocimiento import BaseConocimiento, LerkAgente, Regla
from arkis_lab.modelos.lerk.predicados import hechos
from arkis_lab.modelos.lerk.servicio import ServicioLerk
from arkis_lab.modelos.situacion import percepcion_de, situacion_de
from arkis_lab.nucleo.entorno import Entorno
from arkis_lab.nucleo.motor import Accion, Partida

A, B, I, D = Accion.ARRIBA, Accion.ABAJO, Accion.IZQUIERDA, Accion.DERECHA


def sit(segs, dir_, manzana):
    return situacion_de(Partida.desde_estado("medio", 0, segs, dir_, manzana))


def test_hechos_del_ejemplo_de_la_especificacion():
    # Manzana a la derecha y casilla derecha libre.
    h = hechos(percepcion_de(sit([(3, 3), (2, 3), (1, 3)], D, (6, 3))))
    assert {"libre", "acerca", "recto"} <= h[D]
    assert "aleja" in h[A] and "choque_cuerpo" in h[I]


def test_regla_de_la_especificacion_y_explicacion():
    base = BaseConocimiento([Regla(["libre", "acerca", "!choque_limite"], "preferir", accion="derecha")])
    a, exp = base.inferir(percepcion_de(sit([(3, 3), (2, 3), (1, 3)], D, (6, 3))))
    assert a is D and not exp["sin_conocimiento"]
    assert exp["disparos"][0]["texto"].startswith("SI libre(X) Y acerca(X)")
    assert "ganadora" in exp and exp["hechos"]["derecha"]


def test_lerk_empieza_vacio_y_no_sabe():
    a, exp = BaseConocimiento().inferir(percepcion_de(sit([(3, 3)], D, (6, 3))), random.Random(0))
    assert exp["sin_conocimiento"]


def test_excepcion_ripple_down_y_prohibicion():
    padre = Regla(["libre", "acerca"], "preferir")
    base = BaseConocimiento([padre])
    base.agregar(Regla(["encierro"], "anular", padre=padre.id))
    base.agregar(Regla(["choque_limite"], "prohibir", prioridad=5))
    # Cabeza en la fila 0: arriba sale del tablero; la manzana arriba-izquierda.
    perc = percepcion_de(sit([(4, 0), (5, 0), (6, 0)], I, (1, 5)))
    a, exp = base.inferir(perc, random.Random(0))
    assert "arriba" in exp["prohibidas"] or "arriba" not in exp["hechos"]
    assert a in (I, B)


def test_conflicto_prohibicion_vs_preferencia():
    base = BaseConocimiento([Regla(["acerca"], "preferir"), Regla(["borde"], "prohibir")])
    perc = percepcion_de(sit([(1, 3)], D, (0, 3)))          # acercarse es ir al borde
    _, exp = base.inferir(perc, random.Random(0))
    assert any("gana la prohibición" in c for c in exp["conflictos"])


def test_induccion_por_cobertura_generaliza():
    """Instancias sintéticas: el concepto es libre ∧ acerca. La inducción lo recupera."""
    rng = random.Random(0)
    preds = ["libre", "acerca", "recto", "borde", "aleja"]
    inst = []
    for _ in range(300):
        v = frozenset(p for p in preds if rng.random() < 0.5)
        inst.append(aprendizaje.Instancia(v, {"libre", "acerca"} <= v))
    reglas = aprendizaje.inducir(inst, "preferir", "induccion")
    assert reglas and set(reglas[0].condiciones) == {"libre", "acerca"}
    assert reglas[0].confianza > 0.9


def test_correccion_crea_excepcion_y_cambia_la_decision():
    base = BaseConocimiento([Regla(["acerca"], "preferir")])
    s = sit([(1, 1), (2, 1), (3, 1)], I, (0, 6))     # izquierda y abajo acercan
    elegida, _ = base.inferir(percepcion_de(s), random.Random(0))
    correcta = B if elegida is not B else I
    cambios = aprendizaje.corregir(base, s, correcta.etiqueta)
    assert cambios["elegida_despues"] == correcta.etiqueta
    assert cambios["excepcion"] is not None and cambios["excepcion"]["padre"]


def test_generalizar_elimina_condiciones_innecesarias():
    base = BaseConocimiento([Regla(["libre", "acerca", "recto"], "preferir", origen="induccion")])
    casos = []
    ent = Entorno("medio")
    perc = ent.reiniciar(1)
    rng = random.Random(1)
    while not ent.terminado and len(casos) < 80:
        a = politica_voraz(perc, rng)
        casos.append({"situacion": situacion_de(ent.partida), "etiqueta": a.etiqueta})
        perc = ent.paso(a).percepcion
    # En estos casos, quitar cualquier condición baja algo la precisión (0,879 → 0,853):
    # con tolerancia 0 la regla no se toca; con 0,03 se generaliza y gana cobertura.
    assert aprendizaje.generalizar(base, casos, tolerancia=0.0) == []
    cambios = aprendizaje.generalizar(base, casos, tolerancia=0.03)
    assert cambios and len(base.reglas[0].condiciones) == 2
    assert cambios[0]["precision"] >= 0.879 - 0.03


def test_lerk_aprende_de_la_experiencia(tmp_path):
    """Partiendo de cero, LERK adquiere reglas a partir de los resultados del simulador y
    pasa a jugar claramente mejor que el azar."""
    svc = ServicioLerk(tmp_path)
    assert not svc.base.reglas
    res = svc.entrenamiento_automatico("medio", episodios=60, epsilon=0.3, semilla=0, bloque=20)
    origenes = {r.origen for r in svc.base.reglas}
    assert origenes == {"experiencia"}
    assert any(r.conclusion == "prohibir" for r in svc.base.reglas)
    assert any(r.conclusion == "preferir" for r in svc.base.reglas)
    s = semillas("validacion", 20)
    lerk = evaluar(svc.agente().politica(), "medio", s).manzanas
    azar = evaluar(politica_azar, "medio", s).manzanas
    assert lerk.ic95[0] > azar.ic95[1]
    # Cada actualización quedó versionada y se recarga igual desde disco
    assert len(svc.almacen.manifiesto()["versiones"]) == 3
    assert len(ServicioLerk(tmp_path).base.reglas) == len(svc.base.reglas)


def test_servicio_edicion_versionada(tmp_path):
    svc = ServicioLerk(tmp_path)
    r = svc.crear_regla({"condiciones": ["libre", "acerca"], "conclusion": "preferir"})
    svc.modificar_regla(r["id"], {"prioridad": 3})
    assert svc.base.buscar(r["id"]).prioridad == 3
    with pytest.raises(ValueError):
        svc.crear_regla({"condiciones": ["inventado"], "conclusion": "preferir"})
    svc.eliminar_regla(r["id"])
    assert not svc.base.reglas
    assert len(svc.almacen.manifiesto()["versiones"]) == 3
    svc.almacen.restaurar("v0002")
    svc.cargar()
    assert svc.base.reglas[0].prioridad == 3
