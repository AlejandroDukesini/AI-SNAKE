# -*- coding: utf-8 -*-
"""
================================================================================
  SNAKE resuelto mediante NEUROEVOLUCION (Red Neuronal + Algoritmo Genetico)
  + Menu interactivo, Modo entrenamiento a maxima velocidad, Juego manual y
    Salon de la Fama (trofeos) con persistencia en JSON.
================================================================================
  Reglas:
    - Tablero 8x8, movimiento bloque a bloque.
    - Poblacion de 25 agentes, evolucion de Gen 0 a Gen 4.
    - Red feedforward (numpy): 9 entradas -> 12 ocultas -> 3 salidas.
    - Algoritmo genetico: Elitismo + torneo + crossover + mutacion (5%).

  Requisitos:  pip install pygame numpy
  Ejecucion :  python snake_neuroevolution.py

  Estados:
    MENU              -> Jugar Manualmente / Entrenar IA / Historial de Trofeos
    JUGAR MANUAL      -> flechas del teclado, ESC para volver
    ENTRENAR IA       -> 5 generaciones a maxima velocidad, guarda al campeon
    HISTORIAL         -> lista de campeones guardados; ENTER reproduce su partida
================================================================================
"""

import os
import sys
import json
import random
import datetime
import numpy as np
import pygame

# =============================================================================
#  CONFIGURACION GLOBAL
# =============================================================================
GRID          = 8            # Cuadricula 8x8 (reglas del juego)
CELL          = 64           # Pixeles por bloque
PANEL_H       = 140          # Altura del panel superior de informacion
BOARD_PX      = GRID * CELL  # Tablero en pixeles
WIN_W         = BOARD_PX
WIN_H         = BOARD_PX + PANEL_H

POP_SIZE      = 25           # 25 agentes por generacion
MAX_GEN       = 4            # Se detiene al terminar la Generacion 4
ENERGY_START  = 200          # Contador de energia/pasos inicial
ELITE_COUNT   = 3            # Elitismo: mejores redes conservadas intactas
MUTATION_RATE = 0.05         # Probabilidad de mutacion del 5%
MUTATION_STD  = 0.20         # Desviacion del ruido gaussiano de mutacion
TOURNAMENT_K  = 3            # Tamano del torneo de seleccion

# Arquitectura de la red neuronal
N_INPUTS      = 9            # 3 direcciones (Frente/Izq/Der) x 3 rasgos
N_HIDDEN      = 12
N_OUTPUTS     = 3            # Recto / Girar Izquierda / Girar Derecha

# --- CONTROL DE VELOCIDAD ---
FPS_MENU      = 60           # Fluidez del menu
FPS_PLAY      = 12           # Velocidad jugable (manual y demo de campeon)
TRAIN_UNLIMITED = True       # True = entrenamiento a maxima velocidad (sin tick)
TRAIN_RENDER_EVERY = 4       # Refresca la pantalla cada N pasos durante el entreno

# Persistencia
SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
TROPHY_FILE   = os.path.join(SCRIPT_DIR, "mejores_ias.json")

# Direcciones en orden HORARIO: UP -> RIGHT -> DOWN -> LEFT
DIRS = [(0, -1), (1, 0), (0, 1), (-1, 0)]

# Colores
C_BG      = (18, 18, 24)
C_PANEL   = (28, 28, 40)
C_GRID    = (40, 40, 55)
C_SNAKE   = (60, 220, 120)
C_HEAD    = (150, 255, 190)
C_FOOD    = (240, 80, 80)
C_TEXT    = (235, 235, 245)
C_MUTED   = (150, 150, 170)
C_ACCENT  = (255, 210, 90)
C_BTN     = (44, 44, 62)
C_BTN_SEL = (70, 100, 160)
C_DEAD    = (90, 40, 40)

# Nombres aleatorios para los campeones
NAME_A = ["Alpha", "Cerebro", "Neo", "Viper", "Cobra", "Quantum", "Titan",
          "Nova", "Omega", "Zenith", "Hydra", "Pixel", "Turbo", "Mamba"]
