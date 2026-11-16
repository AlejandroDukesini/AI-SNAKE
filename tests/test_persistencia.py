import json

import pytest

from ia_snake.nucleo.entorno import ResumenEpisodio
from ia_snake.persistencia.almacen import AlmacenModelo, ErrorAlmacen


def resumen(nivel, manzanas, dif="medio"):
    return ResumenEpisodio(dif, 1, 10, manzanas, 3 + manzanas, 5.0, nivel, False, "cuerpo",
                           1.0, {"manzana": 1.0}, 1.0)


def test_versiones_inmutables_y_puntero(tmp_path):
    a = AlmacenModelo("x", tmp_path)
    v1 = a.guardar_version({"f.txt": b"uno"}, "primera", "entrenado")
    v2 = a.guardar_version({"f.txt": b"dos"}, "segunda", "entrenado")
    assert (v1, v2) == ("v0001", "v0002")
    assert a.cargar_version()[1]["f.txt"] == b"dos"
    a.restaurar(v1)
    assert a.cargar_version()[1]["f.txt"] == b"uno"
    assert len(a.manifiesto()["versiones"]) == 2      # restaurar no borra nada
    assert (tmp_path / "x" / "versiones" / v2 / "f.txt").read_bytes() == b"dos"


def test_artefacto_corrupto_retrocede_a_la_ultima_valida(tmp_path):
    a = AlmacenModelo("x", tmp_path)
    a.guardar_version({"f.txt": b"bueno"}, "1", "entrenado")
    v2 = a.guardar_version({"f.txt": b"nuevo"}, "2", "entrenado")
    (tmp_path / "x" / "versiones" / v2 / "f.txt").write_bytes(b"manipulado")
    v, archivos = a.cargar_version()
    assert v == "v0001" and archivos["f.txt"] == b"bueno"
    with pytest.raises(ErrorAlmacen):
        a.cargar_version(v2)


def test_manifiesto_corrupto_se_reconstruye(tmp_path):
    a = AlmacenModelo("x", tmp_path)
    a.guardar_version({"f.txt": b"1"}, "1", "entrenado")
    (tmp_path / "x" / "manifiesto.json").write_text("{roto", encoding="utf-8")
    assert a.manifiesto()["version_actual"] == "v0001"


def test_datos_con_copia_de_seguridad(tmp_path):
    a = AlmacenModelo("x", tmp_path)
    a.escribir_datos("d.json", {"n": 1})
    a.escribir_datos("d.json", {"n": 2})
    (tmp_path / "x" / "datos" / "d.json").write_text("{roto", encoding="utf-8")
    assert a.leer_datos("d.json") == {"n": 1}


def test_record_por_dificultad_nunca_baja(tmp_path):
    a = AlmacenModelo("x", tmp_path)
    assert a.registrar_episodio(resumen(2, 10), "v1", "evaluacion")
    assert not a.registrar_episodio(resumen(1, 4), "v1", "evaluacion")
    a.registrar_episodio(resumen(0, 1, "facil"), "v1", "evaluacion")
    r = a.records()
    assert r["medio"]["nivel"] == 2 and r["facil"]["nivel"] == 0
    assert a.resumen_episodios()["medio"]["n"] == 2


def test_exportar_e_importar_valida_hashes_y_no_borra(tmp_path):
    a = AlmacenModelo("x", tmp_path / "a")
    a.guardar_version({"f.txt": b"hola"}, "1", "entrenado")
    zip_ = a.exportar()
    b = AlmacenModelo("x", tmp_path / "b")
    b.guardar_version({"f.txt": b"propio"}, "propio", "entrenado")
    assert b.importar(zip_) == ["v0002"]
    assert b.cargar_version("v0001")[1]["f.txt"] == b"propio"
    assert b.meta("v0002")["importada"] is True
    with pytest.raises(ErrorAlmacen):
        AlmacenModelo("otro", tmp_path / "c").importar(zip_)
