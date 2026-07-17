# 🐍 Snake IA — Neuroevolución

El clásico **Snake** resuelto por una **IA que aprende sola**, sin datos de entrenamiento ni
supervisión humana. En lugar de ajustar los pesos por descenso de gradiente, se **evoluciona
una población** de serpientes generación tras generación: los mejores hijos de una generación
son la base de la siguiente. Y **cada entrenamiento la hace más lista** — su nivel de
inteligencia sube de forma medible y queda registrado.

**React + Vite + Tailwind** en el frontend. **NumPy** en el cerebro. Servidor **autoritativo**
por WebSocket. Un solo comando para todo.

<p>
  <img alt="Python" src="https://img.shields.io/badge/Python-NumPy-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-WebSocket-009688?logo=fastapi&logoColor=white">
  <img alt="React" src="https://img.shields.io/badge/React-Vite-61DAFB?logo=react&logoColor=black">
  <img alt="Lighthouse desktop 100" src="https://img.shields.io/badge/Lighthouse_desktop-100-0CCE6B?logo=lighthouse&logoColor=white">
</p>

---

## ▶️ Arranque

```bash
pip install -r requirements.txt   # numpy, fastapi, uvicorn
npm install                       # react, vite, tailwind
npm run dev                       # ¡listo!
```

`npm run dev` ejecuta `run.py`, que levanta **dos procesos en paralelo**:

| Proceso | Puerto | Qué hace |
| --- | --- | --- |
| `uvicorn ai_server:app` | 8000 | La IA: reglas del juego, neuroevolución, persistencia. |
| `vite` | 5173 | La interfaz React, con recarga en caliente. |

Abre **<http://localhost:5173>**. `Ctrl+C` cierra los dos.

> El frontend usa rutas relativas (`/api/…`, `/ws/…`) y Vite las reenvía al 8000. Por eso no
> hay ninguna URL escrita a mano y el mismo código vale en local y en un hosting con HTTPS.

---

## 🏛️ Arquitectura

```
        React (navegador)                    Python
    ┌───────────────────────┐        ┌──────────────────────┐
    │  src/                 │        │  ai_server.py        │
    │   ├── App.jsx         │  REST  │   REST + WebSocket   │
    │   ├── views/          │◀──────▶│                      │
    │   ├── components/     │   WS   │  ┌────────────────┐  │
    │   └── lib/            │        │  │ snake_neuro    │  │
    │                       │        │  │ evolution.py   │  │
    │  Solo dibuja.         │        │  │ (NumPy: red +  │  │
    │  Cero reglas.         │        │  │  genético)     │  │
    └───────────────────────┘        │  └────────────────┘  │
                                     │  storage.py          │
              run.py ────────────────┤   historial/         │
         (levanta ambos)             └──────────────────────┘
```

**El servidor es la autoridad.** El navegador no sabe qué es una colisión ni cómo muta una red
neuronal: envía teclas y dibuja el estado que recibe. React no puede desincronizarse del
algoritmo porque no lo conoce.

| Archivo | Responsabilidad |
| --- | --- |
| `snake_neuroevolution.py` | **El cerebro.** Red neuronal, agente, algoritmo genético y niveles. Sin interfaz. |
| `storage.py` | Persistencia: carpetas de especímenes y configuración. |
| `ai_server.py` | Servidor: REST + WebSocket. En producción también sirve `dist/`. |
| `run.py` | Orquestador: levanta la IA y Vite, y los cierra juntos. |
| `src/` | La interfaz React. |
| `benchmarks/` | Medición **reproducible** de rendimiento (motor y carga). |
| `migrar_historial.py` | Migra el formato antiguo (`mejores_ias.json`) al nuevo. |

---

## 🖥️ Las 4 vistas

| Vista | Qué hace |
| --- | --- |
| **Jugar** | Partida manual. Cuenta atrás animada **3 → 2 → 1** (~2 s) antes de darte el control. |
| **Entrenar IA** | Selector de carpeta: nombre nuevo = espécimen desde cero; nombre existente = **sigue su linaje**. Slider de 1 a 100 generaciones. Muestra el **nivel de inteligencia en vivo**. |
| **Historial** | Lista interactiva con récord, nivel alcanzado, cobertura, generaciones acumuladas y mini-gráfica de scores. Probar ▶, marcar ★, borrar. |
| **Configuración** | Estilo (oscura / minimalista / verde), generaciones y tablero (8×8, 10×10, 15×15). |

