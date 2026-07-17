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

    - `NeuralNetwork`  red RECURRENTE 26 -> 20 -> 3 (vision ampliada + memoria)
    - `Snake`          el agente: sensores, movimiento, tamano y fitness
    - `crossover` / `mutate` / `next_generation`   algoritmo genetico
    - `train`          la neuroevolucion completa, con herencia de linaje
    - `nivel_de_cobertura`  clasifica la inteligencia por cobertura (ver plan.txt)

  Lo usan `ai_server.py` (servidor de la web) y cualquier script suelto.
  La persistencia vive en `storage.py`.

  NEUROEVOLUCION CON HERENCIA
  ---------------------------
  No hay descenso de gradiente ni dataset. Se evoluciona una poblacion:
    Gen 1: pesos aleatorios (o heredados de un linaje previo).
    Gen N: los MEJORES hijos de la Gen N-1 son la base de la Gen N.
           La elite pasa intacta; el resto son cruces mutados de los mejores.
  Asi la Generacion 2 se entrena literalmente sobre los mejores de la 1.
================================================================================
"""

import random

import numpy as np

# =============================================================================
#  PARAMETROS DEL MUNDO Y DEL ALGORITMO
# =============================================================================
GRID_SIZES    = (8, 10, 15)  # Dimensiones de tablero que ofrece la interfaz
DEFAULT_GRID  = 8

POP_SIZE      = 25           # Agentes por generacion
DEFAULT_GENERATIONS = 5      # Generaciones por entrenamiento
MIN_GENERATIONS = 1
MAX_GENERATIONS = 100

ENERGY_START  = 200          # Pasos sin comer antes de morir de inanicion
ELITE_COUNT   = 3            # Elitismo: mejores redes que pasan intactas
MUTATION_RATE = 0.05         # Probabilidad de mutacion por peso (5%)
MUTATION_STD  = 0.20         # Desviacion del ruido gaussiano de mutacion (inicial)
TOURNAMENT_K  = 3            # Tamano del torneo de seleccion

INITIAL_LENGTH = 3           # Longitud con la que nace la serpiente
FRUIT_REWARD   = 1000        # Fitness que aporta cada bloque de crecimiento

# --- Fitness shaping: recompensa densa de acercamiento (desbloquea N1/N2) ---
# Ademas de premiar comer (que domina), se da una senal continua por acercarse
# a la manzana. Es ASIMETRICA: alejarse penaliza algo mas que acercarse premia,
# para desincentivar el merodeo en circulos. Es lo que acelera el salto de una
# supervivencia refleja (N0) a un forrajeo intencionado (N1/N2) sin depender del
# golpe de suerte del elitismo.
APPROACH_REWARD  = 3.0       # Fitness por acercarse una casilla a la manzana
APPROACH_PENALTY = 4.0       # Castigo por alejarse una casilla

# --- Mutacion adaptativa (recocido): fiabilidad (N2) ---
# Si el mejor fitness de la poblacion se estanca varias generaciones, se reduce
# la desviacion de la mutacion: se pasa de "saltar al azar" a "afinar" alrededor
# de una solucion que ya funciona, sin dejar nunca de explorar del todo.
STAGNATION_PATIENCE = 4      # Generaciones sin mejora antes de enfriar
MUTATION_DECAY      = 0.85   # Factor de enfriamiento por estancamiento
MUTATION_STD_MIN    = 0.05   # Suelo: nunca deja de explorar del todo

# --- Arquitectura de la red (VISION AMPLIADA) ---
# 8 direcciones EGOCENTRICAS x 3 rasgos (pared / cuerpo / alineacion con la
# comida) = 24 sensores de entorno, mas 2 sensores globales (tamano propio y
# espacio libre alcanzable) = 26 entradas. La capa oculta crece a 20 neuronas
# para explotar esa percepcion mas rica. Es el salto que rompe el techo del
# forrajeo (3 rayos no bastan para ver el tablero) y habilita la conciencia
# espacial (N3): la serpiente puede "ver en diagonal" y saber si se esta
# encerrando antes de hacerlo.
N_RAY_DIRS   = 8             # Rayos egocentricos: F, FD, D, TD, T, TI, I, FI
N_TRAITS     = 3             # Por rayo: pared, cuerpo, alineacion con la comida
N_ENV_INPUTS = N_RAY_DIRS * N_TRAITS      # 24
N_EXTRA      = 2             # Sensor de tamano + sensor de espacio libre
N_INPUTS     = N_ENV_INPUTS + N_EXTRA     # 26
N_HIDDEN     = 20
N_OUTPUTS    = 3             # Recto / Girar Izquierda / Girar Derecha

# Direcciones cardinales en orden HORARIO: UP -> RIGHT -> DOWN -> LEFT
DIRS = [(0, -1), (1, 0), (0, 1), (-1, 0)]

# =============================================================================
#  NIVELES DE INTELIGENCIA  (ver plan.txt)
# =============================================================================
#  La inteligencia de un especimen se mide por su COBERTURA: que fraccion del
#  tablero llega a ocupar su cuerpo. Es independiente del tamano de tablero, asi
#  que compara de forma justa corridas de 8x8, 10x10 y 15x15. Cada entrenamiento
#  que mejora el record sube (o mantiene) el nivel del especimen.
NIVELES = [
    (0.10, 0, "N0 · Supervivencia refleja"),
    (0.20, 1, "N1 · Forrajeo básico"),
    (0.35, 2, "N2 · Forrajeo fiable"),
    (0.55, 3, "N3 · Conciencia espacial"),
    (0.80, 4, "N4 · Planificación emergente"),
]
NIVEL_MAX = (5, "N5 · Casi óptimo")


def cobertura(length, grid):
    """Fraccion del tablero ocupada por la serpiente [0-1] = longitud / area."""
    area = float(grid * grid) or 1.0
    return max(0.0, min(1.0, length / area))


def nivel_de_cobertura(cob):
    """Clasifica una cobertura [0-1] en un nivel de inteligencia (ver plan.txt).

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


