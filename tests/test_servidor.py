"""Pruebas de integración del servidor con un directorio de datos temporal."""
import importlib
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("IA_SNAKE_DATOS", str(tmp_path))
    import ia_snake.servidor.app as m
    m = importlib.reload(m)
    return TestClient(m.app)


def esperar(c, id_, limite=120):
    t0 = time.time()
    while time.time() - t0 < limite:
        t = c.get(f"/api/trabajos/{id_}").json()
        if t["estado"] != "en_curso":
            return t
        time.sleep(0.2)
    raise TimeoutError


def test_panel_presenta_los_cinco_modelos(cliente):
    ms = cliente.get("/api/modelos").json()
    assert [m["clave"] for m in ms] == ["arkis", "lerk", "bork", "clark", "mabu"]
    assert all(m["estado"] == "sin_entrenar" for m in ms[:4]) and ms[4]["estado"] == "pendiente"
    cfg = cliente.get("/api/config").json()
    assert cfg["dificultades"]["dificil"]["casillas"] == 256


def test_demostracion_crea_ejemplos_y_arkis_entrena(cliente):
    s = cliente.post("/api/sesiones", json={"modelo": "arkis", "dificultad": "medio",
                                            "semilla": 1, "modo": "demostrar"}).json()
    assert s["percepcion"]["cuerpo"]["matriz"] and s["decision"]["explicacion"]["tipo"] == "sin_entrenar"
    acciones = ["arriba", "arriba", "derecha", "derecha", "abajo", "abajo", "izquierda"]
    for a in acciones:
        r = cliente.post(f"/api/sesiones/{s['id']}/paso", json={"accion": a})
        assert r.status_code == 200, r.text
    assert r.json()["ejemplos_guardados"] == len(acciones)
    r = cliente.post(f"/api/sesiones/{s['id']}/paso", json={"accion": "derecha"})
    assert r.status_code == 400                       # giro de 180°: no disponible
    est = cliente.post("/api/arkis/ejemplos/aprobar", json={"todos_pendientes": True}).json()
    assert est["estadisticas"]["aprobados"] == len(acciones)
    t = cliente.post("/api/modelos/arkis/trabajos",
                     json={"tipo": "entrenar", "parametros": {"aumentar": False, "n_arboles": 10}}).json()
    t = esperar(cliente, t["id"])
    assert t["estado"] == "terminado", t
    m = cliente.get("/api/modelos/arkis").json()
    assert m["version"] == "v0001" and m["estado"] == "entrenado"


def test_observar_bork_y_regla_de_lerk(cliente):
    t = cliente.post("/api/modelos/bork/trabajos",
                     json={"tipo": "entrenar", "parametros": {"dificultad": "facil", "episodios": 20}}).json()
    assert esperar(cliente, t["id"])["estado"] == "terminado"
    s = cliente.post("/api/sesiones", json={"modelo": "bork", "dificultad": "facil", "semilla": 3}).json()
    f = cliente.post(f"/api/sesiones/{s['id']}/paso", json={"pasos": 5}).json()
    assert f["partida"]["pasos"] >= 1 and "estado" in f["decision"]["explicacion"]
    r = cliente.post("/api/lerk/reglas", json={"condiciones": ["libre", "acerca"], "conclusion": "preferir"})
    assert r.status_code == 201 and r.json()["texto"].startswith("SI libre(X)")
    assert cliente.post("/api/lerk/reglas", json={"condiciones": ["x"], "conclusion": "preferir"}).status_code == 400


def test_comparacion_en_las_mismas_semillas(cliente):
    t = cliente.post("/api/comparar", json={"dificultad": "facil", "episodios": 3}).json()
    t = esperar(cliente, t["id"])
    claves = [f["clave"] for f in t["resultado"]["filas"]]
    assert claves == ["arkis", "lerk", "bork", "clark", "base_azar", "base_voraz"]