NAME_B = ["Snake", "Mind", "Core", "Brain", "Genoma", "Reptil", "IA", "Neura"]


# =============================================================================
#  RED NEURONAL FEEDFORWARD (numpy)
# =============================================================================
class NeuralNetwork:
    """Red feedforward: entrada -> capa oculta (ReLU) -> salida."""

    def __init__(self, weights=None):
        """Crea la red. Sin pesos, los inicializa aleatoriamente (init He);
        con `weights`, reutiliza los pesos dados (hijos del algoritmo genetico)."""
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
        h = np.maximum(0.0, self.W1 @ x + self.b1)   # Capa oculta con activacion ReLU
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
        """Reconstruye una red a partir del diccionario producido por `to_dict`."""
        weights = [np.array(d["W1"]), np.array(d["b1"]),
                   np.array(d["W2"]), np.array(d["b2"])]
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
    """Agente Snake: cuerpo sobre la cuadricula, sensores, movimiento y estado
    de partida. Puede estar gobernado por una red neuronal o por el teclado."""

    def __init__(self, brain=None, use_energy=True):
        """Inicializa el agente con un cerebro (red neuronal) dado o uno nuevo.
        `use_energy` activa la muerte por inanicion (se desactiva en modo manual)."""
        self.brain      = brain if brain is not None else NeuralNetwork()
        self.use_energy = use_energy
        self.reset()

    def reset(self):
        """Coloca la serpiente en el centro y reinicia cuerpo, energia y marcadores."""
        cx = cy = GRID // 2
        self.body   = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
        self.dir_i  = 1                 # Indice de direccion: 1 = mirando a la derecha
        self.alive  = True
        self.energy = ENERGY_START
        self.steps  = 0
        self.fruits = 0
        self.food   = None
        self.spawn_food()

    def spawn_food(self):
        """Sitúa una fruta en una celda libre elegida al azar (None si no queda ninguna)."""
        libres = [(x, y) for x in range(GRID) for y in range(GRID)
                  if (x, y) not in self.body]
        self.food = random.choice(libres) if libres else None

    def _wall_distance(self, head, d):
        """Sensor: distancia normalizada [0-1] hasta la pared en la direccion `d`."""
        x, y = head
        dist, nx, ny = 0, x + d[0], y + d[1]
        while 0 <= nx < GRID and 0 <= ny < GRID:
            dist += 1
            nx += d[0]; ny += d[1]
        return dist / float(GRID)

    def _body_distance(self, head, d):
        """Sensor: proximidad [0-1] al propio cuerpo en la direccion `d`
        (1.0 = adyacente, 0.0 = sin cuerpo en esa linea)."""
        x, y = head
        nx, ny, step = x + d[0], y + d[1], 1
        while 0 <= nx < GRID and 0 <= ny < GRID:
            if (nx, ny) in self.body:
                return 1.0 - (step - 1) / float(GRID)
            nx += d[0]; ny += d[1]; step += 1
        return 0.0

    def get_inputs(self):
        """9 entradas relativas: pared/cuerpo/fruta en Frente, Izq y Der."""
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

        return np.array(wall + body + food, dtype=np.float64)

    def _apply_action(self, action):
        """Traduce la salida de la red en un giro relativo (1=izq, 2=der; 0=recto)."""
        if action == 1:
            self.dir_i = (self.dir_i - 1) % 4   # Girar izquierda
        elif action == 2:
            self.dir_i = (self.dir_i + 1) % 4   # Girar derecha

    def set_absolute_direction(self, new_i):
        """Para juego manual: fija direccion sin permitir giro de 180 grados."""
        if new_i == (self.dir_i + 2) % 4 and len(self.body) > 1:
            return
        self.dir_i = new_i

    def advance(self):
        """Mueve un bloque; gestiona colisiones, energia y frutas."""
        if not self.alive:
            return
        d = DIRS[self.dir_i]
        hx, hy = self.body[0]
        nx, ny = hx + d[0], hy + d[1]

        if not (0 <= nx < GRID and 0 <= ny < GRID):      # Pared
            self.alive = False; return
        if (nx, ny) in self.body[:-1]:                    # Propio cuerpo
            self.alive = False; return

        self.body.insert(0, (nx, ny))
        self.steps += 1
        if self.use_energy:
            self.energy -= 1

        if (nx, ny) == self.food:
            self.fruits += 1
            self.energy = ENERGY_START
            self.spawn_food()
        else:
            self.body.pop()

        if self.use_energy and self.energy <= 0:          # Inanicion
            self.alive = False

    def step_ai(self):
        """Un turno gobernado por la red neuronal."""
        if not self.alive:
            return
        self._apply_action(self.brain.forward(self.get_inputs()))
        self.advance()

    def fitness(self):
        """Fitness = pasos sobrevividos + (frutas * 1000)."""
        return self.steps + self.fruits * 1000