---

## 🧠 Cómo aprende

Cada serpiente lleva su propia red neuronal **recurrente 26 → 20 → 3**.

**Percepción (26 entradas) — visión ampliada.** La serpiente lanza **8 rayos egocéntricos**
(frente, diagonales y laterales, relativos a hacia dónde mira) y en cada uno mide tres cosas:
distancia a la pared, proximidad de su propio cuerpo y alineación con la manzana → **24
sensores**. A eso se suman dos sensores globales:

- **Tamaño propio** (propioceptivo), normalizado por el área del tablero.
- **Espacio libre alcanzable**: un *flood-fill* desde la cabeza que mide qué fracción del
  tablero puede todavía recorrer. Es la señal que le enseña a **no encerrarse a sí misma**.

**Memoria (recurrencia).** La capa oculta se realimenta a sí misma (`W_rec`): en cada turno ve
las entradas del momento **y su propio estado del turno anterior**. Eso le da memoria dentro de
una partida —recordar por dónde venía—, el ingrediente que la planificación emergente necesita.
Nace a cero (se comporta como una feedforward) y la mutación la va introduciendo, así que añadir
memoria no degrada nada de lo aprendido.

**Decisión (3 salidas).** Seguir recto, girar a la izquierda o girar a la derecha.

**Fitness — recompensa densa.**

```
fitness = pasos  +  (tamaño − 3) × 1000  +  shaping_de_acercamiento
```

Crecer sigue valiendo **mil veces** más que sobrevivir, así que la evolución premia sobre todo
comer. La novedad es el `shaping`: una señal continua que **premia acercarse a la manzana y
penaliza (algo más) alejarse**, para orientar a las que aún no han comido en vez de dejarlo al
azar. Es lo que acelera el salto de la supervivencia refleja al forrajeo intencionado.

**Evolución (la herencia).** Al terminar cada generación:

- **Elitismo:** las 3 mejores redes pasan **intactas** a la siguiente generación.
- **Selección por torneo:** grupos de 3 al azar; gana el de mayor fitness.
- **Cruce uniforme:** el hijo hereda cada peso de uno u otro padre.
- **Mutación gaussiana adaptativa:** un 5 % de los pesos se perturba; y si la población se
  **estanca**, la intensidad de la mutación baja sola (*recocido*) para pasar de explorar a
  afinar, sin dejar nunca de explorar del todo.

Por eso la Generación 2 se entrena **literalmente sobre los mejores hijos de la 1**.

---

## 📈 Niveles de inteligencia

La inteligencia de un espécimen se mide con una sola regla objetiva, la **cobertura**: qué
fracción del tablero llega a ocupar su cuerpo. Es independiente del tamaño de tablero, así que
compara de forma justa 8×8, 10×10 y 15×15. **Cada entrenamiento que mejora el récord sube (o
mantiene) el nivel**, y el nivel se muestra en la vista de Entrenar y en el Historial.

```
cobertura = longitud / (grid × grid)
```

| Nivel | Cobertura | Capacidad | Estado en el proyecto |
| --- | --- | --- | --- |
| **N0 · Supervivencia refleja** | < 10 % | Evita la pared un rato; come por accidente. | ✅ punto de partida |
| **N1 · Forrajeo básico** | 10–20 % | Se orienta hacia la comida y come sin azar. | ✅ alcanzable |
| **N2 · Forrajeo fiable** | 20–35 % | Come consistente y deja de encerrarse en cuerpos cortos. | ✅ alcanzable |
| **N3 · Conciencia espacial** | 35–55 % | Con cuerpo largo planifica giros para no atraparse. | ✅ habilitado por la visión de 8 rayos + espacio libre |
| **N4 · Planificación emergente** | 55–80 % | Recorre el tablero de forma eficiente sin encerrarse. | 🧩 mecanismo listo (memoria recurrente); alcanzar la cobertura depende del entrenamiento |
| **N5 · Casi óptimo** | > 80 % | Llena casi todo el tablero (estrategia tipo ciclo hamiltoniano aprendido). | 🔬 I+D: visión global (CNN) + evaluación vectorizada |

