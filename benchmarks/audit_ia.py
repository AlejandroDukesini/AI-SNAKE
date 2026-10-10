# -*- coding: utf-8 -*-
"""
================================================================================
  AUDITORIA CIENTIFICA DEL NUCLEO DE IA (verificaciones reproducibles)
================================================================================
  Comprobaciones que respaldan docs/auditoria-cientifica-ia.md. No modifica
  `historial/`: solo LEE los especimenes que haya (las pruebas de guardado usan
  una carpeta temporal).

  Dos tipos de bloque, separados a proposito:

  DETERMINISTAS (PASA/FALLA; el proceso sale con codigo 1 si alguno falla)
    A  consistencia matematica (parametros, init He, mutacion, cruce, niveles)
    B  sensores contra una implementacion independiente + invarianza a rotacion
    C  carga de modelos antiguos de 9 entradas: misma decision que la red original
    H  compatibilidad: los especimenes guardados cargan con sus pesos exactos;
       advanced_v1 == codigo de 81aa744; ida y vuelta to_dict/from_dict; errores
       explicitos ante modelos incompatibles o corruptos
    F  estabilidad numerica (estado recurrente, sigmoide, NaN) sin alterar
       las decisiones normales (comparado con el codigo de git HEAD)
    G  casos limite y protocolo: parada a mitad de generacion, record con
       fitness negativo, elitismo, validacion monotona, reproducibilidad,
       guardado en storage

  ESTADISTICOS (informan; no tienen umbral de aprobado)
    D  especimenes guardados vs baselines (azar y voraz), N episodios
    E  entrenamientos cortos con semilla: sesgo del record de un episodio
    (la comparacion original/corregido con varias semillas esta en
     benchmarks/experimento_ia.py)

  Uso:
    python benchmarks/audit_ia.py                    # deterministas (A B C H F G)
    python benchmarks/audit_ia.py --solo D E         # estadisticos (minutos)
    python benchmarks/audit_ia.py --solo A B C H F G D E --episodios 50
================================================================================
"""
import os
import sys
import json
import time
import types
import random
import argparse
import tempfile
import warnings
import subprocess
from collections import deque

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import numpy as np
import snake_neuroevolution as ml

HIST = os.path.join(RAIZ, "historial")
FALLOS = []


def check(nombre, ok, detalle=""):
    print(f"  [{'PASA' if ok else 'FALLA'}] {nombre}" + (f"  ({detalle})" if detalle else ""))
    if not ok:
        FALLOS.append(nombre)


def sembrar(s):
    random.seed(s)
    np.random.seed(s % (2 ** 32))


def modulo_git(commit):
    src = subprocess.check_output(["git", "-C", RAIZ, "show", f"{commit}:snake_neuroevolution.py"]).decode("utf-8")
    m = types.ModuleType(f"ml_{commit}")
    exec(compile(src, m.__name__, "exec"), m.__dict__)
    return m


def especimenes():
    if not os.path.isdir(HIST):
        return []
    out = []
    for carpeta in sorted(os.listdir(HIST)):
        p = os.path.join(HIST, carpeta, "modelo.json")
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                out.append((carpeta, json.load(f)))
    return out


def resumen(v):
    a = np.asarray(v, dtype=float)
    if a.size == 0:
        return "n=0"
    rs = np.random.default_rng(0)
    medias = rs.choice(a, size=(2000, a.size), replace=True).mean(axis=1)
    lo, hi = np.percentile(medias, [2.5, 97.5])
    return (f"media={a.mean():.2f} [IC95 {lo:.2f}-{hi:.2f}] mediana={np.median(a):.1f} "
            f"sd={a.std(ddof=1) if a.size > 1 else 0:.2f} min={a.min():.0f} max={a.max():.0f}")


# =============================================================================
#  Episodios con politicas arbitrarias (red o baseline) y causa de muerte
# =============================================================================
def episodio(snake, politica):
    """Juega hasta morir. Devuelve (frutas, pasos, longitud, causa)."""
    causa = "lleno"
    while snake.alive:
        try:
            accion = politica(snake)
        except ml.NumericalError:
            return snake.fruits, snake.steps, snake.length, "invalido"
        snake._apply_action(accion)
        d = ml.DIRS[snake.dir_i]
        hx, hy = snake.body[0]
        nx, ny = hx + d[0], hy + d[1]       # destino calculado ANTES de mover
        snake.advance()
        if not snake.alive:
            if not (0 <= nx < snake.grid and 0 <= ny < snake.grid):
                causa = "pared"
            elif snake.use_energy and snake.energy <= 0:
                causa = "inanicion"
            else:
                causa = "cuerpo"
    return snake.fruits, snake.steps, snake.length, causa


