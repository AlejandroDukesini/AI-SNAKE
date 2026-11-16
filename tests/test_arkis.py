"""ARKIS aprende de ejemplos etiquetados. En las pruebas, el papel del usuario que etiqueta
lo cumple la política voraz (un 'profesor' fijo y conocido); en el laboratorio real las
etiquetas las pone siempre el usuario."""
import random

import numpy as np
import pytest

from arkis_lab.evaluacion.lineas_base import politica_azar, politica_voraz
from arkis_lab.evaluacion.protocolo import estadistico, evaluar, semillas
from arkis_lab.modelos.arkis.caracteristicas import NOMBRES, caracteristicas
from arkis_lab.modelos.arkis.clasificador import ErrorEntrenamiento, entrenar
from arkis_lab.modelos.ejemplos import Dataset, ErrorDataset
from arkis_lab.modelos.arkis.servicio import ServicioArkis
from arkis_lab.modelos.situacion import (SIMETRIAS, percepcion_de, situacion_de,
                                         transformar_accion, transformar_situacion)
from arkis_lab.nucleo.entorno import Entorno
from arkis_lab.nucleo.motor import ACCIONES, Partida


def ejemplos_del_profesor(n_episodios, dificultad="medio", base=0):
    ds = Dataset()
    ent = Entorno(dificultad)
    rng = random.Random(1)
    for s in range(base, base + n_episodios):
        perc = ent.reiniciar(s)
        while not ent.terminado and ent.partida.pasos < 150:
            a = politica_voraz(perc, rng)
            ds.agregar(situacion_de(ent.partida), a.etiqueta, "demostracion", f"ep{s}",
                       ent.partida.pasos)
            perc = ent.paso(a).percepcion
    ds.aprobar([e["id"] for e in ds.ejemplos])
    return ds


def test_caracteristicas_dimension_y_rango():
    v = caracteristicas(percepcion_de(situacion_de(Partida("dificil", 3))))
    assert v.shape == (len(NOMBRES),) == (27,)
    assert np.isfinite(v).all() and v.min() >= -1 and v.max() <= 1


@pytest.mark.parametrize("sim", list(SIMETRIAS))
def test_simetrias_son_exactas(sim):
    p = Partida.desde_estado("medio", 0, [(3, 2), (2, 2), (2, 1), (1, 1)], ACCIONES[3], (6, 5))
    s = situacion_de(p)
    t = transformar_situacion(s, sim, 8)
    po, pt = percepcion_de(s), percepcion_de(t)
    for a in ACCIONES:
        b = transformar_accion(a, sim)
        assert po.cuerpo.colision_por_accion[a] == pt.cuerpo.colision_por_accion[b]
        assert po.cuerpo.espacio_por_accion[a] == pt.cuerpo.espacio_por_accion[b]
    assert po.manzana.manhattan == pt.manzana.manhattan


@pytest.mark.parametrize("sim", list(SIMETRIAS))
def test_simetria_sobre_el_vector_igual_a_recalcular(sim):
    from arkis_lab.modelos.arkis.caracteristicas import transformar_caracteristicas
    rng = random.Random(4)
    for semilla in range(5):
        ent = Entorno("medio")
        perc = ent.reiniciar(semilla)
        for _ in range(30):
            if ent.terminado:
                break
            s = situacion_de(ent.partida)
            v = caracteristicas(percepcion_de(s))
            esperado = caracteristicas(percepcion_de(transformar_situacion(s, sim, 8)))
            assert np.allclose(transformar_caracteristicas(v, sim), esperado)
            perc = ent.paso(politica_voraz(perc, rng)).percepcion


def test_dataset_etiquetas_validas_correccion_y_papelera():
    ds = Dataset()
    sit = situacion_de(Partida.desde_estado("medio", 0, [(4, 4), (3, 4)], ACCIONES[3], (7, 7)))
    with pytest.raises(ErrorDataset):
        ds.agregar(sit, "izquierda", "demostracion", "e1")   # giro al cuello: no disponible
    e = ds.agregar(sit, "arriba", "demostracion", "e1")
    ds.aprobar([e["id"]])
    ds.etiquetar(e["id"], "derecha")
    assert e["etiqueta"] == "derecha" and not e["aprobado"]       # corregir exige reaprobar
    assert e["historial"][0]["etiqueta_anterior"] == "arriba"
    ds.eliminar(e["id"])
    assert ds.estadisticas()["recopilados"] == 0 and len(ds.papelera) == 1
    ds.restaurar(e["id"])
    assert ds.estadisticas()["recopilados"] == 1


def test_requiere_dos_clases():
    ds = Dataset()
    sit = situacion_de(Partida("medio", 0))
    for _ in range(3):
        ds.agregar(sit, "arriba", "demostracion", "e")
    ds.aprobar([e["id"] for e in ds.ejemplos])
    with pytest.raises(ErrorEntrenamiento):
        entrenar(ds.aprobados())


def test_validacion_por_episodio_sin_fugas():
    ds = ejemplos_del_profesor(6)
    res = entrenar(ds.aprobados(), semilla=0, aumentar=False, n_arboles=30)
    val = res.metricas["validacion"]
    assert val["metodo"].startswith("GroupKFold") and val["n"] == len(ds.aprobados())
    assert 0 <= val["accuracy"] <= 1
    assert len(val["matriz_confusion"]["valores"]) == 4


def test_arkis_aprende_de_los_ejemplos():
    """Entrenado con demostraciones, ARKIS imita al profesor en partidas NUEVAS y juega
    mucho mejor que el azar; sin ejemplos no sabe nada."""
    ds = ejemplos_del_profesor(25)
    res = entrenar(ds.aprobados(), semilla=0, aumentar=True, n_arboles=60)
    assert res.metricas["validacion"]["accuracy"] > 0.8
    from arkis_lab.modelos.arkis.clasificador import ArkisAgente
    ag = ArkisAgente(res.modelo)
    s = semillas("validacion", 20)
    arkis = evaluar(ag.politica(), "medio", s).manzanas
    azar = evaluar(politica_azar, "medio", s).manzanas
    assert arkis.ic95[0] > azar.ic95[1]
    sin_entrenar = evaluar(ArkisAgente(None).politica(), "medio", s).manzanas
    assert sin_entrenar.media < 1


def test_servicio_versiones_y_recarga_segura(tmp_path):
    svc = ServicioArkis(tmp_path)
    assert svc.version is None and svc.resumen()["estado"] == "sin_entrenar"
    svc.dataset = ejemplos_del_profesor(4)
    svc.guardar_dataset()
    svc.entrenar(semilla=0, aumentar=False, n_arboles=10)
    assert svc.version == "v0001" and svc.agente().modelo is not None
    # Recarga desde disco (hash verificado → skops confía en el árbol)
    svc2 = ServicioArkis(tmp_path)
    assert svc2.version == "v0001" and svc2.agente().modelo is not None
    assert svc2.dataset.estadisticas()["aprobados"] == len(svc.dataset.aprobados())
    ev = svc2.evaluar("medio", episodios=5)
    assert ev["episodios"] == 5 and svc2.resumen()["estado"] in ("evaluado", "validado")
    # Importado: bloqueado hasta que el usuario confirme
    otro = ServicioArkis(tmp_path / "otro")
    otro.almacen.importar(svc2.almacen.exportar())
    otro.cargar()
    assert otro.bloqueado and otro.agente().modelo is None
    otro.confiar_version_importada()
    assert otro.agente().modelo is not None
