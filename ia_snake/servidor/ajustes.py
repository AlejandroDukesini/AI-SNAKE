"""Configuración del servidor por variables de entorno, validada al arrancar.

| Variable          | Uso                                                                   |
| ----------------- | --------------------------------------------------------------------- |
| APP_ENV           | 'desarrollo' (por defecto) o 'produccion'                             |
| IA_SNAKE_TOKEN       | Clave de escritura. Obligatoria en producción (≥ 16 caracteres)       |
| CORS_ORIGINS      | Orígenes del frontend separados por comas (https://…); sin comodines |
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
    if entorno == "produccion":
        if not token or len(token) < 16:
            raise ErrorConfiguracion(
                "En producción IA_SNAKE_TOKEN es obligatorio (mínimo 16 caracteres): sin él, "
                "cualquiera podría entrenar, borrar o importar modelos")
        for o in origenes:
            if urlparse(o).scheme != "https" or urlparse(o).hostname in ("localhost", "127.0.0.1"):
                raise ErrorConfiguracion(f"En producción los orígenes deben ser https públicos: {o}")
    return Ajustes(entorno, token, origenes)
