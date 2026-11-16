"""Mide las líneas base (azar y voraz) en las tres dificultades con semillas de prueba fijas.

Uso:  python scripts/lineas_base.py [--episodios 100]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arkis_lab.evaluacion.lineas_base import LINEAS_BASE  # noqa: E402
from arkis_lab.evaluacion.protocolo import evaluar, semillas  # noqa: E402
from arkis_lab.nucleo.config import DIFICULTADES, VERSION_MOTOR  # noqa: E402


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodios", type=int, default=100)
    args = ap.parse_args()
    s = semillas("prueba", args.episodios)
    print(f"Motor {VERSION_MOTOR} · {args.episodios} episodios por fila · semillas de prueba "
          f"{s[0]}..{s[-1]}\n")
    print(f"{'dificultad':<9} {'política':<7} {'manzanas media [IC95]':<26} {'mediana':>7} "
          f"{'ocup.máx %':>10} {'E mejor':>7} {'victorias':>9}  causas de fin   (s)")
    for clave in DIFICULTADES:
        for nombre, pol in LINEAS_BASE.items():
            t0 = time.perf_counter()
            ev = evaluar(pol, clave, s)
            m = ev.manzanas
            print(f"{clave:<9} {nombre:<7} {m.media:6.2f} [{m.ic95[0]:6.2f}, {m.ic95[1]:6.2f}]"
                  f"{'':<5} {m.mediana:7.1f} {ev.ocupacion_max.media:10.1f} "
                  f"{'E' + str(ev.mejor_nivel):>7} {ev.victorias:>9}  {ev.causas_fin}"
                  f"   ({time.perf_counter() - t0:.1f})")


if __name__ == "__main__":
    main()
