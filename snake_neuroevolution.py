# -*- coding: utf-8 -*-
"""
VIBECODIGN -> CLAUDE CLI
Progamador -> Alejandro Rodriguez Duque
LICENCIA -> VER ARCHIVO LICENCE
================================================================================
  SNAKE IA - MACHINE LEARNING (Red Neuronal + Algoritmo Genetico)
================================================================================
  Este modulo es el CEREBRO del proyecto y no sabe nada de interfaces: ni web,
  ni WebSocket, ni React. Solo matematicas con NumPy.

    - `Brain` (+ motores)  tres arquitecturas seleccionables sobre 26 entradas:
        intermated 26->20->3 recurrente (por defecto), advanced 26->16->3,
        basic 26->52->26->1. Ver docs/ENGINES.md.
    - `Snake`          el agente: sensores, movimiento, tamano y fitness
    - `crossover` / `mutate` / `next_generation`   algoritmo genetico
    - `train`          la neuroevolucion completa, con herencia de linaje
    - `evaluar`        rendimiento de un cerebro en semillas FIJAS (media, IC...)
    - `nivel_de_cobertura`  clasifica la cobertura en niveles (ver docs/ROADMAP.md)

  Lo usan `ai_server.py` (servidor de la web) y cualquier script suelto.
  La persistencia vive en `storage.py`.

  NEUROEVOLUCION CON HERENCIA
  ---------------------------
  No hay descenso de gradiente ni dataset. Se evoluciona una poblacion:
    Gen 1: pesos aleatorios (o heredados de un linaje previo).
    Gen N: los MEJORES hijos de la Gen N-1 son la base de la Gen N.
           La elite pasa intacta; el resto son cruces mutados de los mejores.

  PROTOCOLO DE EVALUACION (ver docs/auditoria-cientifica-ia.md)
  -------------------------------------------------------------
  Una partida tiene azar (donde aparece la manzana), asi que un solo episodio
  dice poco de un cerebro. Se separan tres conjuntos de semillas:
    - SELECCION: cada generacion sortea EVAL_EPISODES semillas COMUNES y todos
      los individuos (elite incluida) juegan esas mismas partidas. Su fitness de
      seleccion es la media: comparable dentro de la generacion.
    - VALIDACION: el campeon de cada generacion juega VALIDATION_EPISODES
      semillas FIJAS para todo el entrenamiento. Es la unica cifra comparable
      ENTRE generaciones, y la que decide que cerebro se devuelve.
    - PRUEBA: el cerebro devuelto juega TEST_EPISODES semillas fijas que nunca
      intervienen en ninguna decision. Es lo que se presenta como rendimiento.
================================================================================
"""

import math
import time
import random

import numpy as np

# =============================================================================
#  PARAMETROS DEL MUNDO Y DEL ALGORITMO
# =============================================================================
GRID_SIZES    = (8, 10, 15)  # Dimensiones de tablero que ofrece la interfaz
DEFAULT_GRID  = 8

POP_SIZE      = 25           # Agentes por generacion (valor por defecto)
DEFAULT_GENERATIONS = 5      # Generaciones por entrenamiento
MIN_GENERATIONS = 1
MAX_GENERATIONS = 100

# Rango de poblacion que la interfaz puede pedir. El suelo es 4 porque con menos
# agentes el torneo (TOURNAMENT_K=3) y el elitismo se quedan sin donde elegir y
# la evolucion degenera en copiar al unico superviviente. El techo es 100 porque
# el coste por generacion crece LINEALMENTE con la poblacion: 200 agentes no
# entrenan mejor, solo tardan el doble.
MIN_POP_SIZE  = 4
MAX_POP_SIZE  = 100

ENERGY_START  = 200          # Pasos sin comer antes de morir de inanicion
ELITE_COUNT   = 3            # Elitismo: mejores redes que pasan intactas
MUTATION_RATE = 0.05         # Probabilidad de mutacion por peso (5%)
MUTATION_STD  = 0.20         # Desviacion del ruido gaussiano de mutacion (inicial)
TOURNAMENT_K  = 3            # Tamano del torneo de seleccion
CROSSOVER_RATE = 1.0         # Probabilidad de que un hijo nazca de un cruce (si no: mutacion de un padre)

INITIAL_LENGTH = 3           # Longitud con la que nace la serpiente
FRUIT_REWARD   = 1000        # Fitness que aporta cada bloque de crecimiento

# --- Fitness: comer domina; el resto solo orienta a quien aun no come --------
# fitness = pasos * SURVIVAL_REWARD + 1000 * crecimiento + shaping de acercamiento.
# LIMITACION CONOCIDA (medida, no corregida): en una cuadricula cada paso cambia
# la distancia Manhattan en exactamente +-1, asi que un bucle tiene tantos pasos
# de acercamiento como de alejamiento y su fitness sube +1 + (3-4)/2 = +0,5 por
# paso hasta morir de inanicion (~+100, el 10 % de una fruta). Se probo la
# alternativa basada en potencial (Ng, Harada y Russell 1999: +1/-1 y sin premio
# por paso, que suma 0 en un bucle) y NO rindio mejor en partidas completas, asi
# que se conservan los valores originales. Ver docs/auditoria-cientifica-ia.md.
SURVIVAL_REWARD  = 1.0       # Fitness por paso sobrevivido
APPROACH_REWARD  = 3.0       # Fitness por acercarse una casilla a la manzana
APPROACH_PENALTY = 4.0       # Castigo por alejarse una casilla

# --- Protocolo de evaluacion (ver la cabecera del modulo) --------------------
EVAL_EPISODES       = 3          # Partidas por individuo y generacion (semillas comunes)
VALIDATION_EPISODES = 10         # Partidas fijas para validar al campeon
TEST_EPISODES       = 20         # Partidas fijas de prueba del cerebro devuelto
VAL_SEED_BASE       = 1_000_000  # Semillas de validacion: VAL_SEED_BASE + i
TEST_SEED_BASE      = 2_000_000  # Semillas de prueba: TEST_SEED_BASE + i
TRAIN_SEED_MIN      = 3_000_000  # Las de seleccion se sortean por encima: nunca coinciden

# --- Decaimiento adaptativo de la mutacion ------------------------------------
# Si el mejor rendimiento VALIDADO no mejora en varias generaciones, se reduce la
# desviacion de la mutacion: se pasa de explorar a afinar. (No es recocido
# simulado: no hay temperatura ni aceptacion de soluciones peores.)
STAGNATION_PATIENCE = 4      # Generaciones sin mejora antes de reducir sigma
MUTATION_DECAY      = 0.85   # Factor de reduccion por estancamiento
MUTATION_STD_MIN    = 0.05   # Suelo: nunca deja de explorar del todo

# --- Estabilidad numerica ----------------------------------------------------
# Tope del estado oculto recurrente. Con ReLU (sin cota superior) y una `W_rec`
# de radio espectral > 1, el estado puede crecer exponencialmente hasta inf/NaN.
# Los estados medidos en especimenes reales no pasan de ~10, asi que el tope no
# altera ninguna decision normal; solo impide el desbordamiento.
H_MAX = 1e6

