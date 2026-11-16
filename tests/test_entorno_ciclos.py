import ast
from pathlib import Path

import pytest

from arkis_lab.evaluacion.lineas_base import politica_azar, politica_voraz
from arkis_lab.evaluacion.protocolo import estadistico, evaluar, semillas
from arkis_lab.nucleo.ciclos import (CONFIGURACION_REPETIDA, ConfigCiclos, DetectorCiclos)
from arkis_lab.nucleo.config import DIFICULTADES
from arkis_lab.nucleo.entorno import ConfigEntorno, Entorno
from arkis_lab.nucleo.motor import ACCIONES, CICLO, Accion, Partida
from arkis_lab.nucleo.reloj import RelojSesion, RelojSimulacion

A, B, I, D = Accion.ARRIBA, Accion.ABAJO, Accion.IZQUIERDA, Accion.DERECHA


def ciclo_hamiltoniano(ancho, alto):
    """Ciclo que recorre todas las casillas (requiere alto par): filas en serpentina por las
    columnas 1..ancho-1 y retorno por la columna 0."""
    orden = []
    for y in range(alto):
        xs = range(1, ancho) if y % 2 == 0 else range(ancho - 1, 0, -1)
        orden += [(x, y) for x in xs]
    orden += [(0, y) for y in range(alto - 1, -1, -1)]
    return orden


def politica_hamiltoniana(dificultad):
    orden = ciclo_hamiltoniano(dificultad.ancho, dificultad.alto)
    sig = {orden[i]: orden[(i + 1) % len(orden)] for i in range(len(orden))}
    ant = {v: k for k, v in sig.items()}
    mapa = sig
    p = Partida(dificultad, 0)
    if p.longitud >= 2 and sig[p.cabeza] == p.segmentos[1]:
        mapa = ant          # recorrer el ciclo en sentido contrario

    def politica(perc, rng):
        hx, hy = perc.cuerpo.cabeza
        nx, ny = mapa[(hx, hy)]
        return next(a for a in ACCIONES if (hx + a.dx, hy + a.dy) == (nx, ny))
    return politica


@pytest.mark.parametrize("clave", ["facil", "medio", "dificil"])
def test_e8_es_alcanzable_en_las_tres_dificultades(clave):
    """Prueba constructiva: en tableros pares existe una estrategia que siempre gana, y el
    detector de ciclos no la interrumpe porque recorre casillas nuevas."""
    dif = DIFICULTADES[clave]
    ent = Entorno(dif)
    ent.reiniciar(123)
    pol = politica_hamiltoniana(dif)
    while not ent.terminado:
        ent.paso(pol(ent.percepcion, None))
    res = ent.resumen()
    assert res.victoria and res.causa_fin == "victoria"
    assert res.nivel == 8 and res.longitud_max == dif.casillas and res.ocupacion_max == 100.0
    assert ent.partida.manzana is None


def _bucle_2x2(vel):
    # Longitud 3 dando vueltas a un cuadrado 2×2 lejos de la manzana: ciclo puro.
    p = Partida.desde_estado("medio", 0, [(3, 3), (3, 2), (2, 2)], B, (7, 7))
    ent = Entorno("medio", ConfigEntorno(velocidad_movimiento=vel))
    ent.reiniciar(0, partida=p)
    giro = {B: I, I: A, A: D, D: B}
    a = B
    while not ent.terminado:
        a = giro[a]
        t = ent.paso(a)
    return ent, t


def test_ciclo_termina_tras_30_segundos_de_juego():
    ent, t = _bucle_2x2(10.0)
    assert t.causa_fin == CICLO
    assert ent.limite_ciclo == 300
    assert t.pasos_en_ciclo == 300
    # Detección casi inmediata: a los 4 pasos ya se repite la configuración.
    assert ent.partida.pasos <= 300 + 4
    assert t.recompensa.componentes["fin_por_ciclo"] < 0


def test_el_limite_de_ciclo_escala_con_la_velocidad_del_juego():
    ent, _ = _bucle_2x2(20.0)
    assert ent.limite_ciclo == 600 and ent.partida.causa_fin == CICLO


def test_explorar_sin_comer_no_es_ciclo():
    det = DetectorCiclos(64, ConfigCiclos())
    # Barrido por casillas nuevas: nunca en ciclo.
    for y in range(8):
        e = det.registrar([(y, 0)], (7, 7), D)
        assert not e.en_ciclo and e.casilla_nueva


def test_configuracion_repetida_se_detecta():
    det = DetectorCiclos(64)
    det.reiniciar([(0, 0)], (5, 5))
    det.registrar([(1, 0)], (5, 5), D)
    e = det.registrar([(0, 0)], (5, 5), I)
    assert e.en_ciclo and CONFIGURACION_REPETIDA in e.motivos


def test_reloj_simulacion():
    r = RelojSimulacion(10)
    assert r.segundos(300) == 30.0 and r.pasos_para(30) == 300
    with pytest.raises(ValueError):
        RelojSimulacion(0)


def test_reloj_sesion_no_cuenta_pausas():
    t = [0.0]
    reloj = RelojSesion(fuente=lambda: t[0])
    reloj.iniciar(); t[0] = 10
    reloj.pausar(); t[0] = 100           # 90 s en pausa
    reloj.reanudar(); t[0] = 105
    assert reloj.transcurrido() == 15


def test_retorno_por_componente_se_acumula():
    ent = Entorno("medio")
    ent.reiniciar(5)
    total = 0.0
    while not ent.terminado:
        total += ent.paso(politica_voraz(ent.percepcion, None)).recompensa.total
    res = ent.resumen()
    assert res.retorno == pytest.approx(total)
    assert res.retorno == pytest.approx(sum(res.retorno_por_componente.values()))


def test_evaluacion_reproducible_y_semillas_disjuntas():
    s = semillas("prueba", 10)
    a = evaluar(politica_azar, "medio", s)
    b = evaluar(politica_azar, "medio", s)
    assert [e.pasos for e in a.episodios] == [e.pasos for e in b.episodios]
    assert not set(semillas("entrenamiento", 1000)) & set(semillas("prueba", 1000))
    assert not set(semillas("validacion", 1000)) & set(semillas("prueba", 1000))


def test_voraz_supera_al_azar_en_8x8():
    s = semillas("prueba", 30)
    azar = evaluar(politica_azar, "medio", s).manzanas
    voraz = evaluar(politica_voraz, "medio", s).manzanas
    assert voraz.ic95[0] > azar.ic95[1]


def test_estadistico():
    e = estadistico([1, 2, 3, 4])
    assert e.media == 2.5 and e.mediana == 2.5 and e.ic95[0] < 2.5 < e.ic95[1]


def test_el_nucleo_no_depende_de_modelos_ni_servidor():
    raiz = Path(__file__).resolve().parent.parent / "arkis_lab" / "nucleo"
    prohibidos = ("modelos", "servidor", "persistencia", "evaluacion", "entrenamiento")
    for f in raiz.glob("*.py"):
        for nodo in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(nodo, ast.ImportFrom) and nodo.module:
                partes = nodo.module.split(".")
                assert not any(x in partes for x in prohibidos), f"{f.name}: {nodo.module}"
                assert nodo.level <= 1, f"{f.name} sale del núcleo: {nodo.module}"
            if isinstance(nodo, ast.Import):
                for n in nodo.names:
                    assert not n.name.startswith("arkis_lab."), f"{f.name}: {n.name}"