# =============================================================================
#  RED NEURONAL RECURRENTE (numpy)
# =============================================================================
class NeuralNetwork:
    """Red recurrente: entrada + estado anterior -> capa oculta (ReLU) -> salida.

    La capa oculta se realimenta a si misma a traves de `W_rec`: en cada turno ve
    las entradas del momento Y su propio estado del turno anterior. Eso le da
    MEMORIA dentro de una partida (recordar por donde venia), el ingrediente que
    la planificacion emergente (N4) necesita y que una feedforward pura no tiene.

    `W_rec` nace a CERO: una red recien creada se comporta exactamente como una
    feedforward, y la mutacion va introduciendo memoria poco a poco. Asi anadir
    recurrencia no degrada nada de lo ya aprendido (ver `from_dict`).
    """

    def __init__(self, weights=None):
        """Crea la red. Sin pesos, los inicializa (init He; memoria a cero);
        con `weights`, reutiliza los dados (hijos del algoritmo genetico)."""
        if weights is None:
            self.W1 = np.random.randn(N_HIDDEN, N_INPUTS) * np.sqrt(2.0 / N_INPUTS)
            self.b1 = np.zeros(N_HIDDEN)
            self.W_rec = np.zeros((N_HIDDEN, N_HIDDEN))   # Sin memoria al nacer
            self.W2 = np.random.randn(N_OUTPUTS, N_HIDDEN) * np.sqrt(2.0 / N_HIDDEN)
            self.b2 = np.zeros(N_OUTPUTS)
        else:
            self.W1, self.b1, self.W_rec, self.W2, self.b2 = weights
        self.h = np.zeros(N_HIDDEN)   # Estado oculto: la memoria intra-partida

    def reset_state(self):
        """Olvida la memoria: cada partida arranca con el estado oculto a cero."""
        self.h = np.zeros(N_HIDDEN)

    def forward(self, x):
        """Propaga las entradas (mas el estado anterior) y devuelve la accion:
        0=Recto, 1=Girar izquierda, 2=Girar derecha (indice de la salida maxima)."""
        # La capa oculta ve la entrada Y su propio estado previo (memoria).
        h = np.maximum(0.0, self.W1 @ x + self.b1 + self.W_rec @ self.h)
        self.h = h                                    # Se recuerda para el turno siguiente
        o = self.W2 @ h + self.b2                     # Capa de salida lineal
        return int(np.argmax(o))

    def get_weights(self):
        """Devuelve una copia de todos los pesos y sesgos como lista de arrays."""
        return [self.W1.copy(), self.b1.copy(), self.W_rec.copy(),
                self.W2.copy(), self.b2.copy()]

    def clone(self):
        """Crea una red nueva e independiente con los mismos pesos (memoria limpia)."""
        return NeuralNetwork(self.get_weights())

    def to_dict(self):
        """Serializa los pesos a listas de Python para poder guardarlos en JSON."""
        return {"W1": self.W1.tolist(), "b1": self.b1.tolist(),
                "W_rec": self.W_rec.tolist(),
                "W2": self.W2.tolist(), "b2": self.b2.tolist()}

    @classmethod
    def from_dict(cls, d):
        """Reconstruye una red desde `to_dict`, ADAPTANDOLA a la arquitectura
        actual sea cual sea el tamano con que se guardo.

        Los especimenes viejos tienen menos entradas (9 o 10), menos neuronas
        ocultas (12) y NINGUNA conexion recurrente frente a la red de ahora
        (26 -> 20 -> 3 con memoria). Se copian sus pesos en la esquina de una red
        nueva y TODO lo demas se deja NEUTRO: las entradas nuevas con peso cero
        (no influyen), las neuronas nuevas con salida cero (no aportan) y la
        memoria a cero (se comporta como feedforward). Asi la red decide
        EXACTAMENTE lo mismo que antes de crecer, y la mutacion se encarga luego
        de dar uso a la capacidad nueva. Consecuencia: seguir entrenando nunca
        degrada lo aprendido, ni siquiera al agrandar el cerebro entre versiones.
        """
        W1 = np.array(d["W1"], dtype=np.float64)
        b1 = np.array(d["b1"], dtype=np.float64)
        W2 = np.array(d["W2"], dtype=np.float64)
        b2 = np.array(d["b2"], dtype=np.float64)
        W_rec = np.array(d["W_rec"], dtype=np.float64) if "W_rec" in d else None
        return cls(cls._adapt_weights(W1, b1, W2, b2, W_rec))

    @staticmethod
    def _adapt_weights(W1, b1, W2, b2, W_rec=None):
        """Encaja pesos de cualquier tamano en la arquitectura actual sin alterar
        la salida para las entradas que ya existian (ver `from_dict`)."""
        h_old, in_old = W1.shape
        out_old      = W2.shape[0]
        h_copy   = min(h_old, N_HIDDEN)
        in_copy  = min(in_old, N_INPUTS)
        out_copy = min(out_old, N_OUTPUTS)

        # Red nueva: capa oculta con init He; SALIDA a cero => las neuronas que
        # no se hereden empiezan siendo neutras (no aportan hasta que muten).
        # Memoria (W_rec) a cero => sin recurrencia hasta que la mutacion la cree.
        nW1 = np.random.randn(N_HIDDEN, N_INPUTS) * np.sqrt(2.0 / N_INPUTS)
        nb1 = np.zeros(N_HIDDEN)
        nW_rec = np.zeros((N_HIDDEN, N_HIDDEN))
        nW2 = np.zeros((N_OUTPUTS, N_HIDDEN))
        nb2 = np.zeros(N_OUTPUTS)

        # Neuronas heredadas: conservan sus pesos, pero IGNORAN los sensores
        # nuevos (sus columnas nuevas quedan a cero) para no cambiar de decision.
        nW1[:h_copy, :in_copy] = W1[:h_copy, :in_copy]
        nW1[:h_copy, in_copy:] = 0.0
        nb1[:h_copy]           = b1[:h_copy]
        nW2[:out_copy, :h_copy] = W2[:out_copy, :h_copy]
        nb2[:out_copy]          = b2[:out_copy]
        # Recurrencia heredada (si el modelo guardado ya la tenia); si no, queda
        # a cero y la red se comporta como la feedforward que era.
        if W_rec is not None:
            hr = min(W_rec.shape[0], N_HIDDEN)
            hc = min(W_rec.shape[1], N_HIDDEN)
            nW_rec[:hr, :hc] = W_rec[:hr, :hc]
        return [nW1, nb1, nW_rec, nW2, nb2]


