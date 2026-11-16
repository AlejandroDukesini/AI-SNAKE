import pytest

from ia_snake.nucleo import evolucion
from ia_snake.nucleo.recompensas import ConfigRecompensa, calcular_recompensa

CFG = ConfigRecompensa()


def r(**kw):
    base = dict(d_anterior=5, d_actual=4, comio=False, colision=False, victoria=False,
                estado_repetido=False, casilla_nueva=False, fin_por_ciclo=False)
    base.update(kw)
    return calcular_recompensa(CFG, **base)


def test_acercarse_y_alejarse():
    assert r().componentes["distancia"] == pytest.approx(0.1)
    assert r(d_actual=6).componentes["distancia"] == pytest.approx(-0.1)


def test_total_es_la_suma_de_componentes():
    x = r(estado_repetido=True, casilla_nueva=True)
    assert x.total == pytest.approx(sum(x.componentes.values()))


def test_comer_colision_victoria():
    assert r(comio=True).componentes["manzana"] == 10
    assert r(comio=True).componentes["distancia"] == 0      # Δd no comparable tras comer
    c = r(colision=True)
    assert c.componentes["colision"] == -10 and c.componentes["supervivencia"] == 0
    assert r(comio=True, victoria=True).total == pytest.approx(10 + 50 - 0.01)
    assert r(fin_por_ciclo=True).componentes["fin_por_ciclo"] == -5


def test_distancia_no_domina_a_la_colision():
    # Acercarse el máximo posible en un paso nunca compensa una colisión.
    assert CFG.factor_distancia * 1 < abs(CFG.colision)


@pytest.mark.parametrize("casillas,esperado", [
    (16, (0, 2, 4, 6, 8, 10, 12, 14, 16)),
    (64, (0, 8, 16, 24, 32, 40, 48, 56, 64)),
    (256, (0, 32, 64, 96, 128, 160, 192, 224, 256)),
    (225, (0, 29, 57, 85, 113, 141, 169, 197, 225)),   # techo: la fórmula vale con N impar
])
def test_umbrales_C_En(casillas, esperado):
    assert evolucion.tabla_umbrales(casillas) == esperado


def test_nivel_exige_haber_comido():
    assert evolucion.nivel(3, 16, 0) == 0          # longitud inicial no regala nivel
    assert evolucion.nivel(2, 16, 1) == 1           # 4×4: primera manzana → E1
    assert evolucion.nivel(16, 16, 15) == 8
    assert evolucion.nivel(7, 64, 4) == 0
    assert evolucion.nivel(8, 64, 5) == 1
    assert evolucion.ocupacion(32, 64) == 50.0


def test_record_historico_nunca_baja():
    rec = evolucion.RecordHistorico()
    assert rec.registrar("bork", "medio", 2)
    assert not rec.registrar("bork", "medio", 1)
    assert not rec.registrar("bork", "medio", 5, valido=False)
    assert rec.nivel("bork", "medio") == 2
    assert rec.nivel("bork", "facil") == 0          # separado por dificultad
    assert rec.nivel("lerk", "medio") == 0          # separado por modelo
    assert evolucion.RecordHistorico(rec.a_dict()).nivel("bork", "medio") == 2
