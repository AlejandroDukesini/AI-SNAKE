<div align="center">

# 🐍 Snake IA — Neuroevolución

**Una IA que aprende a jugar Snake sola: sin datos, sin gradientes, solo selección natural.**

<p>
  <img alt="Estado" src="https://img.shields.io/badge/estado-en_desarrollo-f5a623?style=flat-square">
  <img alt="Verificaciones" src="https://img.shields.io/badge/audit__ia.py-70%2F70_PASA-5ad19a?style=flat-square">
  <img alt="Licencia BY-NC" src="https://img.shields.io/badge/licencia-BY--NC-6e8bff?style=flat-square">
</p>
<p>
  <img alt="Python" src="https://img.shields.io/badge/Python-NumPy-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-WebSocket-009688?style=flat-square&logo=fastapi&logoColor=white">
  <img alt="React" src="https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black">
  <img alt="Vite" src="https://img.shields.io/badge/Vite-6-646CFF?style=flat-square&logo=vite&logoColor=white">
  <img alt="Tailwind v4" src="https://img.shields.io/badge/Tailwind-v4-38BDF8?style=flat-square&logo=tailwindcss&logoColor=white">
</p>

**[Demo Netlify](https://ia-snake.netlify.app/)** · **[Demo Vercel](https://ai-snake-nine.vercel.app/)** · **[Arquitectura](docs/ARCHITECTURE.md)** · **[Motores](docs/ENGINES.md)** · **[Roadmap](docs/ROADMAP.md)** · **[Auditoría científica](docs/auditoria-cientifica-ia.md)**

</div>

---

## Qué es

Un algoritmo genético evoluciona los pesos de redes neuronales NumPy que controlan la serpiente. No
hay `backward()`, dataset ni modelos de terceros: cada generación se cría a partir de los mejores de
la anterior. El servidor Python es la única autoridad del juego; el navegador solo dibuja.

> Las demos de Netlify/Vercel corren en **modo borrador**: una heurística simulada en el navegador,
> rotulada como tal. La neuroevolución real requiere el servidor local.

## Estado actual

| | |
| --- | --- |
| ✅ **Medición fiable** | Semillas fijas: 3 partidas comunes por individuo (selección), 10 de validación, 20 de prueba independientes. Media, mediana, sd e IC 95 %, con el récord de una partida aparte. |
| ✅ **Modelos preservados** | 7 especímenes cargan con pesos exactos; modelos de 9/10 entradas y `advanced_v1` (26→32→16→3) deciden igual que su red original. Los incompatibles fallan con `ModelError`, nunca se sustituyen por una red aleatoria. |
| ✅ **Robustez** | Sin NaN/inf (estado acotado, sigmoide estable); entrenamientos reproducibles por semilla. |
| ⚠️ **Aprendizaje** | Muy por encima del azar, **por debajo de una regla voraz** sin aprendizaje. |
| 🔬 **No verificado** | Que el protocolo nuevo *aprenda mejor*: a igual cómputo, las diferencias no son significativas. |

### Resultados medidos (frutas por partida, 100 partidas de prueba por entrenamiento)

| Tablero · motor | Original | Original, 3× gen. | Actual | Regla voraz | Azar |
| --- | ---: | ---: | ---: | ---: | ---: |
| 8×8 · `intermated` | 7,00 | 8,48 | 7,80 | 15,72 | 0,24 |
| 8×8 · `advanced` | 8,36 | 8,56 | 8,64 | 15,72 | 0,24 |
| 8×8 · `basic` | 5,78 | 8,93 | **8,42** ¹ | 15,72 | 0,24 |
| 15×15 · `intermated` | 9,04 | 11,62 | **13,28** ¹ | 23,73 | 0,15 |

<sub>40 generaciones, 10 semillas de entrenamiento (6 en 15×15). ¹ Mejora significativa frente al
original con las mismas generaciones (IC 95 % sin 0); frente al original con 3× generaciones —igual
cómputo— ninguna diferencia es significativa. Detalle en la
[auditoría, §16](docs/auditoria-cientifica-ia.md).</sub>

### Limitaciones conocidas

- **Nivel típico N0** (< 10 % de cobertura) en todos los especímenes; N1–N2 solo en partidas sueltas.
- **El fitness premia dar vueltas** (+0,5 por paso sin comer). La alternativa simétrica se probó y no rindió mejor.
- **La diversidad cae al ~30 %** en 40 generaciones: la búsqueda se estanca (el original no mejora de 200 a 600 generaciones).
- **Coste ~5× por generación** (79 → 395 ms en 8×8) por la evaluación multipartida.
- Muestras de 4–10 entrenamientos por configuración: no detectan diferencias < ~1 fruta.

**Siguientes pasos:** evaluación vectorizada por lotes, diversidad (nichos/especiación), fitness sin
premio a bucles. Ver [Roadmap](docs/ROADMAP.md).

---

## Arquitectura

| Motor | Red | Notas |
| --- | --- | --- |
| **`intermated`** (por defecto) | 26 → 20 → 3, recurrente | ReLU + memoria `W_rec` |
| **`advanced`** | 26 → 16 → 3 | LeakyReLU, ~483 pesos |
| **`basic`** | 26 → 52 → 26 → 1 | Salida sigmoide por rangos |
| `advanced_v1` | 26 → 32 → 16 → 3 | Solo carga de especímenes antiguos |

**Percepción:** 26 entradas egocéntricas — 8 rayos (pared, cuerpo, comida) + tamaño + *flood-fill*
de espacio libre. **Genético:** torneo k=3, élite 3, cruce uniforme, mutación gaussiana con σ
adaptativo. **Fitness:** `pasos + 1000·frutas + shaping de acercamiento`.

```
React (solo dibuja) ◀── REST / WebSocket 20 fps ──▶ FastAPI ──▶ snake_neuroevolution.py (NumPy)
                                                       └──▶ storage.py → historial/<espécimen>/
```

El último fotograma se sobrescribe en lugar de encolarse, así el streaming no se satura.

---

## Uso

**Requisitos:** Python 3.10+ · Node.js 18+

```bash
pip install -r requirements.txt     # numpy · fastapi · uvicorn
npm install
npm run dev                         # IA en :8000 + interfaz en :5173
```

| Comando | Qué hace |
| --- | --- |
| `npm run build && npm start` | Producción: un proceso Python sirve web + IA |
| `python benchmarks/audit_ia.py` | 70 verificaciones deterministas + bloques estadísticos |
| `python benchmarks/experimento_ia.py` | Comparación original/actual con varias semillas |
| `python benchmarks/bench_core.py` | Rendimiento de cómputo |

---

## Estructura

```
snake_neuroevolution.py   Redes, agente, genético, evaluación
ai_server.py              FastAPI: REST + WebSocket (autoritativo)
storage.py                Persistencia por espécimen y linaje
src/                      Interfaz React (+ lib/demo: modo borrador)
benchmarks/               Auditoría, experimentos y benchmarks
docs/                     Arquitectura, motores, roadmap, auditoría, changelog
```

<div align="center">

**Licencia:** BY-NC — atribución, no comercial ([`LICENCE`](LICENCE))

*Proyecto en desarrollo: las cifras están medidas y las limitaciones, documentadas.*

</div>