# =============================================================================
#  ALGORITMO GENETICO
# =============================================================================
def tournament_select(pop):
    """Seleccion por torneo: toma K agentes al azar y devuelve el de mayor fitness."""
    aspirantes = random.sample(pop, TOURNAMENT_K)
    return max(aspirantes, key=lambda s: s.fitness())


def next_generation(pop):
    """Construye la siguiente generacion: conserva la elite intacta y rellena el
    resto con hijos obtenidos por seleccion, cruce y mutacion."""
    ordenados = sorted(pop, key=lambda s: s.fitness(), reverse=True)
    nueva = [Snake(ordenados[i].brain.clone()) for i in range(ELITE_COUNT)]
    while len(nueva) < POP_SIZE:
        padre_a = tournament_select(pop)
        padre_b = tournament_select(pop)
        hijo = mutate(crossover(padre_a.brain, padre_b.brain))
        nueva.append(Snake(hijo))
    return nueva


# =============================================================================
#  PERSISTENCIA DE TROFEOS
# =============================================================================
def load_trophies():
    """Lee el Salon de la Fama desde el JSON; devuelve [] si no existe o esta corrupto."""
    if not os.path.exists(TROPHY_FILE):
        return []
    try:
        with open(TROPHY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_trophy(brain, fitness, fruits, steps):
    """Anade un campeon al salon de la fama y ordena por fitness."""
    trofeos = load_trophies()
    nombre = f"{random.choice(NAME_A)}-{random.choice(NAME_B)}-V{random.randint(1, 99)}"
    registro = {
        "nombre":   nombre,
        "fecha":    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "fitness":  int(fitness),
        "frutas":   int(fruits),
        "pasos":    int(steps),
        "pesos":    brain.to_dict(),
    }
    trofeos.append(registro)
    trofeos.sort(key=lambda t: t["fitness"], reverse=True)
    trofeos = trofeos[:15]  # Conserva solo el top 15
    try:
        with open(TROPHY_FILE, "w", encoding="utf-8") as f:
            json.dump(trofeos, f, indent=2, ensure_ascii=False)
    except OSError:
        pass
    return nombre


# =============================================================================
#  UTILIDADES DE RENDER
# =============================================================================
def make_fonts():
    """Crea y devuelve el juego de fuentes (varios tamaños) usado por la interfaz."""
    return {
        "big":   pygame.font.SysFont("consolas", 40, bold=True),
        "mid":   pygame.font.SysFont("consolas", 26, bold=True),
        "reg":   pygame.font.SysFont("consolas", 20),
        "small": pygame.font.SysFont("consolas", 16),
    }


def draw_text(screen, font, text, x, y, color=C_TEXT, center=False):
    """Dibuja una cadena en (x, y); si `center` es True, (x, y) es el centro del texto.
    Devuelve el rectangulo ocupado (util para detectar clics)."""
    surf = font.render(text, True, color)
    rect = surf.get_rect()
    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)
    screen.blit(surf, rect)
    return rect


