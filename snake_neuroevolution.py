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

    - `NeuralNetwork`  red feedforward 10 -> 12 -> 3
    - `Snake`          el agente: sensores, movimiento, tamano y fitness
    - `crossover` / `mutate` / `next_generation`   algoritmo genetico
    - `train`          la neuroevolucion completa, con herencia de linaje

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
MUTATION_STD  = 0.20         # Desviacion del ruido gaussiano de mutacion
TOURNAMENT_K  = 3            # Tamano del torneo de seleccion

INITIAL_LENGTH = 3           # Longitud con la que nace la serpiente
FRUIT_REWARD   = 1000        # Fitness que aporta cada bloque de crecimiento

# --- Arquitectura de la red ---
# 9 sensores del entorno + 1 propioceptivo (su propio tamano) = 10 entradas.
N_ENV_INPUTS = 9             # 3 direcciones (Frente/Izq/Der) x 3 rasgos
N_INPUTS     = 10
N_HIDDEN     = 12
N_OUTPUTS    = 3             # Recto / Girar Izquierda / Girar Derecha

# Direcciones en orden HORARIO: UP -> RIGHT -> DOWN -> LEFT
DIRS = [(0, -1), (1, 0), (0, 1), (-1, 0)]

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
#  RED NEURONAL FEEDFORWARD (numpy)
# =============================================================================
class NeuralNetwork:
    """Red feedforward: entrada -> capa oculta (ReLU) -> salida."""

    def __init__(self, weights=None):
        """Crea la red. Sin pesos, los inicializa aleatoriamente (init He);
        con `weights`, reutiliza los dados (hijos del algoritmo genetico)."""
        if weights is None:
            self.W1 = np.random.randn(N_HIDDEN, N_INPUTS) * np.sqrt(2.0 / N_INPUTS)
            self.b1 = np.zeros(N_HIDDEN)
            self.W2 = np.random.randn(N_OUTPUTS, N_HIDDEN) * np.sqrt(2.0 / N_HIDDEN)
            self.b2 = np.zeros(N_OUTPUTS)
        else:
            self.W1, self.b1, self.W2, self.b2 = weights

    def forward(self, x):
        """Propaga las entradas y devuelve la accion elegida:
        0=Recto, 1=Girar izquierda, 2=Girar derecha (indice de la salida maxima)."""
        h = np.maximum(0.0, self.W1 @ x + self.b1)   # Capa oculta con ReLU
        o = self.W2 @ h + self.b2                     # Capa de salida lineal
        return int(np.argmax(o))

    def get_weights(self):
        """Devuelve una copia de todos los pesos y sesgos como lista de arrays."""
        return [self.W1.copy(), self.b1.copy(), self.W2.copy(), self.b2.copy()]

    def clone(self):
        """Crea una red nueva e independiente con los mismos pesos."""
        return NeuralNetwork(self.get_weights())

    def to_dict(self):
        """Serializa los pesos a listas de Python para poder guardarlos en JSON."""
        return {"W1": self.W1.tolist(), "b1": self.b1.tolist(),
                "W2": self.W2.tolist(), "b2": self.b2.tolist()}

    @classmethod
    def from_dict(cls, d):
        """Reconstruye una red desde el diccionario producido por `to_dict`.

        Acepta redes de 9 entradas guardadas antes de existir el sensor de
        tamano: se les anade una columna de CEROS. El peso cero hace que la
        entrada nueva no influya, asi que la red decide exactamente lo mismo que
        antes; a partir de ahi la mutacion puede empezar a darle uso.
        """
        W1 = np.array(d["W1"], dtype=np.float64)
        if W1.shape[1] == N_ENV_INPUTS:
            W1 = np.hstack([W1, np.zeros((W1.shape[0], 1))])
        weights = [W1, np.array(d["b1"]), np.array(d["W2"]), np.array(d["b2"])]
        return cls(weights)


def crossover(parent_a, parent_b):
    """Crossover uniforme elemento a elemento entre los pesos de dos padres."""
    child_weights = []
    for wa, wb in zip(parent_a.get_weights(), parent_b.get_weights()):
        mask = np.random.rand(*wa.shape) < 0.5
        child_weights.append(np.where(mask, wa, wb))
    return NeuralNetwork(child_weights)


