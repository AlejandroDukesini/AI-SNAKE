"""Mide de forma reproducible cuánto aprende cada modelo con su entrenamiento automático.

Entrena cada modelo DESDE CERO en un directorio temporal (no toca laboratorio/), con
semillas fijas, y lo evalúa en semillas de PRUEBA que nunca se usan para entrenar.

ARKIS necesita etiquetas humanas. Para comprobar que su mecanismo aprende, aquí un
'profesor sintético' (la política voraz) hace de usuario. Esa cifra mide el mecanismo,
no la calidad de tus etiquetas.

Uso:  python scripts/medir_modelos.py [--dificultad medio] [--partidas 50]
"""
from __future__ import annotations

import argparse
import random
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ia_snake.evaluacion.lineas_base import LINEAS_BASE, politica_voraz  # noqa: E402
from ia_snake.evaluacion.protocolo import evaluar, semillas  # noqa: E402
from ia_snake.modelos.arkis.servicio import ServicioArkis  # noqa: E402
from ia_snake.modelos.bork.servicio import ServicioBork  # noqa: E402
from ia_snake.modelos.clark.servicio import ServicioClark  # noqa: E402
from ia_snake.modelos.ejemplos import Dataset  # noqa: E402
from ia_snake.modelos.lerk.servicio import ServicioLerk  # noqa: E402
from ia_snake.modelos.situacion import situacion_de  # noqa: E402
from ia_snake.nucleo.entorno import Entorno  # noqa: E402


def profesor_sintetico(dificultad, episodios):
    ds = Dataset()
    ent = Entorno(dificultad)
    rng = random.Random(1)
    for s in semillas("entrenamiento", episodios):
        perc = ent.reiniciar(s)
        while not ent.terminado and ent.partida.pasos < 200:
            a = politica_voraz(perc, rng)
            ds.agregar(situacion_de(ent.partida), a.etiqueta, "demostracion", f"ep{s}")
            perc = ent.paso(a).percepcion
    ds.aprobar([e["id"] for e in ds.ejemplos])
    return ds


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dificultad", default="medio")
    ap.add_argument("--partidas", type=int, default=50)
    ap.add_argument("--bork", type=int, default=1500)
    ap.add_argument("--lerk", type=int, default=100)
    ap.add_argument("--clark", type=int, default=300)
    ap.add_argument("--arkis", type=int, default=30, help="episodios demostrados por el profesor")
    a = ap.parse_args()
    d = a.dificultad
    prueba = semillas("prueba", a.partidas)
    raiz = Path(tempfile.mkdtemp(prefix="ia-snake-medicion-"))
    filas = []

    def medir(nombre, entrenamiento, politica, t0):
        ev = evaluar(politica, d, prueba)
        filas.append((nombre, entrenamiento, ev, time.time() - t0))
        m = ev.manzanas
        print(f"{nombre:<34} {m.media:6.2f} [{m.ic95[0]:6.2f}, {m.ic95[1]:6.2f}]  mediana {m.mediana:5.1f}  "
              f"E máx {ev.mejor_nivel}  victorias {ev.victorias}  ({time.time() - t0:.0f} s)", flush=True)

    print(f"Dificultad {d} · {a.partidas} partidas de prueba (semillas {prueba[0]}–{prueba[-1]})\n")
    for k, pol in LINEAS_BASE.items():
        medir(f"línea base: {k}", "sin aprendizaje", pol, time.time())

    t = time.time()
    arkis = ServicioArkis(raiz)
    arkis.dataset = profesor_sintetico(d, a.arkis)
    arkis.guardar_dataset()
    n_ej = len(arkis.dataset.aprobados())
    met = arkis.entrenar(semilla=0, aumentar=True)
    medir(f"ARKIS (profesor sintético, {n_ej} ej.)",
          f"accuracy validación {met['validacion']['accuracy']:.3f}", arkis.agente().politica(), t)

    t = time.time()
    lerk = ServicioLerk(raiz)
    medir("LERK (sin entrenar)", "base vacía", lerk.agente().politica(), t)
    t = time.time()
    lerk.entrenamiento_automatico(d, episodios=a.lerk, epsilon=0.3, semilla=0, bloque=20)
    medir(f"LERK ({a.lerk} episodios de experiencia)", f"{len(lerk.base.reglas)} reglas",
          lerk.agente().politica(), t)

    t = time.time()
    bork = ServicioBork(raiz)
    r = bork.entrenar(d, episodios=a.bork, semilla=0)
    medir(f"BORK ({a.bork} episodios)", f"{r['estados']} estados", bork.agente().politica(), t)

    t = time.time()
    clark = ServicioClark(raiz)
    clark.entrenamiento_automatico(d, episodios=a.clark, semilla=0, bloque=50)
    medir(f"CLARK ({a.clark} episodios)", f"{len(clark.comp.simbolico.reglas)} reglas, "
          f"{len(clark.comp.refuerzo.q)} estados Q", clark.agente().politica(), t)
    print("\nReglas aprendidas por LERK:")
    for r in lerk.base.reglas:
        print(f"  {r.conclusion:9} conf={r.confianza:.3f} soporte={r.soporte:6}  {r.texto()}")
    print(f"\nDatos temporales en {raiz}")


if __name__ == "__main__":
    main()