def pol_red(snake):
    return snake.brain.forward(snake.get_inputs())


def pol_azar(snake):
    return random.randrange(3)


def _destino(snake, accion):
    i = snake.dir_i
    if accion == 1:
        i = (i - 1) % 4
    elif accion == 2:
        i = (i + 1) % 4
    d = ml.DIRS[i]
    return snake.body[0][0] + d[0], snake.body[0][1] + d[1]


def _mortal(snake, x, y):
    if not (0 <= x < snake.grid and 0 <= y < snake.grid):
        return True
    if (x, y) not in snake._body_set:
        return False
    return not ((x, y) == snake.body[-1] and (x, y) != snake.food)


def pol_voraz(snake):
    """Baseline sin aprendizaje: de los 3 giros no mortales, el que mas acerca
    (Manhattan) a la manzana; empate -> el primero (recto)."""
    mejor, mejor_d = 0, None
    for a in (0, 1, 2):
        x, y = _destino(snake, a)
        if _mortal(snake, x, y):
            continue
        dd = abs(snake.food[0] - x) + abs(snake.food[1] - y) if snake.food else 0
        if mejor_d is None or dd < mejor_d:
            mejor, mejor_d = a, dd
    return mejor


def evaluar(politica, grid, n, semilla0, brain=None):
    """Evaluacion del informe original (comida con el generador GLOBAL sembrado
    por episodio). Se mantiene para que las cifras D sean comparables con la
    auditoria anterior."""
    fr, lo, causas = [], [], {}
    for e in range(n):
        sembrar(semilla0 + e)
        s = ml.Snake(brain.clone() if brain is not None else ml.make_brain(), grid=grid)
        f, p, l, c = episodio(s, politica)
        fr.append(f); lo.append(l)
        causas[c] = causas.get(c, 0) + 1
    cob = [ml.cobertura(l, grid) for l in lo]
    niveles = {}
    for c in cob:
        k = ml.nivel_de_cobertura(c)["nivel"]
        niveles[k] = niveles.get(k, 0) + 1
    return {"frutas": fr, "cob": cob, "causas": causas, "niveles": niveles}


# =============================================================================
#  A. Consistencia matematica
# =============================================================================
def bloque_a():
    print("\n[A] CONSISTENCIA MATEMATICA")
    esperados = {"advanced": 483, "intermated": 1003, "basic": 2809, "advanced_v1": 1443}
    for nombre, cls in {**ml.ENGINES, **ml.LEGACY_ENGINES}.items():
        n = sum(w.size for w in cls().get_weights())
        check(f"parametros {nombre} = {esperados[nombre]}", n == esperados[nombre], f"{n}")

    rng = np.random.default_rng(1)
    W = np.concatenate([ml.AdvancedNetwork(rng=rng).W1.ravel() for _ in range(400)])
    check("init He: sd de W1 ~ sqrt(2/26)", abs(W.std() - np.sqrt(2 / 26)) < 0.005,
          f"{W.std():.4f} vs {np.sqrt(2/26):.4f}")

    rng = np.random.default_rng(2)
    base = ml.AdvancedNetwork(rng=rng)
    cambios, ruido = [], []
    for _ in range(300):
        hijo = ml.mutate(base, std=0.2, rng=rng)
        for a, b in zip(base.get_weights(), hijo.get_weights()):
            d = (b - a).ravel()
            cambios.append(np.mean(d != 0))
            ruido.extend(d[d != 0])
    check("mutacion: 5 % de pesos, sd 0.20", abs(np.mean(cambios) - 0.05) < 0.003 and abs(np.std(ruido) - 0.2) < 0.01,
          f"{np.mean(cambios):.4f}, {np.std(ruido):.4f}")

    pa, pb = ml.AdvancedNetwork(rng=rng), ml.AdvancedNetwork(rng=rng)
    hijo = ml.crossover(pa, pb, rng=rng)
    de_a = de_b = otro = 0
    for a, b, h in zip(pa.get_weights(), pb.get_weights(), hijo.get_weights()):
        de_a += np.sum(h == a); de_b += np.sum((h == b) & (h != a)); otro += np.sum((h != a) & (h != b))
    check("cruce uniforme: cada gen de un padre, ~50 %", otro == 0 and abs(de_a / (de_a + de_b) - 0.5) < 0.06,
          f"A={de_a} B={de_b} ajenos={otro}")

    tabla = {8: [7, 13, 23, 36, 52], 10: [10, 20, 35, 55, 80], 15: [23, 45, 79, 124, 180]}
    for g in ml.GRID_SIZES:
        fila = [next(L for L in range(1, g * g + 1)
                     if ml.nivel_de_cobertura(ml.cobertura(L, g))["nivel"] >= nivel)
                for nivel in range(1, 6)]
        check(f"longitud minima N1..N5 en {g}x{g} = tabla de ROADMAP", fila == tabla[g], str(fila))


