<div align="center">

# 🐍 Snake IA — Neuroevolución

### Una IA que aprende a jugar Snake **sola**: sin datos, sin gradientes, solo selección natural.

<p>
  <img alt="Estado" src="https://img.shields.io/badge/estado-en_producción-5ad19a?style=flat-square">
  <img alt="Licencia BY-NC" src="https://img.shields.io/badge/licencia-BY--NC-6e8bff?style=flat-square">
  <img alt="Lighthouse 100" src="https://img.shields.io/badge/Lighthouse_desktop-100%2F100-0CCE6B?style=flat-square&logo=lighthouse&logoColor=white">
</p>

<p>
  <img alt="Python" src="https://img.shields.io/badge/Python-NumPy-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-WebSocket-009688?style=flat-square&logo=fastapi&logoColor=white">
  <img alt="React" src="https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black">
  <img alt="Vite" src="https://img.shields.io/badge/Vite-6-646CFF?style=flat-square&logo=vite&logoColor=white">
  <img alt="Tailwind v4" src="https://img.shields.io/badge/Tailwind-v4-38BDF8?style=flat-square&logo=tailwindcss&logoColor=white">
</p>

**📖 [Prueba Técnica](TECHNICAL_PROOF.md)** · **📐 [Planificación Estratégica](PLANNING.md)** · **🖥️ Documentación en la app** (vista *Documentación*) · **🌐 [Demo en vivo](https://ai-snake-nine.vercel.app/)**

</div>

---

## 🚀 ¿Por qué este proyecto es diferente?

No es un Snake con IA cableada a mano. Es una **IA que aprende sola** por neuroevolución, y lo
demuestra con métricas medidas, no con promesas.

- **🧠 Percepción egocéntrica de 26 entradas.** 8 rayos que miden pared, cuerpo y comida (24) + su
  propio tamaño + un *flood-fill* de espacio libre que le enseña a no encerrarse.
- **🔁 Red recurrente 26 → 20 → 3.** Una capa oculta con memoria (`W_rec`) que recuerda por dónde
  venía dentro de la partida. Nace neutra, así que añadir memoria nunca degrada lo aprendido.
- **🧬 Selección natural, sin gradientes.** No hay `backward()` ni dataset. Se evoluciona una
  población: la Generación 2 se entrena literalmente sobre los mejores hijos de la 1.

### La inteligencia se **mide**, no se declara

```
cobertura = longitud / (grid²)      # fracción del tablero que la IA llega a ocupar
```

Una regla objetiva, independiente del tamaño de tablero, clasifica cada IA en una escalera de
niveles. El nivel es **monótono**: solo sube o se mantiene, nunca baja por una mala racha.

| N0 | N1 | N2 | N3 | N4 | N5 |
|:--:|:--:|:--:|:--:|:--:|:--:|
| Supervivencia | Forrajeo básico | Forrajeo fiable | Conciencia espacial | Planificación emergente | Casi óptimo |
| < 10 % | 10–20 % | 20–35 % | 35–55 % | 55–80 % | > 80 % |

---

## 🛠️ Arquitectura en un vistazo (caja blanca)

```
   NAVEGADOR (React — "solo dibuja")            SERVIDOR PYTHON (autoritativo)
 ┌──────────────────────────────┐            ┌─────────────────────────────────────┐
 │  App.jsx · views/ · lib/     │   REST     │  ai_server.py  (FastAPI)            │
 │  cliente TONTO:              │◀──────────▶│    REST /api/…   WS /ws/…           │
 │  captura teclas, pinta el    │            │         │                           │
 │  estado que recibe.          │    WS      │         ▼  hilo dedicado (daemon)   │
 │  CERO reglas de juego.       │◀══════════▶│  snake_neuroevolution.py  (NumPy)   │
 └──────────────────────────────┘  20 fps    │    red recurrente + genético        │
                                             │         │                           │
                                             │         ▼                           │
                                             │  storage.py → historial/<slug>/     │
                                             │    modelo.json · sesiones.json      │
                                             └─────────────────────────────────────┘
```

**El servidor es la única autoridad.** El navegador no conoce ninguna regla del juego: envía
teclas y dibuja lo que recibe. Como el cliente **no** simula nada, no puede desincronizarse del
algoritmo — una clase entera de bugs de *state drift* desaparece por diseño.

**Backpressure resuelto por diseño.** El núcleo produce miles de fotogramas por segundo, pero al
cliente solo le importa el más reciente. El último fotograma se **sobrescribe** (`ultimo["step"]`)
en vez de encolarse; solo los eventos que no se pueden perder (`gen`, `done`) usan cola real. El
streaming va a **20 fps estables** sin saturar memoria ni red.

> 📖 Detalle completo, función por función, en **[TECHNICAL_PROOF.md](TECHNICAL_PROOF.md)**.

---

## 📊 Rendimiento (medido, reproducible)

Todas las cifras salen de `benchmarks/`, no de estimaciones.

| Métrica | Valor | Fuente |
| --- | --- | --- |
| Pasos simulados / s | **≈ 4.000** | `bench_core.py` (8×8, pop 25) |
| Generaciones / s | **≈ 2,6** | `bench_core.py` |
| Tiempo por generación | ≈ 380 ms (p95 650 · p99 775) | `bench_core.py` |
| Streaming WebSocket | **20 fps estables** | `ai_server.py` |
| Lighthouse **desktop** | **100 / 100** | build de Vite |
| LCP · TBT · CLS (desktop) | **0,5 s · 0 ms · 0,016** | Lighthouse |

---

## 💻 Requisitos e instalación

**Prerrequisitos:** Python **3.10+** · Node.js **18+**

```bash
# 1. Clonar
git clone <url-del-repo>
cd IA-SNAKE

# 2. Entorno virtual de Python (recomendado)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 3. Dependencias
pip install -r requirements.txt   # numpy · fastapi · uvicorn
npm install                       # react · vite · tailwind

# 4. Arrancar (un solo comando)
npm run dev
```

`npm run dev` ejecuta `python run.py`, que levanta **dos procesos en paralelo**:

| Proceso | Puerto | Qué hace |
| --- | :--: | --- |
| `uvicorn ai_server:app` | **8000** | La IA: reglas del juego, neuroevolución, persistencia. |
| `vite` | **5173** | La interfaz React, con recarga en caliente. |

Abre **<http://localhost:5173>**. `Ctrl+C` cierra los dos. El frontend usa rutas relativas
(`/api/…`, `/ws/…`) que Vite reenvía al 8000, así que el mismo código vale en local y en producción.

**Producción** (un solo proceso Python sirviendo web + IA):

```bash
npm run build     # compila la web en dist/
npm start         # python run.py --prod  → escucha en 0.0.0.0:$PORT
```

---

## 📁 Estructura del repositorio

```
IA-SNAKE/
├── snake_neuroevolution.py   # 🧠 EL CEREBRO. Red recurrente 26→20→3, agente Snake,
│                             #    algoritmo genético y niveles. Solo NumPy, sin interfaz.
├── ai_server.py              # ⚙️ SERVIDOR FastAPI: REST + WebSocket. Autoritativo.
│                             #    En producción también sirve dist/.
├── storage.py                # 🔒 PERSISTENCIA: una carpeta por espécimen, slugify,
│                             #    herencia de linaje, config.json.
├── run.py                    # ▶️ ORQUESTADOR: levanta uvicorn + Vite y los cierra juntos.
├── migrar_historial.py       # 🔄 Migra el formato antiguo (mejores_ias.json) al nuevo.
│
├── src/                      # 🖥️ INTERFAZ React (cliente tonto, "solo dibuja")
│   ├── App.jsx               #    Estado compartido + navegación entre las 5 vistas.
│   ├── views/                #    Jugar · Entrenar · Historial · Documentación · Configuración
│   ├── components/           #    Piezas de UI reutilizables (ui.jsx, Board, …).
│   └── lib/                  #    api.js, useSocket.js, consent.js (RGPD), …
│
├── benchmarks/               # 📊 Medición reproducible (bench_core.py, load_test.js de k6).
├── historial/                # 💾 Estado: una carpeta por IA entrenada.
│
├── TECHNICAL_PROOF.md        # 📖 Prueba técnica profunda (evidencia de funcionamiento).
├── PLANNING.md               # 📐 Planificación estratégica y análisis de caja blanca.
└── plan.txt                  # 🗺️ Hoja de ruta de la inteligencia (qué desbloquea cada nivel).
```

---

<div align="center">

**Stack:** Python · NumPy · FastAPI · React · Vite · Tailwind v4 &nbsp;·&nbsp; **Licencia:** BY-NC — atribución, no comercial (ver [`LICENCE`](LICENCE))

*La IA aprende sola. Las métricas están medidas. La arquitectura es explicable de arriba a abajo.*

</div>
