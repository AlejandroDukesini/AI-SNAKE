# 📋 CHANGELOG

Registro de cambios notables del proyecto. Las decisiones de arquitectura relevantes se anotan
como **ADR** (Architecture Decision Record) para dejar constancia del *por qué*, no solo del *qué*.

---

## ADR-002 — Motor `advanced`: de red profunda a una sola capa oculta (26 → 16 → 3)

**Estado:** aceptado · **Ámbito:** `snake_neuroevolution.py` (`AdvancedNetwork`), UI de motores.

### Contexto

El motor `advanced` nació como una red profunda (26 → 32 → 16 → 3) y luego se intentó rescatar con
LeakyReLU + skip residual (26 → 16 → 16 → 3). En pruebas cortas seguía rindiendo por debajo de los
motores de **una sola capa** (`intermated`, `basic`).

La causa es un fenómeno conocido de la **neuroevolución** (optimización de pesos sin gradiente):

- **La profundidad agranda el espacio de búsqueda.** Cada capa extra añade parámetros que el
  algoritmo genético debe ajustar por ensayo y error, no por retropropagación.
- **La mutación compone ruido capa a capa.** Una perturbación en la primera capa altera la entrada
  efectiva de la segunda, así que el efecto de una mutación es más difícil de evaluar y de heredar
  de forma útil. En una red sin gradiente, la profundidad no "reparte crédito" bien.
- **Menos evaluaciones por segundo.** Más pesos → más cómputo por individuo → menos generaciones en
  el mismo tiempo límite. En una prueba de minutos, eso pesa.

> **Nota sobre las cifras.** Este ADR documenta el *razonamiento*, no números concretos: las
> métricas de fitness comparables deben medirse con `benchmarks/bench_core.py` en la misma máquina y
> configuración, no declararse. El proyecto reporta solo cifras reproducibles (ver
> `TECHNICAL_PROOF.md`). La regla de negocio del fitness (`pasos + (tamaño−3)×1000 + shaping`, con
> tamaño acotado por el área del tablero) fija además un techo de decenas de miles: cualquier cifra
> muy por encima de ese orden no es alcanzable en este motor.

### Decisión

Simplificar `advanced` a **una sola capa oculta: 26 → 16 → 3**, con **LeakyReLU** y decisión por
**argmax de 3 salidas** (recto / izquierda / derecha), consistente con `intermated`.

- Se elimina por completo la segunda capa oculta (matrices `W3`/`b3` y el skip residual).
- **~483 pesos** (antes ~1.443 en la versión profunda original).
- LeakyReLU se conserva: evita neuronas muertas, que una red evolucionada no revive con facilidad.

### Consecuencias

- **A favor:** espacio de búsqueda mucho menor → el genético converge con menos evaluaciones; más
  evaluaciones/segundo; sin la barrera de propagación de la profundidad.
- **En contra / límite:** menos capacidad de abstracción jerárquica que una red profunda. Es un
  compromiso deliberado: para este entorno (26 sensores ya ricos, incluido el flood-fill) una capa
  basta, y la evolvabilidad importa más que la profundidad.
- **Compatibilidad:** `Brain.from_dict` es tolerante a cambios de forma — un espécimen `advanced`
  guardado con la topología anterior se reinicia limpio en vez de fallar. `intermated` y `basic` no
  se tocan.
- **Salida = 3, no 1.** La decisión es entre tres acciones por argmax; solo `basic` usa 1 salida por
  rangos. La arquitectura compacta no cambia esa semántica.

**Archivos:** `snake_neuroevolution.py`, `ENGINES.md`, `README.md`, y la vista **Documentación → El
Cerebro** (previsualización interactiva del motor), que refleja la nueva topología dinámicamente.

---

## ADR-001 — Motores de red modulares y seleccionables

**Estado:** aceptado · **Ámbito:** núcleo, servidor, frontend.

Se introdujo una arquitectura modular de motores (`Brain` + `IntermatedNetwork`, `AdvancedNetwork`,
`BasicNetwork`) seleccionable por entrenamiento, con el algoritmo genético agnóstico de la topología
(opera sobre `get_weights()`). Detalle completo en **[`ENGINES.md`](ENGINES.md)**.
