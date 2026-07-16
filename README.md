# 🐍 Snake IA — Neuroevolución

El clásico **Snake** resuelto por una **IA que aprende sola**, sin datos de entrenamiento ni
supervisión humana. En lugar de ajustar los pesos por descenso de gradiente, se **evoluciona
una población** de serpientes generación tras generación: los mejores hijos de una generación
son la base de la siguiente.

**React + Vite + Tailwind** en el frontend. **NumPy** en el cerebro. Un solo comando para todo.

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
| `snake_neuroevolution.py` | **El cerebro.** Red neuronal, agente y algoritmo genético. Sin interfaz. |
| `storage.py` | Persistencia: carpetas de especímenes y configuración. |
| `ai_server.py` | Servidor: REST + WebSocket. En producción también sirve `dist/`. |
| `run.py` | Orquestador: levanta la IA y Vite, y los cierra juntos. |
| `src/` | La interfaz React. |
| `migrar_historial.py` | Migra el formato antiguo (`mejores_ias.json`) al nuevo. |

---

## 🖥️ Las 4 vistas

| Vista | Qué hace |
| --- | --- |
| **Jugar** | Partida manual. Cuenta atrás animada **3 → 2 → 1** (~2 s) antes de darte el control. |
| **Entrenar IA** | Selector de carpeta: nombre nuevo = espécimen desde cero; nombre existente = **sigue su linaje**. Slider de 1 a 100 generaciones. |
| **Historial** | Lista interactiva con récord, generaciones acumuladas y mini-gráfica de scores. Probar ▶, marcar ★, borrar. |
| **Configuración** | Estilo (oscura / minimalista / verde), generaciones y tablero (8×8, 10×10, 15×15). |

---

## 🧠 Cómo aprende

Cada serpiente lleva su propia red neuronal **10 → 12 → 3**.

**Percepción (10 entradas).** En sus tres direcciones relativas (Frente, Izquierda, Derecha)
mide: distancia a la pared, distancia a su propio cuerpo y alineación con la manzana. La
décima entrada es **propioceptiva: su propio tamaño**, normalizado por el área del tablero.

**Decisión (3 salidas).** Seguir recto, girar a la izquierda o girar a la derecha.

**Fitness.**

```
fitness = pasos + (tamaño − 3) × 1000
```

La serpiente nace con 3 bloques y **crece uno por cada manzana**. Crecer vale mil veces más
que sobrevivir, así que la evolución premia comer; los pasos solo desempatan entre las que aún
no han comido.

**Evolución (la herencia).** Al terminar cada generación:

- **Elitismo:** las 3 mejores redes pasan **intactas** a la siguiente generación.
- **Selección por torneo:** grupos de 3 al azar; gana el de mayor fitness.
- **Cruce uniforme:** el hijo hereda cada peso de uno u otro padre.
- **Mutación gaussiana:** un 5 % de los pesos se perturba, para explorar.

Por eso la Generación 2 se entrena **literalmente sobre los mejores hijos de la 1**.

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
  "fecha_creacion": "2026-07-16 13:46:19",
  "fecha_actualizacion": "2026-07-16 13:46:19",
  "generaciones": 51,        // acumuladas de TODOS sus entrenamientos
  "fitness": 23209,          // récord histórico
  "frutas": 23, "pasos": 209, "length": 26,
  "grid": 8,
  "favorito": true,
  "pesos": { "W1": [...], "b1": [...], "W2": [...], "b2": [...] }
}
```

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
| `ENERGY_START` | `200` | Pasos sin comer antes de morir de inanición. |
| `ELITE_COUNT` | `3` | Mejores redes que pasan intactas. |
| `MUTATION_RATE` | `0.05` | Probabilidad de mutación por peso. |
| `MUTATION_STD` | `0.20` | Desviación del ruido de mutación. |
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

## 🔄 Migrar desde la versión anterior

```bash
python migrar_historial.py --dry   # muestra qué haría, sin escribir
python migrar_historial.py         # migra
```

Convierte `mejores_ias.json` en carpetas y traduce `config.json`. Es idempotente y **no
destructivo**: no pisa carpetas existentes y conserva el JSON antiguo como copia de seguridad.

Dos detalles de la migración:

- **Las redes antiguas tenían 9 entradas** (sin el sensor de tamaño). Se les añade una columna
  de **ceros**: el peso cero hace que la entrada nueva no influya, así que la red decide
  exactamente lo mismo que antes, y a partir de ahí la mutación puede darle uso.
- **Las generaciones no se pueden deducir** en los especímenes antiguos (el límite ya era
  configurable: podían ser 5 o 51). Se muestran como *"generaciones no registradas"* en vez de
  inventar una cifra.

---

## 🎮 Controles

- **Jugar:** flechas o `WASD`; `R` reinicia. En móvil, botones táctiles.
- **Entrenar:** el botón *Cancelar* detiene la evolución sin guardar nada.

---

## 📄 Licencia

Ver el archivo `LICENCE`.