def draw_board(screen, snake, y_off=PANEL_H):
    """Dibuja el tablero completo: rejilla, fruta y serpiente (cabeza resaltada,
    color apagado si esta muerta). `y_off` desplaza el tablero bajo el panel."""
    pygame.draw.rect(screen, C_BG, (0, y_off, BOARD_PX, BOARD_PX))
    for i in range(GRID + 1):
        pygame.draw.line(screen, C_GRID, (i * CELL, y_off),
                         (i * CELL, y_off + BOARD_PX))
        pygame.draw.line(screen, C_GRID, (0, y_off + i * CELL),
                         (BOARD_PX, y_off + i * CELL))
    if snake.food is not None:
        fx, fy = snake.food
        pygame.draw.rect(screen, C_FOOD,
                         (fx * CELL + 10, y_off + fy * CELL + 10,
                          CELL - 20, CELL - 20), border_radius=14)
    body_color = C_SNAKE if snake.alive else C_DEAD
    for idx, (x, y) in enumerate(snake.body):
        col = C_HEAD if (idx == 0 and snake.alive) else body_color
        pygame.draw.rect(screen, col,
                         (x * CELL + 4, y_off + y * CELL + 4,
                          CELL - 8, CELL - 8), border_radius=9)


def poll_global_quit(event):
    """Cierra la app ante el boton X o Alt+F4."""
    if event.type == pygame.QUIT:
        pygame.quit(); sys.exit()


