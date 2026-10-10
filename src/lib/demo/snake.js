/* ============================================================================
   MODO BORRADOR — motor Snake en JavaScript
   ----------------------------------------------------------------------------
   Copia en JS de las reglas de `snake_neuroevolution.Snake` (mismo tablero,
   misma serpiente inicial, mismas direcciones, misma inanicion) para que el
   borrador estatico de Netlify se vea igual que la app real.

   OJO: aqui NO hay red neuronal. La "IA" es una heuristica (ir a la manzana sin
   encerrarse) con una probabilidad de error que simula lo entrenada que esta.
   Todo usa un generador pseudoaleatorio con SEMILLA FIJA: cada vez que se abre
   la pagina se ve exactamente la misma partida.
   ============================================================================ */

export const INITIAL_LENGTH = 3;
export const ENERGY_START = 200;
export const FRUIT_REWARD = 1000;
// Indices identicos a DIRS en Python: 0=arriba 1=derecha 2=abajo 3=izquierda
const DIRS = [[0, -1], [1, 0], [0, 1], [-1, 0]];

/* PRNG mulberry32: rapido, sin dependencias y reproducible con la semilla. */
export function rng(semilla) {
  let a = semilla >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/* Semilla estable a partir de un texto (nombre de la IA, parametros...). */
export function semillaDe(texto) {
  let h = 2166136261;
  for (const c of String(texto)) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  return h >>> 0;
}

const clave = (x, y) => `${x},${y}`;

export class Snake {
  constructor({ grid = 8, useEnergy = true, random = rng(1) } = {}) {
    this.grid = grid;
    this.useEnergy = useEnergy;
    this.random = random;
    this.reset();
  }

  reset() {
    const c = Math.floor(this.grid / 2);
    this.body = Array.from({ length: INITIAL_LENGTH }, (_, i) => [c - i, c]);
    this.dirI = 1;
    this.alive = true;
    this.energy = ENERGY_START;
    this.steps = 0;
    this.fruits = 0;
    this.ocupadas = new Set(this.body.map(([x, y]) => clave(x, y)));
    this.spawnFood();
  }

  get length() { return this.body.length; }

  fitness() {
    return this.steps + (this.length - INITIAL_LENGTH) * FRUIT_REWARD;
  }

  spawnFood() {
    const libres = [];
    for (let x = 0; x < this.grid; x += 1) {
      for (let y = 0; y < this.grid; y += 1) {
        if (!this.ocupadas.has(clave(x, y))) libres.push([x, y]);
      }
    }
    this.food = libres.length ? libres[Math.floor(this.random() * libres.length)] : null;
  }

  setAbsoluteDirection(d) {
    if (d === (this.dirI + 2) % 4 && this.body.length > 1) return;
    this.dirI = d;
  }

  /* ¿Es mortal mover la cabeza a (x, y)? La cola se libera ese turno salvo que
     se coma, igual que en Python. */
  choca(x, y) {
    if (x < 0 || y < 0 || x >= this.grid || y >= this.grid) return true;
    if (!this.ocupadas.has(clave(x, y))) return false;
    const [tx, ty] = this.body[this.body.length - 1];
    const come = this.food && this.food[0] === x && this.food[1] === y;
    return !(tx === x && ty === y && !come);
  }

  advance() {
    if (!this.alive) return;
    const [dx, dy] = DIRS[this.dirI];
    const [hx, hy] = this.body[0];
    const nx = hx + dx;
    const ny = hy + dy;
    if (this.choca(nx, ny)) { this.alive = false; return; }

    const crece = this.food && this.food[0] === nx && this.food[1] === ny;
    this.body.unshift([nx, ny]);
    this.steps += 1;
    if (this.useEnergy) this.energy -= 1;

    if (crece) {
      this.ocupadas.add(clave(nx, ny));
      this.fruits += 1;
      this.energy = ENERGY_START;
      this.spawnFood();
    } else {
      const [tx, ty] = this.body.pop();
      this.ocupadas.delete(clave(tx, ty));
      this.ocupadas.add(clave(nx, ny));
    }
    if (this.useEnergy && this.energy <= 0) this.alive = false;
  }

  /* Casillas alcanzables desde (x, y): si son menos que el cuerpo, meterse ahi
     es encerrarse. Es lo que hace que la heuristica parezca "pensar". */
  espacioLibre(x, y) {
    const vistos = new Set([clave(x, y)]);
    const pila = [[x, y]];
    while (pila.length) {
      const [cx, cy] = pila.pop();
      for (const [dx, dy] of DIRS) {
        const k = clave(cx + dx, cy + dy);
        if (vistos.has(k) || this.choca(cx + dx, cy + dy)) continue;
        vistos.add(k);
        pila.push([cx + dx, cy + dy]);
      }
    }
    return vistos.size;
  }

  /* Un turno de la "IA". `error` = probabilidad [0-1] de decidir a ciegas:
     cuanto mas baja, mas "entrenada" parece la serpiente. */
  stepAI(error = 0.05) {
    if (!this.alive) return;
    const [hx, hy] = this.body[0];
    const opciones = [this.dirI, (this.dirI + 3) % 4, (this.dirI + 1) % 4]; // recto, izq, der

    if (this.random() < error) {
      this.dirI = opciones[Math.floor(this.random() * 3)];
      this.advance();
      return;
    }

    let mejor = this.dirI;
    let mejorPuntos = -Infinity;
    for (const d of opciones) {
      const nx = hx + DIRS[d][0];
      const ny = hy + DIRS[d][1];
      if (this.choca(nx, ny)) continue;
      const espacio = this.espacioLibre(nx, ny);
      const dist = this.food ? Math.abs(this.food[0] - nx) + Math.abs(this.food[1] - ny) : 0;
      const encierro = espacio < this.length ? -1000 : 0;
      const puntos = encierro + Math.min(espacio, this.length * 2) - dist * 3 + this.random();
      if (puntos > mejorPuntos) { mejorPuntos = puntos; mejor = d; }
    }
    this.dirI = mejor;
    this.advance();
  }

  toState() {
    return {
      body: this.body.map(([x, y]) => [x, y]),
      food: this.food ? [...this.food] : null,
      alive: this.alive,
      fruits: this.fruits,
      steps: this.steps,
      energy: this.energy,
      length: this.length,
      grid: this.grid,
    };
  }
}

/* Mismos umbrales que NIVELES en snake_neuroevolution.py. */
const NIVELES = [
  [0.10, 0, 'N0 · Cobertura < 10 %'],
  [0.20, 1, 'N1 · Cobertura 10–20 %'],
  [0.35, 2, 'N2 · Cobertura 20–35 %'],
  [0.55, 3, 'N3 · Cobertura 35–55 %'],
  [0.80, 4, 'N4 · Cobertura 55–80 %'],
];

export function nivelDeCobertura(length, grid) {
  const cob = Math.max(0, Math.min(1, length / (grid * grid || 1)));
  const fila = NIVELES.find(([umbral]) => cob < umbral);
  const [nivel, etiqueta] = fila ? [fila[1], fila[2]] : [5, 'N5 · Cobertura ≥ 80 %'];
  return { nivel, etiqueta, cobertura: Math.round(cob * 10000) / 10000 };
}
