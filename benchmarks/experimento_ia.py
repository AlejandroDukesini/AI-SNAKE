# -*- coding: utf-8 -*-
"""
================================================================================
  EXPERIMENTO ESTADISTICO: algoritmo ORIGINAL vs CORREGIDO (multiples semillas)
================================================================================
  Complementa a `audit_ia.py` (comprobaciones deterministas). Aqui la unidad de
  replicacion es el ENTRENAMIENTO: cada configuracion se entrena con varias
  semillas independientes y cada cerebro resultante se evalua en un conjunto de
  semillas de evaluacion que no interviene en el entrenamiento.

  - ORIGINAL = `git show HEAD:snake_neuroevolution.py` (algoritmo antes de las
    correcciones; se carga en memoria, no se toca el repositorio).
  - CORREGIDO = `snake_neuroevolution.py` actual, con variantes de fitness
    (F0 = la original, F1 = shaping simetrico sin premio por paso) y de
    episodios por individuo (K).
  - Baselines: azar y voraz (de los giros no mortales, el que mas acerca a la
    manzana), evaluadas en las MISMAS semillas.

  Todas las politicas se evaluan en el entorno actual (`Snake` con
  `rng=random.Random(semilla)`), asi que comparten exactamente las partidas.

  Fases (semillas disjuntas):
    dev       elegir variante. Entrenamiento 0..N-1, evaluacion 500000+.
    confirmar comparar la variante elegida. Entrenamiento 100+, evaluacion 10000+.

  Uso:
    python benchmarks/experimento_ia.py dev
    python benchmarks/experimento_ia.py confirmar --variante F1K3
    python benchmarks/experimento_ia.py confirmar --variante F1K3 --grid 15 --engines intermated
================================================================================
"""
import os
import sys
import json
import time
import types
import random
import argparse
import subprocess
from multiprocessing import Pool

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import numpy as np

# Cada variante fija constantes del modulo. Una variante = una hipotesis.
F0 = {"SURVIVAL_REWARD": 1.0, "APPROACH_REWARD": 3.0, "APPROACH_PENALTY": 4.0}   # fitness original
F1 = {"SURVIVAL_REWARD": 0.0, "APPROACH_REWARD": 1.0, "APPROACH_PENALTY": 1.0}   # shaping simetrico
VARIANTES = {
    "F0K1":   {**F0, "EVAL_EPISODES": 1},
    "F0K3":   {**F0, "EVAL_EPISODES": 3},
    "F1K1":   {**F1, "EVAL_EPISODES": 1},
    "F1K3":   {**F1, "EVAL_EPISODES": 3},
    "F0K5":   {**F0, "EVAL_EPISODES": 5},
    "F0K3X0": {**F0, "EVAL_EPISODES": 3, "CROSSOVER_RATE": 0.0},       # sin cruce
    "F0K3T5": {**F0, "EVAL_EPISODES": 3, "TOURNAMENT_K": 5},           # mas presion selectiva
}

_HEAD = None


def modulo_original():
    global _HEAD
    if _HEAD is None:
        src = subprocess.check_output(
            ["git", "-C", RAIZ, "show", "HEAD:snake_neuroevolution.py"]).decode("utf-8")
        _HEAD = types.ModuleType("snake_original")
        exec(compile(src, "snake_original", "exec"), _HEAD.__dict__)
    return _HEAD


# ------------------------------------------------------------------ politicas
def _destino(s, a):
    import snake_neuroevolution as ml
    i = s.dir_i if a == 0 else ((s.dir_i - 1) % 4 if a == 1 else (s.dir_i + 1) % 4)
    d = ml.DIRS[i]
    return s.body[0][0] + d[0], s.body[0][1] + d[1]


def pol_voraz(s):
    mejor, md = 0, None
    for a in (0, 1, 2):
        x, y = _destino(s, a)
        if not (0 <= x < s.grid and 0 <= y < s.grid):
            continue
        if (x, y) in s._body_set and not ((x, y) == s.body[-1] and (x, y) != s.food):
            continue
        dd = abs(s.food[0] - x) + abs(s.food[1] - y) if s.food else 0
        if md is None or dd < md:
            mejor, md = a, dd
    return mejor


