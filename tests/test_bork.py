import random

import pytest

from ia_snake.evaluacion.lineas_base import politica_azar
from ia_snake.evaluacion.protocolo import evaluar, semillas
from ia_snake.modelos.bork.qlearning import ConfigBork, TablaQ, estado
from ia_snake.modelos.bork.servicio import ServicioBork
from ia_snake.nucleo.motor import Accion, Partida
from ia_snake.nucleo.percepcion import percibir

A, B, I, D = Accion.ARRIBA, Accion.ABAJO, Accion.IZQUIERDA, Accion.DERECHA


def test_formula_de_actualizacion_exacta():
    t = TablaQ()
    t.fila("s2")[:] = [1.0, 5.0, -2.0, 0.0]
    t.actualizar("s1", D, 2.0 + 0.9 * t.max_q("s2", [A, B, I, D]), alfa=0.5)
    # Q ← 0 + 0.5·(2 + 0.9·5 − 0) = 3.25
    assert t.q["s1"][3] == pytest.approx(3.25)
    t.actualizar("s1", D, 0.0, alfa=0.5)
    assert t.q["s1"][3] == pytest.approx(1.625)
    assert t.visitas["s1"][3] == 2


def test_max_q_solo_sobre_acciones_disponibles():
    t = TablaQ()
    t.fila("s")[:] = [9.0, 1.0, 2.0, 3.0]
    assert t.max_q("s", [B, I, D]) == 3.0


def test_estado_compacto():
    p = percibir(Partida.desde_estado("medio", 0, [(0, 3), (1, 3), (2, 3)], I, (5, 1)))
    s = estado(p)
    peligro, encierro, cola, manz = s.split("|")
    assert peligro == "0011"            # izquierda = límite, derecha = cuello
    assert manz == "+-"                 # manzana a la derecha y arriba
    assert estado(p, "basica") == "0011|+-"


def test_config_valida_parametros():
    with pytest.raises(ValueError):
        ConfigBork(alfa=0)
    with pytest.raises(ValueError):
        ConfigBork(epsilon_inicial=0.1, epsilon_final=0.5)
    with pytest.raises(TypeError):
        ConfigBork(recompensa={"inventada": 1})
    c = ConfigBork(epsilon_inicial=1.0, epsilon_final=0.1, decaimiento=0.5)
    assert c.epsilon(0) == 1.0 and c.epsilon(1) == 0.5 and c.epsilon(10) == 0.1


def test_bork_aprende_por_refuerzo(tmp_path):
    svc = ServicioBork(tmp_path)
    s = semillas("validacion", 20)
    antes = evaluar(svc.agente().politica(), "medio", s).manzanas
    res = svc.entrenar("medio", episodios=250, semilla=0)
    despues = evaluar(svc.agente().politica(), "medio", s).manzanas
    azar = evaluar(politica_azar, "medio", s).manzanas
    assert antes.media < 1                       # sin entrenar no sabe
    assert despues.ic95[0] > azar.ic95[1]        # tras entrenar, muy por encima del azar
    assert res["estados"] > 10 and res["aliasing"]["pares_medidos"] > 0
    assert len(svc.curva) == 250 and svc.curva[-1]["epsilon"] < svc.curva[0]["epsilon"]
    # Continúa desde disco sin perder lo aprendido
    svc2 = ServicioBork(tmp_path)
    assert svc2.episodios_totales == 250 and svc2.tabla.q == svc.tabla.q


def test_reiniciar_no_borra_versiones(tmp_path):
    svc = ServicioBork(tmp_path)
    svc.entrenar("facil", episodios=5)
    with pytest.raises(ValueError):
        svc.configurar({"representacion": "basica"})
    svc.reiniciar_tabla()
    svc.configurar({"representacion": "basica"})
    assert not svc.tabla.q and len(svc.almacen.manifiesto()["versiones"]) == 2
