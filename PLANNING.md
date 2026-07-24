# 📐 Planificación Estratégica — Snake IA (Neuroevolución)

> Documento de reconstrucción arquitectónica y de producto, elaborado por ingeniería inversa
> sobre el código real del repositorio (`ai_server.py`, `snake_neuroevolution.py`, `storage.py`,
> `run.py`, `src/`, `plan.txt`). No es marketing: cada afirmación es rastreable a un archivo.

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
`plan.txt` (secciones `[HECHO]`) y de la evolución del esquema de datos.

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

### Pendiente (I+D, documentado en `plan.txt`)
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
| **Flood-fill en Python puro** | Hot path ~9× más lento que el motor simple | Rediseñar el simulador para evaluación vectorizada por lotes (Paso 3, `plan.txt`). |
| **Topología de red fija** | Techo en N4 | Neuroevolución topológica NEAT (Paso 5b). |
| **Percepción por rayos** | Techo hacia N5 | Visión global por CNN sobre la rejilla (Paso 6, I+D). |
| **Windows sin SIGTERM real** | `taskkill /F` deja huérfanos | Mitigado: `comprobar_puertos` los detecta al arrancar. |

> Nota metodológica clave: `plan.txt` distingue explícitamente **tener el mecanismo** de un nivel
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
   una mala racha nunca lo baja. La hoja de ruta técnica (`plan.txt`) documenta qué cambio de
   arquitectura desbloquea cada nivel y separa "mecanismo listo" de "cobertura alcanzada".

---

*Documento generado por análisis de caja blanca sobre el repositorio. Fuentes primarias:
`README.md`, `plan.txt`, `ai_server.py`, `snake_neuroevolution.py`, `storage.py`, `run.py`,
`src/`, `vercel.json`, `vite.config.js`, `benchmarks/`.*