# --- Arquitectura de la red (VISION AMPLIADA) ---
# 8 direcciones EGOCENTRICAS x 3 rasgos (pared / cuerpo / alineacion con la
# comida) = 24 sensores de entorno, mas 2 sensores globales (tamano propio y
# espacio libre alcanzable) = 26 entradas.
N_RAY_DIRS   = 8             # Rayos egocentricos: F, FD, D, TD, T, TI, I, FI
N_TRAITS     = 3             # Por rayo: pared, cuerpo, alineacion con la comida
N_ENV_INPUTS = N_RAY_DIRS * N_TRAITS      # 24
N_EXTRA      = 2             # Sensor de tamano + sensor de espacio libre
N_INPUTS     = N_ENV_INPUTS + N_EXTRA     # 26
N_HIDDEN     = 20
N_OUTPUTS    = 3             # Recto / Girar Izquierda / Girar Derecha

# Direcciones cardinales en orden HORARIO: UP -> RIGHT -> DOWN -> LEFT
DIRS = [(0, -1), (1, 0), (0, 1), (-1, 0)]

# Las redes antiguas de 3 rayos tenian 9 entradas (pared, cuerpo, comida en
# Frente / Izq / Der) o 10 (+ tamano). Indice de cada una en el vector actual de
# 26 (rayos: 0=F, 2=D, 6=I; bloques: pared 0-7, cuerpo 8-15, comida 16-23,
# tamano 24). Lo usa `IntermatedNetwork._adapt_weights`.
_LEGACY_COLS = [0, 6, 2, 8, 14, 10, 16, 22, 18, 24]


class ModelError(ValueError):
    """Un modelo guardado no se puede cargar tal cual (arquitectura desconocida,
    formas incompatibles o valores no finitos). Se lanza en vez de sustituirlo en
    silencio por una red aleatoria."""


class NumericalError(ArithmeticError):
    """La red produjo un valor no finito (inf/NaN) al decidir."""


# =============================================================================
#  NIVELES POR COBERTURA  (ver docs/ROADMAP.md)
# =============================================================================
#  La cobertura es que fraccion del tablero ocupa el cuerpo. Es una medida de
#  RESULTADO; las etiquetas describen ese resultado, no capacidades cognitivas.
NIVELES = [
    (0.10, 0, "N0 · Cobertura < 10 %"),
    (0.20, 1, "N1 · Cobertura 10–20 %"),
    (0.35, 2, "N2 · Cobertura 20–35 %"),
    (0.55, 3, "N3 · Cobertura 35–55 %"),
    (0.80, 4, "N4 · Cobertura 55–80 %"),
]
NIVEL_MAX = (5, "N5 · Cobertura ≥ 80 %")


def cobertura(length, grid):
    """Fraccion del tablero ocupada por la serpiente [0-1] = longitud / area."""
    area = float(grid * grid) or 1.0
    return max(0.0, min(1.0, length / area))


def nivel_de_cobertura(cob):
    """Clasifica una cobertura [0-1] en un nivel (ver docs/ROADMAP.md).

    Devuelve {"nivel": int, "etiqueta": str, "cobertura": float}.
    """
    for umbral, nivel, etiqueta in NIVELES:
        if cob < umbral:
            return {"nivel": nivel, "etiqueta": etiqueta, "cobertura": round(cob, 4)}
    return {"nivel": NIVEL_MAX[0], "etiqueta": NIVEL_MAX[1], "cobertura": round(cob, 4)}

# Nombres aleatorios para bautizar especimenes sin nombre
NAME_A = ["Alpha", "Cerebro", "Neo", "Viper", "Cobra", "Quantum", "Titan",
          "Nova", "Omega", "Zenith", "Hydra", "Pixel", "Turbo", "Mamba"]
NAME_B = ["Snake", "Mind", "Core", "Brain", "Genoma", "Reptil", "IA", "Neura"]


def random_name():
    """Nombre aleatorio para un especimen sin bautizar."""
    return f"{random.choice(NAME_A)}-{random.choice(NAME_B)}-V{random.randint(1, 99)}"


def clamp_generations(value):
    """Normaliza el numero de generaciones que llega del usuario (1 a 100)."""
    try:
        value = int(value)
    except (TypeError, ValueError):
        return DEFAULT_GENERATIONS
    return max(MIN_GENERATIONS, min(MAX_GENERATIONS, value))


def clamp_grid(value):
    """Valida el tamano de tablero; cualquier valor raro cae al de por defecto."""
    try:
        value = int(value)
    except (TypeError, ValueError):
        return DEFAULT_GRID
    return value if value in GRID_SIZES else DEFAULT_GRID


def clamp_pop_size(value):
    """Normaliza el numero de agentes por generacion que llega del usuario."""
    try:
        value = int(value)
    except (TypeError, ValueError):
        return POP_SIZE
    return max(MIN_POP_SIZE, min(MAX_POP_SIZE, value))


def clamp_elite(value, pop_size=POP_SIZE):
    """Normaliza cuantos cerebros se HEREDAN intactos de una generacion a la
    siguiente (elitismo).

    El tope es `pop_size - 1` y no `pop_size` por una razon dura: si la elite
    ocupara toda la poblacion no quedaria hueco para un solo hijo, `next_generation`
    devolveria una copia exacta de la generacion anterior y la evolucion se
    detendria para siempre sin dar ningun error. El suelo es 1 para garantizar que
    el mejor linaje nunca se pierde por mala suerte del cruce.
    """
    tope = max(1, int(pop_size) - 1)
    try:
        value = int(value)
    except (TypeError, ValueError):
        return min(ELITE_COUNT, tope)
    return max(1, min(tope, value))


