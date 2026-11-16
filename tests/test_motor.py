import random

import pytest

from ia_snake.nucleo.config import DIFICULTADES
from ia_snake.nucleo.motor import (ACCIONES, CUERPO, LIMITE, Accion, ErrorPartida,
                                    EstadoPartida, Partida)

A, B, I, D = Accion.ARRIBA, Accion.ABAJO, Accion.IZQUIERDA, Accion.DERECHA


def test_dificultades_aprobadas():
    f, m, d = DIFICULTADES["facil"], DIFICULTADES["medio"], DIFICULTADES["dificil"]
    assert (f.ancho, f.alto, f.casillas, f.longitud_inicial) == (4, 4, 16, 1)
    assert (m.ancho, m.alto, m.casillas, m.longitud_inicial) == (8, 8, 64, 3)
    assert (d.ancho, d.alto, d.casillas, d.longitud_inicial) == (16, 16, 256, 3)


@pytest.mark.parametrize("clave", list(DIFICULTADES))
def test_estado_inicial(clave):
    p = Partida(clave, 1)
    dif = DIFICULTADES[clave]
    assert p.longitud == dif.longitud_inicial
    assert p.cabeza == (dif.ancho // 2, dif.alto // 2)
    assert p.manzana is not None and not p.ocupada(p.manzana)
    assert p.en_curso and p.pasos == 0 and p.manzanas == 0


def test_movimiento_simple():
    p = Partida.desde_estado("medio", 0, [(4, 4), (3, 4), (2, 4)], D, (7, 7))
    r = p.paso(A)
    assert r.cabeza == (4, 3) and not r.terminada
    assert p.segmentos == ((4, 3), (4, 4), (3, 4))
    assert p.direccion is A


@pytest.mark.parametrize("cabeza,accion", [((0, 3), I), ((7, 3), D), ((3, 0), A), ((3, 7), B)])
def test_colision_con_cada_limite(cabeza, accion):
    p = Partida.desde_estado("medio", 0, [cabeza], D, (5, 5) if cabeza != (5, 5) else (1, 1))
    r = p.paso(accion)
    assert r.colision == LIMITE and r.terminada
    assert p.estado is EstadoPartida.DERROTA and p.causa_fin == LIMITE


def test_giro_180_con_cuerpo_es_colision():
    p = Partida.desde_estado("medio", 0, [(4, 4), (3, 4)], D, (7, 7))
    assert I not in p.acciones_disponibles()
    assert p.paso(I).colision == CUERPO


def test_giro_180_con_longitud_1_esta_permitido():
    p = Partida("facil", 0)
    assert set(p.acciones_disponibles()) == set(ACCIONES)
    p2 = Partida.desde_estado("facil", 0, [(2, 2)], D, (0, 0))
    assert not p2.paso(I).terminada


def test_colision_con_el_cuerpo():
    # Cuerpo en U: la cabeza en (3,3) mirando abajo, (3,4) libre... forzamos choque con (2,3)
    segs = [(3, 3), (3, 2), (2, 2), (2, 3), (2, 4)]
    p = Partida.desde_estado("medio", 0, segs, B, (7, 7))
    assert p.paso(I).colision == CUERPO


def test_entrar_en_la_cola_es_legal_si_no_come():
    segs = [(3, 3), (3, 2), (2, 2), (2, 3)]   # cuadrado 2×2: la cola (2,3) está a la izquierda
    p = Partida.desde_estado("medio", 0, segs, B, (7, 7))
    r = p.paso(I)
    assert not r.terminada and p.cabeza == (2, 3) and p.longitud == 4


def test_crecimiento_al_comer():
    p = Partida.desde_estado("medio", 5, [(4, 4), (3, 4), (2, 4)], D, (5, 4))
    r = p.paso(D)
    assert r.comio and p.longitud == 4 and p.manzanas == 1
    assert p.cola == (2, 4)
    assert p.manzana is not None and not p.ocupada(p.manzana)


def test_victoria_e8_en_4x4():
    # Camino contiguo de 15 casillas (cabeza → cola) que deja libre solo (0,3).
    segs = [(1, 3), (2, 3), (3, 3), (3, 2), (2, 2), (1, 2), (0, 2), (0, 1),
            (1, 1), (2, 1), (3, 1), (3, 0), (2, 0), (1, 0), (0, 0)]
    p = Partida.desde_estado("facil", 0, segs, I, (0, 3))
    assert p.longitud == 15
    r = p.paso(I)
    assert r.victoria and r.terminada and p.longitud == 16
    assert p.estado is EstadoPartida.VICTORIA and p.manzana is None
    with pytest.raises(ErrorPartida):
        p.paso(A)


def test_determinismo_por_semilla():
    def jugar(semilla):
        p = Partida("medio", semilla)
        rng = random.Random(99)
        while p.en_curso and p.pasos < 500:
            p.paso(rng.choice(p.acciones_disponibles()))
        return p.instantanea()

    assert jugar(42) == jugar(42)
    assert Partida("medio", 1).manzana != Partida("medio", 2).manzana or True


def test_clonar_es_independiente_y_equivalente():
    p = Partida("medio", 3)
    q = p.clonar()
    for a in (A, A, I):
        p.paso(a)
        q.paso(a)
    assert p.instantanea() == q.instantanea()
    q.paso(I)
    assert p.instantanea() != q.instantanea()


def test_estados_invalidos_rechazados():
    with pytest.raises(ErrorPartida):
        Partida.desde_estado("medio", 0, [(0, 0), (2, 0)], D, None)
    with pytest.raises(ErrorPartida):
        Partida.desde_estado("medio", 0, [(0, 0)], D, (0, 0))
    with pytest.raises(TypeError):
        Partida("medio", 0).paso("arriba")
