# 🗺️ ROADMAP — Evolución de la inteligencia

> Hoja de ruta y visión de *hasta dónde* puede crecer la IA de este proyecto y qué cambios técnicos
> lo hacen posible. Diseño y evidencia en [`ARCHITECTURE.md`](ARCHITECTURE.md) · motores en
> [`ENGINES.md`](ENGINES.md) · decisiones en [`../CHANGELOG.md`](../CHANGELOG.md).

**Qué es y qué NO es este documento**
- Es una **proyección de ingeniería**: dirección de crecimiento y los cambios que la habilitan.
- **No** son resultados medidos, salvo las secciones marcadas como *MEDIDO* (cronometradas con
  `benchmarks/bench_core.py` o `train()` cronometrado).
- Cada **nivel** es una capacidad objetivo con un criterio verificable, para poder afirmar con
  evidencia "el agente alcanzó el Nivel N".

## Arquitectura actual (referencia)

El cerebro es **modular**: tres motores seleccionables por entrenamiento sobre los mismos 26
sensores y el mismo algoritmo genético (ver [`ENGINES.md`](ENGINES.md) y `snake_neuroevolution.py`):

| Motor | Topología | Notas |
| --- | --- | --- |
| `intermated` (por defecto) | 26 → 20 → 3 recurrente (`W_rec`) | ADN compacto, memoria intra-partida |
| `advanced` | 26 → 16 → 3 feedforward (LeakyReLU) | 1 capa compacta (~483 pesos) |
| `basic` | 26 → 52 → 26 → 1 feedforward | salida por rangos, ancho y expresivo |

- **Entradas (26):** 8 rayos egocéntricos × 3 rasgos (pared / cuerpo / alineación con la comida) = 24,
  + tamaño propio + espacio libre alcanzable (flood-fill).
- **Algoritmo genético (común):** elitismo, selección por torneo (k=3), cruce uniforme, mutación
  gaussiana con decaimiento adaptativo de σ por estancamiento. Población configurable (4–100).
- **Evaluación:** 3 partidas con semillas comunes por individuo (selección), 10 semillas fijas para
  validar al campeón y 20 semillas fijas de prueba para el rendimiento guardado (`eval`).
- **Fitness:** `pasos + (tamaño−3)×1000 + shaping_de_acercamiento` (comer domina; premia +0,5/paso
  los bucles sin comer, limitación conocida).
- **Compatibilidad:** `advanced_v1` (26 → 32 → 16 → 3) solo para cargar especímenes antiguos.

> El `advanced` se simplificó de una red profunda a una sola capa por evolvabilidad (ver
> [`../CHANGELOG.md`](../CHANGELOG.md), ADR-002).

---

## Métrica de visión (la regla que mide "qué tan lista es")

**Métrica principal:** `cobertura = longitud_final / (grid × grid)` — la fracción del tablero que el
agente llega a ocupar (0.0–1.0). Un Snake perfecto tiende a 1.0. Es **independiente del tamaño de
tablero**, así que compara de forma justa 8×8, 10×10 y 15×15.

**Métricas de apoyo:** frutas/partida (media y máximo) · tasa de muerte por inanición vs. colisión
propia · eficiencia = frutas/pasos · generaciones hasta el primer fruto consistente.

---

## Línea base MEDIDA (números reales)

> Las cifras de esta sección son de **cómputo** y se midieron con el protocolo anterior (1 partida
> por individuo). Con el protocolo actual cada generación juega ~3× partidas (medido en la
> auditoría: 2,6–3,6× pasos simulados por generación).

*Fecha: 2026-07-17 · máquina del desarrollador · grid 8×8, pop 25 · `benchmarks/bench_core.py`
(5 repeticiones).*

**Motor recurrente 26 → 20 → 3** (8 rayos + espacio libre + memoria):

- Generaciones / s: **~2,6** · Individuos / s: **~66** · Pasos simulados / s: **~4.000**
- Tiempo medio por generación: **~380 ms** (p95 ~650 ms · p99 ~775 ms)

**Referencia — motor simple anterior** 10 → 12 → 3 (3 rayos, sin flood-fill): ~36.500 pasos/s
(**~9× más rápido**).

El motor actual es ~9× más lento **por diseño**: cada paso ejecuta la red más un *flood-fill* del
espacio alcanzable — el precio de la percepción más rica y la memoria. Sigue siendo de sobra
interactivo. El cuello de botella deja de ser el algoritmo y pasa a ser el **cómputo por paso** en
Python puro.

> **Tensión real que conviene documentar, no esconder:** el *flood-fill* del sensor de espacio
> libre es justo lo más difícil de vectorizar. Por eso "recuperar el 9× con vectorización" **no**
> es un cambio de una línea: es rediseñar el simulador para que N agentes avancen en paralelo con
> operaciones matriciales (ver **Paso 3**).