def evaluar_politica(politica, grid, semillas, brain=None):
    """Frutas por episodio en el entorno ACTUAL con comida decidida por semilla."""
    import snake_neuroevolution as ml
    frutas = []
    for sem in semillas:
        s = ml.Snake(brain.clone() if brain is not None else None, grid=grid,
                     rng=random.Random(sem))
        rp = random.Random(sem + 7)
        while s.alive:
            if politica == "red":
                s.step_ai()
                continue
            a = pol_voraz(s) if politica == "voraz" else rp.randrange(3)
            s._apply_action(a)
            s.advance()
        frutas.append(s.fruits)
    return frutas


# ------------------------------------------------------------------ trabajo
def correr(tarea):
    """Un entrenamiento + su evaluacion. Se ejecuta en un proceso aparte."""
    algo, engine, grid, gens, sem, eval_sem = tarea
    pasos = {"n": 0}
    curva = []

    def on_event(t, d):
        if t == "step":
            pasos["n"] += 1
        elif t == "gen":
            curva.append(d)
        return True

    t0 = time.perf_counter()
    if algo.startswith("ORIG"):
        ml0 = modulo_original()
        ml0.MAX_GENERATIONS = max(ml0.MAX_GENERATIONS, gens)   # el tope de la UI (100) no aplica aqui
        random.seed(sem)
        np.random.seed(sem)
        r = ml0.train(generations=gens, grid=grid, pop_size=25, engine=engine, on_event=on_event)
        val_curva = None
    else:
        import snake_neuroevolution as ml
        ml.MAX_GENERATIONS = max(ml.MAX_GENERATIONS, gens)
        for clave, valor in VARIANTES[algo].items():
            assert hasattr(ml, clave), clave
            setattr(ml, clave, valor)
        r = ml.train(generations=gens, grid=grid, pop_size=25, engine=engine,
                     on_event=on_event, seed=sem)
        val_curva = [c["val_record"] for c in curva]
    t = time.perf_counter() - t0
    fr = evaluar_politica("red", grid, eval_sem, brain=r["brain"])
    best = [c["best"] for c in curva]
    out = {
        "algo": algo, "engine": engine, "grid": grid, "gens": len(curva), "seed": sem,
        "frutas_media": float(np.mean(fr)), "frutas_sd": float(np.std(fr, ddof=1)),
        "record_frutas": int(r["frutas"]), "segundos": round(t, 1), "pasos": pasos["n"],
        "retrocesos_best": sum(1 for i in range(1, len(best))
                               if best[i] is not None and best[i - 1] is not None
                               and best[i] < best[i - 1]),
    }
    if val_curva is not None:
        out["retrocesos_val_record"] = sum(1 for i in range(1, len(val_curva))
                                           if val_curva[i] < val_curva[i - 1])
        out["diversidad"] = [round(c["diversidad"], 3) for c in curva]
    return out


# ------------------------------------------------------------------ estadistica
def ic95(v, n_boot=5000):
    a = np.asarray(v, float)
    m = np.random.default_rng(0).choice(a, size=(n_boot, a.size)).mean(axis=1)
    return np.percentile(m, [2.5, 97.5])


def ic95_dif(a, b, n_boot=5000):
    rng = np.random.default_rng(1)
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = rng.choice(a, (n_boot, a.size)).mean(1) - rng.choice(b, (n_boot, b.size)).mean(1)
    return np.percentile(d, [2.5, 97.5])