def crossover(parent_a, parent_b):
    """Crossover uniforme elemento a elemento entre los pesos de dos padres."""
    child_weights = []
    for wa, wb in zip(parent_a.get_weights(), parent_b.get_weights()):
        mask = np.random.rand(*wa.shape) < 0.5
        child_weights.append(np.where(mask, wa, wb))
    return NeuralNetwork(child_weights)


def mutate(net, std=MUTATION_STD):
    """Mutacion gaussiana con probabilidad MUTATION_RATE por peso.

    `std` es la desviacion del ruido; el entrenamiento la baja cuando la
    poblacion se estanca (recocido) para pasar de explorar a afinar.
    """
    new_weights = []
    for w in net.get_weights():
        mask = np.random.rand(*w.shape) < MUTATION_RATE
        noise = np.random.randn(*w.shape) * std
        new_weights.append(w + mask * noise)
    return NeuralNetwork(new_weights)


# =============================================================================
#  AGENTE (SNAKE)
# =============================================================================
class Snake:
    """Agente Snake: cuerpo sobre la cuadricula, sensores, movimiento y estado.

    El tablero es un parametro (`grid`), no una constante global: la interfaz
    ofrece 8x8, 10x10 y 15x15. Los sensores se normalizan dividiendo por `grid`,
    de modo que una red entrenada en 8x8 sigue siendo valida en 15x15.
    """

    def __init__(self, brain=None, grid=DEFAULT_GRID, use_energy=True):
        """Inicializa el agente con un cerebro dado o uno nuevo.
        `use_energy` activa la muerte por inanicion (se desactiva en modo manual)."""
        self.grid       = grid
        self.brain      = brain if brain is not None else NeuralNetwork()
        self.use_energy = use_energy
        self.reset()

    def reset(self):
        """Coloca la serpiente en el centro y reinicia cuerpo, energia y marcadores."""
        cx = cy = self.grid // 2
        self.body   = [(cx - i, cy) for i in range(INITIAL_LENGTH)]
        self.dir_i  = 1                 # 1 = mirando a la derecha
        self.alive  = True
        self.brain.reset_state()        # Nueva partida = memoria en blanco
        self.energy = ENERGY_START
        self.steps  = 0
        self.fruits = 0
        self.food   = None
        self.shaping = 0.0              # Fitness acumulado por acercarse a la comida
        # Copia del cuerpo como SET: la percepcion (8 rayos + flood-fill) consulta
        # colisiones miles de veces por partida, y `en un set` es O(1) frente al
        # O(n) de `en una lista`. Se mantiene en sincronia dentro de `advance`.
        self._body_set = set(self.body)
        self.spawn_food()
        self._prev_food_dist = self._food_distance()

    # --- Tamano -------------------------------------------------------------
    @property
    def length(self):
        """Tamano actual de la serpiente. Crece 1 bloque por cada manzana."""
        return len(self.body)

    def _length_sensor(self):
        """Sensor propioceptivo [0-1]: que fraccion del tablero ocupa su cuerpo.

        Es la entrada que le permite 'saber que tiene un tamano'. Se normaliza
        por el area total para que el valor signifique lo mismo en 8x8 que en
        15x15 (en un tablero pequeno, 10 bloques son muchisimo; en uno grande,
        casi nada).
        """
        return self.length / float(self.grid * self.grid)

    def spawn_food(self):
        """Situa una manzana en una celda libre al azar (None si no queda ninguna)."""
        libres = [(x, y) for x in range(self.grid) for y in range(self.grid)
                  if (x, y) not in self._body_set]
        self.food = random.choice(libres) if libres else None

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
        Frente, Frente-Der, Der, Tras-Der, Tras, Tras-Izq, Izq, Frente-Izq.

        Se construyen a partir del rumbo actual sumando cardinales, asi que las
        diagonales salen solas y la percepcion es siempre relativa a hacia donde
        mira la serpiente (lo que aprende en 8x8 vale en cualquier tablero)."""
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
        """Sensor global [0-1]: fraccion del tablero ALCANZABLE desde la cabeza.

        Un flood-fill sobre las celdas libres partiendo de la cabeza. Es la senal
        que evita el suicidio por encierro: si la serpiente esta a punto de
        sellarse en un hueco pequeno, este valor se desploma antes del choque, y
        la evolucion puede aprender a no meterse ahi (base de la conciencia
        espacial, N3).

        Se calcula en CADA turno de CADA agente, asi que es el punto mas caliente
        del simulador. Por eso usa indices planos (y*grid+x) y un `bytearray` de
        visitados en vez de un set de tuplas: misma semantica, sin el coste de
        hashear miles de tuplas por partida.
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
            # Shaping denso: premia acercarse a la manzana, castiga (algo mas)
            # alejarse. Solo cuando NO se ha comido este turno (comer ya lo premia
            # FRUIT_REWARD, mil veces mas: crecer sigue siendo lo que manda).
            nueva = self._food_distance()
            if nueva < self._prev_food_dist:
                self.shaping += APPROACH_REWARD
            elif nueva > self._prev_food_dist:
                self.shaping -= APPROACH_PENALTY
            self._prev_food_dist = nueva

        if self.use_energy and self.energy <= 0:                 # Inanicion
            self.alive = False

    def step_ai(self):
        """Un turno gobernado por la red neuronal."""
        if not self.alive:
            return
        self._apply_action(self.brain.forward(self.get_inputs()))
        self.advance()

    def fitness(self):
        """Fitness = pasos + crecimiento * FRUIT_REWARD + shaping de acercamiento.

        El crecimiento (`length - INITIAL_LENGTH`, bloques ganados comiendo) sigue
        dominando por mil, asi que la evolucion premia sobre todo COMER. Lo nuevo
        es el `shaping`: una senal densa por acercarse a la manzana que orienta a
        los que aun no han comido, en vez de dejar que solo el azar los desempate.
        Es lo que acelera el aprendizaje del forrajeo (N0 -> N1/N2).
        """
        crecimiento = self.length - INITIAL_LENGTH
        return self.steps + crecimiento * FRUIT_REWARD + self.shaping

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
#  ALGORITMO GENETICO
# =============================================================================
def tournament_select(pop):
    """Seleccion por torneo: toma K agentes al azar y devuelve el de mayor fitness."""
    aspirantes = random.sample(pop, min(TOURNAMENT_K, len(pop)))
    return max(aspirantes, key=lambda s: s.fitness())


