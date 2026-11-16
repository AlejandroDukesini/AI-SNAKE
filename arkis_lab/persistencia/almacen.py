"""Almacenamiento independiente por modelo.

laboratorio/<modelo>/
  manifiesto.json          versión actual, estado, lista de versiones
  versiones/v0001/         artefactos inmutables + meta.json (hashes SHA-256, motivo, métricas)
  datos/                   datos de trabajo (ejemplos, casos) en JSON
  registros.sqlite         episodios, sesiones de entrenamiento y récord E por dificultad

Reglas: las versiones nunca se sobrescriben; reentrenar crea una versión nueva; restaurar
solo mueve el puntero (y queda registrado). Escrituras atómicas (temporal + os.replace).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sqlite3
import tempfile
import threading
import time
import zipfile
from contextlib import contextmanager
from pathlib import Path

RAIZ_POR_DEFECTO = Path(os.environ.get("ARKIS_LAB_DATOS",
                                       Path(__file__).resolve().parents[2] / "laboratorio"))


class ErrorAlmacen(RuntimeError):
    pass


def sha256(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def _ahora() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def escribir_atomico(ruta: Path, datos: bytes) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=ruta.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(datos)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, ruta)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def a_json(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, indent=1).encode("utf-8")


_ESQUEMA = """
CREATE TABLE IF NOT EXISTS episodios (
  id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, version TEXT, modo TEXT, sesion TEXT,
  dificultad TEXT, semilla INTEGER, pasos INTEGER, manzanas INTEGER, longitud_max INTEGER,
  ocupacion_max REAL, nivel INTEGER, victoria INTEGER, causa_fin TEXT, retorno REAL,
  componentes TEXT, extra TEXT
);
CREATE TABLE IF NOT EXISTS sesiones (
  id TEXT PRIMARY KEY, fecha TEXT, version_inicial TEXT, version_final TEXT, tipo TEXT,
  parametros TEXT, resumen TEXT
);
CREATE TABLE IF NOT EXISTS record (
  dificultad TEXT PRIMARY KEY, nivel INTEGER, manzanas INTEGER, fecha TEXT, version TEXT
);
CREATE TABLE IF NOT EXISTS eventos (
  id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, tipo TEXT, detalle TEXT
);
"""


class AlmacenModelo:
    def __init__(self, modelo: str, raiz: Path | str | None = None):
        self.modelo = modelo
        self.dir = Path(raiz or RAIZ_POR_DEFECTO) / modelo
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "versiones").mkdir(exist_ok=True)
        (self.dir / "datos").mkdir(exist_ok=True)
        self._lock = threading.RLock()
        with self._db() as db:
            db.executescript(_ESQUEMA)

    # --- SQLite --------------------------------------------------------------
    @contextmanager
    def _db(self):
        """Conexión que confirma al salir sin error y SIEMPRE se cierra (en Windows una
        conexión abierta bloquea el archivo)."""
        con = sqlite3.connect(self.dir / "registros.sqlite", timeout=30)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()

    # --- Manifiesto y versiones ---------------------------------------------
    @property
    def _ruta_manifiesto(self) -> Path:
        return self.dir / "manifiesto.json"

    def manifiesto(self) -> dict:
        try:
            return json.loads(self._ruta_manifiesto.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"modelo": self.modelo, "version_actual": None, "estado": "sin_entrenar",
                    "versiones": []}
        except json.JSONDecodeError:
            return self._reconstruir_manifiesto()

    def _guardar_manifiesto(self, m: dict) -> None:
        escribir_atomico(self._ruta_manifiesto, a_json(m))

    def _reconstruir_manifiesto(self) -> dict:
        """Recuperación ante un manifiesto corrupto: se rehace desde las versiones válidas."""
        versiones = []
        for d in sorted((self.dir / "versiones").glob("v*")):
            try:
                meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
                versiones.append({k: meta.get(k) for k in ("version", "fecha", "motivo", "estado")})
            except (OSError, json.JSONDecodeError):
                continue
        m = {"modelo": self.modelo, "versiones": versiones,
             "version_actual": versiones[-1]["version"] if versiones else None,
             "estado": versiones[-1]["estado"] if versiones else "sin_entrenar"}
        self._guardar_manifiesto(m)
        self.evento("recuperacion", "manifiesto reconstruido desde las versiones")
        return m

    def guardar_version(self, archivos: dict[str, bytes], motivo: str, estado: str,
                        metricas: dict | None = None, extra: dict | None = None) -> str:
        with self._lock:
            m = self.manifiesto()
            n = 1 + max([int(v["version"][1:]) for v in m["versiones"]] or [0])
            version = f"v{n:04d}"
            d = self.dir / "versiones" / version
            if d.exists():
                raise ErrorAlmacen(f"La versión {version} ya existe")
            d.mkdir(parents=True)
            for nombre, datos in archivos.items():
                escribir_atomico(d / nombre, datos)
            meta = {"version": version, "modelo": self.modelo, "fecha": _ahora(),
                    "motivo": motivo, "estado": estado, "padre": m["version_actual"],
                    "hashes": {k: sha256(v) for k, v in archivos.items()},
                    "metricas": metricas or {}, **(extra or {})}
            escribir_atomico(d / "meta.json", a_json(meta))
            m["versiones"].append({"version": version, "fecha": meta["fecha"],
                                   "motivo": motivo, "estado": estado})
            m["version_actual"] = version
            m["estado"] = estado
            self._guardar_manifiesto(m)
            self.evento("version", f"{version}: {motivo}")
            return version

    def meta(self, version: str) -> dict:
        return json.loads((self.dir / "versiones" / version / "meta.json").read_text(encoding="utf-8"))

    def cargar_version(self, version: str | None = None) -> tuple[str, dict[str, bytes]] | None:
        """Devuelve (versión, archivos) verificando cada hash. Si la versión pedida está
        corrupta y no se pidió explícitamente, retrocede a la última válida."""
        m = self.manifiesto()
        if version:
            candidatas = [version]
        else:
            actual = m.get("version_actual")
            if actual is None:
                return None
            todas = [v["version"] for v in m["versiones"]]
            anteriores = [v for v in reversed(todas[:todas.index(actual)])] if actual in todas else []
            candidatas = [actual] + anteriores
        for v in candidatas:
            try:
                meta = self.meta(v)
                archivos = {}
                for nombre, h in meta["hashes"].items():
                    datos = (self.dir / "versiones" / v / nombre).read_bytes()
                    if sha256(datos) != h:
                        raise ErrorAlmacen(f"Hash incorrecto en {v}/{nombre}")
                    archivos[nombre] = datos
                if v != m["version_actual"] and version is None:
                    self.evento("recuperacion", f"{m['version_actual']} inválida; se usa {v}")
                return v, archivos
            except (OSError, json.JSONDecodeError, ErrorAlmacen, KeyError) as e:
                if version:
                    raise ErrorAlmacen(f"No se pudo cargar {v}: {e}") from e
        return None

    def restaurar(self, version: str) -> None:
        with self._lock:
            self.cargar_version(version)          # valida antes de mover el puntero
            m = self.manifiesto()
            m["version_actual"] = version
            m["estado"] = self.meta(version)["estado"]
            self._guardar_manifiesto(m)
            self.evento("restauracion", f"versión actual -> {version}")

    def actualizar_estado(self, estado: str) -> None:
        with self._lock:
            m = self.manifiesto()
            m["estado"] = estado
            self._guardar_manifiesto(m)

    # --- Datos de trabajo ------------------------------------------------------
    def leer_datos(self, nombre: str, defecto=None):
        ruta = self.dir / "datos" / nombre
        try:
            return json.loads(ruta.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return defecto
        except json.JSONDecodeError:
            copia = ruta.with_suffix(ruta.suffix + ".bak")
            if copia.exists():
                self.evento("recuperacion", f"{nombre} corrupto; se usa la copia de seguridad")
                return json.loads(copia.read_text(encoding="utf-8"))
            raise

    def escribir_datos(self, nombre: str, obj) -> None:
        with self._lock:
            ruta = self.dir / "datos" / nombre
            if ruta.exists():
                escribir_atomico(ruta.with_suffix(ruta.suffix + ".bak"), ruta.read_bytes())
            escribir_atomico(ruta, a_json(obj))

    # --- Registros ---------------------------------------------------------------
    def evento(self, tipo: str, detalle: str) -> None:
        with self._db() as db:
            db.execute("INSERT INTO eventos (fecha, tipo, detalle) VALUES (?,?,?)",
                       (_ahora(), tipo, detalle))

    def registrar_episodio(self, resumen, version: str | None, modo: str,
                           sesion: str | None = None, extra: dict | None = None) -> bool:
        """Guarda el episodio y actualiza el récord. Devuelve True si hubo récord nuevo."""
        with self._db() as db:
            db.execute(
                "INSERT INTO episodios (fecha, version, modo, sesion, dificultad, semilla, pasos,"
                " manzanas, longitud_max, ocupacion_max, nivel, victoria, causa_fin, retorno,"
                " componentes, extra) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (_ahora(), version, modo, sesion, resumen.dificultad, resumen.semilla,
                 resumen.pasos, resumen.manzanas, resumen.longitud_max, resumen.ocupacion_max,
                 resumen.nivel, int(resumen.victoria), resumen.causa_fin, resumen.retorno,
                 json.dumps(resumen.retorno_por_componente), json.dumps(extra or {})))
            fila = db.execute("SELECT nivel, manzanas FROM record WHERE dificultad=?",
                              (resumen.dificultad,)).fetchone()
            if fila is None or (resumen.nivel, resumen.manzanas) > (fila["nivel"], fila["manzanas"]):
                db.execute("INSERT OR REPLACE INTO record VALUES (?,?,?,?,?)",
                           (resumen.dificultad, resumen.nivel, resumen.manzanas, _ahora(), version))
                return fila is None or resumen.nivel > fila["nivel"]
        return False

    def records(self) -> dict:
        with self._db() as db:
            return {r["dificultad"]: dict(r) for r in db.execute("SELECT * FROM record")}

    def episodios(self, limite: int = 500, dificultad: str | None = None) -> list[dict]:
        q = "SELECT * FROM episodios"
        args: tuple = ()
        if dificultad:
            q += " WHERE dificultad=?"
            args = (dificultad,)
        q += " ORDER BY id DESC LIMIT ?"
        with self._db() as db:
            filas = [dict(r) for r in db.execute(q, args + (limite,))]
        return list(reversed(filas))

    def resumen_episodios(self) -> dict:
        with self._db() as db:
            filas = db.execute(
                "SELECT dificultad, COUNT(*) n, AVG(manzanas) media, MAX(longitud_max) lmax,"
                " MAX(ocupacion_max) omax, SUM(victoria) victorias, SUM(pasos) pasos,"
                " SUM(causa_fin IN ('limite','cuerpo')) colisiones FROM episodios GROUP BY dificultad")
            return {r["dificultad"]: dict(r) for r in filas}

    def registrar_sesion(self, id_: str, tipo: str, version_inicial, version_final,
                         parametros: dict, resumen: dict) -> None:
        with self._db() as db:
            db.execute("INSERT OR REPLACE INTO sesiones VALUES (?,?,?,?,?,?,?)",
                       (id_, _ahora(), version_inicial, version_final, tipo,
                        json.dumps(parametros, default=str), json.dumps(resumen, default=str)))

    def sesiones(self, limite: int = 50) -> list[dict]:
        with self._db() as db:
            return [dict(r) for r in db.execute(
                "SELECT * FROM sesiones ORDER BY fecha DESC LIMIT ?", (limite,))]

    # --- Exportación / importación / copias ---------------------------------
    def exportar(self) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for ruta in sorted(self.dir.rglob("*")):
                if ruta.is_file() and not ruta.name.startswith(".tmp-"):
                    z.write(ruta, ruta.relative_to(self.dir).as_posix())
        return buf.getvalue()

    def copia_de_seguridad(self) -> Path:
        destino = self.dir.parent / "_copias" / f"{self.modelo}-{time.strftime('%Y%m%d-%H%M%S')}.zip"
        escribir_atomico(destino, self.exportar())
        return destino

    def importar(self, datos_zip: bytes) -> list[str]:
        """Añade las versiones del zip como versiones NUEVAS (no borra nada). Valida hashes."""
        importadas = []
        with zipfile.ZipFile(io.BytesIO(datos_zip)) as z:
            nombres = set(z.namelist())
            metas = sorted(n for n in nombres if n.startswith("versiones/") and n.endswith("/meta.json"))
            if not metas:
                raise ErrorAlmacen("El archivo no contiene versiones")
            for n in metas:
                meta = json.loads(z.read(n))
                if meta.get("modelo") != self.modelo:
                    raise ErrorAlmacen(f"El archivo es de {meta.get('modelo')}, no de {self.modelo}")
                base = n.rsplit("/", 1)[0]
                archivos = {}
                for nombre, h in meta["hashes"].items():
                    datos = z.read(f"{base}/{nombre}")
                    if sha256(datos) != h:
                        raise ErrorAlmacen(f"Hash incorrecto en {base}/{nombre}")
                    archivos[nombre] = datos
                v = self.guardar_version(
                    archivos, f"importada ({meta['version']}: {meta.get('motivo', '')})",
                    meta.get("estado", "entrenado"), meta.get("metricas"),
                    {"importada": True, "origen": meta["version"]})
                importadas.append(v)
        self.evento("importacion", ", ".join(importadas))
        return importadas
