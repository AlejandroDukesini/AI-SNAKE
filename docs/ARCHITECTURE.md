# 🏗️ Arquitectura y Evidencia — Snake IA

> **Documento consolidado.** Fusiona la *planificación estratégica / caja blanca* (antes
> `PLANNING.md`) con la *prueba técnica de funcionamiento* (antes `TECHNICAL_PROOF.md`): diseño y
> evidencia medida en un solo sitio. Hoja de ruta de inteligencia en [`ROADMAP.md`](ROADMAP.md) ·
> los motores en [`ENGINES.md`](ENGINES.md) · cambios en [`../CHANGELOG.md`](../CHANGELOG.md).

---

## Parte I · Planificación estratégica y arquitectura (caja blanca)

> Documento de reconstrucción arquitectónica y de producto, elaborado por ingeniería inversa
> sobre el código real del repositorio (`ai_server.py`, `snake_neuroevolution.py`, `storage.py`,
> `run.py`, `src/`, `ROADMAP.md`). No es marketing: cada afirmación es rastreable a un archivo.

**Versión del producto:** 2.0.0 · **Stack:** Python (NumPy · FastAPI) + React (Vite · Tailwind) · **Despliegue:** Netlify / Vercel

---

## 1. 🎯 Resumen Ejecutivo y Propuesta de Valor

### El problema

El aprendizaje por refuerzo y la neuroevolución son intimidantes: cajas negras que exigen
datasets, GPUs y tooling de investigación. No existe un artefacto **interactivo, visual y
honesto** que permita a una persona *ver aprender a una IA desde cero*, medir cuánto de lista
se ha vuelto y conservar su linaje entre sesiones — sin escribir una línea de código ni
entender gradientes.

### La propuesta de valor

Snake IA resuelve el clásico juego mediante una **IA que aprende sola**: no hay descenso de
gradiente ni datos de entrenamiento supervisado. En su lugar se **evoluciona una población** de
serpientes generación tras generación (los mejores hijos de una generación son la base de la
siguiente). El valor diferencial se sostiene en tres pilares:

1. **Aprendizaje observable en vivo.** El usuario ve, en tiempo real por WebSocket, cómo la
   población evoluciona — no un log, sino el juego dibujándose.
2. **Inteligencia medida, no declarada.** Una única métrica objetiva —la **cobertura**
   (`longitud / (grid × grid)`)— clasifica a cada espécimen en niveles N0–N5. El nivel **solo
   puede subir** entrenamiento a entrenamiento; una mala racha nunca degrada lo aprendido.
3. **Herencia persistente.** Cada IA es una carpeta con su mejor linaje. Reentrenar un nombre
   existente **continúa** ese linaje, no lo reemplaza.

### Objetivos del sistema

- **Educar/demostrar** cómo la selección natural produce comportamiento inteligente emergente.
- **Servir como portafolio técnico** de dominio full-stack + ML clásico sin frameworks pesados.
- **Garantizar honestidad metodológica:** todas las cifras de rendimiento son medidas y
  reproducibles (`benchmarks/`), y la escalera de niveles distingue explícitamente "tener el
  mecanismo" de "alcanzar la cobertura".

### Casos de uso clave

| Caso | Vista | Flujo |
| --- | --- | --- |
| Jugar manualmente al Snake | **Jugar** | Cuenta atrás 3→2→1, luego control por teclado/táctil. |
| Entrenar una IA nueva o continuar una | **Entrenar IA** | Selector de carpeta, slider de generaciones, nivel en vivo. |
| Auditar el progreso de un linaje | **Historial** | Récord, nivel, cobertura, mini-gráfica de scores; probar ▶ / ★ / borrar. |
| Ajustar tablero / tema / generaciones | **Configuración** | Persistido en `config.json`. |

### Perfil del usuario final

- **Entusiasta técnico / estudiante de IA** que quiere *intuición visual* sobre neuroevolución.
- **Reclutador o revisor técnico** evaluando profundidad de ingeniería (el proyecto está
  diseñado para ser explicable de arriba a abajo).
- **Uso personal / demo:** el estado (`historial/`) es una carpeta compartida por todos los
  visitantes — perfecto para single-user, explícitamente no multi-tenant (ver §5).