# =============================================================================
#  MOTORES DE RED NEURONAL (numpy) — arquitectura modular y seleccionable
# =============================================================================
#  El juego, los sensores (26 entradas) y el algoritmo genetico son SIEMPRE los
#  mismos. Lo unico que cambia entre motores es la topologia de la red y como su
#  salida se traduce en un giro. El GA opera sobre `get_weights()` (una lista de
#  arrays) y reconstruye una red del MISMO motor con `type(padre)(pesos_hijo)`.
#
#  Cada motor declara su `_layout`: (clave, forma, fan_in). fan_in > 0 => init He
#  N(0, 2/fan_in); fan_in == 0 => ceros. Asi las formas esperadas se conocen sin
#  crear una red (y sin consumir numeros aleatorios) al validar un modelo.
#
#    - intermated  26 -> 20 -> 3            recurrente (el motor de siempre)
#    - advanced    26 -> 16 -> 3            feedforward compacto (1 capa, LeakyReLU)
#    - basic       26 -> 52 -> 26 -> 1      feedforward ancho, salida por rangos
#    - advanced_v1 26 -> 32 -> 16 -> 3      SOLO CARGA: version anterior de advanced
# =============================================================================
class Brain:
    """Contrato comun a los motores. Las subclases definen `_layout` y
    `forward(x) -> accion`. Clonar, serializar y exponer pesos al GA vive aqui."""

    NAME = "base"
    _layout = ()

    def __init__(self, weights=None, rng=None):
        """Sin pesos, los inicializa (init He) con `rng` (un np.random.Generator;
        por defecto el generador global de numpy). Con `weights`, reutiliza los
        dados (hijos del algoritmo genetico o modelo recargado)."""
        if weights is None:
            weights = self._random_weights(np.random if rng is None else rng)
        for clave, w in zip(self._keys(), weights):
            setattr(self, clave, w)
        self._on_init()

    @classmethod
    def _keys(cls):
        return tuple(k for k, _, _ in cls._layout)

    @classmethod
    def shapes(cls):
        """Formas que espera esta arquitectura, {clave: forma}."""
        return {k: s for k, s, _ in cls._layout}

    @classmethod
    def _random_weights(cls, rng):
        return [rng.standard_normal(s) * np.sqrt(2.0 / fan) if fan else np.zeros(s)
                for _, s, fan in cls._layout]

    def _on_init(self):
        """Gancho tras fijar los pesos (los motores con memoria lo usan)."""

    def reset_state(self):
        """Feedforward no tiene memoria que reiniciar."""

    def forward(self, x):
        raise NotImplementedError

    def get_weights(self):
        """Copia de todas las matrices, en el orden de `_layout`."""
        return [getattr(self, k).copy() for k in self._keys()]

    def clone(self):
        """Red nueva e independiente con los mismos pesos (memoria limpia)."""
        return type(self)(self.get_weights())

    def to_dict(self):
        """Serializa los pesos sellando el motor (ver `brain_from_dict`)."""
        d = {k: getattr(self, k).tolist() for k in self._keys()}
        d["engine"] = self.NAME
        return d

    @classmethod
    def matches(cls, d):
        """True si las matrices de `d` tienen exactamente las formas de este motor."""
        try:
            return all(np.shape(d[k]) == s for k, s in cls.shapes().items())
        except (KeyError, TypeError, ValueError):
            return False

    @classmethod
    def from_dict(cls, d):
        """Reconstruye la red desde `to_dict`. Nunca devuelve una red aleatoria en
        lugar del modelo: si faltan matrices, sus formas no coinciden o contienen
        valores no finitos, lanza `ModelError` con el motivo."""
        pesos = []
        for k, forma in cls.shapes().items():
            w = _as_array(d, k)
            if w.shape != forma:
                raise ModelError(
                    f"El motor '{cls.NAME}' espera {k} con forma {forma} y el modelo "
                    f"trae {w.shape}: es otra arquitectura.")
            pesos.append(w)
        return cls(pesos)

    def _check(self, o):
        if not np.all(np.isfinite(o)):
            raise NumericalError(f"Salida no finita del motor '{self.NAME}': {o}")


