"""Configuración del servidor por variables de entorno, validada al arrancar.

| Variable          | Uso                                                                   |
| ----------------- | --------------------------------------------------------------------- |
| APP_ENV           | 'desarrollo' (por defecto) o 'produccion'                             |
| IA_SNAKE_TOKEN       | Clave de escritura. Obligatoria en producción (≥ 16 caracteres)       |
| CORS_ORIGINS      | Orígenes del frontend separados por comas; sin comodines. En producción: |
|                   | https públicos, y http://localhost:PUERTO / http://127.0.0.1:PUERTO para |
|                   | conectar un frontend local al backend desplegado                      |
| CORS_ORIGIN_REGEX | Opcional: patrón para vistas previas (p. ej. Vercel). Debe empezar por |
|                   | ^https:// y terminar en $; no admite patrones que abran a cualquiera   |
| IA_SNAKE_DATOS   | Carpeta persistente de los modelos (por defecto ./laboratorio)        |
| PORT              | Puerto (lo usa run.py y el contenedor)                                |

Con IA_SNAKE_TOKEN definido, toda petición que modifique algo (POST/PATCH/DELETE) y la
exportación exigen la cabecera X-IA-Snake-Token. La clave nunca va en el build del
frontend: la escribe el usuario en la interfaz.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


class ErrorConfiguracion(RuntimeError):
    pass


@dataclass(frozen=True)
class Ajustes:
    entorno: str
    token: str | None
    origenes_cors: tuple[str, ...]
    patron_cors: str | None = None

    @property
    def produccion(self) -> bool:
        return self.entorno == "produccion"


def _origenes(valor: str) -> tuple[str, ...]:
    out = []
    for o in (x.strip().rstrip("/") for x in valor.split(",")):
        if not o:
            continue
        if "*" in o:
            raise ErrorConfiguracion("CORS_ORIGINS no admite comodines: lista los dominios exactos")
        u = urlparse(o)
        if u.scheme not in ("http", "https") or not u.netloc or u.path not in ("", "/"):
            raise ErrorConfiguracion(f"Origen CORS inválido: {o!r} (formato: https://dominio)")
        out.append(o)
    return tuple(out)


def cargar_ajustes(env=os.environ) -> Ajustes:
    entorno = env.get("APP_ENV", "desarrollo").strip().lower()
    if entorno not in ("desarrollo", "produccion"):
        raise ErrorConfiguracion("APP_ENV debe ser 'desarrollo' o 'produccion'")
    token = env.get("IA_SNAKE_TOKEN", "").strip() or None
    origenes = _origenes(env.get("CORS_ORIGINS", ""))
    patron = env.get("CORS_ORIGIN_REGEX", "").strip() or None
    if patron:
        import re
        if not (patron.startswith("^https://") and patron.endswith("$")):
            raise ErrorConfiguracion("CORS_ORIGIN_REGEX debe empezar por ^https:// y terminar en $")
        cuerpo = patron[len("^https://"):-1]
        if cuerpo.startswith((".*", ".+", "[^")) or r"\." not in cuerpo:
            raise ErrorConfiguracion("CORS_ORIGIN_REGEX demasiado amplio: fija el dominio (p. ej. "
                                     r"^https://mi-app-[a-z0-9-]+\.vercel\.app$)")
        try:
            re.compile(patron)
        except re.error as e:
            raise ErrorConfiguracion(f"CORS_ORIGIN_REGEX inválido: {e}") from None
    if entorno == "produccion":
        if not token or len(token) < 16:
            raise ErrorConfiguracion(
                "En producción IA_SNAKE_TOKEN es obligatorio (mínimo 16 caracteres): sin él, "
                "cualquiera podría entrenar, borrar o importar modelos")
        for o in origenes:
            u = urlparse(o)
            local = u.hostname in ("localhost", "127.0.0.1")
            if not ((u.scheme == "https" and not local) or (u.scheme == "http" and local)):
                raise ErrorConfiguracion(
                    f"En producción los orígenes deben ser https públicos o http://localhost: {o}")
    return Ajustes(entorno, token, origenes, patron)
