"""Verificación del backend antes de desplegar (la ejecuta `npm run build:backend`).

Python no se compila: se despliega como código fuente y el proveedor instala las
dependencias. Esto comprueba que el backend REALMENTE arranca en el entorno actual:
dependencias instaladas, configuración válida, la app se importa y responde.

Uso:  python -m arkis_lab.servidor.verificar
"""
from __future__ import annotations

import importlib.metadata as md
import os
import sys
import tempfile

DEPENDENCIAS = ["numpy", "scikit-learn", "skops", "fastapi", "uvicorn"]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    fallos = 0
    print(f"Python {sys.version.split()[0]}")
    if sys.version_info < (3, 10):
        print("  ✗ Se necesita Python 3.10 o superior")
        return 1
    for d in DEPENDENCIAS:
        try:
            print(f"  ✓ {d} {md.version(d)}")
        except md.PackageNotFoundError:
            print(f"  ✗ falta {d}  →  pip install -r requirements.txt")
            fallos += 1
    if fallos:
        return 1

    from .ajustes import ErrorConfiguracion, cargar_ajustes
    try:
        a = cargar_ajustes()
        print(f"  ✓ configuración válida (APP_ENV={a.entorno}, clave={'sí' if a.token else 'no'}, "
              f"CORS={', '.join(a.origenes_cors) or 'mismo origen'})")
    except ErrorConfiguracion as e:
        print(f"  ✗ configuración: {e}")
        return 1

    # Importar la app crea los servicios: se usa una carpeta temporal para no tocar datos.
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["ARKIS_LAB_DATOS"] = tmp
        from fastapi.testclient import TestClient
        from .app import app
        rutas = [r.path for r in app.routes if getattr(r, "path", "").startswith("/api/")]
        print(f"  ✓ app importada: {len(rutas)} rutas /api")
        c = TestClient(app)
        for ruta in ("/api/salud", "/api/config", "/api/modelos"):
            r = c.get(ruta)
            ok = r.status_code == 200 and r.headers["content-type"].startswith("application/json")
            print(f"  {'✓' if ok else '✗'} GET {ruta} → {r.status_code}")
            fallos += not ok
        r = c.get("/api/inexistente")
        print(f"  {'✓' if r.status_code == 404 else '✗'} ruta API inexistente → {r.status_code}")
        fallos += r.status_code != 404
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
