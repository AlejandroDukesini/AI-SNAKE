# 📖 Prueba Técnica — Snake IA funciona, y así está construido

> Documento de **evidencia de funcionamiento**. Cada afirmación remite a un archivo y una
> función reales del repositorio; las cifras de rendimiento son medidas y reproducibles con los
> scripts de `benchmarks/`. La versión navegable de este documento vive dentro de la app, en la
> vista **Documentación Técnica** (`src/views/DocsView.jsx`).

**Índice**
1. [El Cerebro: percepción y red recurrente 26 → 20 → 3](#1--el-cerebro-percepción-y-red-recurrente-26--20--3)
2. [Selección natural: el algoritmo genético](#2--selección-natural-el-algoritmo-genético)
3. [Runtime, concurrencia y rendimiento](#3--runtime-concurrencia-y-rendimiento)
4. [Seguridad y persistencia](#4--seguridad-y-persistencia)
5. [Cómo reproducir cada cifra](#5--cómo-reproducir-cada-cifra)

---

## 1. 🧠 El Cerebro: percepción y red recurrente 26 → 20 → 3

**Archivo:** `snake_neuroevolution.py` · **Constantes:** `N_INPUTS → N_HIDDEN → N_OUTPUTS = 26 → 20 → 3`

Cada serpiente lleva su propia red neuronal recurrente. No comparten pesos: la población **es** un
conjunto de redes distintas compitiendo.

### Las 26 entradas (percepción egocéntrica)

| Origen | Sensores | Qué mide |
| --- | ---: | --- |
| **8 rayos egocéntricos × 3 rasgos** | 24 | Por cada rayo (frente, diagonales, laterales, relativos a hacia dónde mira): distancia a la pared, proximidad del propio cuerpo y alineación con la manzana. |
| **Tamaño propio** | 1 | Longitud del cuerpo normalizada por el área del tablero (propiocepción). |
| **Espacio libre alcanzable** | 1 | *Flood-fill* desde la cabeza: qué fracción del tablero puede aún recorrer. La señal anti-encierro. |
| **Total** | **26** | |

Los sensores están **normalizados** (`distancia / grid`), así que una red entrenada en 8×8
también sabe jugar en 15×15 — el motivo por el que la demo y el juego pueden usar un tablero
distinto al del entrenamiento.

### Por qué NumPy puro y no PyTorch/TensorFlow

La red se **evoluciona**, no se entrena por gradiente. No hay `loss.backward()` en ningún punto
del proyecto. En ese régimen, un framework de deep learning es peso muerto:

- **Sin autograd ni GPU.** El *forward* es un puñado de multiplicaciones de matrices; NumPy lo
  resuelve de sobra en CPU.
- **Instalación mínima:** `numpy · fastapi · uvicorn`. Sin CUDA, sin ruedas de 2 GB.
- **Cero caja negra.** Coherente con el objetivo educativo: cada operación es legible.

### Memoria recurrente (`W_rec`)

La capa oculta se realimenta con su propio estado del turno anterior:

```python
h      = tanh(W1 @ x + W_rec @ h_prev + b1)   # h_prev = estado del turno anterior
salida = W2 @ h + b2                           # recto | izquierda | derecha
```

`W_rec` **nace a cero**: la red se comporta como una *feedforward* pura y la mutación va
introduciendo la memoria poco a poco. Consecuencia clave: **añadir memoria no degrada nada de lo
aprendido**, y `NeuralNetwork.from_dict` adapta redes antiguas a la arquitectura nueva copiando
los pesos heredados y dejando `W_rec` a cero (sin regresión).

---

## 2. 🧬 Selección natural: el algoritmo genético

**Archivo:** `snake_neuroevolution.py` · **Funciones:** `crossover`, `mutate`, `next_generation`, `train`

No hay descenso de gradiente ni datos supervisados. Se evoluciona una población de `POP_SIZE = 25`:
la Generación *N* se construye sobre los mejores hijos de la *N-1*.

### Función de fitness (recompensa densa)

```
fitness = pasos + (tamaño − 3) × 1000 + shaping_de_acercamiento
```

Crecer vale **mil veces** más que sobrevivir (`FRUIT_REWARD = 1000`), así que la evolución premia
sobre todo comer. El `shaping` es una señal continua **asimétrica** (`APPROACH_REWARD = 3.0`,
`APPROACH_PENALTY = 4.0`): alejarse penaliza algo más que acercarse premia, para desincentivar el
merodeo en círculos y acelerar el salto de la supervivencia refleja al forrajeo intencionado.

### Los operadores

| Operador | Constante | Qué hace |
| --- | --- | --- |
| **Elitismo** | `ELITE_COUNT = 3` | Las 3 mejores redes pasan **intactas** a la siguiente generación. |
| **Selección por torneo** | `TOURNAMENT_K = 3` | Grupos de 3 al azar; gana el de mayor fitness. |
| **Cruce uniforme** | — | El hijo hereda cada peso de uno u otro padre. |
| **Mutación gaussiana adaptativa** | `MUTATION_RATE = 0.05`, `MUTATION_STD = 0.20` | Un 5 % de los pesos se perturba con ruido gaussiano. |
| **Recocido por estancamiento** | `STAGNATION_PATIENCE = 4`, `MUTATION_DECAY = 0.85`, `MUTATION_STD_MIN = 0.05` | Si el mejor fitness se estanca, la intensidad de mutación **baja sola**: de explorar a afinar, sin dejar de explorar del todo. |

### La escalera de inteligencia (métrica objetiva)

```
cobertura = longitud / (grid × grid)      # fracción del tablero ocupada, 0.0 – 1.0
```

Es **independiente del tamaño de tablero**, así que compara 8×8, 10×10 y 15×15 de forma justa.

| Nivel | Cobertura | Capacidad | Estado |
| --- | --- | --- | --- |
| **N0** Supervivencia refleja | < 10 % | Evita la pared; come por accidente. | ✅ punto de partida |
| **N1** Forrajeo básico | 10–20 % | Se orienta hacia la comida sin azar. | ✅ alcanzable |
| **N2** Forrajeo fiable | 20–35 % | Come consistente; deja de encerrarse en cuerpos cortos. | ✅ alcanzable |
| **N3** Conciencia espacial | 35–55 % | Con cuerpo largo planifica giros. | ✅ habilitado (8 rayos + flood-fill) |
| **N4** Planificación emergente | 55–80 % | Recorre el tablero sin encerrarse. | 🧩 mecanismo listo (memoria recurrente) |
| **N5** Casi óptimo | > 80 % | Llena casi todo el tablero. | 🔬 I+D (visión CNN + evaluación vectorizada) |

> **Honestidad metodológica.** El nivel **se mide** del resultado real de cada entrenamiento; no se
> declara. Tener el *mecanismo* de un nivel (p. ej. memoria para N4) no equivale a **alcanzar** su
> cobertura. El `record_cobertura` es **monótono** (persistido en `storage.py`): solo sube o se
> mantiene, nunca baja por una mala racha evolutiva.

---

## 3. ⚙️ Runtime, concurrencia y rendimiento

**Archivo:** `ai_server.py` (endpoint `WS /ws/train`)

### Hilo dedicado vs. bucle asyncio

La neuroevolución es CPU-intensiva; ejecutarla en el bucle de asyncio congelaría el WebSocket. Se
separa en dos:

- **Hilo de neuroevolución** (`threading.Thread(daemon=True)`): simula miles de pasos/segundo.
- **Bucle asyncio (FastAPI):** escucha órdenes (`pause`/`stop`/`cancel`), drena colas y emite a
  ritmo fijo. Nunca hace trabajo pesado.

El hilo es *daemon* y se cierra con `join(timeout=2.0)` acotado: si el cliente cierra la pestaña,
el servidor **no** se queda con un núcleo quemándose para nadie.

### Control de backpressure: sobrescribir, no encolar

El núcleo produce miles de fotogramas por segundo; al cliente solo le importa el más reciente.
Encolarlos todos agotaría memoria y saturaría la red. La solución es un patrón productor/consumidor
donde el último fotograma **pisa** al anterior:

```python
# productor (hilo de entrenamiento): el frame nuevo SOBRESCRIBE al anterior
ultimo["step"] = datos

# consumidor (bucle asyncio): emite a ritmo fijo, nunca acumula
await asyncio.sleep(1.0 / STREAM_FPS)          # STREAM_FPS = 20
if ultimo["step"] is not None:
    await ws.send_json({"type": "step", **ultimo["step"]})
    ultimo["step"] = None
```

Los eventos que **no** se pueden perder (`gen`, `done`) sí usan una `queue.Queue` real. Resultado:
**20 fps estables** independientes de lo rápido que simule el hilo, sin crecimiento de memoria.

### Métricas medidas

**Motor** (`benchmarks/bench_core.py`, tablero 8×8, población 25, media de 5 corridas):

| Métrica | Valor |
| --- | --- |
| Pasos simulados (inferencias) / s | **≈ 4.000** |
| Individuos evaluados / s | ≈ 66 |
| Generaciones / s | ≈ 2,6 |
| Tiempo por generación | **≈ 380 ms** (p95 ≈ 650 ms · p99 ≈ 775 ms) |

**Frontend** (Google Lighthouse sobre el build de Vite, Chrome headless):

| Dispositivo | Performance | LCP | TBT | CLS |
| --- | ---: | ---: | ---: | ---: |
| **Desktop** | **100** | 0,5 s | 0 ms | 0,016 |
| **Mobile** | ~90 | ~2,2–3,6 s | 10–160 ms | ≤ 0,04 |

El *hot path* es el flood-fill (usa índices planos y un `bytearray` de visitados en vez de un `set`
de tuplas). Es también lo más difícil de vectorizar: por eso el siguiente salto —evaluación por
lotes en NumPy— es un rediseño del simulador, documentado en `plan.txt`, no un cambio de una línea.

---

## 4. 🔒 Seguridad y persistencia

**Archivo:** `storage.py`

### Path traversal cerrado en origen: `slugify`

El nombre de una IA lo escribe el usuario y se convierte en nombre de carpeta. `slugify` es la
única barrera entre esa entrada y el sistema de ficheros:

```python
def slugify(nombre):
    nombre = re.sub(r"\s+", "_", nombre)             # espacios -> _
    nombre = re.sub(r"[^A-Za-z0-9_\-]", "", nombre)  # fuera todo lo demás
    nombre = nombre.strip("._-")[:40]                # sin puntos guía; máx 40
    return nombre or ml.random_name()
```

Un nombre como `../../algo` queda reducido a caracteres seguros: **imposible escribir fuera de
`historial/`**.

### Cero pérdida de progreso

- Cada espécimen es una **carpeta**: `modelo.json` (mejor linaje: pesos y sesgos) + `sesiones.json`
  (histórico, un registro por entrenamiento).
- Reentrenar un nombre existente **acumula** generaciones, pero los pesos **solo se sustituyen si se
  batió el récord** de fitness. La evolución tiene azar; una tanda peor **nunca** degrada la IA que
  el usuario ya tenía.
- `record_cobertura` es **monótono**: el nivel solo sube o se mantiene.

### Lectura tolerante a fallos

Los archivos del historial son editables a mano y pueden corromperse. La lectura nunca tumba el
servidor:

```python
def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default   # ante un JSON inválido, valor por defecto
```

### Superficie mínima en el cliente

- Estado y consentimiento en `localStorage`, **no** en cookies → `allow_credentials=False` (sin
  CSRF por cookie).
- **CORS** por lista blanca de orígenes + regex acotado para previews de Vercel.
- Scripts de terceros inyectados con `createElement + .src` (nunca `innerHTML`/`eval`) y solo desde
  URLs https en lista blanca (`consent.js`) → sin XSS por inyección de `<script>`.
- Cabeceras HTTP en `vercel.json`: `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: strict-origin-when-cross-origin`.

---

## 5. 🔁 Cómo reproducir cada cifra

```bash
# Motor (pasos/s, generaciones/s, tiempo por generación)
python benchmarks/bench_core.py

# Carga del backend (REST), umbrales PASS/FAIL p95 < 200 ms
python ai_server.py                 # levanta la API en :8000
k6 run benchmarks/load_test.js      # requiere instalar k6

# Frontend (Lighthouse)
npm run build                       # genera dist/
# Lighthouse (Chrome headless) sobre el dist/ servido
```

Todas las constantes citadas (`POP_SIZE`, `MUTATION_RATE`, `ELITE_COUNT`, …) están en la cabecera
de `snake_neuroevolution.py` y documentadas en el `README.md`. La hoja de ruta de qué desbloquea
cada nivel vive en `plan.txt`; la reconstrucción arquitectónica completa, en `PLANNING.md`.