> **Sobre la honestidad de esta tabla:** el nivel **se mide de verdad** (cobertura del mejor
> resultado), no se declara. La arquitectura actual soporta los mecanismos hasta **N4**
> (percepción de 8 rayos + espacio libre para N3, y memoria recurrente para N4); *alcanzar* la
> cobertura de N4 es un resultado empírico de entrenamiento, no algo cableado. **N5** (visión
> global por CNN) es línea de I+D: está documentado, no fingido. La hoja de ruta técnica
> completa —qué desbloquea cada nivel y en qué orden— está en **[`plan.txt`](plan.txt)**.

---

## ⚡ Performance & Scalability

> Todas las cifras son **medidas y reproducibles**, no estimadas. Los scripts viven en
> `benchmarks/`.

**Motor de neuroevolución (CPU-bound, NumPy).** El entrenamiento corre en un **hilo dedicado**,
desacoplado del bucle asyncio del servidor por un patrón productor/consumidor: el último
fotograma se **sobrescribe** en lugar de encolarse (el núcleo produce miles de pasos por
segundo y al cliente solo le importa el más reciente), de modo que el streaming por WebSocket
nunca genera *backpressure*. Medido con `benchmarks/bench_core.py` (`time.perf_counter`,
tablero 8×8, población 25, promedio de 5 corridas):

| Métrica | Valor |
| --- | --- |
| Pasos simulados (inferencias) / s | **≈ 4.000** |
| Individuos evaluados / s | **≈ 66** |
| Generaciones / s | **≈ 2,6** |
| Tiempo por generación | **≈ 380 ms** (p95 ≈ 650 ms · p99 ≈ 775 ms) |

Cada paso ejecuta la red recurrente completa **más** un *flood-fill* del espacio alcanzable; ese
sensor es el punto más caliente, así que usa índices planos y un `bytearray` de visitados en vez
de un `set` de tuplas — misma semántica, sin el coste de hashear miles de tuplas por partida. El
cuello de botella restante es inherente a la percepción rica en Python puro: y hay una tensión
real que vale la pena nombrar —el *flood-fill* que da la inteligencia espacial es justo lo más
difícil de vectorizar—, así que el siguiente salto (evaluación **vectorizada por lotes** para
poblaciones de miles) es un rediseño del simulador, documentado en `plan.txt`, no un cambio de
una línea.

**Frontend — Google Lighthouse** sobre el build de Vite (`dist/`), Chrome headless:

| Dispositivo | Performance | A11y | Best Practices | SEO | LCP | TBT | CLS |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Desktop** | **100** | 94 | 96 | 90 | 0,5 s | 0 ms | 0,016 |
| **Mobile** | **~90** ¹ | 94 | 96 | 90 | ~2,2–3,6 s | 10–160 ms | ≤ 0,04 |

¹ *El score móvil bajo throttling simulado varía entre corridas (observado 84–97); se reporta
el rango honesto en vez del mejor dato.*

Optimizaciones aplicadas: build con **Vite** (tree-shaking, minificación y hashing de assets),
**CSS utilitario purgado** con Tailwind, y un cliente "tonto" que **solo dibuja** (cero lógica
de juego) para minimizar el trabajo del hilo principal. CLS ≈ 0 gracias a un tablero de
dimensiones fijas.

**Carga del backend (opcional).** `benchmarks/load_test.js` es una prueba de **k6** real contra
los endpoints REST, con umbrales de PASS/FAIL (p95 < 200 ms, éxito > 99 %):

```bash
python ai_server.py                 # levanta la API en :8000
k6 run benchmarks/load_test.js      # requiere instalar k6
```

---

## 📁 El historial: una carpeta por espécimen

```
historial/
  Serpiente_Pro_v1/
    modelo.json      ← identidad + el mejor linaje (pesos y sesgos óptimos)
    sesiones.json    ← histórico de scores, un registro por entrenamiento
  Cobra-IA-V14/
    ...
```

`modelo.json`:

```jsonc
{
  "carpeta": "Cobra-IA-V14",
  "nombre": "Cobra-IA-V14",
  "generaciones": 51,        // acumuladas de TODOS sus entrenamientos
  "fitness": 23209,          // récord histórico
  "frutas": 23, "pasos": 209, "length": 26,
  "grid": 8,
  "favorito": true,
  "pesos": { "W1": [...], "b1": [...], "W2": [...], "b2": [...] }
}
```