def _as_array(d, k):
    """Lee la matriz `k` de un modelo como float64 finito o lanza ModelError."""
    if k not in d:
        raise ModelError(f"Al modelo le falta la matriz '{k}'.")
    try:
        w = np.array(d[k], dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ModelError(f"La matriz '{k}' no es numerica o esta mal formada: {exc}")
    if not np.all(np.isfinite(w)):
        raise ModelError(f"La matriz '{k}' contiene valores no finitos (inf/NaN).")
    return w


class IntermatedNetwork(Brain):
    """Motor `intermated` — el de siempre.

    Red RECURRENTE 26 -> 20 -> 3: la capa oculta (ReLU) se realimenta a traves de
    `W_rec`, viendo en cada turno la entrada Y su propio estado anterior. `W_rec`
    nace a CERO (se comporta como feedforward) y la mutacion la introduce poco a
    poco. Es el unico motor con especimenes de versiones anteriores, por eso
    conserva la carga adaptativa de 9/10 entradas.
    """

    NAME = "intermated"
    HIDDEN = N_HIDDEN            # 20
    _layout = (("W1", (N_HIDDEN, N_INPUTS), N_INPUTS),
               ("b1", (N_HIDDEN,), 0),
               ("W_rec", (N_HIDDEN, N_HIDDEN), 0),   # Sin memoria al nacer
               ("W2", (N_OUTPUTS, N_HIDDEN), N_HIDDEN),
               ("b2", (N_OUTPUTS,), 0))

    def _on_init(self):
        self.h = np.zeros(self.HIDDEN)      # Estado oculto: memoria intra-partida

    def reset_state(self):
        self.h = np.zeros(self.HIDDEN)

    def forward(self, x):
        # La capa oculta ve la entrada Y su propio estado previo (memoria). El
        # tope H_MAX solo actua ante un crecimiento explosivo (ver H_MAX).
        h = np.maximum(0.0, self.W1 @ x + self.b1 + self.W_rec @ self.h)
        np.minimum(h, H_MAX, out=h)
        o = self.W2 @ h + self.b2           # Capa de salida lineal
        self._check(o)
        self.h = h                          # Se recuerda para el turno siguiente
        return int(np.argmax(o))

    @classmethod
    def matches(cls, d):
        """Acepta las formas que `_adapt_weights` sabe convertir SIN cambiar la
        decision: 9, 10 o 26 entradas, hasta 20 neuronas ocultas y 3 salidas."""
        try:
            W1, W2 = np.shape(d["W1"]), np.shape(d["W2"])
            b1, b2 = np.shape(d["b1"]), np.shape(d["b2"])
        except (KeyError, TypeError, ValueError):
            return False
        if len(W1) != 2 or len(W2) != 2:
            return False
        h_old, in_old = W1
        ok = (in_old in (9, 10, N_INPUTS) and 1 <= h_old <= N_HIDDEN
              and W2 == (N_OUTPUTS, h_old) and b1 == (h_old,) and b2 == (N_OUTPUTS,))
        if ok and "W_rec" in d:
            ok = np.shape(d["W_rec"]) == (h_old, h_old)
        return ok

    @classmethod
    def from_dict(cls, d):
        """Reconstruye ADAPTANDO un tamano guardado a la arquitectura actual sin
        alterar la decision: los especimenes viejos (9 o 10 entradas, 12 neuronas,
        sin recurrencia) se copian en las posiciones de sus mismos sensores y el
        resto queda NEUTRO. Formas que no se pueden convertir sin cambiar el
        comportamiento (p. ej. mas de 20 neuronas) lanzan ModelError."""
        if not cls.matches(d):
            formas = {k: np.shape(d.get(k)) for k in ("W1", "b1", "W_rec", "W2", "b2") if k in d}
            raise ModelError(f"Formas no convertibles a intermated 26->20->3: {formas}")
        W1, b1, W2, b2 = (_as_array(d, k) for k in ("W1", "b1", "W2", "b2"))
        W_rec = _as_array(d, "W_rec") if "W_rec" in d else None
        return cls(cls._adapt_weights(W1, b1, W2, b2, W_rec))

    @staticmethod
    def _adapt_weights(W1, b1, W2, b2, W_rec=None):
        """Encaja pesos de 9/10/26 entradas y <=20 neuronas en 26 -> 20 -> 3 sin
        cambiar la decision para las entradas heredadas (ver `from_dict`)."""
        h_old, in_old = W1.shape
        h_copy = min(h_old, N_HIDDEN)

        # Las neuronas NUEVAS reciben pesos de entrada aleatorios pero su salida
        # (columnas de W2) es cero: no cambian la decision hasta que la mutacion
        # las conecte. Se usa un generador propio para no tocar el global.
        rng = np.random.default_rng(0)
        nW1 = rng.standard_normal((N_HIDDEN, N_INPUTS)) * np.sqrt(2.0 / N_INPUTS)
        nb1 = np.zeros(N_HIDDEN)
        nW_rec = np.zeros((N_HIDDEN, N_HIDDEN))
        nW2 = np.zeros((N_OUTPUTS, N_HIDDEN))
        nb2 = np.zeros(N_OUTPUTS)

        if in_old < N_INPUTS:
            # Red de 3 rayos (9 o 10 entradas): cada columna va a la posicion
            # que ocupa ESE MISMO sensor en el vector actual. Copiarlas en la
            # esquina las desordenaba (la "pared izquierda" caia en la diagonal).
            cols = _LEGACY_COLS[:in_old]
            nW1[:h_copy, :] = 0.0
            nW1[:h_copy, cols] = W1[:h_copy, :in_old]
        else:
            nW1[:h_copy, :] = W1[:h_copy, :]
        nb1[:h_copy] = b1[:h_copy]
        nW2[:, :h_copy] = W2[:, :h_copy]
        nb2[:] = b2
        if W_rec is not None:
            nW_rec[:h_copy, :h_copy] = W_rec[:h_copy, :h_copy]
        return [nW1, nb1, nW_rec, nW2, nb2]


def _leaky_relu(z, alpha=0.01):
    """LeakyReLU: como ReLU pero deja pasar una fraccion pequeña de lo negativo,
    para que ninguna neurona quede muerta para siempre (una red evolucionada no la
    revive con facilidad)."""
    return np.where(z > 0.0, z, alpha * z)


class AdvancedNetwork(Brain):
    """Motor `advanced` — feedforward COMPACTO de una sola capa oculta (26 -> 16 -> 3).

    Se simplifico desde la version profunda anterior (26 -> 32 -> 16 -> 3, que
    sigue pudiendose CARGAR como `advanced_v1`) para reducir el espacio de busqueda
    del genetico a 483 pesos. LeakyReLU en la capa oculta; decide por argmax de
    las 3 salidas (recto / izquierda / derecha), igual que `intermated`.
    """

    NAME = "advanced"
    HIDDEN = 16
    _layout = (("W1", (16, N_INPUTS), N_INPUTS),
               ("b1", (16,), 0),
               ("W2", (N_OUTPUTS, 16), 16),
               ("b2", (N_OUTPUTS,), 0))

    def forward(self, x):
        h = _leaky_relu(self.W1 @ x + self.b1)
        o = self.W2 @ h + self.b2
        self._check(o)
        return int(np.argmax(o))


class AdvancedV1Network(Brain):
    """Version ANTERIOR de `advanced` (commit 81aa744): 26 -> 32 -> 16 -> 3 con dos
    capas ReLU y argmax. Copia exacta de aquel `forward`.

    No se ofrece para especimenes nuevos; existe para que los guardados con esa
    arquitectura se carguen con sus pesos reales en vez de perderse. Al continuar
    su entrenamiento el linaje conserva esta arquitectura (el GA no la cambia)."""

    NAME = "advanced_v1"
    _layout = (("W1", (32, N_INPUTS), N_INPUTS),
               ("b1", (32,), 0),
               ("W2", (16, 32), 32),
               ("b2", (16,), 0),
               ("W3", (N_OUTPUTS, 16), 16),
               ("b3", (N_OUTPUTS,), 0))

    def forward(self, x):
        h1 = np.maximum(0.0, self.W1 @ x + self.b1)
        h2 = np.maximum(0.0, self.W2 @ h1 + self.b2)
        o  = self.W3 @ h2 + self.b3
        self._check(o)
        return int(np.argmax(o))


class BasicNetwork(Brain):
    """Motor `basic` — teorico / expansivo.

    Feedforward 26 -> 52 -> 26 -> 1 (ReLU). Al tener UNA sola salida, el giro se
    decide por rangos sobre su valor aplastado a [0,1] con una sigmoide:
        v < 1/3 -> izquierda   |   1/3 <= v <= 2/3 -> recto   |   v > 2/3 -> derecha
    Es el motor con mas pesos (2.809).
    """

    NAME = "basic"
    _layout = (("W1", (52, N_INPUTS), N_INPUTS),
               ("b1", (52,), 0),
               ("W2", (26, 52), 52),
               ("b2", (26,), 0),
               ("W3", (1, 26), 26),
               ("b3", (1,), 0))

    def forward(self, x):
        h1 = np.maximum(0.0, self.W1 @ x + self.b1)
        h2 = np.maximum(0.0, self.W2 @ h1 + self.b2)
        raw = float((self.W3 @ h2 + self.b3)[0])    # Una sola salida
        self._check(raw)
        # Recorte a +-500 antes de exp: evita el desbordamiento sin cambiar
        # ninguna decision (con |raw| > 500 la sigmoide ya vale 0 o 1).
        v = 1.0 / (1.0 + math.exp(-max(-500.0, min(500.0, raw))))
        if v < 1.0 / 3.0:
            return 1                                # Izquierda
        if v > 2.0 / 3.0:
            return 2                                # Derecha
        return 0                                    # Recto


# --- Registro de motores -----------------------------------------------------
#  ENGINES: los que se pueden elegir para un especimen nuevo.
#  _CARGADORES: que clases pueden reconstruir un modelo segun su sello `engine`.
ENGINES = {c.NAME: c for c in (IntermatedNetwork, AdvancedNetwork, BasicNetwork)}
LEGACY_ENGINES = {AdvancedV1Network.NAME: AdvancedV1Network}
DEFAULT_ENGINE = "intermated"
_CARGADORES = {
    "intermated":  (IntermatedNetwork,),
    "advanced":    (AdvancedNetwork, AdvancedV1Network),   # sello antiguo compartido
    "advanced_v1": (AdvancedV1Network,),
    "basic":       (BasicNetwork,),
}

# Metadatos para la interfaz y la documentacion (no afectan al calculo).
ENGINE_INFO = {
    "advanced": {
        "label": "Advanced",
        "arch": "26 → 16 → 3",
        "resumen": "Feedforward compacto de una sola capa oculta (LeakyReLU, 483 "
                   "pesos): el espacio de busqueda mas pequeno de los tres.",
    },
    "intermated": {
        "label": "Intermated",
        "arch": "26 → 20 → 3",
        "resumen": "Recurrente (ReLU + memoria W_rec, 1.003 pesos). El motor por "
                   "defecto y el de los especimenes mas antiguos.",
    },
    "basic": {
        "label": "Basic",
        "arch": "26 → 52 → 26 → 1",
        "resumen": "Feedforward ancho con una salida por rangos (2.809 pesos). El "
                   "espacio de busqueda mas grande.",
    },
}
LEGACY_INFO = {
    "advanced_v1": {"label": "Advanced v1 (antiguo)", "arch": "26 → 32 → 16 → 3",
                    "resumen": "Version anterior de advanced, solo para especimenes "
                               "guardados con ella."},
}

# Retrocompatibilidad: el codigo que habla de `NeuralNetwork` apunta al motor
# por defecto, el de siempre.
NeuralNetwork = IntermatedNetwork


def clamp_engine(value):
    """Normaliza el motor pedido: cualquier valor desconocido cae al de defecto."""
    return value if value in ENGINES else DEFAULT_ENGINE


def make_brain(engine=DEFAULT_ENGINE, rng=None):
    """Crea un cerebro nuevo (pesos aleatorios) del motor indicado."""
    return ENGINES[clamp_engine(engine)](rng=rng)


def brain_from_dict(d):
    """Reconstruye un cerebro desde su JSON, eligiendo el motor por su sello
    `engine` y, si el sello es ambiguo (`advanced` antiguo), por las formas.
    Sin sello (modelos anteriores a los motores) => `intermated`.

    Lanza `ModelError` si el modelo no corresponde a ninguna arquitectura
    conocida: nunca lo cambia por una red nueva sin avisar."""
    if not isinstance(d, dict):
        raise ModelError("Los pesos del modelo no son un objeto JSON.")
    name = d.get("engine") or DEFAULT_ENGINE
    candidatos = _CARGADORES.get(name)
    if not candidatos:
        raise ModelError(f"Motor desconocido '{name}'.")
    for cls in candidatos:
        if cls.matches(d):
            return cls.from_dict(d)
    if len(candidatos) == 1:
        return candidatos[0].from_dict(d)       # Su ModelError explica el motivo
    def forma(v):
        try:
            return np.shape(v)
        except ValueError:
            return "irregular"
    trae = {k: forma(v) for k, v in d.items() if k != "engine"}
    esperadas = "; ".join(f"{c.NAME}: {c.shapes()}" for c in candidatos)
    raise ModelError(f"El modelo '{name}' trae {trae}, que no coincide con ninguna "
                     f"arquitectura conocida ({esperadas}).")


def crossover(parent_a, parent_b, rng=None):
    """Crossover uniforme elemento a elemento entre los pesos de dos padres.
    Reconstruye un hijo del MISMO motor que los padres (poblacion homogenea)."""
    rng = np.random if rng is None else rng
    child_weights = []
    for wa, wb in zip(parent_a.get_weights(), parent_b.get_weights()):
        mask = rng.random(wa.shape) < 0.5
        child_weights.append(np.where(mask, wa, wb))
    return type(parent_a)(child_weights)


def mutate(net, std=MUTATION_STD, rng=None):
    """Mutacion gaussiana con probabilidad MUTATION_RATE por peso y desviacion
    `std`. Reconstruye una red del mismo motor que la de entrada."""
    rng = np.random if rng is None else rng
    new_weights = []
    for w in net.get_weights():
        mask = rng.random(w.shape) < MUTATION_RATE
        noise = rng.standard_normal(w.shape) * std
        new_weights.append(w + mask * noise)
    return type(net)(new_weights)


# =============================================================================
#  AGENTE (SNAKE)
# =============================================================================
class Snake:
    """Agente Snake: cuerpo sobre la cuadricula, sensores, movimiento y estado.

    `rng` (un random.Random) decide donde aparece la comida: con la misma semilla
    y las mismas decisiones, la partida es identica. Sin `rng` usa el generador
    global (juego manual). Los sensores se normalizan dividiendo por `grid`.
    """

    def __init__(self, brain=None, grid=DEFAULT_GRID, use_energy=True, rng=None):
        """Inicializa el agente con un cerebro dado o uno nuevo.
        `use_energy` activa la muerte por inanicion (se desactiva en modo manual)."""
        self.grid       = grid
        self.brain      = brain if brain is not None else NeuralNetwork()
        self.use_energy = use_energy
        self._rng       = random if rng is None else rng
        self.reset()

    def reset(self):
        """Coloca la serpiente en el centro y reinicia cuerpo, energia y marcadores."""
        cx = cy = self.grid // 2
        self.body   = [(cx - i, cy) for i in range(INITIAL_LENGTH)]
        self.dir_i  = 1                 # 1 = mirando a la derecha
        self.alive  = True
        self.invalid = False            # True si la red produjo inf/NaN
        self.brain.reset_state()        # Nueva partida = memoria en blanco
        self.energy = ENERGY_START
        self.steps  = 0
        self.fruits = 0
        self.food   = None
        self.shaping = 0.0              # Fitness acumulado por acercarse a la comida
        # Copia del cuerpo como SET: la percepcion consulta colisiones miles de
        # veces por partida. Se mantiene en sincronia dentro de `advance`.
        self._body_set = set(self.body)
        self.spawn_food()
        self._prev_food_dist = self._food_distance()

    # --- Tamano -------------------------------------------------------------
    @property
    def length(self):
        """Tamano actual de la serpiente. Crece 1 bloque por cada manzana."""
        return len(self.body)

    def _length_sensor(self):
        """Sensor propioceptivo [0-1]: que fraccion del tablero ocupa su cuerpo."""
        return self.length / float(self.grid * self.grid)

    def spawn_food(self):
        """Situa una manzana en una celda libre al azar (None si no queda ninguna)."""
        libres = [(x, y) for x in range(self.grid) for y in range(self.grid)
                  if (x, y) not in self._body_set]
        self.food = self._rng.choice(libres) if libres else None

    def _food_distance(self):
        """Distancia Manhattan de la cabeza a la manzana (0 si no queda comida)."""
        if self.food is None:
            return 0
        hx, hy = self.body[0]
        return abs(self.food[0] - hx) + abs(self.food[1] - hy)

    def _wall_distance(self, head, d):
        """Sensor: distancia normalizada [0-1] hasta la pared en la direccion `d`."""
        x, y = head
        dist, nx, ny = 0, x + d[0], y + d[1]
        while 0 <= nx < self.grid and 0 <= ny < self.grid:
            dist += 1
            nx += d[0]; ny += d[1]
        return dist / float(self.grid)

    def _body_distance(self, head, d):
        """Sensor: proximidad [0-1] al propio cuerpo en la direccion `d`
        (1.0 = adyacente, 0.0 = sin cuerpo en esa linea)."""
        x, y = head
        nx, ny, step = x + d[0], y + d[1], 1
        while 0 <= nx < self.grid and 0 <= ny < self.grid:
            if (nx, ny) in self._body_set:
                return 1.0 - (step - 1) / float(self.grid)
            nx += d[0]; ny += d[1]; step += 1
        return 0.0

    def _ray_dirs(self):
        """Las 8 direcciones EGOCENTRICAS de los rayos, horario desde el frente:
        Frente, Frente-Der, Der, Tras-Der, Tras, Tras-Izq, Izq, Frente-Izq."""
        f = DIRS[self.dir_i]
        r = DIRS[(self.dir_i + 1) % 4]
        b = DIRS[(self.dir_i + 2) % 4]
        l = DIRS[(self.dir_i - 1) % 4]
        return [f,
                (f[0] + r[0], f[1] + r[1]),   # Frente-Derecha
                r,
                (b[0] + r[0], b[1] + r[1]),   # Tras-Derecha
                b,
                (b[0] + l[0], b[1] + l[1]),   # Tras-Izquierda
                l,
                (f[0] + l[0], f[1] + l[1])]   # Frente-Izquierda

    def _free_space_sensor(self):
        """Sensor global [0-1]: fraccion del tablero ALCANZABLE desde la cabeza
        (flood-fill sobre las celdas libres; la cola cuenta como ocupada).

        Se calcula en CADA turno de CADA agente, asi que es el punto mas caliente
        del simulador: indices planos y un `bytearray` de visitados.
        """
        g = self.grid
        area = g * g
        bloqueado = bytearray(area)                 # 1 = cuerpo o ya visitado
        for x, y in self._body_set:
            bloqueado[y * g + x] = 1

        hx, hy = self.body[0]
        pila = [hy * g + hx]
        bloqueado[hy * g + hx] = 1                  # La cabeza no cuenta como libre
        alcanzables = 0
        while pila:
            idx = pila.pop()
            x = idx % g
            if x > 0 and not bloqueado[idx - 1]:
                bloqueado[idx - 1] = 1; alcanzables += 1; pila.append(idx - 1)
            if x < g - 1 and not bloqueado[idx + 1]:
                bloqueado[idx + 1] = 1; alcanzables += 1; pila.append(idx + 1)
            if idx >= g and not bloqueado[idx - g]:
                bloqueado[idx - g] = 1; alcanzables += 1; pila.append(idx - g)
            if idx < area - g and not bloqueado[idx + g]:
                bloqueado[idx + g] = 1; alcanzables += 1; pila.append(idx + g)
        return alcanzables / float(area)

    def get_inputs(self):
        """26 entradas: pared/cuerpo/comida en 8 rayos egocentricos (24) + tamano
        propio + espacio libre alcanzable (2)."""
        head = self.body[0]
        dirs = self._ray_dirs()

        wall = [self._wall_distance(head, d) for d in dirs]
        body = [self._body_distance(head, d) for d in dirs]

        if self.food is not None:
            fx, fy = self.food
            vx, vy = fx - head[0], fy - head[1]
            norm = (vx * vx + vy * vy) ** 0.5 or 1.0
            vx, vy = vx / norm, vy / norm
        else:
            vx = vy = 0.0
        # Alineacion de cada rayo con la manzana (rayo normalizado por su modulo).
        food = []
        for dx, dy in dirs:
            dn = (dx * dx + dy * dy) ** 0.5 or 1.0
            food.append((vx * dx + vy * dy) / dn)

        extra = [self._length_sensor(), self._free_space_sensor()]
        return np.array(wall + body + food + extra, dtype=np.float64)

    def _apply_action(self, action):
        """Traduce la salida de la red en un giro relativo (1=izq, 2=der; 0=recto)."""
        if action == 1:
            self.dir_i = (self.dir_i - 1) % 4
        elif action == 2:
            self.dir_i = (self.dir_i + 1) % 4

    def set_absolute_direction(self, new_i):
        """Para juego manual: fija direccion sin permitir giro de 180 grados."""
        if new_i == (self.dir_i + 2) % 4 and len(self.body) > 1:
            return
        self.dir_i = new_i

    def advance(self):
        """Mueve un bloque; gestiona colisiones, energia y crecimiento."""
        if not self.alive:
            return
        d = DIRS[self.dir_i]
        hx, hy = self.body[0]
        nx, ny = hx + d[0], hy + d[1]

        if not (0 <= nx < self.grid and 0 <= ny < self.grid):   # Pared
            self.alive = False; return

        crece = ((nx, ny) == self.food)
        # La cola se libera este turno salvo que se coma: moverse HACIA la propia
        # cola es un movimiento valido (la casilla queda libre al avanzar).
        cola = self.body[-1]
        if (nx, ny) in self._body_set and not (not crece and (nx, ny) == cola):
            self.alive = False; return

        self.body.insert(0, (nx, ny))
        self.steps += 1
        if self.use_energy:
            self.energy -= 1

        if crece:
            # Comer = NO quitar la cola: el cuerpo crece un bloque.
            self._body_set.add((nx, ny))
            self.fruits += 1
            self.energy = ENERGY_START
            self.spawn_food()
            self._prev_food_dist = self._food_distance()   # Nueva manzana, nueva referencia
        else:
            # Liberar la cola ANTES de fijar la cabeza: si la cabeza ocupa justo la
            # casilla que dejaba la cola, el set debe quedarse con la cabeza.
            self._body_set.discard(self.body.pop())
            self._body_set.add((nx, ny))
            # Shaping denso (solo cuando NO se ha comido este turno).
            nueva = self._food_distance()
            if nueva < self._prev_food_dist:
                self.shaping += APPROACH_REWARD
            elif nueva > self._prev_food_dist:
                self.shaping -= APPROACH_PENALTY
            self._prev_food_dist = nueva

        if self.use_energy and self.energy <= 0:                 # Inanicion
            self.alive = False

    def step_ai(self):
        """Un turno gobernado por la red neuronal. Si la red produce inf/NaN la
        partida termina marcada como `invalid`: no se elige una accion por
        defecto en silencio."""
        if not self.alive:
            return
        try:
            accion = self.brain.forward(self.get_inputs())
        except NumericalError:
            self.alive = False
            self.invalid = True
            return
        self._apply_action(accion)
        self.advance()

    def fitness(self):
        """Fitness = crecimiento * FRUIT_REWARD + shaping + pasos * SURVIVAL_REWARD.

        Comer domina (1000 por fruta); el shaping orienta a quien aun no come
        (ver la limitacion documentada junto a SURVIVAL_REWARD). Un individuo invalido
        (salida no finita) vale -inf: nunca gana una seleccion ni un record.
        """
        if self.invalid:
            return float("-inf")
        crecimiento = self.length - INITIAL_LENGTH
        return self.steps * SURVIVAL_REWARD + crecimiento * FRUIT_REWARD + self.shaping

    def to_state(self):
        """Instantanea serializable, pensada para enviarla al navegador.
        El cliente solo dibuja: nunca calcula reglas."""
        return {
            "body":   [list(c) for c in self.body],
            "food":   list(self.food) if self.food else None,
            "alive":  self.alive,
            "fruits": self.fruits,
            "steps":  self.steps,
            "energy": self.energy,
            "length": self.length,
            "grid":   self.grid,
        }


# =============================================================================
#  EVALUACION REPRODUCIBLE
# =============================================================================
def jugar(brain, grid, semilla):
    """Juega UNA partida completa con la comida decidida por `semilla`.
    Devuelve {"fitness", "frutas", "pasos", "length", "invalid"}."""
    s = Snake(brain, grid=grid, rng=random.Random(semilla))
    while s.alive:
        s.step_ai()
    return {"fitness": s.fitness(), "frutas": s.fruits, "pasos": s.steps,
            "length": s.length, "invalid": s.invalid}


def semillas_validacion(n=None):
    return [VAL_SEED_BASE + i for i in range(VALIDATION_EPISODES if n is None else n)]


def semillas_prueba(n=None):
    return [TEST_SEED_BASE + i for i in range(TEST_EPISODES if n is None else n)]


def _ic95_media(valores):
    """IC 95 % de la media por bootstrap percentil (1.000 remuestreos, semilla 0:
    el mismo dato da siempre el mismo intervalo)."""
    a = np.asarray(valores, dtype=float)
    if a.size < 2:
        return [float(a.mean()) if a.size else 0.0] * 2
    medias = np.random.default_rng(0).choice(a, size=(1000, a.size)).mean(axis=1)
    lo, hi = np.percentile(medias, [2.5, 97.5])
    return [round(float(lo), 3), round(float(hi), 3)]


def evaluar(brain, grid, semillas=None):
    """Rendimiento de un cerebro en un conjunto FIJO de semillas (por defecto las
    de prueba). Es lo que describe el rendimiento HABITUAL del modelo, a
    diferencia del record de un episodio. Las partidas invalidas se cuentan
    aparte y no entran en las medias."""
    semillas = semillas_prueba() if semillas is None else list(semillas)
    partidas = [jugar(brain, grid, s) for s in semillas]
    validas = [p for p in partidas if not p["invalid"]]
    fr = [p["frutas"] for p in validas]
    cob = [cobertura(p["length"], grid) for p in validas]
    tipico = nivel_de_cobertura(float(np.median(cob)) if cob else 0.0)
    return {
        "episodios":      len(semillas),
        "semillas":       f"{semillas[0]}-{semillas[-1]}" if semillas else "",
        "grid":           int(grid),
        "invalidos":      len(partidas) - len(validas),
        "frutas_media":   round(float(np.mean(fr)), 3) if fr else 0.0,
        "frutas_mediana": float(np.median(fr)) if fr else 0.0,
        "frutas_sd":      round(float(np.std(fr, ddof=1)), 3) if len(fr) > 1 else 0.0,
        "frutas_ic95":    _ic95_media(fr) if fr else [0.0, 0.0],
        "frutas_max":     int(max(fr)) if fr else 0,
        "fitness_media":  round(float(np.mean([p["fitness"] for p in validas])), 2) if validas else None,
        "cobertura_media":   round(float(np.mean(cob)), 4) if cob else 0.0,
        "cobertura_mediana": round(float(np.median(cob)), 4) if cob else 0.0,
        "nivel_tipico":          tipico["nivel"],
        "nivel_tipico_etiqueta": tipico["etiqueta"],
    }


def _media_fitness(brain, grid, semillas):
    """Fitness medio en `semillas`; -inf si alguna partida es invalida."""
    total = 0.0
    for s in semillas:
        f = jugar(brain, grid, s)["fitness"]
        if f == float("-inf"):
            return f
        total += f
    return total / len(semillas)


# =============================================================================
#  ALGORITMO GENETICO
# =============================================================================
class Individuo:
    """Un cerebro de la poblacion y lo que se sabe de el.

    `score` es su fitness de SELECCION en la generacion actual (media sobre las
    semillas comunes de esa generacion). `n_eval`/`suma_eval` acumulan todas sus
    partidas de seleccion a lo largo de las generaciones que sobrevive como
    elite: la nueva evaluacion se SUMA a la anterior, no la borra. `val` es su
    fitness medio en las semillas de validacion (se calcula una vez: los pesos
    de un individuo no cambian)."""

    __slots__ = ("brain", "score", "n_eval", "suma_eval", "val")

    def __init__(self, brain):
        self.brain = brain
        self.score = float("-inf")
        self.n_eval = 0
        self.suma_eval = 0.0
        self.val = None

    @property
    def media_historica(self):
        return self.suma_eval / self.n_eval if self.n_eval else float("-inf")


def tournament_select(pop, rng=random):
    """Seleccion por torneo: toma K individuos al azar y devuelve el de mayor score."""
    aspirantes = rng.sample(pop, min(TOURNAMENT_K, len(pop)))
    return max(aspirantes, key=lambda i: i.score)


def next_generation(pop, pop_size=POP_SIZE, mutation_std=MUTATION_STD,
                    elite=ELITE_COUNT, rng_py=random, rng_np=None):
    """Construye la siguiente generacion a partir de la actual (ya evaluada).

    La elite pasa como el MISMO individuo: mismos pesos y la misma informacion de
    rendimiento acumulada. El resto son hijos de padres elegidos por torneo, con
    cruce uniforme y mutacion. Los individuos invalidos (score -inf) nunca son
    elite y pierden cualquier torneo frente a uno valido.
    """
    ordenados = sorted(pop, key=lambda i: i.score, reverse=True)
    nueva = [i for i in ordenados[:min(elite, len(ordenados))] if i.score > float("-inf")]
    while len(nueva) < pop_size:
        padre_a = tournament_select(pop, rng_py)
        if rng_py.random() < CROSSOVER_RATE:
            padre_b = tournament_select(pop, rng_py)
            base = crossover(padre_a.brain, padre_b.brain, rng_np)
        else:
            base = padre_a.brain
        nueva.append(Individuo(mutate(base, std=mutation_std, rng=rng_np)))
    return nueva


def seed_population(seed_brain=None, pop_size=POP_SIZE, engine=DEFAULT_ENGINE, rng_np=None):
    """Poblacion inicial de un entrenamiento (lista de `Individuo`).

    Sin `seed_brain`: `pop_size` cerebros aleatorios del `engine` elegido. Con
    `seed_brain`, hereda el linaje: el propio cerebro (pesos exactos) mas variantes
    mutadas alrededor; el motor lo fija el `seed_brain`."""
    if seed_brain is None:
        return [Individuo(make_brain(engine, rng=rng_np)) for _ in range(pop_size)]
    poblacion = [Individuo(seed_brain.clone())]
    while len(poblacion) < pop_size:
        poblacion.append(Individuo(mutate(seed_brain, rng=rng_np)))
    return poblacion


def _diversidad(pop):
    """Distancia euclidea media de cada genoma al centroide de la poblacion."""
    W = np.array([np.concatenate([w.ravel() for w in i.brain.get_weights()]) for i in pop])
    return float(np.mean(np.linalg.norm(W - W.mean(axis=0), axis=1)))


def train(generations=DEFAULT_GENERATIONS, grid=DEFAULT_GRID, pop_size=POP_SIZE,
          seed_brain=None, on_event=None, elite=ELITE_COUNT, infinite=False,
          stop_check=None, pause_check=None, engine=DEFAULT_ENGINE, seed=None):
    """Ejecuta la neuroevolucion durante `generations` generaciones (1 a 100), o
    SIN LIMITE si `infinite=True`. Ver el protocolo de evaluacion en la cabecera.

    `seed` fija TODO el azar del entrenamiento (poblacion inicial, semillas de
    seleccion, cruce y mutacion): con la misma semilla y los mismos parametros el
    resultado es identico. Sin `seed` se sortea una y se devuelve en el resultado.
    Usa generadores propios, asi que otros hilos (juego manual, demo) no la alteran.

    Terminar antes de tiempo:
      - DESCARTAR: `on_event` devuelve False. Devuelve None (no se guarda nada).
      - DETENER: `stop_check()` devuelve True. La generacion en curso, si no ha
        terminado, se DESCARTA entera (no cuenta ni aporta records); se devuelve
        el resultado de las generaciones completas. No existe reanudacion: la
        poblacion no se persiste, solo el mejor cerebro.

    `pause_check()` congela el entrenamiento entre pasos mientras devuelva True.
    Su implementacion DEBE dejar de devolver True si se pide descartar o detener.

    Devuelve un dict con:
      brain          cerebro con el MEJOR fitness medio en validacion (o el
                     heredado si ningun candidato lo supero)
      mejora_validada  True si `brain` supera en validacion al heredado (o es nuevo)
      validacion     {"episodios", "fitness_media"} del cerebro devuelto
      eval           `evaluar(brain, grid)`: rendimiento en las semillas de prueba
      fitness/frutas/pasos/length  la MEJOR PARTIDA INDIVIDUAL observada en las
                     generaciones completas (record de un episodio, al final de la
                     partida); cobertura/nivel/nivel_etiqueta salen de ella
      generaciones   generaciones COMPLETADAS
      grid, engine, detenido, seed, invalidos

    Eventos: ("step", {...}) por turno simulado, ("gen", {...}) por generacion.
    """
    generations = 0 if infinite else clamp_generations(generations)
    grid = clamp_grid(grid)
    pop_size = clamp_pop_size(pop_size)
    elite = clamp_elite(elite, pop_size)
    engine = seed_brain.NAME if seed_brain is not None else clamp_engine(engine)
    if seed is None:
        seed = random.SystemRandom().randrange(2 ** 31)
    seed = int(seed)
    rng_py = random.Random(seed)
    rng_np = np.random.default_rng(seed)
    population = seed_population(seed_brain, pop_size, engine, rng_np)
    sem_val = semillas_validacion()

    # Mejor cerebro VALIDADO hasta ahora. Al continuar un linaje, el heredado se
    # valida primero: solo se sustituye si un candidato lo supera en las MISMAS
    # semillas de validacion.
    mejor = None
    heredado = None
    if seed_brain is not None:
        heredado = population[0]
        heredado.val = _media_fitness(heredado.brain, grid, sem_val)
        mejor = heredado

    record = None            # Mejor partida individual de las generaciones completas
    invalidos = 0
    frame = 0
    mutation_std = MUTATION_STD
    sin_mejora = 0

    def emit(tipo, datos):
        """Notifica a la interfaz; devuelve False si esta pide cancelar."""
        if on_event is None:
            return True
        return on_event(tipo, datos) is not False

    def esperar():
        while pause_check is not None and pause_check():
            time.sleep(0.05)
        return stop_check is not None and stop_check()

    gen = 0
    completadas = 0
    detenido = False

    while infinite or gen < generations:
        gen += 1
        semillas = [rng_py.randrange(TRAIN_SEED_MIN, 2 ** 31) for _ in range(EVAL_EPISODES)]
        record_gen = None
        invalidos_gen = 0
        largo_gen = INITIAL_LENGTH
        puntuaciones = []

        for idx, ind in enumerate(population, start=1):
            if esperar():
                detenido = True
                break
            total, valido = 0.0, True
            for ep, sem in enumerate(semillas, start=1):
                snake = Snake(ind.brain, grid=grid, rng=random.Random(sem))
                while snake.alive:
                    if esperar():
                        detenido = True
                        break
                    snake.step_ai()
                    frame += 1
                    if not emit("step", {
                        "generation":   gen,
                        "generations":  generations,
                        "infinito":     infinite,
                        "agent":        idx,
                        "episodio":     ep,
                        "episodios":    len(semillas),
                        "pop_size":     pop_size,
                        "best_fitness": record["fitness"] if record else None,
                        "frame":        frame,
                        "snake":        snake.to_state(),
                    }):
                        return None
                if detenido:
                    break
                if snake.invalid:
                    valido = False
                    break
                f = snake.fitness()
                total += f
                largo_gen = max(largo_gen, snake.length)
                if record_gen is None or f > record_gen["fitness"]:
                    record_gen = {"fitness": f, "frutas": snake.fruits,
                                  "pasos": snake.steps, "length": snake.length}
            if detenido:
                break
            if valido:
                ind.score = total / len(semillas)
                ind.n_eval += len(semillas)
                ind.suma_eval += total
                puntuaciones.append(ind.score)
            else:
                ind.score = float("-inf")
                invalidos_gen += 1

        # Parada dentro de la generacion: se descarta entera.
        if detenido:
            break

        completadas = gen
        invalidos += invalidos_gen
        if record_gen is not None and (record is None or record_gen["fitness"] > record["fitness"]):
            record = record_gen

        # Validacion del campeon de la generacion en semillas FIJAS.
        campeon = max(population, key=lambda i: i.score)
        if campeon.score > float("-inf") and campeon.val is None:
            campeon.val = _media_fitness(campeon.brain, grid, sem_val)
        mejoro = (campeon.val is not None and campeon.val > float("-inf")
                  and (mejor is None or campeon.val > mejor.val))
        if mejoro:
            mejor = campeon
            sin_mejora = 0
        else:
            sin_mejora += 1
            if sin_mejora >= STAGNATION_PATIENCE:
                mutation_std = max(MUTATION_STD_MIN, mutation_std * MUTATION_DECAY)
                sin_mejora = 0

        info = nivel_de_cobertura(cobertura(record["length"] if record else INITIAL_LENGTH, grid))
        if not emit("gen", {
            "generation":     gen,
            "generations":    generations,
            "infinito":       infinite,
            # Fitness de SELECCION (media en las semillas de esta generacion):
            # comparable dentro de la generacion, no entre generaciones.
            "best":           campeon.score if campeon.score > float("-inf") else None,
            "avg":            sum(puntuaciones) / len(puntuaciones) if puntuaciones else None,
            # Fitness de VALIDACION (semillas fijas): comparable entre generaciones.
            "val_campeon":    campeon.val if campeon.val not in (None, float("-inf")) else None,
            "val_record":     mejor.val if mejor is not None else None,
            "best_length":    largo_gen,
            "cobertura":      info["cobertura"],
            "nivel":          info["nivel"],
            "nivel_etiqueta": info["etiqueta"],
            "mutation_std":   round(mutation_std, 4),
            "invalidos":      invalidos_gen,
            "diversidad":     round(_diversidad(population), 4),
            "episodios_por_agente": len(semillas),
        }):
            return None

        if stop_check is not None and stop_check():
            detenido = True
            break

        if infinite or gen < generations:
            population = next_generation(population, pop_size, mutation_std=mutation_std,
                                         elite=elite, rng_py=rng_py, rng_np=rng_np)

    if mejor is None:
        # Ninguna generacion completa y especimen nuevo: no hay nada validado. Se
        # devuelve el primer cerebro tal cual (generaciones = 0 lo deja claro).
        mejor = population[0]
        mejor.val = _media_fitness(mejor.brain, grid, sem_val)
    brain = mejor.brain.clone()
    evaluacion = evaluar(brain, grid)
    if record is None:
        record = {"fitness": 0.0, "frutas": 0, "pasos": 0, "length": INITIAL_LENGTH}
    info = nivel_de_cobertura(cobertura(record["length"], grid))
    return {
        "brain":           brain,
        "mejora_validada": heredado is None or mejor is not heredado,
        "validacion":      {"episodios": len(sem_val),
                            "fitness_media": None if mejor.val in (None, float("-inf"))
                            else round(float(mejor.val), 2)},
        "eval":            evaluacion,
        "fitness":         int(math.floor(record["fitness"])),
        "frutas":          int(record["frutas"]),
        "pasos":           int(record["pasos"]),
        "length":          int(record["length"]),
        "generaciones":    completadas,
        "grid":            grid,
        "engine":          engine,
        "cobertura":       info["cobertura"],
        "nivel":           info["nivel"],
        "nivel_etiqueta":  info["etiqueta"],
        "detenido":        detenido,
        "seed":            seed,
        "invalidos":       invalidos,
    }
