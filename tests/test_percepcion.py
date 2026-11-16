import random

import numpy as np
import pytest

from ia_snake.nucleo.motor import ACCIONES, Accion, Partida
from ia_snake.nucleo.percepcion import percibir, verificar_sincronia

A, B, I, D = Accion.ARRIBA, Accion.ABAJO, Accion.IZQUIERDA, Accion.DERECHA


@pytest.mark.parametrize("clave", ["facil", "medio", "dificil"])
def test_matriz_y_segmentos_sincronizados_en_partidas_aleatorias(clave):
    rng = random.Random(7)
    for semilla in range(20):
        p = Partida(clave, semilla)
        while p.en_curso and p.pasos < 300:
            c = percibir(p).cuerpo
            assert verificar_sincronia(c)
            assert c.segmentos == p.segmentos
            seguras = [a for a in c.acciones_disponibles if c.colision_por_accion[a] is None]
            p.paso(rng.choice(seguras or list(c.acciones_disponibles)))


def test_colision_por_accion_coincide_con_el_motor():
    rng = random.Random(3)
    for semilla in range(30):
        p = Partida("medio", semilla)
        while p.en_curso and p.pasos < 200:
            perc = percibir(p)
            for a in ACCIONES:
                q = p.clonar()
                r = q.paso(a)
                assert r.colision == perc.cuerpo.colision_por_accion[a]
            p.paso(rng.choice(p.acciones_disponibles()))


def test_sentido_cuerpo_ejemplo():
    segs = [(3, 2), (2, 2), (2, 1), (1, 1)]
    p = Partida.desde_estado("medio", 0, segs, D, (6, 2))
    c = percibir(p).cuerpo
    esperado = np.zeros((8, 8), dtype=np.uint8)
    for x, y in segs:
        esperado[y, x] = 1
    assert (c.matriz == esperado).all()
    assert c.cabeza == (3, 2) and c.cola == (1, 1) and c.longitud == 4
    assert c.direccion is D and c.casillas_libres == 60
    assert I not in c.acciones_disponibles
    with pytest.raises(ValueError):
        c.matriz[0, 0] = 1          # la percepción es de solo lectura


def test_sentido_manzana():
    p = Partida.desde_estado("medio", 0, [(2, 5)], D, (6, 1))
    m = percibir(p).manzana
    assert (m.x, m.y, m.dx, m.dy) == (6, 1, 4, -4)
    assert m.manhattan == 8
    assert m.direccion_relativa == ("arriba", "derecha")
    assert set(m.acciones_que_acercan) == {A, D}


def test_sentido_muros():
    p = Partida.desde_estado("medio", 0, [(0, 6)], D, (5, 5))
    mu = percibir(p).muros
    assert (mu.arriba, mu.abajo, mu.izquierda, mu.derecha) == (6, 1, 0, 7)
    assert mu.colision_limite_por_accion[I] and not mu.colision_limite_por_accion[D]
    assert mu.espacio_libre == 63


def test_espacio_y_cola_alcanzable_detectan_encierro():
    # El cuerpo encierra la esquina superior izquierda; la cola está lejos.
    segs = [(1, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2), (0, 3), (1, 3), (2, 3)]
    p = Partida.desde_estado("medio", 0, segs, I, (7, 7))
    c = percibir(p).cuerpo
    # Única acción sin colisión inmediata: izquierda, que entra en una bolsa (0,0)-(0,1).
    assert [a for a in ACCIONES if c.colision_por_accion[a] is None] == [I]
    assert c.espacio_por_accion[I] == 1          # solo (0,1) además de la nueva cabeza
    assert c.cola_alcanzable_por_accion[I] is False
    assert c.espacio_por_accion[A] == 0 and c.colision_por_accion[A] == "limite"
    # Caso contrario: con la cola junto a la bolsa, la cola sí es alcanzable.
    p2 = Partida.desde_estado("medio", 0, segs[:6], I, (7, 7))
    assert percibir(p2).cuerpo.cola_alcanzable_por_accion[I] is True


def test_a_dict_serializable():
    import json
    p = Partida("dificil", 4)
    json.dumps(percibir(p).a_dict(completa=True))
