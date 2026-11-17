"""Contrato REST: salud, códigos de estado y recursos inexistentes."""
import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def c(tmp_path, monkeypatch):
    monkeypatch.setenv("IA_SNAKE_DATOS", str(tmp_path))
    import ia_snake.servidor.app as m
    return TestClient(importlib.reload(m).app)


def test_health_sin_informacion_sensible(c):
    r = c.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert set(r.json()) == {"status", "service", "version"}


def test_codigos_de_creacion_y_asincronos(c):
    assert c.post("/api/sesiones", json={"modelo": "bork", "dificultad": "facil"}).status_code == 201
    assert c.post("/api/lerk/reglas", json={"condiciones": ["libre"], "conclusion": "preferir"}).status_code == 201
    t = c.post("/api/modelos/bork/trabajos", json={"tipo": "entrenar", "parametros": {"dificultad": "facil", "episodios": 2}})
    assert t.status_code == 202 and t.json()["estado"] == "en_curso"
    assert c.post("/api/modelos/bork/trabajos", json={"tipo": "volar"}).status_code == 400


def test_ejemplo_crear_borrar_204_y_404(c):
    s = c.post("/api/sesiones", json={"modelo": "arkis", "dificultad": "medio", "semilla": 1, "modo": "demostrar"}).json()
    sit = c.get(f"/api/sesiones/{s['id']}/situacion").json()
    e = c.post("/api/arkis/ejemplos", json={"situacion": sit, "etiqueta": "arriba"})
    assert e.status_code == 201
    r = c.delete(f"/api/arkis/ejemplos/{e.json()['id']}")
    assert r.status_code == 204 and r.content == b""
    assert c.delete(f"/api/arkis/ejemplos/{e.json()['id']}").status_code == 404
    assert c.patch("/api/arkis/ejemplos/no-existe", json={"etiqueta": "arriba"}).status_code == 404
    assert c.post("/api/arkis/ejemplos/no-existe/restaurar").status_code == 404
    assert c.post(f"/api/arkis/ejemplos/{e.json()['id']}/restaurar").status_code == 200


def test_recursos_inexistentes_dan_404(c):
    assert c.patch("/api/lerk/reglas/nada", json={"prioridad": 1}).status_code == 404
    assert c.delete("/api/lerk/reglas/nada").status_code == 404
    assert c.get("/api/trabajos/nada").status_code == 404
    assert c.post("/api/trabajos/nada/cancelar").status_code == 404
    assert c.get("/api/trabajos/nada/vista").status_code == 404
    assert c.post("/api/modelos/bork/restaurar", json={"version": "v9999"}).status_code == 404
    assert c.get("/api/modelos/inventado").status_code == 404
    assert c.get("/api/sesiones/nada").status_code == 404


def test_validacion_422_y_400(c):
    assert c.post("/api/sesiones", json={"dificultad": 5, "velocidad": "rápido"}).status_code == 422
    assert c.post("/api/sesiones", json={"modelo": "bork", "dificultad": "imposible"}).status_code == 400