---

## 2. 🏗️ Arquitectura del Sistema y Análisis de Caja Blanca

### Patrón arquitectónico: Cliente-Servidor Autoritativo con núcleo desacoplado

No es un monolito ni un microservicio: es un **backend autoritativo desacoplado de un cliente
"tonto"**. La decisión rectora, presente en cada archivo, es:

> **El servidor es la única autoridad. El navegador no conoce ninguna regla del juego: envía
> teclas y dibuja el estado que recibe. React no puede desincronizarse del algoritmo porque no
> lo conoce.**

Esto colapsa una clase entera de bugs (cliente y servidor divergiendo) por diseño. El sistema
se estratifica en tres capas con fronteras estrictas:

| Capa | Archivo | Responsabilidad | Qué NO hace |
| --- | --- | --- | --- |
| **Cerebro (dominio puro)** | `snake_neuroevolution.py` | Red recurrente 26→20→3, agente `Snake`, algoritmo genético, niveles. Solo NumPy. | No sabe de HTTP, WebSocket ni React. |
| **Persistencia** | `storage.py` | Carpetas de especímenes, `config.json`, slugify, herencia de linaje. | No sabe de ML (importa `ml` solo para clamps/niveles). |
| **Servidor (BFF)** | `ai_server.py` | REST + WebSocket; en prod sirve `dist/`. Orquesta cerebro ↔ cliente. | No implementa reglas de juego (delega en el cerebro). |
| **Cliente (presentación)** | `src/` (React) | Dibuja estado, captura input, navega. | Cero lógica de juego. |
| **Orquestador** | `run.py` | Levanta uvicorn + Vite (dev) o solo uvicorn (prod). | — |

El servidor cumple el rol de un **BFF (Backend-For-Frontend)**: expone exactamente lo que la UI
necesita (p. ej. `/api/config` devuelve también `limits` y `themes` para que React construya sus
controles **sin duplicar constantes** del núcleo).

### Diagrama de flujo de datos

```
   NAVEGADOR (React — "solo dibuja")                    SERVIDOR PYTHON (autoritativo)
 ┌───────────────────────────────────┐              ┌──────────────────────────────────────┐
 │  App.jsx  (estado + navegación)   │              │           ai_server.py               │
 │    ├─ PlayView   ─ useSocket ─┐   │              │  ┌────────────────────────────────┐  │
 │    ├─ TrainView  ─ WS directo ┤   │   REST       │  │ REST  /api/config /api/models  │  │
 │    ├─ HistoryView ─ api.js ───┼───┼─────────────▶│  │       /api/exists/{n} ...      │  │
 │    └─ ConfigView ─ api.js ────┘   │◀─────────────│  └────────────────────────────────┘  │
 │                                   │   JSON        │  ┌────────────────────────────────┐  │
 │  lib/api.js  (rutas relativas)    │              │  │ WS /ws/play  /ws/train         │  │
 │  lib/useSocket.js (ciclo de vida) │   WebSocket  │  │    /ws/demo/{carpeta}          │  │
 │  lib/consent.js (RGPD, terceros)  │◀════════════▶│  └───────────────┬────────────────┘  │
 └───────────────────────────────────┘   frames      │                 │ hilo dedicado     │
        │  proxy Vite (dev)                           │                 ▼ (productor)        │
        │  mismo origen (prod)                        │  ┌────────────────────────────────┐  │
        ▼                                             │  │  snake_neuroevolution.py       │  │
   Vite :5173  ──/api,/ws──▶  uvicorn :8000           │  │  NeuralNetwork · Snake · GA    │  │
                                                      │  └───────────────┬────────────────┘  │
                                                      │                  ▼                    │
                                                      │  ┌────────────────────────────────┐  │
                                                      │  │  storage.py → historial/<slug>/│  │
                                                      │  │   modelo.json · sesiones.json  │  │
                                                      │  └────────────────────────────────┘  │
                                                      └──────────────────────────────────────┘
```

**Recorrido de un entrenamiento (el flujo crítico):**