El **nivel y la cobertura** se derivan siempre de `length` y `grid` al leer el modelo, así que
hasta los especímenes guardados antes de existir el sistema de niveles muestran el suyo.

### Seguir entrenando

Entrenar con un nombre que **ya existe** continúa ese linaje: la población inicial no es
aleatoria, sino un clon exacto de su red más variantes mutadas a su alrededor. Las
generaciones se suman, y **el récord solo puede subir**: si la tanda sale peor (la evolución
tiene azar), se conservan los pesos anteriores. Seguir entrenando nunca empeora tu IA.

### Favoritos

Vaciar el historial **conserva los favoritos**: son justo lo que marcaste para no perder.

---

## ⚙️ Parámetros

En `snake_neuroevolution.py`:

| Parámetro | Valor | Descripción |
| --- | --- | --- |
| `POP_SIZE` | `25` | Agentes por generación. |
| `N_INPUTS` → `N_HIDDEN` → `N_OUTPUTS` | `26 → 20 → 3` | Arquitectura de la red (visión ampliada + capa oculta recurrente `W_rec`). |
| `ENERGY_START` | `200` | Pasos sin comer antes de morir de inanición. |
| `ELITE_COUNT` | `3` | Mejores redes que pasan intactas. |
| `MUTATION_RATE` | `0.05` | Probabilidad de mutación por peso. |
| `MUTATION_STD` | `0.20` | Desviación inicial del ruido de mutación. |
| `MUTATION_DECAY` / `MUTATION_STD_MIN` | `0.85` / `0.05` | Recocido adaptativo y su suelo. |
| `STAGNATION_PATIENCE` | `4` | Generaciones sin mejora antes de enfriar la mutación. |
| `APPROACH_REWARD` / `APPROACH_PENALTY` | `3.0` / `4.0` | Shaping por acercarse / alejarse de la comida. |
| `TOURNAMENT_K` | `3` | Tamaño del torneo. |
| `FRUIT_REWARD` | `1000` | Fitness por bloque de crecimiento. |
| `GRID_SIZES` | `(8, 10, 15)` | Tableros disponibles. |

> **Los sensores están normalizados** (`distancia / grid`), así que una red entrenada en 8×8
> también sabe jugar en 15×15 — aunque peor: nunca vio tanto espacio.

---

## 🚀 Despliegue

```bash
npm run build     # compila la web en dist/
npm start         # un solo proceso Python sirviendo web + IA
```

En producción `run.py --prod` **no levanta Vite**: `ai_server.py` detecta `dist/` y sirve la
web él mismo. Un proceso, un puerto (`$PORT` o 8000).

Dos cosas antes de publicarlo:

- **Necesita WebSockets.** El juego y el entrenamiento van por WS; un hosting estático
  (GitHub Pages) no sirve. Render, Railway o Fly.io sí.
- **El estado es una carpeta, no una base de datos.** `historial/` es compartido por todos los
  visitantes. Perfecto para uso personal o una demo; para varios usuarios con historiales
  separados harían falta sesiones y una BD.

---

## 🔄 Migrar / compatibilidad de modelos

```bash
python migrar_historial.py --dry   # muestra qué haría, sin escribir
python migrar_historial.py         # migra
```

Convierte `mejores_ias.json` en carpetas y traduce `config.json`. Es idempotente y **no
destructivo**.

Las redes cambian de tamaño entre versiones (antes `9`/`10 → 12 → 3` feedforward, ahora
`26 → 20 → 3` recurrente), y `NeuralNetwork.from_dict` **adapta cualquier red guardada a la
arquitectura actual sin regresión**: copia los pesos heredados en la esquina de una red nueva y
deja el resto **neutro** (las entradas nuevas con peso cero, las neuronas nuevas con salida cero
y la **memoria `W_rec` a cero**, que la hace comportarse como la feedforward que era). La red
decide exactamente lo mismo que antes de crecer, y la mutación se encarga luego de dar uso a la
capacidad nueva. Por eso seguir entrenando un espécimen antiguo **nunca degrada lo aprendido**.

---

## 🎮 Controles

- **Jugar:** flechas o `WASD`; `R` reinicia. En móvil, botones táctiles.
- **Entrenar:** el botón *Cancelar* detiene la evolución sin guardar nada.

---

## 📄 Licencia

Ver el archivo `LICENCE`.