def next_generation(pop, grid=DEFAULT_GRID, pop_size=POP_SIZE, mutation_std=MUTATION_STD):
    """Construye la siguiente generacion a partir de los MEJORES de la actual.

    Aqui ocurre la herencia: se ordena por fitness, la elite pasa intacta y el
    resto son hijos de padres elegidos por torneo (los buenos salen mas), con
    cruce uniforme y mutacion. La Gen N+1 nace, literalmente, de la Gen N.

    `mutation_std` la fija el entrenamiento: baja cuando la poblacion se estanca
    (recocido) para afinar en vez de saltar al azar.
    """
    ordenados = sorted(pop, key=lambda s: s.fitness(), reverse=True)
    nueva = [Snake(ordenados[i].brain.clone(), grid=grid)
             for i in range(min(ELITE_COUNT, len(ordenados)))]
    while len(nueva) < pop_size:
        padre_a = tournament_select(pop)
        padre_b = tournament_select(pop)
        hijo = mutate(crossover(padre_a.brain, padre_b.brain), std=mutation_std)
        nueva.append(Snake(hijo, grid=grid))
    return nueva


def seed_population(seed_brain=None, grid=DEFAULT_GRID, pop_size=POP_SIZE):
    """Poblacion inicial de un entrenamiento.

    Sin `seed_brain` empieza de cero (especimen nuevo, pesos aleatorios). Con el,
    hereda el linaje: un clon exacto -para no perder nunca lo aprendido- mas
    variantes mutadas que exploran a su alrededor. Es lo que permite continuar
    entrenando a un especimen guardado en vez de reiniciarlo.
    """
    if seed_brain is None:
        return [Snake(grid=grid) for _ in range(pop_size)]
    poblacion = [Snake(seed_brain.clone(), grid=grid)]
    while len(poblacion) < pop_size:
        poblacion.append(Snake(mutate(seed_brain), grid=grid))
    return poblacion