1. `TrainView` abre `WS /ws/train` y envía `{generations, grid, agents, elite, nombre, infinite}`.
2. `ai_server` valida (clamps del núcleo), resuelve la carpeta (`slugify`) y decide **herencia**:
   si existe, `seed_brain = NeuralNetwork.from_dict(previo)`; si no, población aleatoria.
3. La neuroevolución corre en un **hilo dedicado** (patrón productor/consumidor). El último
   fotograma se **sobrescribe** (`ultimo["step"]`), no se encola: el núcleo produce miles de
   pasos/s y al cliente solo le importa el más reciente → **sin backpressure**.
4. El bucle emisor asyncio drena a `STREAM_FPS` (20 fps) y emite `step` / `gen` / `done`.
5. Al terminar, `storage.save_training` acumula generaciones y **solo sustituye los pesos si se
   batió el récord** (la evolución tiene azar; reentrenar nunca empeora tu IA).

### Justificación técnica de la pila

| Elección | Por qué esta y no otra |
| --- | --- |
| **NumPy puro (sin PyTorch/TF)** | El modelo es una red pequeña (26→20→3) evolucionada, no entrenada por gradiente. Un framework de DL sería peso muerto: NumPy vectoriza el forward y mantiene el proyecto instalable con `pip install numpy fastapi uvicorn`. Coherente con el objetivo educativo: **no hay caja negra**. |
| **FastAPI + uvicorn** | Necesita **REST y WebSocket en el mismo proceso** con asyncio de primera clase. FastAPI da tipado con Pydantic (validación de `/api/config`), WS nativo y un ASGI que convive con el hilo de cómputo. Flask no trae WS nativo; Django es desproporcionado. |
| **WebSocket (no polling/SSE)** | El streaming de fotogramas es **alta frecuencia y bidireccional** (el cliente manda `pause/stop/cancel` mientras recibe). SSE es unidireccional; polling añadiría latencia y carga. |
| **React + Vite** | Cuatro vistas con estado y ciclo de vida (montar/desmontar cierra sockets). Vite da HMR en dev y un build con tree-shaking/hashing que rinde **Lighthouse desktop 100**. |
| **Tailwind v4** | CSS utilitario **purgado**: solo las clases usadas llegan al build → payload mínimo, clave para el LCP. |
| **Estado en carpetas JSON (no BD)** | El dominio es "un archivo por espécimen" con pesos legibles a mano y migrables. Una BD sería sobreingeniería para single-user; la deuda (multi-tenant) está documentada, no oculta. |
| **Rutas relativas + `VITE_BACKEND_URL`** | Un solo build vale para despliegue **monolítico** (mismo origen) y **partido** (frontend Vercel + backend Render). Cero URLs hardcodeadas. |

---

## 3. 🗺️ Planificación por Rebanadas Verticales (Vertical Slices)

Reconstrucción de la hoja de ruta. Cada rebanada conecta **Persistencia + Núcleo/API +
Interfaz** de principio a fin, entregando una capacidad usable. El orden se infiere de
`ROADMAP.md` (secciones `[HECHO]`) y de la evolución del esquema de datos.

### Sprint 0 — Cimientos: el juego autoritativo
- **Núcleo:** clase `Snake` (movimiento, colisión, tablero), reglas del juego en Python.
- **API:** `WS /ws/play` — servidor manda, cliente dibuja. `start` tras la cuenta atrás.
- **UI:** `PlayView` + `Board.jsx`, controles teclado/táctil.
- **Entregable:** jugar Snake manualmente con el servidor como única autoridad.

### Sprint 1 — El cerebro evolutivo mínimo
- **Núcleo:** `NeuralNetwork` feedforward (base `10→12→3`), `crossover`, `mutate`,
  `next_generation`, `train`. Fitness = pasos + crecimiento × 1000.
- **API:** `WS /ws/train` con hilo dedicado y patrón productor/consumidor.
- **UI:** `TrainView` con streaming en vivo.
- **Entregable:** ver evolucionar una población desde pesos aleatorios.