**Ya implementado:** fitness shaping denso · decaimiento adaptativo de σ · visión de 8 rayos +
espacio libre · memoria recurrente `W_rec` · cobertura y nivel persistidos · **protocolo de
evaluación con semillas fijas** (selección / validación / prueba) · semilla de entrenamiento por
sesión · carga explícita de modelos (`ModelError`).

> **Honestidad sobre los niveles:** tener un *mecanismo* (sensores, memoria) no equivale a alcanzar
> una cobertura. Ninguno de esos mecanismos ha demostrado por sí solo subir de nivel.

## Estado MEDIDO (auditoría, 2026-10-10)

Detalle, intervalos y semillas en [`auditoria-cientifica-ia.md`](auditoria-cientifica-ia.md), §16.

- **Por encima del azar, por debajo de la regla voraz.** En 8×8, tras 40 generaciones, los tres
  motores logran ~6–9 frutas por partida de media; la regla voraz sin aprendizaje, 15,7; el azar, 0,2. En
  15×15 (intermated, 40–120 gen.): ~9–13 frente a 23,7.
- **Nivel típico de todos los especímenes medidos: N0.** N1 y N2 solo en partidas sueltas.
- **El protocolo nuevo no acelera el aprendizaje a igual cómputo**: frente al algoritmo anterior con
  3× generaciones, las diferencias no son significativas. Sí da resultados más consistentes entre
  entrenamientos y medidas fiables.
- **Probado sin mejora:** fitness basado en potencial, quitar el cruce, torneo de 5, 5 partidas por
  individuo.

---

## Niveles por cobertura (objetivos)

> Las descripciones de la segunda columna son **objetivos de comportamiento**, no capacidades
> observadas. La métrica solo mide cobertura; esos comportamientos no tienen todavía una métrica
> propia que los demuestre.

| Nivel | Capacidad | Criterio (cobertura) | Cómo se desbloquea |
| --- | --- | --- | --- |
| **N0** | Evita la pared un rato; come por accidente. | < 0.10 | Punto de partida (pesos aleatorios). |
| **N1** | Se orienta hacia la comida; come sin azar. | 0.10–0.20 | Ya soportado: más generaciones/población + shaping denso. |
| **N2** | Come consistente; deja de encerrarse en cuerpos cortos. | 0.20–0.35 | Por medir: currículum 8×8→10×10, poblaciones mayores (torneo mayor ya probado sin mejora). |
| **N3** | Con cuerpo largo evita encerrarse; empieza a "rodear" la comida. | 0.35–0.55 | Sensores ya ampliados (8 rayos + espacio libre); no observado todavía. |
| **N4** | Recorre el tablero eficiente sin encerrarse ("camino seguro"). | 0.55–0.80 | Memoria recurrente (hecho) · NEAT topológico (I+D) · fitness multiobjetivo. |
| **N5** | Llena casi todo; ~ciclo hamiltoniano aprendido. | > 0.80 | Visión global por CNN · especiación/nichos · evaluación vectorizada. |

---

## Ejes de mejora transversales

1. **Sensorial:** 3 rayos → 8 rayos → rejilla local → tablero completo (CNN)
2. **Modelo:** feedforward → recurrente → topología evolutiva (NEAT)
3. **Evolución:** mutación fija → adaptativa → especiación / nichos / multiobjetivo
4. **Fitness:** escaso (solo comer) → shaping denso → multiobjetivo
5. **Cómputo:** 1 agente por vez → lotes vectorizados NumPy → multiproceso
6. **Currículum:** tablero fijo → pequeño→grande → aleatorización de tablero

---

## Orden recomendado de trabajo (mayor retorno primero)

- ✅ **Paso 1 — Cobertura** como métrica de primera clase (persistida en `storage.py`). Sin métrica no hay progreso demostrable.
- ✅ **Paso 2 — Fitness shaping denso + mutación adaptativa** (implementado; su efecto aislado no está medido).
- ✅ **Paso 4 — Ampliar sensores** (8 rayos + espacio libre) (implementado; N3 no observado).
- ✅ **Paso 5a — Memoria recurrente** (`W_rec`) (implementado; uso para planificar no medido).
- ✅ **Paso 1b — Protocolo de evaluación con semillas fijas** (selección / validación / prueba). Hace fiables las cifras; a igual cómputo no acelera el aprendizaje.
- ⏳ **Paso 3 — Evaluación vectorizada por lotes** (rediseño del simulador en NumPy) → poblaciones grandes sin coste y recupera el ~9× de la percepción rica. **Pendiente de mayor retorno hoy**, más aún porque el protocolo fiable cuesta ~3× por generación.
- ⏳ **Paso 3b — Diversidad** (nichos / especiación): la diversidad genética cae a ~30 % en 40 generaciones.
- ⏳ **Paso 5b — Neuroevolución topológica** (NEAT) → afina N4.
- ⏳ **Paso 6 — Visión CNN** del tablero completo → N5 (I+D; alcanzar >80% es un resultado de entrenamiento, no de código).

---

## Análisis de tiempo por nivel, motor y tablero