def informe(resultados, baselines, ref="ORIG"):
    grupos = {}
    for r in resultados:
        grupos.setdefault((r["engine"], r["grid"], r["algo"]), []).append(r)
    for (engine, grid), (vz, az) in baselines.items():
        print(f"\n== {engine} {grid}x{grid} ==  baselines (mismas semillas): voraz media={np.mean(vz):.2f} "
              f"[IC95 {ic95(vz)[0]:.2f}-{ic95(vz)[1]:.2f}] | azar media={np.mean(az):.2f}")
        base = [r["frutas_media"] for r in grupos.get((engine, grid, ref), [])]
        for (e, g, algo), rs in sorted(grupos.items()):
            if (e, g) != (engine, grid):
                continue
            m = [r["frutas_media"] for r in rs]
            lo, hi = ic95(m)
            extra = ""
            if base and algo != ref:
                dlo, dhi = ic95_dif(m, base)
                extra = f" | dif vs {ref}: {np.mean(m)-np.mean(base):+.2f} [IC95 {dlo:+.2f} {dhi:+.2f}]"
            ret = sum(r["retrocesos_best"] for r in rs)
            gens_tot = sum(r["gens"] - 1 for r in rs)
            rv = sum(r.get("retrocesos_val_record", 0) for r in rs)
            print(f"  {algo:9s} n={len(rs):2d} gens={rs[0]['gens']:3d} frutas media por run="
                  f"{np.mean(m):6.2f} sd={np.std(m, ddof=1):5.2f} [IC95 {lo:5.2f}-{hi:5.2f}] "
                  f"min={min(m):5.2f} max={max(m):5.2f}{extra}")
            print(f"  {'':9s} record medio={np.mean([r['record_frutas'] for r in rs]):.1f} "
                  f"| best de gen. empeora {ret}/{gens_tot} | val_record empeora {rv} "
                  f"| pasos medios={np.mean([r['pasos'] for r in rs]):,.0f} "
                  f"| s medios={np.mean([r['segundos'] for r in rs]):.0f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fase", choices=["dev", "confirmar"])
    ap.add_argument("--variante", default="F0K3")
    ap.add_argument("--variantes", nargs="*", default=None, help="fase dev: variantes a probar")
    ap.add_argument("--sin-orig", action="store_true", help="no repetir las corridas ORIG")
    ap.add_argument("--engines", nargs="*", default=None)
    ap.add_argument("--grid", type=int, default=8)
    ap.add_argument("--gens", type=int, default=40)
    ap.add_argument("--semillas", type=int, default=None)
    ap.add_argument("--episodios", type=int, default=None)
    ap.add_argument("--procesos", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--salida", default=None)
    ap.add_argument("--algos", nargs="*", default=None, help="confirmar: subconjunto de ORIG ORIG_x3 <variante>")
    a = ap.parse_args()

    if a.fase == "dev":
        engines = a.engines or ["intermated"]
        n_sem = a.semillas or 6
        train_seeds = list(range(n_sem))
        eval_seeds = list(range(500000, 500000 + (a.episodios or 50)))
        algos = ([] if a.sin_orig else [("ORIG", a.gens), ("ORIG_x3", a.gens * 3)]) +                 [(v, a.gens) for v in (a.variantes or VARIANTES)]
    else:
        engines = a.engines or ["intermated", "advanced", "basic"]
        n_sem = a.semillas or 10
        train_seeds = list(range(100, 100 + n_sem))
        eval_seeds = list(range(10000, 10000 + (a.episodios or 100)))
        algos = [("ORIG", a.gens), ("ORIG_x3", a.gens * 3), (a.variante, a.gens)]
        if a.algos:
            algos = [x for x in algos if x[0] in a.algos]

    tareas = []
    for engine in engines:
        for algo, gens in algos:
            for s in train_seeds:
                tareas.append((algo, engine, a.grid, gens, s, eval_seeds))
    print(f"fase={a.fase} engines={engines} grid={a.grid} semillas entrenamiento={train_seeds[0]}..{train_seeds[-1]} "
          f"semillas evaluacion={eval_seeds[0]}..{eval_seeds[-1]} ({len(eval_seeds)}) tareas={len(tareas)} "
          f"procesos={a.procesos}", flush=True)
    t0 = time.perf_counter()
    with Pool(a.procesos) as pool:
        resultados = []
        for r in pool.imap_unordered(correr, tareas):
            resultados.append(r)
            print(f"  hecho {len(resultados)}/{len(tareas)} {r['algo']} {r['engine']} s{r['seed']} "
                  f"-> {r['frutas_media']:.2f} frutas ({r['segundos']}s)", flush=True)
    baselines = {(e, a.grid): (evaluar_politica("voraz", a.grid, eval_seeds),
                               evaluar_politica("azar", a.grid, eval_seeds)) for e in engines}
    informe(resultados, baselines)
    print(f"\ntiempo total {time.perf_counter() - t0:.0f}s")
    if a.salida:
        with open(a.salida, "w", encoding="utf-8") as f:
            json.dump(resultados, f, indent=1)


if __name__ == "__main__":
    main()