# =============================================================================
#  B. Sensores frente a una implementacion independiente
# =============================================================================
def sensores_ref(s):
    """Recalculo independiente de las 26 entradas (geometria explicita)."""
    g = s.grid
    hx, hy = s.body[0]
    cuerpo = set(s.body)
    fx, fy = ml.DIRS[s.dir_i]
    rx, ry = -fy, fx            # 90 grados horario en pantalla
    lx, ly = fy, -fx
    bx, by = -fx, -fy
    rayos = [(fx, fy), (fx + rx, fy + ry), (rx, ry), (bx + rx, by + ry),
             (bx, by), (bx + lx, by + ly), (lx, ly), (fx + lx, fy + ly)]
    pared, cue, com = [], [], []
    for dx, dy in rayos:
        k = 0
        while 0 <= hx + (k + 1) * dx < g and 0 <= hy + (k + 1) * dy < g:
            k += 1
        pared.append(k / g)
        v = 0.0
        for paso in range(1, k + 1):
            if (hx + paso * dx, hy + paso * dy) in cuerpo:
                v = 1.0 - (paso - 1) / g
                break
        cue.append(v)
        if s.food is None:
            com.append(0.0)
        else:
            vx, vy = s.food[0] - hx, s.food[1] - hy
            nv = np.hypot(vx, vy) or 1.0
            com.append((vx * dx + vy * dy) / (nv * np.hypot(dx, dy)))
    vistos = {(hx, hy)}
    q = deque([(hx, hy)])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if 0 <= n[0] < g and 0 <= n[1] < g and n not in cuerpo and n not in vistos:
                vistos.add(n); q.append(n)
    libre = (len(vistos) - 1) / (g * g)
    return np.array(pared + cue + com + [len(s.body) / (g * g), libre])


def rotar(s):
    """Copia de la serpiente girada 90 grados horario (pantalla)."""
    g = s.grid
    t = ml.Snake(s.brain, grid=g, rng=random.Random(0))
    f = lambda c: (g - 1 - c[1], c[0])
    t.body = [f(c) for c in s.body]
    t._body_set = set(t.body)
    t.food = f(s.food) if s.food else None
    t.dir_i = (s.dir_i + 1) % 4
    return t