# =============================================================================
#  ESTADO: MENU PRINCIPAL
# =============================================================================
def run_menu(screen, clock, fonts):
    """Muestra el menu principal y bloquea hasta que el usuario elige una opcion.
    Devuelve la accion elegida: 'manual', 'train' o 'trophies'."""
    opciones = ["Jugar Manualmente", "Entrenar IA Evolutiva", "Historial de Trofeos"]
    resultados = ["manual", "train", "trophies"]
    sel = 0
    btn_w, btn_h, gap = 380, 62, 20
    x0 = WIN_W // 2 - btn_w // 2
    y0 = 250

    def button_rects():
        """Calcula los rectangulos de los botones (para dibujarlos y detectar clics)."""
        return [pygame.Rect(x0, y0 + i * (btn_h + gap), btn_w, btn_h)
                for i in range(len(opciones))]

    while True:
        rects = button_rects()
        mouse = pygame.mouse.get_pos()

        for event in pygame.event.get():
            poll_global_quit(event)
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE,):
                    pygame.quit(); sys.exit()
                if event.key in (pygame.K_DOWN, pygame.K_s):
                    sel = (sel + 1) % len(opciones)
                if event.key in (pygame.K_UP, pygame.K_w):
                    sel = (sel - 1) % len(opciones)
                if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                    return resultados[sel]
            if event.type == pygame.MOUSEMOTION:
                for i, r in enumerate(rects):
                    if r.collidepoint(mouse):
                        sel = i
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for i, r in enumerate(rects):
                    if r.collidepoint(mouse):
                        return resultados[i]

        # --- Render ---
        screen.fill(C_BG)
        draw_text(screen, fonts["big"], "S N A K E   I A", WIN_W // 2, 90,
                  C_ACCENT, center=True)
        draw_text(screen, fonts["reg"], "Neuroevolucion: Redes Neuronales + Algoritmo Genetico",
                  WIN_W // 2, 145, C_MUTED, center=True)

        for i, (r, txt) in enumerate(zip(rects, opciones)):
            col = C_BTN_SEL if i == sel else C_BTN
            pygame.draw.rect(screen, col, r, border_radius=12)
            pygame.draw.rect(screen, C_ACCENT if i == sel else C_GRID, r, 2,
                             border_radius=12)
            draw_text(screen, fonts["mid"], txt, r.centerx, r.centery,
                      C_TEXT, center=True)

        draw_text(screen, fonts["small"],
                  "Flechas / Raton para elegir  -  ENTER para confirmar  -  ESC para salir",
                  WIN_W // 2, WIN_H - 40, C_MUTED, center=True)

        pygame.display.flip()
        clock.tick(FPS_MENU)


# =============================================================================
#  ESTADO: JUGAR MANUALMENTE
# =============================================================================
def run_manual(screen, clock, fonts):
    """Modo de juego manual: el usuario controla la serpiente con flechas/WASD.
    `R` reinicia tras perder y `ESC` vuelve al menu."""
    snake = Snake(use_energy=False)   # Sin muerte por inanicion en modo manual
    key_to_dir = {
        pygame.K_UP: 0, pygame.K_RIGHT: 1, pygame.K_DOWN: 2, pygame.K_LEFT: 3,
        pygame.K_w: 0, pygame.K_d: 1, pygame.K_s: 2, pygame.K_a: 3,
    }
    pending = None   # Direccion pedida (se aplica en el proximo tick)

    while True:
        for event in pygame.event.get():
            poll_global_quit(event)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return
                if event.key in key_to_dir:
                    pending = key_to_dir[event.key]
                if event.key == pygame.K_r and not snake.alive:
                    snake = Snake(use_energy=False); pending = None

        if snake.alive:
            if pending is not None:
                snake.set_absolute_direction(pending)
                pending = None
            snake.advance()

        # --- Render ---
        screen.fill(C_BG)
        pygame.draw.rect(screen, C_PANEL, (0, 0, WIN_W, PANEL_H))
        pygame.draw.line(screen, C_GRID, (0, PANEL_H), (WIN_W, PANEL_H), 2)
        draw_text(screen, fonts["mid"], "MODO MANUAL", 16, 14, C_ACCENT)
        draw_text(screen, fonts["reg"], f"Frutas: {snake.fruits}", 16, 58)
        draw_text(screen, fonts["reg"], f"Longitud: {len(snake.body)}", 16, 84)
        draw_text(screen, fonts["small"],
                  "Flechas/WASD para moverte   -   ESC para volver al menu",
                  16, 112, C_MUTED)
        draw_board(screen, snake)

        if not snake.alive:
            overlay = pygame.Surface((BOARD_PX, BOARD_PX)); overlay.set_alpha(200)
            overlay.fill((10, 10, 16)); screen.blit(overlay, (0, PANEL_H))
            draw_text(screen, fonts["big"], "GAME OVER", WIN_W // 2,
                      PANEL_H + BOARD_PX // 2 - 30, C_FOOD, center=True)
            draw_text(screen, fonts["reg"], f"Frutas: {snake.fruits}",
                      WIN_W // 2, PANEL_H + BOARD_PX // 2 + 20, C_TEXT, center=True)
            draw_text(screen, fonts["small"], "R para reiniciar  -  ESC para menu",
                      WIN_W // 2, PANEL_H + BOARD_PX // 2 + 55, C_MUTED, center=True)

        pygame.display.flip()
        clock.tick(FPS_PLAY)


# =============================================================================
#  ESTADO: ENTRENAR IA EVOLUTIVA (maxima velocidad)
# =============================================================================
def run_training(screen, clock, fonts):
    """Entrena la IA por neuroevolucion: simula cada agente de cada generacion a
    maxima velocidad, evoluciona la poblacion y guarda al campeon global al terminar."""
    population = [Snake() for _ in range(POP_SIZE)]
    generation = 0
    best_fitness = 0

    # Mejor agente encontrado en toda la simulacion (campeon global)
    best_brain = population[0].brain.clone()
    best_fruits = best_steps = 0
    frame = 0

    def draw_train_panel(gen, agent_idx, snake):
        """Dibuja el panel superior con el progreso del entrenamiento en curso."""
        pygame.draw.rect(screen, C_PANEL, (0, 0, WIN_W, PANEL_H))
        pygame.draw.line(screen, C_GRID, (0, PANEL_H), (WIN_W, PANEL_H), 2)
        draw_text(screen, fonts["mid"], "ENTRENANDO IA (max. velocidad)", 16, 12, C_ACCENT)
        draw_text(screen, fonts["reg"], f"Generacion: {gen} / {MAX_GEN}", 16, 52)
        draw_text(screen, fonts["reg"], f"Agente: #{agent_idx} / {POP_SIZE}", 16, 76)
        draw_text(screen, fonts["reg"], f"Mejor Fitness Hist.: {best_fitness}", 250, 52, C_ACCENT)
        draw_text(screen, fonts["reg"], f"Frutas (actual): {snake.fruits}", 250, 76)
        draw_text(screen, fonts["small"], "ESC para cancelar y volver al menu", 16, 110, C_MUTED)

    while generation <= MAX_GEN:
        for idx, snake in enumerate(population, start=1):
            while snake.alive:
                # Procesa eventos periodicamente (evita congelar la ventana)
                if frame % TRAIN_RENDER_EVERY == 0:
                    for event in pygame.event.get():
                        poll_global_quit(event)
                        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                            return

                snake.step_ai()
                frame += 1

                if snake.fitness() > best_fitness:
                    best_fitness = snake.fitness()
                    best_brain   = snake.brain.clone()
                    best_fruits  = snake.fruits
                    best_steps   = snake.steps

                # Render throttled -> maxima velocidad de computo
                if frame % TRAIN_RENDER_EVERY == 0:
                    screen.fill(C_BG)
                    draw_train_panel(generation, idx, snake)
                    draw_board(screen, snake)
                    pygame.display.flip()
                    if not TRAIN_UNLIMITED:
                        clock.tick(FPS_PLAY)

        avg = sum(s.fitness() for s in population) / POP_SIZE
        print(f"[Gen {generation}] Mejor fitness: {max(s.fitness() for s in population):5d} "
              f"| Promedio: {avg:7.1f}")

        if generation == MAX_GEN:
            break
        population = next_generation(population)
        generation += 1

    # --- Guardar campeon global ---
    nombre = save_trophy(best_brain, best_fitness, best_fruits, best_steps)

    # --- Pantalla de resultados (espera a ESC/ENTER) ---
    while True:
        for event in pygame.event.get():
            poll_global_quit(event)
            if event.type == pygame.KEYDOWN and event.key in (
                    pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                return

        screen.fill(C_BG)
        draw_text(screen, fonts["big"], "ENTRENAMIENTO COMPLETADO", WIN_W // 2, 120,
                  C_ACCENT, center=True)
        lineas = [
            f"Generaciones evolucionadas: 0 -> {MAX_GEN}",
            "",
            f"Campeon global: {nombre}",
            f"Fitness maximo: {best_fitness}",
            f"Frutas comidas: {best_fruits}",
            f"Pasos sobrevividos: {best_steps}",
            "",
            "Guardado en el Historial de Trofeos.",
            "",
            "Presiona ENTER o ESC para volver al menu.",
        ]
        for i, txt in enumerate(lineas):
            col = C_ACCENT if txt.startswith(("Campeon", "Fitness")) else C_TEXT
            draw_text(screen, fonts["reg"], txt, WIN_W // 2, 190 + i * 32, col, center=True)
        pygame.display.flip()
        clock.tick(FPS_MENU)


# =============================================================================
#  ESTADO: HISTORIAL DE TROFEOS
# =============================================================================
def run_trophies(screen, clock, fonts):
    """Muestra el Salon de la Fama con los campeones guardados; `ENTER` reproduce
    la partida del seleccionado y `ESC` vuelve al menu."""
    trofeos = load_trophies()
    sel = 0

    while True:
        for event in pygame.event.get():
            poll_global_quit(event)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return
                if not trofeos:
                    continue
                if event.key in (pygame.K_DOWN, pygame.K_s):
                    sel = (sel + 1) % len(trofeos)
                if event.key in (pygame.K_UP, pygame.K_w):
                    sel = (sel - 1) % len(trofeos)
                if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                    run_demo(screen, clock, fonts, trofeos[sel])

        # --- Render ---
        screen.fill(C_BG)
        draw_text(screen, fonts["big"], "SALON DE LA FAMA", WIN_W // 2, 55,
                  C_ACCENT, center=True)

        if not trofeos:
            draw_text(screen, fonts["reg"],
                      "Aun no hay campeones guardados.", WIN_W // 2, 220, C_MUTED, center=True)
            draw_text(screen, fonts["reg"],
                      "Entrena una IA para crear el primero.", WIN_W // 2, 255, C_MUTED, center=True)
        else:
            y = 120
            for i, t in enumerate(trofeos[:10]):
                r = pygame.Rect(30, y, WIN_W - 60, 48)
                col = C_BTN_SEL if i == sel else C_BTN
                pygame.draw.rect(screen, col, r, border_radius=8)
                if i == sel:
                    pygame.draw.rect(screen, C_ACCENT, r, 2, border_radius=8)
                medal = "#{}".format(i + 1)
                draw_text(screen, fonts["reg"], f"{medal}  {t['nombre']}", 45, y + 13)
                draw_text(screen, fonts["reg"], f"Fitness: {t['fitness']}",
                          WIN_W - 250, y + 13, C_ACCENT)
                draw_text(screen, fonts["small"], t["fecha"], 45, y + 32, C_MUTED)
                y += 56

        draw_text(screen, fonts["small"],
                  "Flechas para elegir  -  ENTER para ver jugar al campeon  -  ESC para volver",
                  WIN_W // 2, WIN_H - 35, C_MUTED, center=True)
        pygame.display.flip()
        clock.tick(FPS_MENU)


# =============================================================================
#  ESTADO: DEMO DE UN CAMPEON GUARDADO
# =============================================================================
def run_demo(screen, clock, fonts, registro):
    """Reproduce en bucle la partida de un campeon guardado, reconstruyendo su
    cerebro desde el registro JSON. `ESC` vuelve al historial."""
    brain = NeuralNetwork.from_dict(registro["pesos"])
    snake = Snake(brain=brain.clone())

    while True:
        for event in pygame.event.get():
            poll_global_quit(event)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return

        if snake.alive:
            snake.step_ai()
        else:
            pygame.time.wait(700)                    # Pausa breve
            snake = Snake(brain=brain.clone())        # Reinicia la demostracion

        # --- Render ---
        screen.fill(C_BG)
        pygame.draw.rect(screen, C_PANEL, (0, 0, WIN_W, PANEL_H))
        pygame.draw.line(screen, C_GRID, (0, PANEL_H), (WIN_W, PANEL_H), 2)
        draw_text(screen, fonts["mid"], f"CAMPEON: {registro['nombre']}", 16, 12, C_ACCENT)
        draw_text(screen, fonts["reg"], f"Adaptacion (fitness): {registro['fitness']}", 16, 52)
        draw_text(screen, fonts["reg"],
                  f"Frutas ahora: {snake.fruits}   Energia: {snake.energy}", 16, 78)
        draw_text(screen, fonts["small"], "ESC para volver al historial", 16, 112, C_MUTED)
        draw_board(screen, snake)
        pygame.display.flip()
        clock.tick(FPS_PLAY)


# =============================================================================
#  BUCLE PRINCIPAL / MAQUINA DE ESTADOS
# =============================================================================
def main():
    """Punto de entrada: inicializa Pygame y ejecuta la maquina de estados que
    encadena menu, juego manual, entrenamiento e historial hasta que se cierra la app."""
    pygame.init()
    pygame.display.set_caption("Snake IA - Neuroevolucion")
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    clock = pygame.time.Clock()
    fonts = make_fonts()

    while True:
        accion = run_menu(screen, clock, fonts)
        if accion == "manual":
            run_manual(screen, clock, fonts)
        elif accion == "train":
            run_training(screen, clock, fonts)
        elif accion == "trophies":
            run_trophies(screen, clock, fonts)


if __name__ == "__main__":
    main()
