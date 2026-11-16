<div align="center">

# IA-SNAKE

**Cinco metodologías de aprendizaje resolviendo el mismo Snake.**

<p>
  <img alt="Estado" src="https://img.shields.io/badge/estado-en_desarrollo-f5a623?style=flat-square">
  <img alt="Pruebas" src="https://img.shields.io/badge/pytest-118_pasan-5ad19a?style=flat-square">
  <img alt="Licencia BY-NC" src="https://img.shields.io/badge/licencia-BY--NC-6e8bff?style=flat-square">
</p>
<p>
  <img alt="Python" src="https://img.shields.io/badge/Python-NumPy_·_scikit--learn-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-REST-009688?style=flat-square&logo=fastapi&logoColor=white">
  <img alt="React" src="https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black">
  <img alt="Vite" src="https://img.shields.io/badge/Vite-6-646CFF?style=flat-square&logo=vite&logoColor=white">
</p>

**[Despliegue](DOCUMENTACION_DESPLIEGUE_NETLIFY_VERCEL.txt)** · **[Arquitectura](docs/ia-snake/ARQUITECTURA.md)** · **[Manual de uso](docs/ia-snake/MANUAL-USUARIO.md)** · **[Resultados](docs/ia-snake/RESULTADOS.md)** · **[Decisiones](docs/ia-snake/DECISIONES.md)** · **[Cambios](CAMBIOS.txt)**

</div>

---

## Qué es

Un laboratorio experimental en el que cada modelo resuelve el mismo Snake con una metodología
distinta, sobre el mismo motor, los mismos sentidos y la misma evaluación:

| Modelo | Metodología | Cómo aprende | Estado inicial |
| --- | --- | --- | --- |
| **ARKIS** | Machine Learning supervisado | Random Forest entrenado con **tus** etiquetas | Sin entrenar |
| **LERK** | Aprendizaje simbólico | Inducción de reglas, experiencia, excepciones (RDR), generalización | Sin entrenar (base vacía) |
| **BORK** | Aprendizaje por refuerzo | Q-Learning tabular sobre un estado compacto | Sin entrenar |
| **CLARK** | Híbrido de referencia | Tres componentes propios (RF + reglas + tabla Q) integrados con vetos y pesos | Sin entrenar (decisión D4) |
| **MABU** | Híbrido experimental | Pendiente: arquitectura en la Etapa 5, preentrenamiento al final | — |

Ningún modelo usa redes neuronales ni Deep Learning. Un estado («entrenado», «validado»…) solo
cambia con evidencia registrada.

## Estado actual

| | |
| --- | --- |
| ✅ **Motor** | Tableros 4×4, 8×8 y 16×16; tres sentidos; recompensa por componentes; ciclos y regla de 30 s en tiempo de juego; E0–E8. E8 demostrado alcanzable en los tres tableros. |
| ✅ **ARKIS, LERK, BORK, CLARK** | Implementados, con pruebas que demuestran que cada uno pasa de no saber a superar al azar con su propia metodología. |
| ✅ **Laboratorio** | Interfaz con panel, simulador, percepción, un panel de entrenamiento distinto por modelo, evolución y comparación. Persistencia versionada por modelo. |
| ✅ **Entrenamiento en vivo** | Mientras un modelo entrena o se evalúa, se ve jugar: cada movimiento es su decisión real, con su explicación, resultado, recompensa (si aplica) y comparación entre episodios. Pausa, reanudación, parada y ritmo ajustable sin alterar lo aprendido (probado). |
| ✅ **Etiquetado guiado de ARKIS** | Cinco pasos explicados: observar, elegir la acción, guardar, revisar y entrenar. |
| ⏳ **MABU** | Pendiente: Etapa 5. |
| 🔬 **Pendiente de verificar por el director** | Las pruebas de uso. La interfaz se revisó con capturas de Chrome/Edge headless a 1920×1080, 1366×768 y 390 px (emulación de móvil). |

Cifras medidas: [docs/ia-snake/RESULTADOS.md](docs/ia-snake/RESULTADOS.md).

## Uso

**Requisitos:** Python 3.10+ · Node.js 18+

```bash
pip install -r requirements.txt     # numpy · scikit-learn · skops · fastapi · uvicorn
npm install
npm run dev:all                     # servidor en :8000 + interfaz en http://localhost:5173
```

| Comando | Qué hace |
| --- | --- |
| `npm run build && npm start` | Producción local: un solo proceso Python sirve la web y la API |
| `npm run build:netlify` / `build:vercel` | Builds de despliegue ([guía](DOCUMENTACION_DESPLIEGUE_NETLIFY_VERCEL.txt)) |
| `python -m pytest` | Todas las pruebas (`pip install -r requirements-dev.txt`) |
| `python scripts/lineas_base.py` | Líneas base sin aprendizaje (azar y voraz) en las tres dificultades |
| `python scripts/medir_modelos.py` | Entrena cada modelo desde cero y lo evalúa con semillas de prueba |

Los datos de tus modelos se guardan en `laboratorio/` (no se versiona en git).

## Estructura

```
ia_snake/
  nucleo/        motor, percepción, recompensas, ciclos, reloj, evolución, entorno
  modelos/       arkis · lerk · bork · clark (+ interfaz común, ejemplos, simetrías)
  persistencia/  versiones con SHA-256, SQLite de episodios, skops sin pickle
  evaluacion/    semillas disjuntas, IC 95 %, líneas base
  servidor/      FastAPI: sesiones en vivo, trabajos en segundo plano, API por modelo
src/             interfaz React (solo dibuja)
tests/           pruebas por capa e integración
scripts/         mediciones reproducibles
docs/ia-snake/      análisis, decisiones, arquitectura, manual, resultados
```

La versión anterior del proyecto (neuroevolución) se conserva en la etiqueta git `v2-neuroevolucion`.

<div align="center">

**Licencia:** BY-NC — atribución, no comercial ([`LICENCE`](LICENCE))

</div>