### Sprint 2 — Persistencia y linaje
- **Persistencia:** `storage.py` → una **carpeta por espécimen** (`modelo.json` +
  `sesiones.json`). `slugify` como barrera anti path-traversal. Herencia: reentrenar un nombre
  existente **continúa** el linaje; el récord solo sube.
- **API:** REST `/api/models`, `/api/models/{c}`, `/api/exists/{n}`, favoritos, rename, delete.
- **UI:** `HistoryView` (lista, récord, mini-gráfica), selector "crear vs continuar".
- **Entregable:** IAs con identidad persistente que mejoran entre sesiones.

### Sprint 3 — Medir la inteligencia (Paso 1 del plan)
- **Núcleo:** métrica de **cobertura** + `nivel_de_cobertura` (clasificador N0–N5).
- **Persistencia:** `record_cobertura` **monótono** por espécimen; nivel por sesión.
- **UI:** nivel en vivo en Entrenar y en el Historial (derivado incluso de modelos antiguos).
- **Entregable:** progreso demostrable con una regla objetiva. *"Sin métrica no hay progreso."*

### Sprint 4 — Inteligencia "gratis" sin tocar arquitectura (Paso 2)
- **Núcleo:** **fitness shaping** denso (acercarse/alejarse, asimétrico) + **mutación adaptativa**
  (recocido por estancamiento). Desbloquea N1/N2.
- **Entregable:** forrajeo intencionado sin cambiar la red.

### Sprint 5 — Romper el techo perceptivo (Paso 4, adelantado por alto retorno)
- **Núcleo:** percepción de **8 rayos egocéntricos × 3 rasgos + 2 sensores globales** (tamaño +
  **flood-fill** de espacio libre) → entrada crece a **26**. Habilita N3 (conciencia espacial).
- **Compatibilidad:** `NeuralNetwork.from_dict` **adapta redes viejas sin regresión** (pesos
  nuevos a cero). `migrar_historial.py` convierte el formato legado.
- **Entregable:** la IA deja de encerrarse; visión suficiente para planificar giros.

### Sprint 6 — Memoria (Paso 5a)
- **Núcleo:** capa oculta **recurrente** (`W_rec`, estado que persiste entre turnos; nace a cero
  = neutra). Mecanismo de N4 (planificación emergente).
- **Entregable:** ingrediente para "recordar por dónde venía" sin degradar lo aprendido.

### Sprint 7 — Producción y cumplimiento
- **Servidor:** `/health` (GET+HEAD), `0.0.0.0` + `$PORT`, sirve `dist/` en prod; CORS por lista
  blanca + regex de previews.
- **Cliente:** gestor de **consentimiento RGPD** (`consent.js`, 4 categorías, scripts de terceros
  bloqueados hasta consentir), `vercel.json` con cabeceras de seguridad y cache inmutable.
- **Entregable:** desplegado en Netlify y Vercel, Lighthouse desktop 100.

### Pendiente (I+D, documentado en `ROADMAP.md`)
- **Paso 3:** evaluación **vectorizada por lotes** en NumPy (poblaciones de miles).
- **Paso 5b:** neuroevolución topológica (NEAT).
- **Paso 6:** visión global por **CNN** → N5 (casi óptimo).

---

## 4. 🔒 Seguridad, Rendimiento y Puntos Críticos

### Seguridad

- **Path traversal cerrado en origen.** `slugify` es la única barrera entre un nombre de usuario
  y el sistema de ficheros: `re.sub(r"[^A-Za-z0-9_\-]", "", ...)` + strip de puntos guía + máx 40
  chars. Un nombre `../../etc` no puede escribir fuera de `historial/`.
- **CORS explícito, no comodín.** Lista blanca de orígenes conocidos + regex acotado para previews
  de Vercel. `allow_credentials=False` porque **no viajan cookies** — el estado y el consentimiento
  viven en `localStorage`, reduciendo superficie (sin CSRF por cookie).
- **Consentimiento RGPD por diseño (`consent.js`).** Consentimiento **explícito y previo**: ningún
  script de terceros se carga sin permiso de su categoría. Los scripts se inyectan con
  `createElement + .src` (nunca `innerHTML`/`eval`) y solo desde **URLs https absolutas en lista
  blanca** (regex `SAFE_SRC`) → sin superficie de XSS por inyección de `<script>`.
