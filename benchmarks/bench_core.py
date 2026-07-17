# -*- coding: utf-8 -*-
"""
================================================================================
  BENCHMARK DEL NUCLEO DE NEUROEVOLUCION (medicion REAL, reproducible)
================================================================================
  No inventa numeros: ejecuta `train()` de verdad y cronometra con
  time.perf_counter (reloj monotonico de alta resolucion del propio lenguaje).

  Metricas que reporta:
    - Generaciones / segundo
    - Individuos (agentes) evaluados / segundo
    - Pasos simulados (forward passes de la red) / segundo
    - Tiempo medio por generacion (ms)
    - Latencia p50 / p95 / p99 por generacion (ms)

  Uso:
    python benchmarks/bench_core.py
    python benchmarks/bench_core.py --generations 30 --grid 10 --repeat 3
================================================================================
"""
import os
import sys
import time
import argparse

# Permite ejecutar el script desde la raiz del repo importando el nucleo.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import snake_neuroevolution as ml


def percentile(sorted_vals, p):
    """Percentil p (0-100) por interpolacion lineal sobre una lista ordenada."""
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def run_once(generations, grid, pop_size):
    """Ejecuta un entrenamiento completo midiendo el tiempo de cada generacion.

    Devuelve (segundos_total, [ms_por_generacion...], pasos_totales).
    """
    gen_times = []          # duracion de cada generacion, en segundos
    steps = {"n": 0}        # pasos simulados totales (un forward por paso)
    mark = {"t": None}

    def on_event(tipo, datos):
        # Cada 'step' es un turno gobernado por la red: cuenta un forward pass.
        if tipo == "step":
            steps["n"] += 1
        elif tipo == "gen":
            ahora = time.perf_counter()
            if mark["t"] is not None:
                gen_times.append(ahora - mark["t"])
            mark["t"] = ahora
        return True

    t0 = time.perf_counter()
    mark["t"] = t0
    ml.train(generations=generations, grid=grid, pop_size=pop_size,
             seed_brain=None, on_event=on_event)
    total = time.perf_counter() - t0
    return total, gen_times, steps["n"]


def main():
    ap = argparse.ArgumentParser(description="Benchmark del nucleo de neuroevolucion")
    ap.add_argument("--generations", type=int, default=20)
    ap.add_argument("--grid", type=int, default=ml.DEFAULT_GRID)
    ap.add_argument("--pop", type=int, default=ml.POP_SIZE)
    ap.add_argument("--repeat", type=int, default=3)
    args = ap.parse_args()

    print("=" * 70)
    print("  BENCHMARK NEUROEVOLUCION  |  Snake IA")
    print("=" * 70)
    print(f"  Config: grid={args.grid}x{args.grid}  pop={args.pop}  "
          f"generations={args.generations}  repeticiones={args.repeat}")
    print(f"  Reloj:  time.perf_counter() (monotonico, alta resolucion)")
    print("-" * 70)

    totales, all_gen_ms, all_steps = [], [], 0
    for r in range(1, args.repeat + 1):
        total, gen_times, steps = run_once(args.generations, args.grid, args.pop)
        gen_ms = [t * 1000.0 for t in gen_times]
        all_gen_ms.extend(gen_ms)
        totales.append(total)
        all_steps += steps
        gps = args.generations / total
        print(f"  Run {r}: {total:6.3f}s total | {gps:6.2f} gen/s | "
              f"{steps:,} pasos | {steps/total:,.0f} pasos/s")

    total_prom = sum(totales) / len(totales)
    gen_ms_sorted = sorted(all_gen_ms)
    indiv_por_run = args.generations * args.pop

    print("-" * 70)
    print("  RESULTADOS (promedio de las repeticiones)")
    print("-" * 70)
    print(f"  Generaciones / segundo .......... {args.generations / total_prom:8.2f}")
    print(f"  Individuos evaluados / segundo .. {indiv_por_run / total_prom:8.2f}")
    print(f"  Pasos simulados / segundo ....... {all_steps / sum(totales):10,.0f}")
    print(f"  Tiempo medio por generacion ..... {sum(all_gen_ms)/len(all_gen_ms):8.2f} ms")
    print(f"  Latencia p50 por generacion ..... {percentile(gen_ms_sorted, 50):8.2f} ms")
    print(f"  Latencia p95 por generacion ..... {percentile(gen_ms_sorted, 95):8.2f} ms")
    print(f"  Latencia p99 por generacion ..... {percentile(gen_ms_sorted, 99):8.2f} ms")
    print("=" * 70)


if __name__ == "__main__":
    main()