def bloque_b(n_estados=3000):
    print("\n[B] SENSORES vs IMPLEMENTACION INDEPENDIENTE")
    peor, peor_rot, n = 0.0, 0.0, 0
    sembrar(3)
    for gi, g in enumerate(ml.GRID_SIZES):
        tope = n_estados * (gi + 1) // 3
        while n < tope:
            s = ml.Snake(grid=g)
            while s.alive and n < tope:
                x = s.get_inputs()
                peor = max(peor, float(np.max(np.abs(x - sensores_ref(s)))))
                peor_rot = max(peor_rot, float(np.max(np.abs(x - rotar(s).get_inputs()))))
                n += 1
                s._apply_action(pol_voraz(s) if random.random() < 0.8 else pol_azar(s))
                s.advance()
    check(f"26 sensores == implementacion independiente ({n} estados)", peor < 1e-12, f"max {peor:.1e}")
    check("invarianza a rotacion de 90 grados", peor_rot == 0.0, f"max {peor_rot:.1e}")
    vals = []
    for g in ml.GRID_SIZES:
        s = ml.Snake(grid=g, rng=random.Random(0))
        s.body = [(g - 2, g // 2), (g - 3, g // 2), (g - 4, g // 2)]
        s._body_set = set(s.body); s.dir_i = 1; s.food = (0, 0)
        vals.append(round(float(s.get_inputs()[0]), 3))
    print(f"  (informativo) pared a 1 casilla en 8/10/15: {vals} -> el sensor NO es invariante a escala")


# =============================================================================
#  C. Carga de modelos antiguos (9 entradas -> 26)
# =============================================================================
def entradas_antiguas(s):
    """Las 9 entradas de la version original: pared/cuerpo/comida en F, I, D."""
    head = s.body[0]
    f, l, r = ml.DIRS[s.dir_i], ml.DIRS[(s.dir_i - 1) % 4], ml.DIRS[(s.dir_i + 1) % 4]
    wall = [s._wall_distance(head, d) for d in (f, l, r)]
    body = [s._body_distance(head, d) for d in (f, l, r)]
    vx, vy = s.food[0] - head[0], s.food[1] - head[1]
    nv = (vx * vx + vy * vy) ** 0.5 or 1.0
    food = [(vx * d[0] + vy * d[1]) / nv for d in (f, l, r)]
    return np.array(wall + body + food)


def bloque_c(n_estados=4000):
    print("\n[C] CARGA ADAPTATIVA DE MODELOS ANTIGUOS (mejores_ias.json)")
    ruta = os.path.join(RAIZ, "mejores_ias.json")
    if not os.path.isfile(ruta):
        print("  (no hay mejores_ias.json: no verificable)")
        return
    with open(ruta, encoding="utf-8") as f:
        viejos = json.load(f)
    for v in viejos:
        W1, b1 = np.array(v["pesos"]["W1"]), np.array(v["pesos"]["b1"])
        W2, b2 = np.array(v["pesos"]["W2"]), np.array(v["pesos"]["b2"])
        vieja = lambda x: int(np.argmax(W2 @ np.maximum(0, W1 @ x + b1) + b2))
        nueva = ml.brain_from_dict(v["pesos"])
        iguales = total = 0
        s = ml.Snake(nueva.clone(), grid=8, rng=random.Random(4))
        while total < n_estados // 4:
            if not s.alive or s.food is None:
                s = ml.Snake(nueva.clone(), grid=8, rng=random.Random(total))
            a_old = vieja(entradas_antiguas(s))
            a_new = s.brain.forward(s.get_inputs())
            iguales += (a_old == a_new); total += 1
            s._apply_action(a_old); s.advance()
        if iguales != total:
            check(f"{v.get('nombre')}: misma decision", False, f"{iguales}/{total}")
    check(f"{len(viejos)} modelos de 9 entradas: misma decision que la red original en todos los estados",
          not any("misma decision" in f for f in FALLOS))
    # 10 entradas (version bf1b2e3): red sintetica, porque no hay ninguna guardada
    rng = np.random.default_rng(5)
    W1, b1 = rng.standard_normal((12, 10)), rng.standard_normal(12)
    W2, b2 = rng.standard_normal((3, 12)), rng.standard_normal(3)
    nueva = ml.brain_from_dict({"W1": W1.tolist(), "b1": b1.tolist(), "W2": W2.tolist(), "b2": b2.tolist()})
    iguales = total = 0
    s = ml.Snake(nueva.clone(), grid=10, rng=random.Random(6))
    while total < 2000:
        if not s.alive or s.food is None:
            s = ml.Snake(nueva.clone(), grid=10, rng=random.Random(total))
        x10 = np.append(entradas_antiguas(s), s._length_sensor())
        a_old = int(np.argmax(W2 @ np.maximum(0, W1 @ x10 + b1) + b2))
        iguales += (a_old == s.brain.forward(s.get_inputs())); total += 1
        s._apply_action(a_old); s.advance()
    check("red SINTETICA de 10 entradas: misma decision tras adaptarla", iguales == total, f"{iguales}/{total}")


# =============================================================================
#  H. Compatibilidad y preservacion de pesos
# =============================================================================
def bloque_h():
    print("\n[H] COMPATIBILIDAD DE MODELOS")
    esp = especimenes()
    if not esp:
        print("  (no hay historial/: carga de especimenes no verificable)")
    for carpeta, m in esp:
        p = m["pesos"]
        try:
            b = ml.brain_from_dict(p)
            ident = (set(b._keys()) == {k for k in p if k != "engine"} and
                     all(np.array_equal(np.array(p[k]), getattr(b, k)) for k in b._keys()))
            check(f"{carpeta}: carga como {b.NAME} con los pesos EXACTOS", ident)
            d2 = b.to_dict()
            b2 = ml.brain_from_dict(json.loads(json.dumps(d2)))
            check(f"{carpeta}: ida y vuelta to_dict -> JSON -> from_dict sin cambios",
                  type(b2) is type(b) and all(np.array_equal(getattr(b, k), getattr(b2, k)) for k in b._keys()))
        except ml.ModelError as exc:
            check(f"{carpeta}: carga", False, str(exc))

    viejo = modulo_git("81aa744")
    adv = [(c, m) for c, m in esp if ml.AdvancedV1Network.matches(m["pesos"])]
    rng = np.random.default_rng(1)
    X = rng.random((5000, ml.N_INPUTS)) * 2 - 1
    for carpeta, m in adv:
        nuevo = ml.brain_from_dict(m["pesos"]); ref = viejo.AdvancedNetwork.from_dict(m["pesos"])
        iguales = sum(nuevo.forward(x) == ref.forward(x) for x in X)
        check(f"{carpeta}: advanced_v1 decide igual que AdvancedNetwork de 81aa744", iguales == len(X),
              f"{iguales}/{len(X)}")

    base = {"W1": np.zeros((16, 26)).tolist(), "b1": [0] * 16, "W2": np.zeros((3, 16)).tolist(), "b2": [0] * 3}
    malos = {
        "formas de otra arquitectura": {**base, "engine": "advanced", "W1": np.zeros((7, 26)).tolist()},
        "NaN en los pesos": {**base, "engine": "advanced", "W1": np.full((16, 26), np.nan).tolist()},
        "inf en los pesos": {**base, "engine": "advanced", "b2": [0, float("inf"), 0]},
        "falta una matriz": {k: v for k, v in base.items() if k != "b2"} | {"engine": "advanced"},
        "motor desconocido": {**base, "engine": "xyz"},
        "intermated con 30 neuronas (no convertible sin perder)": {
            "W1": np.zeros((30, 26)).tolist(), "b1": [0] * 30, "W2": np.zeros((3, 30)).tolist(), "b2": [0] * 3},
        "intermated con 15 entradas (disposicion desconocida)": {
            "W1": np.zeros((12, 15)).tolist(), "b1": [0] * 12, "W2": np.zeros((3, 12)).tolist(), "b2": [0] * 3},
        "texto en vez de numeros": {**base, "engine": "basic", "W1": "hola"},
        "no es un objeto": [1, 2, 3],
    }
    for nombre, d in malos.items():
        try:
            ml.brain_from_dict(d)
            check(f"rechazo explicito: {nombre}", False, "se cargo")
        except ml.ModelError as exc:
            check(f"rechazo explicito: {nombre}", True, str(exc)[:70])


# =============================================================================
#  F. Estabilidad numerica
# =============================================================================
def bloque_f():
    print("\n[F] ESTABILIDAD NUMERICA")
    head = modulo_git("HEAD")
    for carpeta, m in especimenes():
        b = ml.brain_from_dict(m["pesos"])
        if b.NAME == "advanced_v1":
            continue            # HEAD no sabia cargarlo (lo cambiaba por una red aleatoria)
        ref = head.brain_from_dict(m["pesos"])
        iguales = total = 0
        hmax = 0.0
        for e in range(5):
            s = ml.Snake(b.clone(), grid=15, rng=random.Random(30000 + e))
            ref.reset_state()
            while s.alive and total < 4000:
                x = s.get_inputs()
                a_ref = ref.forward(x)
                a = s.brain.forward(x)
                if b.NAME == "intermated":
                    hmax = max(hmax, float(np.max(np.abs(s.brain.h))))
                iguales += (a == a_ref); total += 1
                s._apply_action(a); s.advance()
        extra = f", max|h|={hmax:.2f}, rho(W_rec)={max(abs(np.linalg.eigvals(b.W_rec))):.3f}" \
            if b.NAME == "intermated" else ""
        check(f"{carpeta}: los controles numericos no cambian ninguna decision (vs HEAD)",
              iguales == total, f"{iguales}/{total}{extra}")

    rng = np.random.default_rng(5)
    b = ml.IntermatedNetwork(rng=rng)
    b.W_rec = np.eye(ml.N_HIDDEN) * 1.5
    b.reset_state()
    x = np.abs(rng.standard_normal(ml.N_INPUTS))
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            for _ in range(5000):
                b.forward(x)
            ok, det = np.all(np.isfinite(b.h)) and len(w) == 0, f"max|h|={np.max(b.h):.1e}, avisos={len(w)}"
        except ml.NumericalError as exc:
            ok, det = True, f"NumericalError: {exc}"
    check("W_rec = 1.5*I durante 5000 pasos: sin inf/NaN ni avisos (antes: NaN)", ok, det)

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        bb = ml.BasicNetwork(rng=rng)
        bb.W3 = bb.W3 * 1e4
        acc = [bb.forward(rng.random(ml.N_INPUTS)) for _ in range(200)]
    check("basic con salida saturada: sin avisos de overflow (antes: 177)", len(w) == 0,
          f"avisos={len(w)}, acciones={sorted(set(acc))}")

    for nombre in ("intermated", "advanced", "basic", "advanced_v1"):
        cls = {**ml.ENGINES, **ml.LEGACY_ENGINES}[nombre]
        net = cls(rng=rng)
        setattr(net, net._keys()[0], np.full_like(getattr(net, net._keys()[0]), np.nan))
        s = ml.Snake(net, grid=8, rng=random.Random(1))
        s.step_ai()
        check(f"{nombre} con pesos NaN: la partida queda INVALIDA (no se elige accion por defecto)",
              s.invalid and not s.alive and s.fitness() == float("-inf"))

    # Un individuo invalido no contamina la seleccion
    pop = [ml.Individuo(ml.AdvancedNetwork(rng=rng)) for _ in range(6)]
    for i, ind in enumerate(pop):
        ind.score = float(i)
    pop[5].score = float("-inf")
    nueva = ml.next_generation(pop, pop_size=6, elite=5, rng_py=random.Random(0), rng_np=rng)
    check("un individuo invalido nunca es elite", pop[5] not in nueva[:5] and pop[5] not in nueva)


# =============================================================================
#  G. Casos limite y protocolo de evaluacion
# =============================================================================
def bloque_g():
    print("\n[G] CASOS LIMITE Y PROTOCOLO DE EVALUACION")
    cont = {"n": 0}
    def stop():
        cont["n"] += 1
        return cont["n"] > 40
    r = ml.train(generations=10, grid=8, pop_size=25, stop_check=stop, seed=9)
    check("parada a mitad de la generacion 1 -> 0 generaciones completadas", r["generaciones"] == 0 and r["detenido"],
          f"generaciones={r['generaciones']}")

    gens = {"n": 0}
    cont2 = {"gens": 0}
    def on_ev(t, d):
        if t == "gen":
            cont2["gens"] += 1
        return True
    def stop2():
        return cont2["gens"] >= 2 and (gens.__setitem__("n", gens["n"] + 1) or gens["n"] > 30)
    r = ml.train(generations=10, grid=8, pop_size=10, stop_check=stop2, on_event=on_ev, seed=9)
    check("parada a mitad de la generacion 3 -> 2 generaciones completadas", r["generaciones"] == 2,
          f"generaciones={r['generaciones']}")

    s = ml.Snake(grid=8, rng=random.Random(0))
    s.food = (0, s.grid // 2); s._prev_food_dist = s._food_distance()
    while s.alive:
        s.advance()
    check("fitness negativo posible (recto alejandose de la manzana)", s.fitness() < 0, f"{s.fitness()}")
    # Con todos los individuos de fitness negativo, el record sigue siendo una partida real
    sv = (ml.SURVIVAL_REWARD, ml.APPROACH_PENALTY, ml.FRUIT_REWARD, ml.APPROACH_REWARD)
    ml.SURVIVAL_REWARD, ml.APPROACH_PENALTY, ml.FRUIT_REWARD, ml.APPROACH_REWARD = -1.0, 50.0, 0.0, 0.0  # todo fitness < 0
    try:
        r = ml.train(generations=2, grid=8, pop_size=6, seed=4)
    finally:
        ml.SURVIVAL_REWARD, ml.APPROACH_PENALTY, ml.FRUIT_REWARD, ml.APPROACH_REWARD = sv
    check("record con TODOS los fitness negativos: se registra la mejor partida real (antes quedaba -1)",
          r["fitness"] < -1 and r["pasos"] > 0, f"fitness={r['fitness']} pasos={r['pasos']}")

    a = ml.train(generations=4, grid=8, pop_size=12, seed=123)
    b = ml.train(generations=4, grid=8, pop_size=12, seed=123)
    c = ml.train(generations=4, grid=8, pop_size=12, seed=124)
    igual = lambda x, y: all(np.array_equal(p, q) for p, q in zip(x["brain"].get_weights(), y["brain"].get_weights()))
    check("misma semilla -> mismos pesos, record y evaluacion", igual(a, b) and a["eval"] == b["eval"] and a["fitness"] == b["fitness"])
    check("otra semilla -> otro resultado", not igual(a, c))
    # Reproducible aunque otro codigo use el generador global entre medias
    random.seed(999); np.random.seed(999)
    d = ml.train(generations=4, grid=8, pop_size=12, seed=123)
    check("la semilla del entrenamiento es independiente del generador global", igual(a, d))

    # Elitismo y validacion
    curva, elites = [], []
    orig_next = ml.next_generation
    def espia(pop, *args, **kw):
        nueva = orig_next(pop, *args, **kw)
        ordenados = sorted(pop, key=lambda i: i.score, reverse=True)
        k = kw.get("elite", ml.ELITE_COUNT)
        elites.append(all(any(n is e for n in nueva) for e in ordenados[:k] if e.score > float("-inf")))
        return nueva
    ml.next_generation = espia
    try:
        r = ml.train(generations=15, grid=8, pop_size=15, seed=77,
                     on_event=lambda t, d: curva.append(d) if t == "gen" else True)
    finally:
        ml.next_generation = orig_next
    val = [c["val_record"] for c in curva]
    check("la elite pasa como el MISMO individuo (pesos e historial intactos)", all(elites), f"{sum(elites)}/{len(elites)}")
    check("record VALIDADO (semillas fijas) nunca retrocede", all(val[i] >= val[i - 1] for i in range(1, len(val))))
    ref = ml._media_fitness(r["brain"], 8, ml.semillas_validacion())
    check("el cerebro devuelto tiene exactamente el fitness validado anunciado",
          abs(ref - r["validacion"]["fitness_media"]) < 0.01, f"{ref:.2f} vs {r['validacion']['fitness_media']}")
    ev = ml.evaluar(r["brain"], 8)
    check("eval devuelto == evaluar() de nuevo en las semillas de prueba", ev == r["eval"])
    check("eval: mediana, sd e IC presentes y coherentes",
          r["eval"]["frutas_ic95"][0] <= r["eval"]["frutas_media"] <= r["eval"]["frutas_ic95"][1])

    # Continuar un linaje: sin mejora validada se devuelve el heredado
    semilla = r["brain"]
    r2 = ml.train(generations=1, grid=8, pop_size=4, seed_brain=semilla, seed=5)
    if not r2["mejora_validada"]:
        check("sin mejora validada se conserva el cerebro heredado",
              all(np.array_equal(p, q) for p, q in zip(semilla.get_weights(), r2["brain"].get_weights())))
    else:
        vs = ml._media_fitness(semilla, 8, ml.semillas_validacion())
        check("con mejora validada el nuevo supera al heredado en validacion",
              r2["validacion"]["fitness_media"] > vs, f"{r2['validacion']['fitness_media']} > {vs:.2f}")

    # storage en carpeta temporal
    import storage
    viejo_dir = storage.HISTORY_DIR
    with tempfile.TemporaryDirectory() as tmp:
        storage.HISTORY_DIR = tmp
        try:
            s1 = storage.save_training("Prueba", r)
            m1 = storage.load_model("Prueba")
            check("storage: guarda eval, validacion y semilla",
                  m1.get("eval") == r["eval"] and s1["sesiones"][-1]["semilla"] == 77)
            falso = dict(r, mejora_validada=False, fitness=r["fitness"] + 10_000, brain=ml.make_brain("intermated"),
                         generaciones=3)
            storage.save_training("Prueba", falso)
            m2 = storage.load_model("Prueba")
            check("storage: sin mejora validada NO se sustituyen los pesos aunque el record de 1 partida suba",
                  m2["pesos"] == m1["pesos"] and m2["fitness"] == r["fitness"] + 10_000)
            check("storage: las generaciones se acumulan", m2["generaciones"] == r["generaciones"] + 3)
            # especimen antiguo sin eval ni generaciones (None): no revienta
            storage._write_json(os.path.join(tmp, "Antiguo", storage.MODEL_FILE),
                                {"nombre": "Antiguo", "generaciones": None, "fitness": 5000, "frutas": 5,
                                 "pasos": 10, "length": 8, "grid": 8, "pesos": r["brain"].to_dict()})
            storage.save_training("Antiguo", dict(r, mejora_validada=False))
            check("storage: especimen antiguo con generaciones=None continua sin error",
                  storage.load_model("Antiguo")["generaciones"] == r["generaciones"])
            orden = [x["carpeta"] for x in storage.list_models()]
            check("storage: el historial lista primero los evaluados", len(orden) == 2)
            # modelo incompatible en el historial: se informa, no se sustituye
            storage._write_json(os.path.join(tmp, "Roto", storage.MODEL_FILE),
                                {"nombre": "Roto", "pesos": {"engine": "advanced", "W1": [[1.0]]}})
            roto = [x for x in storage.list_models() if x["carpeta"] == "Roto"][0]
            check("storage: un modelo incompatible aparece con `modelo_error`", "modelo_error" in roto)
        finally:
            storage.HISTORY_DIR = viejo_dir


# =============================================================================
#  D. Especimenes guardados vs baselines (ESTADISTICO)
# =============================================================================
def bloque_d(n_ep):
    print(f"\n[D] ESPECIMENES GUARDADOS ({n_ep} episodios independientes, semillas 10000+)")
    esp = especimenes()
    if not esp:
        print("  (no hay historial/: no verificable)")
        return
    for g in (8, 15):
        for nombre, pol in (("BASELINE azar", pol_azar), ("BASELINE voraz", pol_voraz)):
            ev = evaluar(pol, g, n_ep, 10000)
            print(f"  {nombre:28s} {g}x{g}: frutas {resumen(ev['frutas'])}  causas={ev['causas']}")
    for carpeta, m in esp:
        brain = ml.brain_from_dict(m["pesos"])
        g = int(m.get("grid", 8))
        ev = evaluar(pol_red, g, n_ep, 10000, brain=brain)
        rec = int(m.get("frutas", 0))
        pct = 100.0 * np.mean(np.array(ev["frutas"]) >= rec)
        print(f"  {carpeta:28s} {brain.NAME:11s} {g}x{g} record={rec:3d} | frutas {resumen(ev['frutas'])}")
        print(f"  {'':28s} episodios >= record: {pct:.1f}%  causas={ev['causas']}  niveles={ev['niveles']}")
        for g2 in ml.GRID_SIZES:
            if g2 == g:
                continue
            ev2 = evaluar(pol_red, g2, max(20, n_ep // 2), 20000, brain=brain)
            print(f"  {'':28s} transferido a {g2}x{g2}: frutas media={np.mean(ev2['frutas']):.2f} "
                  f"cobertura media={np.mean(ev2['cob']):.3f}")


# =============================================================================
#  E. Entrenamientos cortos con semilla (ESTADISTICO)
# =============================================================================
def bloque_e(semillas, gens, n_ep):
    print(f"\n[E] ENTRENAMIENTOS CORTOS (8x8, pop 25, {gens} gen, semillas 0..{semillas-1})")
    for engine in ("intermated", "advanced", "basic"):
        recs, medias, dif = [], [], []
        t0 = time.perf_counter()
        for sd in range(semillas):
            r = ml.train(generations=gens, grid=8, pop_size=25, engine=engine, seed=sd)
            ev = evaluar(pol_red, 8, n_ep, 50000, brain=r["brain"])
            recs.append(r["frutas"]); medias.append(np.mean(ev["frutas"]))
            dif.append(r["frutas"] - np.mean(ev["frutas"]))
        print(f"  {engine:10s} record de 1 partida (frutas): {recs}")
        print(f"  {'':10s} media en {n_ep} ep independientes: {[round(float(x), 2) for x in medias]}")
        print(f"  {'':10s} record - media real: {resumen(dif)}   tiempo {time.perf_counter()-t0:.0f}s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", nargs="*", default=list("ABCHFG"))
    ap.add_argument("--episodios", type=int, default=100)
    ap.add_argument("--semillas", type=int, default=5)
    ap.add_argument("--gens", type=int, default=30)
    a = ap.parse_args()
    print(f"Python {sys.version.split()[0]}  NumPy {np.__version__}")
    bloques = {"A": bloque_a, "B": bloque_b, "C": bloque_c, "H": bloque_h, "F": bloque_f, "G": bloque_g,
               "D": lambda: bloque_d(a.episodios),
               "E": lambda: bloque_e(a.semillas, a.gens, max(20, a.episodios // 2))}
    for k in a.solo:
        bloques[k]()
    deterministas = [k for k in a.solo if k in "ABCHFG"]
    if deterministas:
        print(f"\nRESULTADO bloques {' '.join(deterministas)}: "
              f"{'TODO PASA' if not FALLOS else f'{len(FALLOS)} FALLO(S): ' + '; '.join(FALLOS)}")
    sys.exit(1 if FALLOS else 0)


if __name__ == "__main__":
    main()