- **Validación en frontera.** Pydantic (`ConfigIn`, `FavoriteIn`, `RenameIn`) valida los cuerpos
  REST; el núcleo **recorta** (`clamp_*`) todo parámetro de entrenamiento y devuelve el valor
  efectivo para que la UI no muestre cifras que no se están ejecutando.
- **Lectura tolerante a fallos.** `_read_json` devuelve un default ante JSON corrupto (los archivos
  del historial son editables a mano) en vez de reventar el servidor.
- **Cabeceras HTTP** (`vercel.json`): `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: strict-origin-when-cross-origin`.

### Rendimiento (medido, `benchmarks/bench_core.py`)

| Métrica (8×8, pop 25) | Valor |
| --- | --- |
| Pasos simulados / s | ≈ 4.000 |
| Individuos evaluados / s | ≈ 66 |
| Generaciones / s | ≈ 2,6 (≈ 380 ms/gen; p95 650 ms · p99 775 ms) |
| Lighthouse **desktop** | **Performance 100** · LCP 0,5 s · TBT 0 ms · CLS 0,016 |

**Optimizaciones aplicadas:**
- **Cliente tonto:** cero lógica de juego en el hilo principal del navegador → TBT bajísimo.
- **Build Vite** (tree-shaking, minificación, hashing) + **Tailwind purgado** → payload mínimo.
- **CLS ≈ 0** por tablero de dimensiones fijas.
- **Cache inmutable** de `/assets/*` (`max-age=31536000, immutable`).
- **Hot path del núcleo:** el flood-fill usa índices planos y un `bytearray` de visitados en vez
  de un `set` de tuplas — misma semántica, sin hashear miles de tuplas por partida.

### Puntos críticos y cómo se previenen en el código

| Cuello de botella / riesgo | Prevención en el código |
| --- | --- |
| **Cómputo CPU-bound bloquearía asyncio** | El entrenamiento corre en **hilo dedicado** (`threading.Thread(daemon=True)`); el bucle emisor solo drena colas. |
| **Backpressure del streaming** | El fotograma se **sobrescribe** (`ultimo["step"]`); solo `gen`/`done` usan cola real (no se pueden perder). |
| **Procesos huérfanos quemando CPU** | Al desconectar el WS se señaliza `parar`/`cancelar`; `esta_pausado` devuelve False al cerrar para no dejar el hilo girando; `join(timeout=2.0)` acotado nunca congela el servidor. |
| **Puertos zombie (npm→node huérfano)** | `run.py` mata el **árbol** de procesos (`taskkill /T` en Windows) y `comprobar_puertos` avisa antes de arrancar. |
| **Health check devolviendo 405** | `/health` y `/` aceptan **GET y HEAD** (muchos hosts sondean con HEAD). |
| **Pérdida de trabajo al cerrar en modo infinito** | Cerrar la pestaña se traduce en `stop` (guarda), no `cancel` (descarta). |
| **Regresión al reentrenar** | El récord (pesos) solo se sustituye si se supera; `record_cobertura` es monótono. |

---

## 5. 📈 Estrategia de Escalabilidad y Futuro

### Escalar a 10× de tráfico

El límite duro actual es que **el estado es una carpeta compartida por todos los visitantes** y el
servidor es un proceso con estado en memoria. Plan por capas:

1. **Frontend (ya listo).** La web es estática (`dist/`) tras CDN (Netlify/Vercel) con cache
   inmutable: absorbe 10× de lectores sin tocar el backend. El despliegue **partido**
   (`VITE_BACKEND_URL`) ya separa la carga de la web de la del backend.
2. **Aislar cómputo de I/O.** El streaming de partidas escala horizontalmente (varias réplicas
   uvicorn tras un balanceador con sticky sessions por WS). El **entrenamiento** es CPU-bound: se
   externaliza a una **cola de trabajos** (workers dedicados) en vez de correr en el proceso web.
3. **Multi-tenancy (el cambio estructural).** Introducir **sesiones/usuarios** y migrar
   `historial/` de carpetas a una **BD** (Postgres para metadatos + blob store para pesos). Hoy
   `storage.py` es una fachada estrecha: reemplazar sus funciones de lectura/escritura aísla la
   migración sin tocar el resto.