**Lo que este análisis SÍ y NO afirma:**
- **No** dice "el motor X tarda Z minutos en llegar a N4". El nivel **típico** de todos los
  especímenes medidos es N0; N1 y N2 solo aparecen en partidas sueltas (el récord N2 es de
  `basic-tablerop` en 8×8). Cualquier tiempo-a-N2..N5 sería *declarado*, no medido. No se inventa.
- **Sí** da las piezas reales para estimarlo uno mismo tras entrenar, separando lo determinista
  (mate), lo medido (coste/generación) y lo empírico (a medir).

Descomposición:

```
tiempo_hasta_Nk  =  generaciones_hasta_Nk  ×  coste_por_generacion
```
- `coste_por_generacion` → **MEDIBLE** (bloque B); depende de motor y tablero.
- `generaciones_hasta_Nk` → **EMPÍRICO** (bloque C); depende de evolvabilidad y suerte. Se obtiene entrenando.

### A) Determinista — longitud que exige cada nivel en cada tablero

`cobertura = longitud / (grid²)`. La serpiente nace con longitud 3. Umbral mínimo para estar EN el
nivel: `N1≥0.10  N2≥0.20  N3≥0.35  N4≥0.55  N5≥0.80`.

Longitud mínima requerida (entre paréntesis: frutas a comer = longitud − 3):

| Tablero | N1 | N2 | N3 | N4 | N5 |
| --- | --- | --- | --- | --- | --- |
| **8×8** | 7 (4) | 13 (10) | 23 (20) | 36 (33) | 52 (49) |
| **10×10** | 10 (7) | 20 (17) | 35 (32) | 55 (52) | 80 (77) |
| **15×15** | 23 (20) | 45 (42) | 79 (76) | 124 (121) | 180 (177) |

**Lectura clave:** el mismo nivel es mucho más fácil en un tablero pequeño. N2 son 10 frutas en 8×8
pero 42 en 15×15. Por eso los tests en 15×15 se estancan en N0/N1: el tablero grande dispara el
listón de longitud. Para **subir de nivel rápido conviene entrenar en 8×8** (los sensores están
normalizados: lo aprendido transfiere a tableros mayores).

### B) MEDIDO — coste por generación (ms), población 25

*Máquina del desarrollador; media de 4 generaciones iniciales; `train()` cronometrado.*

| Motor | 8×8 | 10×10 | 15×15 |
| --- | --- | --- | --- |
| `intermated` | 102 ms | 121 ms | 264 ms |
| `advanced` | 97 ms | 98 ms | 258 ms |
| `basic` | 60 ms | 92 ms | 153 ms |

- El coste lo domina la **percepción** (flood-fill, ~área del tablero), no el forward: por eso los
  tres motores cuestan parecido y el **tablero pesa más que el motor**. 15×15 cuesta ~2,5× más que 8×8.
- **Caveat:** son generaciones **iniciales** (serpientes que mueren pronto). Cuando la población
  mejora y sobrevive más pasos, el coste por generación **sube**. Úsalos como *suelo*, no como techo.

**Generaciones por 10 min** (derivado, orden de magnitud, población joven):

| 8×8 | 10×10 | 15×15 |
| --- | --- | --- |
| ~6.000 – 10.000 | ~5.000 – 6.500 | ~2.300 – 3.900 |

Es exactamente lo que limita cuánto se puede evolucionar en tiempo dado: más tablero → menos
generaciones → nivel más bajo. Y es la razón de que el **Paso 3** (evaluación vectorizada) sea el
pendiente de mayor retorno: multiplicar gen/min sube el techo de nivel alcanzable sin cambiar la red.

### C) EMPÍRICO — generaciones hasta cada nivel (lo que falta medir)

Observado hasta hoy (único dato real):
- **N0:** inmediato (generación 1). Longitud 3 ya es <10% en cualquier tablero.
- **N1:** récord de una partida de `PRUEBA-UNO` en 15×15 en algún punto de sus 5.608 gen (no se
  registró la generación exacta). Su nivel **típico** sigue siendo N0 (92 % de sus partidas).
- **N2:** solo como récord de una partida (`basic-tablerop`, 8×8; 2 % de sus partidas).
- **N3..N5:** **no observado** en ningún motor ni tablero. Sin dato no hay número.

**Receta para obtenerlo de verdad** (y luego rellenar esto como MEDIDO):
1. Entrenar con semilla y registrar por generación el récord validado (`val_record` en el evento `gen`); al final, el nivel típico de `eval`.
2. Anotar la primera generación en que sube el nivel (N0→N1, N1→N2, …).
3. `tiempo_a_Nk = esa_generacion × (ms/gen del bloque B para ese motor+tablero)`.
4. Repetir varias corridas (la evolución tiene azar) y reportar mediana + rango.

Hasta que existan esos datos, `generaciones_hasta_Nk` queda vacío **a propósito**: preferimos un
hueco honesto a un número inventado.
