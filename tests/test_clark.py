import random

import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier

from ia_snake.evaluacion.lineas_base import politica_azar
from ia_snake.evaluacion.protocolo import evaluar, semillas
from ia_snake.modelos.bork.qlearning import TablaQ, estado
from ia_snake.modelos.bosque_rapido import BosqueRapido
from ia_snake.modelos.clark.hibrido import ClarkAgente, Componentes, ConfigClark
from ia_snake.modelos.clark.servicio import ServicioClark
from ia_snake.modelos.lerk.conocimiento import BaseConocimiento, Regla
from ia_snake.modelos.situacion import situacion_de
from ia_snake.nucleo.motor import Accion, Partida
from ia_snake.nucleo.percepcion import percibir

A, B, I, D = Accion.ARRIBA, Accion.ABAJO, Accion.IZQUIERDA, Accion.DERECHA


@pytest.mark.parametrize("cw", [None, "balanced"])
def test_bosque_rapido_identico_a_sklearn(cw):
    rng = np.random.default_rng(0)
    X = rng.random((2000, 8))
    y = (X[:, 0] + rng.normal(0, 0.3, 2000) > 0.5).astype(int)
    m = RandomForestClassifier(30, min_samples_leaf=3, class_weight=cw, random_state=0).fit(X, y)
    Xt = np.vstack([rng.random((300, 8)), X[:50]])
    assert np.array_equal(m.predict_proba(Xt), BosqueRapido(m).predict_proba(Xt))


def percepcion():
    return percibir(Partida.desde_estado("medio", 0, [(3, 3), (2, 3), (1, 3)], D, (6, 3)))


def test_sin_entrenar_las_opiniones_son_neutras():
    ag = ClarkAgente(Componentes(None, BaseConocimiento(), TablaQ()), ConfigClark())
    d = ag.decidir(percepcion(), random.Random(0))
    comp = d.explicacion["componentes"]
    assert set(comp["ml"].values()) == {0.5}
    assert set(comp["simbolico"].values()) == {0.0}
    assert not d.explicacion["ml_entrenado"] and not d.explicacion["estado_conocido"]


def test_el_veto_simbolico_prevalece_sobre_la_puntuacion():
    p = percepcion()
    q = TablaQ()
    q.fila(estado(p))[:] = [0.0, 0.0, 0.0, 100.0]       # el refuerzo adora 'derecha'
    base = BaseConocimiento([Regla([], "prohibir", accion="derecha")])
    d = ClarkAgente(Componentes(None, base, q), ConfigClark()).decidir(p, random.Random(0))
    assert d.accion is not D and d.explicacion["vetos"] == ["derecha"]
    assert not d.explicacion["acuerdo"]["refuerzo"]
    assert d.explicacion["conflictos"]


def test_si_todo_esta_vetado_se_ignoran_los_vetos():
    base = BaseConocimiento([Regla([], "prohibir")])
    d = ClarkAgente(Componentes(None, base, TablaQ()), ConfigClark()).decidir(percepcion(), random.Random(0))
    assert any("todas" in c for c in d.explicacion["conflictos"])


def test_pesos_determinan_la_integracion():
    p = percepcion()
    q = TablaQ()
    q.fila(estado(p))[:] = [0.0, 0.0, 0.0, 50.0]
    base = BaseConocimiento([Regla([], "preferir", accion="arriba", origen="experiencia")])
    solo_q = ConfigClark(peso_ml=0, peso_simbolico=0, peso_refuerzo=1)
    solo_b = ConfigClark(peso_ml=0, peso_simbolico=1, peso_refuerzo=0)
    comp = Componentes(None, base, q)
    assert ClarkAgente(comp, solo_q).decidir(p, random.Random(0)).accion is D
    assert ClarkAgente(comp, solo_b).decidir(p, random.Random(0)).accion is A
    with pytest.raises(ValueError):
        ConfigClark(peso_ml=0, peso_simbolico=0, peso_refuerzo=0)


def test_el_conocimiento_del_usuario_restringe_la_eleccion():
    p = percepcion()
    q = TablaQ()
    q.fila(estado(p))[:] = [0.0, 0.0, 0.0, 50.0]
    base = BaseConocimiento([Regla([], "preferir", accion="arriba", origen="usuario")])
    d = ClarkAgente(Componentes(None, base, q), ConfigClark()).decidir(p, random.Random(0))
    assert d.accion is A and d.explicacion["restriccion_usuario"] == ["arriba"]


def test_clark_empieza_sin_entrenar_y_aprende(tmp_path):
    svc = ServicioClark(tmp_path)
    assert svc.version is None and svc.resumen()["estado"] == "sin_entrenar"
    res = svc.entrenamiento_automatico("medio", episodios=80, semilla=0, bloque=40)
    assert res["componentes"]["ml"]["entrenado"]
    assert svc.comp.simbolico.reglas and svc.comp.refuerzo.q
    s = semillas("validacion", 20)
    clark = evaluar(svc.agente().politica(), "medio", s).manzanas
    azar = evaluar(politica_azar, "medio", s).manzanas
    assert clark.ic95[0] > azar.ic95[1]
    # Recarga desde disco con los tres componentes
    svc2 = ServicioClark(tmp_path)
    assert svc2.comp.ml is not None and len(svc2.comp.refuerzo.q) == len(svc.comp.refuerzo.q)
    # Corrección manual: afecta a ML y simbólico, nunca a la tabla Q
    q_antes = {k: list(v) for k, v in svc2.comp.refuerzo.q.items()}
    sit = situacion_de(Partida("medio", 5))
    cambios = svc2.corregir(sit, "arriba")
    assert cambios["elegida_despues"] == "arriba"
    assert svc2.comp.refuerzo.q == q_antes


def test_clark_no_comparte_nada_con_lerk_ni_bork(tmp_path):
    from ia_snake.modelos.bork.servicio import ServicioBork
    from ia_snake.modelos.lerk.servicio import ServicioLerk
    lerk, bork, clark = ServicioLerk(tmp_path), ServicioBork(tmp_path), ServicioClark(tmp_path)
    lerk.crear_regla({"condiciones": ["libre"], "conclusion": "preferir"})
    bork.entrenar("facil", episodios=3)
    assert clark.comp.simbolico is not lerk.base and not clark.comp.simbolico.reglas
    assert clark.comp.refuerzo is not bork.tabla and not clark.comp.refuerzo.q
    assert {p.name for p in tmp_path.iterdir()} >= {"lerk", "bork", "clark"}