4. **Vectorización del núcleo (Paso 3).** Simular N agentes en paralelo con operaciones
   matriciales NumPy recupera el ~9× perdido por la percepción rica y permite poblaciones de miles
   por el mismo presupuesto de cómputo.

### Deuda técnica identificada (honesta, ya documentada)

| Deuda | Impacto | Plan de refinamiento |
| --- | --- | --- |
| **Estado global sin multi-usuario** | Todos comparten `historial/` | Sesiones + BD (paso 3 de arriba). |
| **Flood-fill en Python puro** | Hot path ~9× más lento que el motor simple | Rediseñar el simulador para evaluación vectorizada por lotes (Paso 3, `ROADMAP.md`). |
| **Topología de red fija** | Techo en N4 | Neuroevolución topológica NEAT (Paso 5b). |
| **Percepción por rayos** | Techo hacia N5 | Visión global por CNN sobre la rejilla (Paso 6, I+D). |
| **Windows sin SIGTERM real** | `taskkill /F` deja huérfanos | Mitigado: `comprobar_puertos` los detecta al arrancar. |

> Nota metodológica clave: `ROADMAP.md` distingue explícitamente **tener el mecanismo** de un nivel
> (p. ej. memoria recurrente para N4) de **alcanzar su cobertura** (resultado empírico de
> entrenamiento). La deuda no se disfraza de feature.

---

## 6. 💡 Resumen Técnico de Control (guía en 5 puntos)

Cómo explicárselo a cualquier desarrollador tradicional, de la interfaz a la base de datos:

1. **El servidor es la única autoridad; el cliente solo dibuja.** Toda regla del juego y todo el
   ML viven en Python (`snake_neuroevolution.py`). React (`src/`) captura teclas y pinta el estado
   que recibe. Por eso el cliente **no puede** desincronizarse del algoritmo: no lo conoce.

2. **Dos protocolos, un servidor (`ai_server.py`).** **REST** para lo puntual (config, listar y
   gestionar especímenes) y **WebSocket** para lo continuo y bidireccional (jugar, entrenar en
   vivo, ver una demo). Las rutas del cliente son **relativas** → un solo build funciona en local,
   monolítico y partido.

3. **El entrenamiento no bloquea el servidor.** La neuroevolución (CPU-bound) corre en un **hilo
   dedicado** con patrón productor/consumidor: el último fotograma se **sobrescribe** (nunca se
   encola) y el bucle asyncio lo emite a 20 fps. Así miles de pasos/segundo no saturan la red ni
   congelan el proceso.

4. **La identidad de una IA es su carpeta (`storage.py`).** Cada espécimen = una carpeta con
   `modelo.json` (mejor linaje: pesos) + `sesiones.json` (histórico). Reentrenar un nombre
   existente **hereda** sus pesos y **acumula** generaciones; el récord **solo sube**. `slugify`
   protege el sistema de ficheros de nombres maliciosos.

5. **La inteligencia se mide, no se declara.** Una sola regla —**cobertura** = `longitud /
   (grid²)`— clasifica cada IA en niveles N0–N5. El nivel es **monótono** (`record_cobertura`):
   una mala racha nunca lo baja. La hoja de ruta técnica (`ROADMAP.md`) documenta qué cambio de
   arquitectura desbloquea cada nivel y separa "mecanismo listo" de "cobertura alcanzada".

---

*Documento generado por análisis de caja blanca sobre el repositorio. Fuentes primarias:
`README.md`, `ROADMAP.md`, `ai_server.py`, `snake_neuroevolution.py`, `storage.py`, `run.py`,
`src/`, `vercel.json`, `vite.config.js`, `benchmarks/`.*


---

## Parte II · Prueba técnica de funcionamiento (evidencia medida)

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
lotes en NumPy— es un rediseño del simulador, documentado en `ROADMAP.md`, no un cambio de una línea.

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
cada nivel vive en `ROADMAP.md`; la reconstrucción arquitectónica completa, en la Parte I de este documento.
