<div align="center">

# ARKIS AI LAB

**Cinco metodologías de aprendizaje resolviendo el mismo Snake.**

<p>
  <img alt="Estado" src="https://img.shields.io/badge/estado-en_desarrollo-f5a623?style=flat-square">
  <img alt="Pruebas" src="https://img.shields.io/badge/pytest-112_pasan-5ad19a?style=flat-square">
  <img alt="Licencia BY-NC" src="https://img.shields.io/badge/licencia-BY--NC-6e8bff?style=flat-square">
</p>
<p>
  <img alt="Python" src="https://img.shields.io/badge/Python-NumPy_·_scikit--learn-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-REST-009688?style=flat-square&logo=fastapi&logoColor=white">
  <img alt="React" src="https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black">
  <img alt="Vite" src="https://img.shields.io/badge/Vite-6-646CFF?style=flat-square&logo=vite&logoColor=white">
</p>

**[Despliegue](DOCUMENTACION_DESPLIEGUE_NETLIFY_VERCEL.txt)** · **[Arquitectura](docs/arkis/ARQUITECTURA.md)** · **[Manual de uso](docs/arkis/MANUAL-USUARIO.md)** · **[Resultados](docs/arkis/RESULTADOS.md)** · **[Decisiones](docs/arkis/DECISIONES.md)** · **[Cambios](CAMBIOS.txt)**

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
| ⏳ **MABU** | Pendiente: Etapa 5. |
| 🔬 **Pendiente de verificar por el director** | Las pruebas de uso de la interfaz: la web compila y el servidor se probó de extremo a extremo, pero la interfaz no se ha revisado visualmente en un navegador. |

Cifras medidas: [docs/arkis/RESULTADOS.md](docs/arkis/RESULTADOS.md).

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
arkis_lab/
  nucleo/        motor, percepción, recompensas, ciclos, reloj, evolución, entorno
  modelos/       arkis · lerk · bork · clark (+ interfaz común, ejemplos, simetrías)
  persistencia/  versiones con SHA-256, SQLite de episodios, skops sin pickle
  evaluacion/    semillas disjuntas, IC 95 %, líneas base
  servidor/      FastAPI: sesiones en vivo, trabajos en segundo plano, API por modelo
src/             interfaz React (solo dibuja)
tests/           pruebas por capa e integración
scripts/         mediciones reproducibles
docs/arkis/      análisis, decisiones, arquitectura, manual, resultados
```

La versión anterior del proyecto (neuroevolución) se conserva en la etiqueta git `v2-neuroevolucion`.

<div align="center">

**Licencia:** BY-NC — atribución, no comercial ([`LICENCE`](LICENCE))

</div>
