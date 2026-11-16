"""Sistema evolutivo E0–E8 por ocupación del tablero.

C(E_n) = techo(n · N / 8) casillas. Nivel de una partida = mayor n con longitud ≥ C(E_n),
siempre que se haya comido al menos una manzana (la longitud inicial no regala niveles).
E0 = no alcanzar E1 (incluye terminar por la regla de los 30 s sin comer).
"""
from __future__ import annotations

NIVEL_MAXIMO = 8


def umbral_casillas(n: int, casillas: int) -> int:
    if not 0 <= n <= NIVEL_MAXIMO:
        raise ValueError("n debe estar entre 0 y 8")
    return -(-n * casillas // NIVEL_MAXIMO)   # techo entero, sin coma flotante


def tabla_umbrales(casillas: int) -> tuple[int, ...]:
    return tuple(umbral_casillas(n, casillas) for n in range(NIVEL_MAXIMO + 1))


def ocupacion(longitud: int, casillas: int) -> float:
    return 100.0 * longitud / casillas


def nivel(longitud: int, casillas: int, manzanas: int) -> int:
    if manzanas <= 0:
        return 0
    n = 0
    for k in range(1, NIVEL_MAXIMO + 1):
        if longitud >= umbral_casillas(k, casillas):
            n = k
    return n


class RecordHistorico:
    """Mejor nivel por (modelo, dificultad). Nunca disminuye; solo cuentan episodios válidos."""

    def __init__(self, datos: dict | None = None):
        self._r: dict[tuple[str, str], int] = {}
        for clave, v in (datos or {}).items():
            modelo, dificultad = clave.split("|", 1)
            self._r[(modelo, dificultad)] = int(v)

    def registrar(self, modelo: str, dificultad: str, nivel_alcanzado: int,
                  valido: bool = True) -> bool:
        """Devuelve True si es un nuevo récord."""
        if not valido:
            return False
        actual = self._r.get((modelo, dificultad), 0)
        if nivel_alcanzado > actual:
            self._r[(modelo, dificultad)] = nivel_alcanzado
            return True
        return False

    def nivel(self, modelo: str, dificultad: str) -> int:
        return self._r.get((modelo, dificultad), 0)

    def a_dict(self) -> dict:
        return {f"{m}|{d}": v for (m, d), v in self._r.items()}
