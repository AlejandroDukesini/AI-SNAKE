"""La visualización del entrenamiento muestra lo que realmente ocurre y no lo altera."""
import importlib
import threading
import time

from fastapi.testclient import TestClient

from ia_snake.evaluacion.protocolo import evaluar, semillas
from ia_snake.modelos.bork.servicio import ServicioBork
from ia_snake.modelos.clark.servicio import ServicioClark
from ia_snake.modelos.lerk.servicio import ServicioLerk
from ia_snake.modelos.observacion import Observador


def test_observar_y_frenar_no_cambia_el_entrenamiento(tmp_path):
    """Mismo entrenamiento de BORK sin observador, con observador al máximo y con ritmo
    limitado: la tabla Q resultante es idéntica."""
    a = ServicioBork(tmp_path / "a")
    a.entrenar("facil", episodios=25, semilla=3)
    b = ServicioBork(tmp_path / "b")
    b.entrenar("facil", episodios=25, semilla=3, observador=Observador(0))
    c = ServicioBork(tmp_path / "c")
    c.entrenar("facil", episodios=3, semilla=3, observador=Observador(2000))
    c2 = ServicioBork(tmp_path / "c2")
    c2.entrenar("facil", episodios=3, semilla=3)
    assert a.tabla.q == b.tabla.q
    assert c.tabla.q == c2.tabla.q


def test_fotogramas_de_bork_son_las_decisiones_reales(tmp_path):
    svc = ServicioBork(tmp_path)
    obs = Observador(0)
    svc.entrenar("medio", episodios=4, semilla=1, observador=obs)
    f = obs.fotograma
    exp = f["decision"]["explicacion"]
    assert f["decision"]["accion"] == f["transicion"]["accion"]
    assert exp["tipo"] == "valores_q" and len(exp["q_antes"]) == 4
    # El Q mostrado "después" es el que quedó en la tabla (o fue actualizado después)
    assert exp["estado"] in svc.tabla.q
    assert len(obs.episodios) == 4
    ep = obs.episodios[-1]
    assert ep["pasos"] == ep["acerca"] + ep["aleja"] + (ep["pasos"] - ep["acerca"] - ep["aleja"])
    assert {"manzanas", "longitud", "ocupacion", "retorno", "epsilon"} <= set(ep)
    assert f["transicion"]["movimiento"] in ("acerca", "aleja", "igual", "come", "colision")


def test_lerk_y_clark_exponen_su_metodologia(tmp_path):
    lerk = ServicioLerk(tmp_path)
    o1 = Observador(0)
    lerk.entrenamiento_automatico("facil", episodios=10, epsilon=0.3, bloque=5, observador=o1)
    assert o1.fotograma["decision"]["explicacion"]["tipo"] == "cadena_inferencia"
    assert o1.contexto["aprendizajes"] and "reglas" in o1.contexto
    clark = ServicioClark(tmp_path)
    o2 = Observador(0)
    clark.entrenamiento_automatico("facil", episodios=6, bloque=3, observador=o2)
    e = o2.fotograma["decision"]["explicacion"]
    assert e["tipo"] == "hibrido" and set(e["componentes"]) == {"ml", "simbolico", "refuerzo"}
    assert set(o2.fotograma["extra"]["chocaria_por_componente"]) == {"ml", "simbolico", "refuerzo"}
    assert "choques_evitables_por_componente" in o2.episodios[-1]


def test_evaluacion_observada_da_los_mismos_resultados(tmp_path):
    svc = ServicioBork(tmp_path)
    svc.entrenar("medio", episodios=30, semilla=0)
    lista = semillas("validacion", 6)
    normal = [e.manzanas for e in evaluar(svc.agente().politica(), "medio", lista).episodios]
    obs = Observador(0)
    svc.evaluar("medio", episodios=6, observador=obs)
    assert [e["manzanas"] for e in obs.episodios] == normal


def test_pausa_detiene_el_avance_y_reanudar_continua(tmp_path):
    svc = ServicioBork(tmp_path)
    obs = Observador(0)
    obs.pausar()
    hilo = threading.Thread(target=svc.entrenar, args=("facil",),
                            kwargs={"episodios": 5, "observador": obs}, daemon=True)
    hilo.start()
    time.sleep(0.4)
    s1 = obs.secuencia
    time.sleep(0.4)
    assert obs.secuencia == s1 <= 1           # en pausa no avanza
    obs.reanudar()
    hilo.join(30)
    assert not hilo.is_alive() and obs.secuencia > s1


def test_api_vista_y_control(tmp_path, monkeypatch):
    monkeypatch.setenv("IA_SNAKE_DATOS", str(tmp_path))
    import ia_snake.servidor.app as m
    c = TestClient(importlib.reload(m).app)
    t = c.post("/api/modelos/bork/trabajos", json={"tipo": "entrenar", "parametros": {
        "dificultad": "facil", "episodios": 400, "pasos_por_segundo": 50}}).json()
    assert t["observable"]
    time.sleep(0.5)
    v = c.get(f"/api/trabajos/{t['id']}/vista").json()
    assert v["fotograma"]["partida"]["segmentos"] and v["pasos_por_segundo"] == 50
    assert c.post(f"/api/trabajos/{t['id']}/control", json={"accion": "pausar"}).json()["pausado"]
    c.post(f"/api/trabajos/{t['id']}/control", json={"pasos_por_segundo": 0, "accion": "reanudar"})
    assert c.post(f"/api/trabajos/{t['id']}/control", json={"accion": "volar"}).status_code == 400
    c.post(f"/api/trabajos/{t['id']}/control", json={"accion": "detener"})
    for _ in range(100):
        if c.get(f"/api/trabajos/{t['id']}").json()["estado"] != "en_curso":
            break
        time.sleep(0.1)
    assert c.get(f"/api/trabajos/{t['id']}").json()["estado"] in ("cancelado", "terminado")