def train(generations=DEFAULT_GENERATIONS, grid=DEFAULT_GRID, pop_size=POP_SIZE,
          seed_brain=None, on_event=None):
    """Ejecuta la neuroevolucion durante `generations` generaciones (1 a 100).

    En vez de dibujar, llama a `on_event(tipo, datos)`: cada interfaz decide que
    hacer con el progreso. Si `on_event` devuelve False, el entrenamiento se
    CANCELA y esta funcion devuelve None.

    NO guarda nada: devuelve el mejor linaje y es quien llama el que decide si
    crea un especimen nuevo o le suma generaciones a uno existente.

    Devuelve {"brain", "fitness", "frutas", "pasos", "length", "generaciones",
    "grid", "cobertura", "nivel", "nivel_etiqueta"}, o None si se cancelo.

    Eventos: ("step", {...}) por turno simulado, ("gen", {...}) por generacion.
    """
    generations = clamp_generations(generations)
    grid = clamp_grid(grid)
    population = seed_population(seed_brain, grid, pop_size)

    best_fitness = -1
    best_brain   = population[0].brain.clone()
    best_fruits  = best_steps = 0
    best_length  = INITIAL_LENGTH
    frame = 0

    # Estado del recocido de mutacion: si el mejor fitness no mejora durante
    # STAGNATION_PATIENCE generaciones, se enfria la desviacion de la mutacion.
    mutation_std = MUTATION_STD
    mejor_historico = -1
    sin_mejora = 0

    def emit(tipo, datos):
        """Notifica a la interfaz; devuelve False si esta pide cancelar."""
        if on_event is None:
            return True
        return on_event(tipo, datos) is not False

    for gen in range(1, generations + 1):
        for idx, snake in enumerate(population, start=1):
            while snake.alive:
                snake.step_ai()
                frame += 1

                if snake.fitness() > best_fitness:
                    best_fitness = snake.fitness()
                    best_brain   = snake.brain.clone()
                    best_fruits  = snake.fruits
                    best_steps   = snake.steps
                    best_length  = snake.length

                if not emit("step", {
                    "generation":   gen,
                    "generations":  generations,
                    "agent":        idx,
                    "pop_size":     pop_size,
                    "best_fitness": best_fitness,
                    "frame":        frame,
                    "snake":        snake.to_state(),
                }):
                    return None

        fitnesses = [s.fitness() for s in population]
        gen_best = max(fitnesses)

        # Recocido adaptativo de la mutacion.
        if gen_best > mejor_historico + 1e-9:
            mejor_historico = gen_best
            sin_mejora = 0
        else:
            sin_mejora += 1
            if sin_mejora >= STAGNATION_PATIENCE:
                mutation_std = max(MUTATION_STD_MIN, mutation_std * MUTATION_DECAY)
                sin_mejora = 0

        info = nivel_de_cobertura(cobertura(best_length, grid))
        if not emit("gen", {
            "generation":     gen,
            "generations":    generations,
            "best":           gen_best,
            "avg":            sum(fitnesses) / float(len(population)),
            "best_length":    max(s.length for s in population),
            "cobertura":      info["cobertura"],
            "nivel":          info["nivel"],
            "nivel_etiqueta": info["etiqueta"],
            "mutation_std":   round(mutation_std, 4),
        }):
            return None

        # La ultima generacion no necesita descendencia: ya se evaluo.
        if gen < generations:
            population = next_generation(population, grid, pop_size,
                                         mutation_std=mutation_std)

    info = nivel_de_cobertura(cobertura(best_length, grid))
    return {
        "brain":          best_brain,
        "fitness":        int(best_fitness),
        "frutas":         int(best_fruits),
        "pasos":          int(best_steps),
        "length":         int(best_length),
        "generaciones":   generations,
        "grid":           grid,
        "cobertura":      info["cobertura"],
        "nivel":          info["nivel"],
        "nivel_etiqueta": info["etiqueta"],
    }