def mutate(net):
    """Mutacion gaussiana con probabilidad MUTATION_RATE por peso."""
    new_weights = []
    for w in net.get_weights():
        mask = np.random.rand(*w.shape) < MUTATION_RATE
        noise = np.random.randn(*w.shape) * MUTATION_STD
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
        self.energy = ENERGY_START
        self.steps  = 0
        self.fruits = 0
        self.food   = None
        self.spawn_food()

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
                  if (x, y) not in self.body]
        self.food = random.choice(libres) if libres else None

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
            if (nx, ny) in self.body:
                return 1.0 - (step - 1) / float(self.grid)
            nx += d[0]; ny += d[1]; step += 1
        return 0.0

    def get_inputs(self):
        """10 entradas: pared/cuerpo/manzana en Frente, Izq y Der + su tamano."""
        head  = self.body[0]
        front = DIRS[self.dir_i]
        left  = DIRS[(self.dir_i - 1) % 4]
        right = DIRS[(self.dir_i + 1) % 4]

        wall = [self._wall_distance(head, d) for d in (front, left, right)]
        body = [self._body_distance(head, d) for d in (front, left, right)]

        fx, fy = self.food
        vx, vy = fx - head[0], fy - head[1]
        norm = (vx * vx + vy * vy) ** 0.5 or 1.0
        vx, vy = vx / norm, vy / norm
        food = [vx * d[0] + vy * d[1] for d in (front, left, right)]

        return np.array(wall + body + food + [self._length_sensor()],
                        dtype=np.float64)

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
        if (nx, ny) in self.body[:-1]:                           # Propio cuerpo
            self.alive = False; return

        self.body.insert(0, (nx, ny))
        self.steps += 1
        if self.use_energy:
            self.energy -= 1

        if (nx, ny) == self.food:
            # Comer = NO quitar la cola: el cuerpo crece un bloque.
            self.fruits += 1
            self.energy = ENERGY_START
            self.spawn_food()
        else:
            self.body.pop()

        if self.use_energy and self.energy <= 0:                 # Inanicion
            self.alive = False

    def step_ai(self):
        """Un turno gobernado por la red neuronal."""
        if not self.alive:
            return
        self._apply_action(self.brain.forward(self.get_inputs()))
        self.advance()

    def fitness(self):
        """Fitness = pasos sobrevividos + crecimiento * FRUIT_REWARD.

        El crecimiento es `length - INITIAL_LENGTH`, es decir cuantos bloques ha
        ganado comiendo. Sobrevivir suma poco y crecer suma muchisimo, asi que
        la evolucion premia sobre todo comer manzanas; los pasos solo desempatan
        entre agentes que aun no han comido.
        """
        crecimiento = self.length - INITIAL_LENGTH
        return self.steps + crecimiento * FRUIT_REWARD

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


def next_generation(pop, grid=DEFAULT_GRID, pop_size=POP_SIZE):
    """Construye la siguiente generacion a partir de los MEJORES de la actual.

    Aqui ocurre la herencia: se ordena por fitness, la elite pasa intacta y el
    resto son hijos de padres elegidos por torneo (los buenos salen mas), con
    cruce uniforme y mutacion. La Gen N+1 nace, literalmente, de la Gen N.
    """
    ordenados = sorted(pop, key=lambda s: s.fitness(), reverse=True)
    nueva = [Snake(ordenados[i].brain.clone(), grid=grid)
             for i in range(min(ELITE_COUNT, len(ordenados)))]
    while len(nueva) < pop_size:
        padre_a = tournament_select(pop)
        padre_b = tournament_select(pop)
        hijo = mutate(crossover(padre_a.brain, padre_b.brain))
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
    "grid"}, o None si se cancelo.

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
        if not emit("gen", {
            "generation":  gen,
            "generations": generations,
            "best":        max(fitnesses),
            "avg":         sum(fitnesses) / float(len(population)),
            "best_length": max(s.length for s in population),
        }):
            return None

        # La ultima generacion no necesita descendencia: ya se evaluo.
        if gen < generations:
            population = next_generation(population, grid, pop_size)

    return {
        "brain":        best_brain,
        "fitness":      int(best_fitness),
        "frutas":       int(best_fruits),
        "pasos":        int(best_steps),
        "length":       int(best_length),
        "generaciones": generations,
        "grid":         grid,
    }
