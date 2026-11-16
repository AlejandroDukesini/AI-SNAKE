"""Configuración de producción: clave de escritura, CORS y validación al arrancar."""
import importlib

import pytest
from fastapi.testclient import TestClient

from arkis_lab.servidor.ajustes import ErrorConfiguracion, cargar_ajustes

TOKEN = "clave-de-prueba-muy-larga-123"
FRONT = "https://arkis.example.app"


def test_produccion_exige_clave_y_https():
    with pytest.raises(ErrorConfiguracion):
        cargar_ajustes({"APP_ENV": "produccion"})
    with pytest.raises(ErrorConfiguracion):
        cargar_ajustes({"APP_ENV": "produccion", "ARKIS_TOKEN": "corta"})
    with pytest.raises(ErrorConfiguracion):
        cargar_ajustes({"APP_ENV": "produccion", "ARKIS_TOKEN": TOKEN,
                        "CORS_ORIGINS": "http://localhost:5173"})
    with pytest.raises(ErrorConfiguracion):
        cargar_ajustes({"CORS_ORIGINS": "*"})
    a = cargar_ajustes({"APP_ENV": "produccion", "ARKIS_TOKEN": TOKEN,
                        "CORS_ORIGINS": f"{FRONT}/, https://otro.example.app"})
    assert a.origenes_cors == (FRONT, "https://otro.example.app")


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKIS_LAB_DATOS", str(tmp_path))
    monkeypatch.setenv("APP_ENV", "produccion")
    monkeypatch.setenv("ARKIS_TOKEN", TOKEN)
    monkeypatch.setenv("CORS_ORIGINS", FRONT)
    import arkis_lab.servidor.app as m
    yield TestClient(importlib.reload(m).app)
    monkeypatch.delenv("APP_ENV")
    monkeypatch.delenv("ARKIS_TOKEN")
    monkeypatch.delenv("CORS_ORIGINS")
    importlib.reload(m)


def test_lectura_libre_escritura_con_clave(cliente):
    assert cliente.get("/api/modelos").status_code == 200
    assert cliente.get("/api/salud").json()["requiere_clave"] is True
    r = cliente.post("/api/lerk/reglas", json={"condiciones": ["libre"], "conclusion": "preferir"})
    assert r.status_code == 401
    r = cliente.post("/api/lerk/reglas", json={"condiciones": ["libre"], "conclusion": "preferir"},
                     headers={"X-Arkis-Token": "incorrecta"})
    assert r.status_code == 401
    r = cliente.post("/api/lerk/reglas", json={"condiciones": ["libre"], "conclusion": "preferir"},
                     headers={"X-Arkis-Token": TOKEN})
    assert r.status_code == 200
    assert cliente.get("/api/modelos/lerk/exportar").status_code == 401
    assert cliente.get("/api/modelos/lerk/exportar", headers={"X-Arkis-Token": TOKEN}).status_code == 200


def test_cors_solo_para_el_origen_autorizado(cliente):
    pre = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "x-arkis-token"}
    ok = cliente.options("/api/sesiones", headers={"Origin": FRONT, **pre})
    assert ok.headers.get("access-control-allow-origin") == FRONT
    malo = cliente.options("/api/sesiones", headers={"Origin": "https://ajeno.example", **pre})
    assert "access-control-allow-origin" not in malo.headers
    # Un 401 también lleva CORS, para que la interfaz pueda mostrar el motivo
    r = cliente.post("/api/sesiones", json={}, headers={"Origin": FRONT})
    assert r.status_code == 401 and r.headers.get("access-control-allow-origin") == FRONT


def test_produccion_oculta_docs_y_api_inexistente_es_404(cliente):
    r = cliente.get("/openapi.json")
    assert r.status_code == 404 or "application/json" not in r.headers.get("content-type", "")
    r = cliente.get("/api/no-existe")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")
