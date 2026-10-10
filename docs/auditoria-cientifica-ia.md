# Auditoría científica y técnica de la IA — Snake IA

> **Fecha:** 2026-10-10 · **Rama:** `Beta` (cambios locales sin commitear) · **Entorno:** Windows 11,
> Python 3.13.14, NumPy 2.4.4, 8 núcleos.
> **Scripts reproducibles:** [`benchmarks/audit_ia.py`](../benchmarks/audit_ia.py) (verificaciones
> deterministas PASA/FALLA y bloques estadísticos D/E) y
> [`benchmarks/experimento_ia.py`](../benchmarks/experimento_ia.py) (comparación original/corregido
> con varias semillas). Todas las cifras salen de esos scripts o de lecturas directas del código y
> los datos. Donde algo no se pudo verificar, se dice.
>
> **Estructura:** Parte I (§1–§12) = auditoría inicial, estado **previo** a las correcciones.
> Parte II (§14–§19) = correcciones, experimentos y estado **vigente**. Referencias al final.

---

## 1. Resumen ejecutivo (estado vigente)

**Qué es la IA:** neuroevolución (algoritmo genético sobre los pesos de redes de topología fija) con
tres redes NumPy (`intermated`, `advanced`, `basic`) más `advanced_v1`, solo para cargar
especímenes antiguos. No hay descenso de gradiente, dataset, modelos de terceros ni API externa. El
**modo borrador** de Netlify es una heurística programada a mano, rotulada como tal en la interfaz.

| Aspecto | Estado tras la fase 2 |
| --- | --- |
| Matemática de redes, operadores genéticos, init He, niveles | **Correcto y verificado** (`audit_ia.py` A) |
| Sensores (26) e invarianza a rotación | **Correcto y verificado** (B). No son invariantes a escala |
| Modelos antiguos de 9/10 entradas | **Corregido y verificado**: misma decisión que la red original (C) |
| Especímenes `advanced` 26→32→16→3 | **Corregido y verificado**: cargan como `advanced_v1` con sus pesos exactos y el `forward` original (H) |
| Modelos incompatibles o corruptos | **Corregido y verificado**: `ModelError` explícito; nunca se sustituyen por una red aleatoria (H, prueba de servidor) |
| Récord de un episodio usado como rendimiento | **Corregido y verificado**: rendimiento en 20 semillas de prueba fijas (media, mediana, sd, IC 95 %, nivel típico), separado del récord (G) |
| Élite reevaluada que "empeoraba" | **Corregido y verificado**: semillas comunes por generación, élite conservada con su historial, récord validado sin retrocesos (G, §16) |
| Parada a mitad de generación, récord inicial −1 | **Corregido y verificado** (G) |
| NaN/inf numéricos | **Corregido y verificado** sin alterar decisiones normales (F) |
| Reproducibilidad | **Corregido y verificado**: `train(seed=…)`, semilla guardada por sesión (G) |
| Documentación | **Corregida**: retiradas las afirmaciones sin respaldo y las etiquetas cognitivas |
| **Aprender mejor** | **No demostrado.** A igual cómputo, el protocolo nuevo no aprende mejor que el original en ningún motor ni tablero (§16.4). Resultados más consistentes entre entrenamientos |
| **Frente a la regla voraz** | **No resuelto.** Todo queda por debajo (mejor media 10,2 vs 15,7 en 8×8; 13,3 vs 23,7 en 15×15). Muy por encima del azar |
| Fitness que premia bucles (+0,5/paso) | **Limitación documentada**: la alternativa basada en potencial se probó y no rindió mejor |

`python benchmarks/audit_ia.py` → **70 PASA, 0 FALLA**.

---

# Parte I — Auditoría inicial (estado previo a las correcciones)

### 1.1 Resumen ejecutivo original

| Aspecto | Veredicto (antes de la fase 2) |
| --- | --- |
| Formulación matemática de redes, mutación, cruce, torneo, elitismo, init He | **Correcto y verificado** (comparado con implementación independiente y con valores teóricos) |
| Sensores (26 entradas) e invarianza a rotación | **Correcto y verificado** (3.000 estados, error máx. 2,2·10⁻¹⁶) |
| Carga "sin regresión" de modelos antiguos de 9/10 entradas | **Problema confirmado** → corregido en la fase 1 (de 0,02 a 8,96 frutas de media; 100 % de decisiones idénticas) |
| Carga de especímenes `advanced` guardados con la arquitectura anterior | **Problema confirmado** (se sustituían en silencio por una red aleatoria) |
| "Récord" de fitness/frutas como medida de calidad | **Problema confirmado** de sesgo optimista (máximo de episodios ruidosos; ver §8) |
| "Invarianza a escala / lo aprendido en 8×8 vale en 15×15" | **Parcialmente verificado** (ver §8, transferencia) |
| Niveles N0–N5 | Cálculo **correcto y verificado**; su interpretación cognitiva era **no verificable** |
| Afirmaciones de rendimiento en docs ("sube de N0 a N2–N3 (medido)") | **Problema confirmado** de documentación |
| Reproducibilidad | El núcleo era determinista con semilla, pero la app no fijaba ni registraba semillas |
| Calidad real de las políticas aprendidas | **Resultado negativo confirmado:** por debajo de una heurística voraz trivial; por encima del azar |
| Fuga de datos / train-test | No había evaluación independiente del cerebro devuelto |

> Las cifras de la Parte I se obtuvieron con el núcleo anterior (equivalente a `git show
> HEAD:snake_neuroevolution.py`) y la versión anterior de `audit_ia.py`. El bloque D (especímenes
> guardados, mismo entorno y semillas) se reproduce con `python benchmarks/audit_ia.py --solo D`:
> cifras idénticas en los 5 especímenes no `advanced`; los dos `advanced` cambian porque ahora cargan
> sus pesos reales (ver §17).
> El bloque E **no** se reproduce con el núcleo actual porque `train` cambió; su sucesor es
> `benchmarks/experimento_ia.py`, que carga el algoritmo original desde git para compararlo.

## 2. Alcance

**Inspeccionado línea a línea:**

| Archivo | Componentes |
| --- | --- |
| `snake_neuroevolution.py` | `Brain`, `IntermatedNetwork`, `AdvancedNetwork`, `BasicNetwork`, `_leaky_relu`, `brain_from_dict`, `crossover`, `mutate`, `Snake` (sensores, `advance`, `fitness`), `tournament_select`, `next_generation`, `seed_population`, `train`, `cobertura`, `nivel_de_cobertura`, `clamp_*` |
| `ai_server.py` | `/ws/train`, `/ws/demo/{carpeta}`, `/ws/play`, REST de config/modelos |
| `storage.py` | `save_training`, `model_summary`, `list_models`, persistencia del récord y del nivel |
| `migrar_historial.py` | migración de `mejores_ias.json` (modelos de 9 entradas) |
| `benchmarks/bench_core.py` | método de medición de rendimiento |
| `src/lib/demo/snake.js`, `src/lib/demo/server.js`, `src/App.jsx` | modo borrador (simulación en navegador) y su aviso |
| `docs/ENGINES.md`, `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`, `docs/CHANGELOG.md`, `README.md`, `src/views/DocsView.jsx` | afirmaciones científicas y de rendimiento |
| Historial git (`f99d379`, `bf1b2e3`, `3715ec2`) | disposición antigua de las entradas (para verificar la carga adaptativa) |

**Datos inspeccionados:** `historial/*/modelo.json` y `sesiones.json` (7 especímenes locales; la
carpeta está en `.gitignore`, no forma parte del repositorio) y `mejores_ias.json` (18 modelos
antiguos de 9 entradas).

**No inspeccionado en profundidad:** el resto del frontend React (renderizado, cola de
entrenamiento, cookies/analítica), porque no realiza cálculos de IA: solo dibuja estados enviados
por el servidor.

---

## 3. Arquitectura de la IA (extremo a extremo)

```
Cliente React ──WS /ws/train {nombre, engine, agents, elite, generations, grid}──► ai_server.ws_train
                                                                                    │ hilo
                                         storage.load_model(carpeta) ── existe? ──► seed_brain (brain_from_dict)
                                                                                    ▼
                         ml.train ─► seed_population ─► por generación:
                                       para cada agente: Snake.step_ai() hasta morir
                                          get_inputs() (26 sensores) → brain.forward → giro relativo
                                          advance() → fitness = pasos + 1000·(long−3) + shaping
                                       next_generation: élite intacta + torneo(k=3) → cruce uniforme → mutación gaussiana
                                       recocido: si el mejor no mejora en 4 gen → σ ← max(0,05; 0,85·σ)
                                     devuelve el cerebro con MAYOR fitness instantáneo visto en cualquier paso
                                                                                    ▼
                         storage.save_training: acumula generaciones; sustituye pesos solo si fitness > récord;
                                                record_cobertura = max(histórico, actual) → nivel N0–N5
```

El modo borrador sustituye todo lo anterior por `src/lib/demo/server.js`: una heurística
"voraz + flood-fill" con probabilidad de error `0,55·e^(−gen/6)` y una curva de `mutation_std`
fabricada (`0,3·e^(−gen/40)`) que **no corresponde** al algoritmo real (σ₀ = 0,20 con decaimiento
escalonado). Está etiquetado como borrador en la UI (`src/App.jsx:103-114`).

---

## 4. Inventario de métodos

| # | Técnica | Objetivo | Entradas | Salidas | Ubicación |
| --- | --- | --- | --- | --- | --- |
| M1 | Red recurrente Elman-like, ReLU, salida lineal + argmax | Política `intermated` | 26 sensores + estado `h` | acción ∈ {recto, izq, der} | `snake_neuroevolution.py` `IntermatedNetwork.forward` |
| M2 | MLP 1 capa oculta, LeakyReLU(α=0,01), argmax | Política `advanced` | 26 | acción | `AdvancedNetwork.forward` |
| M3 | MLP 2 capas ReLU, 1 salida sigmoide discretizada en tercios | Política `basic` | 26 | acción | `BasicNetwork.forward` |
| M4 | Inicialización He N(0, 2/fan_in) | Escala inicial de pesos | — | pesos | `_random_weights` |
| M5 | Selección por torneo k=3 | Presión selectiva | población + fitness | padre | `tournament_select` |
| M6 | Elitismo (1…pop−1, por defecto 3) | Conservar los mejores | población | élite clonada | `next_generation`, `clamp_elite` |
| M7 | Cruce uniforme gen a gen (p=0,5) | Recombinación | 2 padres | hijo | `crossover` |
| M8 | Mutación gaussiana por gen (p=0,05, σ=0,20) | Exploración | red | red mutada | `mutate` |
| M9 | Decaimiento de σ por estancamiento (paciencia 4, ×0,85, suelo 0,05) | Pasar de explorar a afinar | mejor fitness por generación | σ | `train` |
| M10 | Fitness con *shaping* asimétrico (+3 acercarse / −4 alejarse, Manhattan) | Señal densa | trayectoria | escalar | `Snake.advance`, `Snake.fitness` |
| M11 | Sensores: rayos (pared, cuerpo), coseno a la comida, flood-fill | Percepción | estado del tablero | vector ∈ ℝ²⁶ | `Snake.get_inputs` y auxiliares |
| M12 | Cobertura = longitud/área y umbrales N0–N5 | Clasificación de "nivel" | longitud, grid | nivel | `cobertura`, `nivel_de_cobertura` |
| M13 | Récord monótono (máximo histórico) | Persistencia del mejor | resultados de `train` | pesos, nivel | `storage.save_training` |
| M14 | Adaptación de pesos antiguos | Compatibilidad | pesos 9/10/12/26 | red 26→20→3 | `IntermatedNetwork._adapt_weights` |
| M15 | Heurística con error simulado | Borrador sin servidor | estado | acción | `src/lib/demo/snake.js` `stepAI` |

**Clasificación:** M1–M10 son IA/optimización evolutiva real e implementada. M11 es ingeniería de
características determinista. M12–M13 son estadísticas descriptivas (máximos). M15 es una
heurística determinista con ruido, **no** aprendizaje, y está divulgada como simulación.

---

## 5. Fundamento científico

- **Neuroevolución con topología fija.** Evolucionar directamente los pesos de una red con un GA es
  un método establecido; Such et al. (2017) muestran que un GA simple es competitivo en RL incluso
  con millones de parámetros. Base teórica general del GA: Holland (1975); manual de referencia:
  Eiben & Smith (2015). **Corresponde** con lo implementado.
- **Torneo y ruido.** Miller & Goldberg (1995) modelan la presión selectiva del torneo y su
  degradación con fitness ruidoso. Aquí el fitness **es** ruidoso (posición aleatoria de la manzana,
  un solo episodio por individuo), situación estudiada en Jin & Branke (2005): con evaluación única
  el elitismo no garantiza "no retroceder" en rendimiento esperado, y seleccionar el máximo de
  evaluaciones ruidosas sobreestima la calidad. Esto contradice la frase de `docs/ENGINES.md` «el
  elitismo conserva lo mejor (nunca se retrocede)» (ver §8, bloque E).
- **Cruce uniforme en redes.** Es válido, pero mezclar neuronas ocultas de padres no emparentados
  sufre el problema de las "convenciones en competencia" (permutación de unidades ocultas)
  descrito por Stanley & Miikkulainen (2002, §2 de NEAT). El efecto se mitiga en linajes que parten
  de un mismo antecesor. **Limitación conocida, no defecto.**
- **Inicialización He.** `randn·√(2/fan_in)` es exactamente la propuesta de He et al. (2015) para
  ReLU. En un GA su función es solo fijar la escala inicial de búsqueda; no hay gradientes que
  estabilizar. **Correcto.** LeakyReLU: Maas, Hannun & Ng (2013).
- **"Recocido".** El decaimiento de σ por estancamiento **no** es recocido simulado (Kirkpatrick et
  al., 1983: aceptación probabilística de soluciones peores con una temperatura). Es un control
  adaptativo escalonado del paso de mutación (familia de métodos de autoadaptación descritos en
  Eiben & Smith, cap. 8). El nombre es impreciso; el mecanismo es razonable.
- **Shaping.** Ng, Harada & Russell (1999) demuestran que solo el *shaping* basado en potencial
  F = γΦ(s′) − Φ(s) garantiza no alterar la política óptima. El *shaping* implementado (+3/−4
  asimétrico) **no es basado en potencial**: penaliza rodeos que pueden ser necesarios para no
  encerrarse con un cuerpo largo. Su peso es pequeño frente a 1.000 por fruta (≤ ~3·(2·grid) por
  fruta), por lo que el sesgo práctico es probablemente bajo, pero **cambia el objetivo** que se
  optimiza. Es una elección de diseño defendible, no un error, pero la documentación no debe
  presentarla como neutra.
- **Aproximación universal.** Cybenko (1989) y Hornik (1991) garantizan existencia de una red que
  aproxima funciones continuas, **no** que el GA la encuentre ni con 16–20 neuronas. La frase de
  `ENGINES.md` «es representable» es correcta solo en ese sentido de existencia.
- **Recurrencia y estabilidad.** Con ReLU sin acotar y `W_rec` de radio espectral > 1, el estado
  oculto puede crecer sin límite (análisis dinámico de Pascanu, Mikolov & Bengio, 2013, aunque allí
  centrado en gradientes). Ver §8, bloque F.
- **Metodología de evaluación.** Agarwal et al. (2021) recomiendan informar intervalos de confianza
  sobre varias corridas en lugar de estimaciones puntuales; Efron (1979) para el bootstrap usado en
  este informe.

---

## 6. Verificación matemática (bloques A, B, G de `audit_ia.py`)

Comando: `python benchmarks/audit_ia.py --solo A B G`

| Comprobación | Resultado | Estado |
| --- | --- | --- |
| Nº de parámetros: intermated 1003, advanced 483, basic 2809 | Coinciden con el cálculo manual y con `ENGINES.md` | Correcto y verificado |
| Init He: σ empírica de W1 (10.400 pesos) | 0,2769 vs teórica √(2/26)=0,2774 | Correcto y verificado |
| Mutación: fracción de genes mutados / σ del ruido | 0,0499 / 0,1984 (esperado 0,05 / 0,20) | Correcto y verificado |
| Cruce uniforme | 50,7 % de A, 0 genes ajenos a ambos padres | Correcto y verificado |
| Umbrales de nivel: longitud mínima N1..N5 | 8×8 [7,13,23,36,52] · 10×10 [10,20,35,55,80] · 15×15 [23,45,79,124,180] = tabla de `ROADMAP.md` (incluido el caso frontera exacto 0,35·100) | Correcto y verificado |
| Sensores frente a reimplementación independiente (geometría con vectores rotados + BFS con `deque`) | 3.000 estados en 8/10/15; error máx. 2,2·10⁻¹⁶ | Correcto y verificado |
| Invarianza a rotación 90° del tablero | Diferencia máx. 0 | Correcto y verificado |
| Reglas: entrar en la casilla de la cola es legal salvo al comer; giros relativos (180° imposible para la IA) | Código coherente; idéntico en la copia JS | Correcto y verificado (inspección) |
| Fitness monótono dentro de una partida | **No**: en una partida aleatoria baja en 9 de 20 pasos (pico 11, final 6). `train` guarda el cerebro en su **pico**, mientras que la selección usa el fitness **final** | Problema confirmado (menor) |
| Fitness puede ser < −1 | Sí (−9 en el caso construido); `best_fitness` arranca en −1 y `mejor_historico` también | Problema confirmado (impacto bajo: solo si toda una generación queda < −1) |
| Parada a mitad de generación | `generaciones` devuelve 1 aunque se completaron 0; contradice el docstring de `train` («las REALMENTE completadas») | Problema confirmado (contador, impacto bajo) |
| Unidades/escalas | Distancias /grid ∈ [0,1); cuerpo ∈ [0,1]; coseno ∈ [−1,1]; tamaño y espacio libre ∈ [0,1] | Coherente |
| Valores nulos/entradas inválidas | `food=None` (tablero lleno) manejado en sensores y distancia; parámetros de usuario saneados por `clamp_*`; JSON corrupto → valor por defecto | Correcto (inspección) |

---

## 7. Calidad de datos

No hay dataset de entrenamiento: los "datos" son episodios simulados generados en línea, de modo
que no existen problemas de etiquetado, desbalance de clases ni fuga train/test en el sentido
clásico. Los datos relevantes son los **especímenes y sesiones guardados**:

- **Tamaño de muestra.** 7 especímenes locales; 6 de ellos con **una sola sesión**. Cada cifra de
  "récord" (frutas, longitud, nivel) procede de **un único episodio** —el mejor de todos los
  evaluados—, no de una media. Es insuficiente para estimar rendimiento esperado.
- **Sesgo de selección / "maldición del ganador".** Al guardar el máximo de miles de episodios
  ruidosos, el récord sobreestima sistemáticamente el rendimiento típico (cuantificado en §8).
- **Comparabilidad entre tableros.** `save_training` compara `fitness` brutos entre sesiones con
  `grid` distinto; el fitness no está normalizado por tablero (la cobertura sí).
- **Comparabilidad entre versiones.** Los modelos migrados conservan el fitness calculado con la
  fórmula antigua (sin *shaping*, otra versión de reglas); se comparan como si fuesen la misma
  magnitud.
- **Inconsistencia arquitectura/datos.** Los especímenes `PRUEBA-ADVA10MIN` y
  `Advanced-prueba-error-nousar` tienen pesos 26→32→16→3 (versión de `advanced` anterior al
  ADR-002). La arquitectura actual es 26→16→3 y `Brain.from_dict` devuelve **una red aleatoria nueva**
  sin avisar (ver H2).
- **Contradicción documental.** `docs/ROADMAP.md` afirma «ningún espécimen ha superado N1»; el dato
  local `basic-tablerop` (8×8) tiene cobertura récord 0,219 → N2. `docs/ENGINES.md` afirma «un
  entrenamiento corto sube de N0 a N2–N3 (medido)»: N3 no aparece en ningún dato disponible.
- **Privacidad.** Los datos guardados contienen solo pesos, métricas, fechas y nombres elegidos por
  el usuario. No se encontraron datos personales ni secretos en los artefactos de IA.

---

## 8. Validación experimental

Todo con semillas fijas. Comandos:

```bash
python benchmarks/audit_ia.py --solo A B C F G
python -W ignore benchmarks/audit_ia.py --solo D E --episodios 100 --semillas 5 --gens 30
```

Las cifras D y E son **experimentos con simulaciones sintéticas controladas** del propio juego:
miden el comportamiento del agente en este simulador, no "rendimiento en producción" (no existe
otro entorno real).

### Bloque C — carga de modelos antiguos (9 entradas)

Metodología: 5 modelos de `mejores_ias.json`. Se compara la red original con sus 9 sensores
originales (reconstruidos de `f99d379`) contra la red tras `IntermatedNetwork.from_dict` con los 26
sensores actuales: (a) % de estados en que ambas eligen la misma acción (4.000 estados) y (b) frutas
medias en 50 episodios con las mismas semillas, 8×8.

| Modelo | Récord | Frutas medias red original | **Antes** de la corrección | Decisión igual (antes) | **Después** | Decisión igual (después) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Cobra-IA-V14 | 23 | 8,96 | 0,02 | 19,1 % | 8,96 | 100 % |
| Cobra-Core-V51 | 22 | 9,44 | 0,02 | 40,5 % | 9,44 | 100 % |
| Titan-Brain-V28 | 22 | 7,88 | 0,02 | 43,9 % | 7,88 | 100 % |
| Hydra-Brain-V66 | 20 | 6,56 | 0,00 | 62,0 % | 6,56 | 100 % |
| Turbo-Neura-V60 | 20 | 9,54 | 0,02 | 64,1 % | 9,54 | 100 % |

Conclusión: la afirmación «adapta redes viejas sin regresión» era **falsa** (las columnas se
copiaban en la esquina pero el orden de los sensores había cambiado); tras la corrección es
**verdadera** para las redes de 9 entradas. Nótese también que el récord (20–23 frutas) es 2,3–3×
la media real (6,6–9,5): el mismo sesgo de selección que se observa en D/E.

### Bloque D — especímenes guardados frente a baselines

Metodología: cada espécimen de `historial/` se carga con `brain_from_dict` y juega **100 episodios
independientes** (semillas 10000–10099, distintas de las de su entrenamiento) en su tablero de
entrenamiento. IC 95 % de la media por bootstrap (2.000 remuestreos). Dos baselines con las mismas
semillas:

- **Azar:** acción uniforme en {recto, izq, der}.
- **Voraz:** sin aprendizaje; de los giros no mortales en el siguiente paso, el que más reduce la
  distancia Manhattan a la manzana (`pol_voraz` en el script, ~10 líneas, sin flood-fill).

| Política | Tablero | Récord guardado | Frutas: media [IC95] | Mediana | Máx. | Episodios ≥ récord | Causa de muerte dominante |
| --- | --- | ---: | --- | ---: | ---: | ---: | --- |
| Baseline azar | 8×8 | — | 0,18 [0,10–0,27] | 0 | 2 | — | pared 99 % |
| **Baseline voraz** | 8×8 | — | **15,72 [14,69–16,73]** | 15,5 | 31 | — | cuerpo 83 % |
| Baseline azar | 15×15 | — | 0,14 [0,06–0,23] | 0 | 3 | — | pared 99 % |
| **Baseline voraz** | 15×15 | — | **23,73 [21,99–25,33]** | 24 | 54 | — | cuerpo 99 % |
| `PRUEBA-UNO` (intermated, 5.608 gen) | 15×15 | 41 | 10,22 [9,16–11,26] | 10 | 26 | 0 % | cuerpo 80 % |
| `PRUEBA-INTERMATED-10min` | 15×15 | 17 | 4,62 [3,92–5,31] | 4 | 14 | 0 % | pared 52 % / cuerpo 48 % |
| `PRUEBA-INTERMATED-DOS` | 15×15 | 15 | 3,16 [2,69–3,66] | 2,5 | 13 | 0 % | **inanición 90 %** |
| `PRUEBA-BASIC-10min` | 15×15 | 13 | 1,91 [1,46–2,43] | 1 | 10 | 0 % | inanición 62 % |
| `basic-tablerop` | 8×8 | 11 | 3,61 [3,25–4,00] | 3 | 11 | 1 % | cuerpo 70 % |
| `PRUEBA-ADVA10MIN` (advanced) | 15×15 | 16 | 0,00 | 0 | 0 | 0 % | pared 100 % ← **red aleatoria (H2)** |
| `Advanced-prueba-error-nousar` | 15×15 | 14 | 0,00 | 0 | 0 | 0 % | pared 100 % ← **red aleatoria (H2)** |

**Niveles** en esos 100 episodios: `PRUEBA-UNO` (nivel guardado N1) queda en N0 en el 92 % de
los episodios; `basic-tablerop` (nivel guardado N2) alcanza N2 en el 2 %, N1 en el 37 % y N0 en el
61 %.

**Transferencia entre tableros** (50 episodios, semillas 20000+):

| Espécimen (entrenado en) | 8×8 frutas / cobertura | 10×10 frutas / cobertura | 15×15 frutas / cobertura |
| --- | --- | --- | --- |
| `PRUEBA-UNO` (15×15) | 5,46 / 0,132 | 7,96 / 0,110 | 10,22 / 0,059* |
| `PRUEBA-INTERMATED-10min` (15×15) | 3,72 / 0,105 | 3,18 / 0,062 | 4,62 / 0,034* |
| `PRUEBA-BASIC-10min` (15×15) | 4,48 / 0,117 | 2,72 / 0,057 | 1,91 / 0,022* |
| `basic-tablerop` (8×8) | 3,61 / 0,103* | 2,78 / 0,058 | 2,02 / 0,022 |

\* cobertura derivada de la media de frutas: (3 + frutas)/área.

**Conclusiones del bloque D (evidencia observada):**

1. **Todas las políticas evolucionadas rinden muy por debajo de la heurística voraz trivial**: la
   mejor (`PRUEBA-UNO`, 5.608 generaciones) obtiene el 43 % de las frutas del voraz en 15×15, con IC
   que no se solapan. Sí superan claramente al azar. El proyecto no incluye ningún baseline, así
   que esto no era visible.
2. **El récord no es representativo**: en 6 de 7 especímenes, ninguno de los 100 episodios iguala
   el récord guardado; el récord es 3–7× la media.
3. **El nivel mostrado sobreestima la capacidad típica** (N1 guardado → N0 en el 92 % de partidas).
4. **Transferencia de tablero: parcialmente verificada.** Las políticas siguen comiendo fuera de su
   tablero (no colapsan al nivel del azar), pero el rendimiento cambia y no de forma constante; la
   afirmación «lo aprendido en 8×8 sigue siendo válido en 15×15» es solo cualitativamente cierta. La
   causa es que los sensores de distancia no son invariantes a escala: estar a 1 casilla de la pared
   vale 0,125 en 8×8 y 0,067 en 15×15 (bloque B); solo los valores "adyacente" (0 y 1) coinciden.
5. Las muertes por **inanición** (90 % en `PRUEBA-INTERMATED-DOS`) indican bucles sin comer: el
   *shaping* penaliza esos bucles, pero no lo suficiente frente a +1 por paso sobrevivido
   (200 pasos de supervivencia ≈ 20 % de una fruta).

### Bloque E — entrenamientos cortos con semilla

Metodología: `train(generations=30, grid=8, pop_size=25)` por motor con semillas 0–4 (15
entrenamientos). Para cada uno se compara el récord de frutas que devuelve `train` con la media real
del cerebro devuelto en 50 episodios nuevos (semillas 50000+). También se cuenta cuántas veces el
mejor fitness de una generación es **menor** que el de la anterior.

**Reproducibilidad:** dos corridas con la misma semilla dan curvas y pesos **idénticos** → el núcleo
es determinista dado el estado de `random` y `numpy.random`.

| Motor | Récord de `train` (frutas) por semilla | Media real (50 ep) por semilla | Media de las 5 | Sesgo récord − media real [IC95] | Gen. en que el mejor empeora | Tiempo (5 corridas) |
| --- | --- | --- | ---: | --- | ---: | ---: |
| intermated | 15, 20, 16, 16, 14 | 6,88 · 5,66 · 5,80 · 7,80 · 6,78 | 6,58 | +9,62 [7,78–12,09] | 64 / 145 (44 %) | 37,5 s |
| advanced | 16, 20, 16, 18, 21 | 5,20 · 7,66 · 6,70 · 8,30 · 10,72 | 7,72 | +10,48 [9,66–11,42] | 59 / 145 (41 %) | 40,7 s |
| basic | 11, 15, 11, 12, 13 | 3,52 · 5,02 · 5,40 · 4,98 · 3,78 | 4,54 | +7,86 [6,54–9,18] | 64 / 145 (44 %) | 39,7 s |
| *referencia: voraz 8×8* | — | — | *15,72* | — | — | — |

**Conclusiones del bloque E:**

1. El récord de `train` sobreestima el rendimiento esperado del cerebro devuelto en **~8–10 frutas**
   (≈ 2–3×), con IC lejos de 0: sesgo de selección confirmado (H3).
2. El mejor de cada generación **empeora en ~42 % de las transiciones** pese al elitismo: la élite
   se re-evalúa con un episodio nuevo, de modo que «el elitismo conserva lo mejor (nunca se
   retrocede)» no se cumple sobre el fitness observado.
3. Con 5 semillas, `basic` parece inferior a los otros dos; `advanced` e `intermated` **no se
   distinguen** (rangos solapados). No se puede afirmar que un motor sea mejor que otro con esta
   muestra.
4. Ninguna corrida corta alcanza la media de la heurística voraz.

### Bloque F — estabilidad numérica

| Caso | Resultado |
| --- | --- |
| `PRUEBA-UNO` (intermated): radio espectral de `W_rec` | **1,512** (> 1) |
| máx. \|h\| en 20 partidas 15×15 | 7,73 (acotado en la práctica: la ReLU recorta) |
| Otros intermated guardados | ρ = 0,045 y 0,000; máx. \|h\| 1,90 y 2,87 |
| Sintético `W_rec = 1,5·I`, entrada fija, 2.000 pasos | **h → NaN** (overflow); `argmax` de NaN devuelve siempre 0 → la serpiente iría siempre recta |
| Sintético `basic` con salida saturada | 177 avisos de overflow en `np.exp`, pero acciones válidas (el resultado de la sigmoide sigue siendo correcto) |

Estado: **parcialmente verificado**. No se observó inestabilidad en los modelos reales, pero no hay
salvaguarda contra ella y la mutación puede seguir aumentando ρ(W_rec).

---

## 9. Hallazgos

Ordenados por severidad.

| ID | Hallazgo | Estado | Evidencia | Impacto | Corrección mínima |
| --- | --- | --- | --- | --- | --- |
| H1 | `IntermatedNetwork._adapt_weights` copiaba los pesos de redes de 9/10 entradas en las primeras columnas, pero el orden de sensores cambió (F,I,D → 8 rayos en sentido horario): la "pared izquierda" caía en la diagonal frente-derecha, etc. | **Problema confirmado → corregido** | Bloque C; `git show f99d379:snake_neuroevolution.py` (`get_inputs`) | Cualquier modelo migrado con `migrar_historial.py` quedaba prácticamente inútil (0,02 frutas) mientras la documentación decía «sin regresión» | Mapa de columnas `_LEGACY_COLS` (aplicado, §10) |
| H2 | `Brain.from_dict` devuelve en silencio una red **aleatoria** si las formas no coinciden. Los 2 especímenes `advanced` guardados (26→32→16→3) se cargan así en `/ws/demo` y al **continuar** su entrenamiento: se muestra/entrena una red aleatoria bajo su nombre, y `save_training` le acumula generaciones a un linaje que en realidad se reinició | **Problema confirmado** — no corregido | `historial/PRUEBA-ADVA10MIN/modelo.json` (formas); comprobación de carga en §8 | Resultados presentados como de un espécimen que no son suyos | Requiere decisión: (a) rechazar con error explícito, (b) marcar el espécimen como "arquitectura obsoleta" y no permitir continuar, o (c) conservar la clase antigua para cargarla |
| H0 | Las políticas evolucionadas rinden por debajo de una baseline voraz de ~10 líneas (sin aprendizaje) en todos los casos medidos; el proyecto no compara contra ninguna baseline | **Problema confirmado** (resultado negativo, no defecto de código) | Bloques D y E | La etiqueta "inteligencia" y los niveles no indican competencia frente a soluciones triviales | Incluir la baseline voraz en la vista de métricas; evaluar con más generaciones/población antes de sacar conclusiones de capacidad |
| H3 | El récord (fitness, frutas, longitud, nivel) es el **máximo de un único episodio** entre miles; se usa para decidir si se sustituyen los pesos y para el nivel mostrado. Ver magnitudes en D/E | **Problema confirmado** (sesgo metodológico) | Bloques C, D, E | Sobreestima la capacidad real; "seguir entrenando nunca empeora tu IA" no está demostrado en rendimiento esperado; un cambio de pesos puede deberse a suerte | Evaluar el candidato en K episodios con semillas fijas (p. ej. K=20–30) y guardar media ± IC; usar esa media para el récord y el nivel |
| H4 | Documentación afirma activaciones `tanh` (`ARCHITECTURE.md`, `DocsView.jsx`) y `tanh_relu` (`ENGINES.md`) para `intermated`; el código usa ReLU. El docstring del módulo decía `advanced 26->32->16->3` | **Problema confirmado → corregido** | `IntermatedNetwork.forward` línea `np.maximum(0.0, …)` | Descripción científica incorrecta del modelo | Texto corregido (§10) |
| H5 | Afirmaciones de rendimiento no respaldadas: «sube de N0 a N2–N3 (medido)» (`ENGINES.md`), «nunca se retrocede» por elitismo, N3 "✅ habilitado" presentado junto a niveles alcanzables; `ROADMAP.md` desactualizado («ningún espécimen ha superado N1») | **Problema confirmado** (documentación) | §7; bloque E | Expectativas infundadas | Reescribir con los datos de §8 (no aplicado: requiere decisión editorial del autor) |
| H6 | Las etiquetas de nivel ("Conciencia espacial", "Planificación emergente") describen capacidades cognitivas que la métrica (longitud/área máxima) no mide | **No verificable** | `NIVELES` | Riesgo de antropomorfización | Presentarlas como rangos de cobertura, o validar con métricas de comportamiento (tasa de muerte por encierro, etc.) |
| H7 | `train` guarda el cerebro con el **pico** de fitness instantáneo, que no es monótono por el *shaping*; la selección usa el fitness final | **Problema confirmado** (menor) | Bloque G | `fitness`/`pasos` guardados pueden no corresponder al final de la partida | Actualizar el récord solo al morir el agente |
| H8 | Parar a mitad de generación cuenta esa generación como completada | **Problema confirmado** (menor) | Bloque G | Contador de generaciones inflado en 1 por parada | Devolver `gen - 1` si se detuvo dentro de la generación (no aplicado: cambia un contador visible; decisión del autor) |
| H9 | `best_fitness` y `mejor_historico` inicializados a −1 aunque el fitness puede ser negativo | **Problema confirmado** (impacto bajo) | Bloque G | En una 1ª generación muy mala se devuelve `population[0]` en vez del mejor | Inicializar a `-inf` |
| H10 | Sin cota en el estado recurrente (ρ(W_rec)=1,51 en un modelo real) | **Parcialmente verificado** | Bloque F | NaN posible → serpiente "ciega" | `np.clip` del estado o vigilar `np.isfinite` |
| H11 | Reproducibilidad: la app no fija ni guarda semillas; RNG globales de `random` y `numpy` | **Mejora recomendada** | Bloque E (con semilla sí es reproducible) | Ningún resultado del historial puede reproducirse | Aceptar/guardar una semilla por sesión |
| H12 | *Shaping* asimétrico no basado en potencial | **Mejora recomendada** | §5 (Ng et al. 1999) | Cambia levemente el objetivo | Usar Φ(s)=−dist y F=Φ(s′)−Φ(s) si se quiere neutralidad |
| H13 | "Recocido" es un nombre impreciso | **Mejora recomendada** | §5 | Terminología | Llamarlo "decaimiento adaptativo de σ" |
| H14 | `save_training` compara fitness brutos entre tableros y entre fórmulas de fitness distintas | **Mejora recomendada** | `storage.save_training` | Récord no comparable | Comparar por cobertura media evaluada (ver H3) |
| H15 | Modo borrador: curva de `mutation_std` y "aprendizaje" fabricados | **Correcto y verificado como divulgado** | `src/App.jsx:103`; `server.js` | Bajo, porque hay aviso | Mantener el aviso; opcionalmente indicar en la gráfica que es simulada |
| H16 | Benchmarks de rendimiento (`bench_core.py`) | **Parcialmente verificado** | Método correcto (`perf_counter`, percentiles con interpolación lineal); cifras de `README.md` no reejecutadas en su máquina original | — | — |

---

## 10. Correcciones aplicadas

| Archivo | Cambio | Motivo |
| --- | --- | --- |
| `snake_neuroevolution.py` | Nueva constante `_LEGACY_COLS = [0, 6, 2, 8, 14, 10, 16, 22, 18, 24]` y su uso en `IntermatedNetwork._adapt_weights` cuando la red guardada tiene 9 o 10 entradas | H1. Reubica cada columna en la posición de ese mismo sensor. Verificado: 100 % de decisiones idénticas y mismas frutas medias que la red original. Solo afecta a redes de 9/10 entradas; los 7 especímenes actuales (26 entradas) cargan con pesos idénticos (comprobado) |
| `snake_neuroevolution.py` (docstring) | `advanced 26->32->16->3` → `26->16->3` | H4 |
| `docs/ENGINES.md`, `docs/ARCHITECTURE.md`, `src/views/DocsView.jsx` | Pseudocódigo de `intermated`: `tanh`/`tanh_relu` → `relu` | H4 |
| `benchmarks/audit_ia.py` (nuevo) | Script de verificación reproducible de esta auditoría | Reproducibilidad de las conclusiones |

No se modificaron: hiperparámetros, fitness, selección, datos de `historial/`, pruebas existentes
(no hay suite de tests en el repositorio) ni el comportamiento de entrenamiento.

---

## 11. Limitaciones de la auditoría

- **No hay suite de tests** en el repositorio; no se pudo ejecutar ninguna prueba preexistente.
- **Muestras pequeñas:** 100 episodios por espécimen y 5 semillas × 30 generaciones por motor. Las
  comparaciones entre motores de §8 son indicativas, no concluyentes; con este coste computacional
  (Python puro) no se pudieron hacer corridas largas (miles de generaciones) con repeticiones.
- **Modelos de 10 entradas** (`bf1b2e3`): no hay ninguno guardado, así que su carga solo se verificó
  por inspección del mapeo, no empíricamente.
- **Reglas antiguas:** en el bloque C la red antigua se evalúa con las reglas de juego actuales; la
  regla de colisión con la cola pudo diferir en la versión original, por lo que "frutas medias de la
  red original" no reproduce exactamente su entorno de entrenamiento.
- **Cifras de rendimiento** (`README.md`, `ROADMAP.md`) proceden de la máquina del desarrollador y
  no se reprodujeron allí.
- **Despliegues** (Netlify/Vercel/Render) no se inspeccionaron en vivo.
- **Interpretación cognitiva** de los niveles: no existe una métrica en el proyecto que permita
  verificarla.

---

## 12. Plan de mejora priorizado

| Prioridad | Acción | Impacto | Esfuerzo |
| --- | --- | --- | --- |
| 1 | H2: no cargar en silencio pesos incompatibles; marcar o rechazar especímenes de arquitectura obsoleta | Alto (integridad de linajes) | Bajo |
| 2 | H3: evaluar el cerebro candidato en K episodios con semillas fijas y persistir media ± IC; basar récord y nivel en esa media | Alto (validez de todas las métricas mostradas) | Medio |
| 3 | H5/H6: actualizar `ENGINES.md`, `ROADMAP.md`, `README.md` y `DocsView.jsx` con los números de este informe y retirar afirmaciones no medidas | Alto (honestidad) | Bajo |
| 4 | H11: semilla por sesión guardada en `sesiones.json` | Medio | Bajo |
| 5 | Añadir tests automáticos (bloques A, B, C, G de `audit_ia.py` como `pytest`) | Medio | Bajo |
| 6 | H7, H8, H9: récord al morir, contador de generaciones, `-inf` | Bajo | Bajo |
| 7 | H10: acotar el estado recurrente | Bajo-medio | Bajo |
| 8 | Métricas de comportamiento de `ROADMAP.md` (muerte por inanición vs colisión, frutas/paso) calculadas en la evaluación de H3 | Medio | Medio |
| 9 | H12/H13: *shaping* basado en potencial y renombrar "recocido" | Bajo | Bajo |

---

---

# Parte II — Correcciones y validación experimental (fase 2)

> Esta parte describe el **estado vigente** del código. La Parte I (§1–§13) se conserva como
> registro de la auditoría inicial: sus descripciones del protocolo de evaluación, del récord y de
> la carga de modelos se refieren al código **anterior** a estas correcciones.

## 14. Problemas corregidos y archivos afectados

| ID | Problema (Parte I) | Estado ahora | Archivos | Verificación |
| --- | --- | --- | --- | --- |
| H1 | Carga de redes de 9/10 entradas con sensores desordenados | **Corregido y verificado** (fase 1, conservado) | `snake_neuroevolution.py` | `audit_ia.py` C: 18/18 modelos reales de 9 entradas y una red sintética de 10 deciden igual que la original en todos los estados |
| H2 | Especímenes `advanced` 26→32→16→3 sustituidos en silencio por una red aleatoria | **Corregido y verificado** | `snake_neuroevolution.py` (`AdvancedV1Network`, `brain_from_dict`, `ModelError`), `ai_server.py`, `storage.py`, vistas | H: pesos exactos y 5.000/5.000 decisiones iguales al `forward` de `81aa744`; 9 tipos de modelo incompatible o corrupto rechazados con `ModelError` |
| H3 | Récord de un episodio usado como rendimiento y para decidir los pesos | **Corregido y verificado** | `snake_neuroevolution.py` (`train`, `evaluar`), `storage.py`, vistas | G: `eval` reproducible; los pesos solo cambian con `mejora_validada`; récord y rendimiento rotulados por separado |
| H5 | Afirmaciones de rendimiento sin respaldo | **Corregido** | `README.md`, `docs/ENGINES.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `src/views/DocsView.jsx` | Revisión manual contra §17 |
| H6 | Etiquetas cognitivas de nivel | **Corregido** | `NIVELES` (núcleo), `src/lib/demo/*`, docs | Etiquetas operativas «N· Cobertura a–b %» |
| H7 | Récord tomado en el pico instantáneo del fitness | **Corregido** | `train` | El récord se toma al **terminar** cada partida |
| H8 | Parada a mitad de generación contada como completa | **Corregido y verificado** | `train`, `ai_server.py` (texto), `TrainView.jsx` | G: parada en gen. 1 → 0 completadas; en gen. 3 → 2 |
| H9 | Récord inicializado a −1 | **Corregido y verificado** | `train` | G: con todos los fitness negativos el récord es una partida real (−3), no −1 |
| H10 | Estado recurrente sin cota → NaN | **Corregido y verificado** | `IntermatedNetwork.forward`, `Brain._check`, `Snake.step_ai` | F: `W_rec = 1,5·I` 5.000 pasos sin inf/NaN; pesos NaN → partida inválida en los 4 motores; 0 decisiones cambiadas en los 5 especímenes comparables con `HEAD` |
| H11 | Sin semillas | **Corregido y verificado** | `train(seed=…)`, `ai_server.py`, `storage.py` | G: misma semilla → mismos pesos/récord/eval, independiente del generador global |
| H12 | *Shaping* no basado en potencial (premia bucles: +0,5/paso) | **Probado, no adoptado** | — | §16: la variante basada en potencial no rindió mejor. Queda como limitación documentada |
| H13 | Nombre "recocido" | **Corregido** | comentarios y docs | — |
| H14 | Récord comparado entre tableros | **Mitigado** | `storage.py` | Los pesos ya no se deciden por el récord; el historial se ordena por cobertura media evaluada |
| — | `basic`: avisos de desbordamiento en `exp` | **Corregido y verificado** | `BasicNetwork.forward` | F: 0 avisos (antes 177), mismas decisiones |
| — | Errores de mi propio script de auditoría | **Corregido** | `benchmarks/audit_ia.py` | La causa de muerte con red se calcula antes de mover |
| H0 | Rendimiento inferior a la regla voraz | **No resuelto** | — | §16–§17 |

## 15. Cambios en el algoritmo y su justificación

**Protocolo de evaluación** (`snake_neuroevolution.py`, cabecera y `train`):

| Fitness | Cómo se obtiene | Para qué sirve | Comparable |
| --- | --- | --- | --- |
| De **selección** (`Individuo.score`) | Media en `EVAL_EPISODES = 3` semillas **comunes** a toda la generación (élite incluida) | Torneo y élite | Dentro de la generación |
| **Histórico** del individuo (`n_eval`, `suma_eval`) | Acumula las partidas de selección de todas las generaciones que sobrevive | No borra lo medido al reevaluar a la élite | — |
| De **validación** (`Individuo.val`) | Media en `VALIDATION_EPISODES = 10` semillas fijas (1.000.000+) | Elegir el cerebro devuelto; decaimiento de σ | **Entre generaciones** |
| De **prueba** (`eval`) | `TEST_EPISODES = 20` semillas fijas (2.000.000+) | Lo que se guarda y se muestra | Entre sesiones y especímenes (mismo tablero) |
| **Récord de un episodio** | Máximo, al terminar cada partida | Dato histórico, rotulado como tal | — |

Justificación: con un único episodio ruidoso por individuo, el ranking de dos episodios del mismo
individuo correlacionaba solo ρ = 0,31 (diagnóstico §16.1). Las semillas comunes son la técnica de
*common random numbers* para comparar alternativas estocásticas con menos varianza, y separar
selección, validación y prueba evita presentar como rendimiento el mismo dato con el que se eligió
(Jin y Branke, 2005, ref. 4). Las semillas de entrenamiento se sortean por encima de 3.000.000, así
que nunca coinciden con las de validación o prueba.

**Élite:** pasa como el **mismo objeto** `Individuo` (pesos y evaluaciones acumuladas); un individuo
inválido nunca es élite. **Continuar un linaje:** el heredado se valida primero y solo se sustituye
si un candidato lo supera en las mismas semillas (`mejora_validada`).

**Lo que NO se cambió, con motivo:** sensores, reglas del juego, arquitecturas, fitness, cruce,
torneo, tasa de mutación. Para el fitness, el cruce y el torneo se midieron alternativas (§16.2) y
ninguna mejoró. Cambiar la arquitectura o los sensores quedaba fuera del alcance pedido.

**Coste:** cada generación juega ~3× más partidas (más 10 de validación del campeón si no estaba
validado, y 20 de prueba al final).

## 16. Experimentos

Comandos (todos con semillas fijas; tiempos medidos en esta máquina, con 7 procesos en paralelo):

```bash
python benchmarks/audit_ia.py                                     # deterministas: 70 PASA, 0 FALLA
python benchmarks/experimento_ia.py dev --gens 40 --semillas 6 --episodios 50
python benchmarks/experimento_ia.py dev --sin-orig --variantes F0K3 F0K3X0 F0K3T5 F0K5 --gens 40 --semillas 6 --episodios 50
python benchmarks/experimento_ia.py confirmar --variante F0K3 --gens 40 --semillas 10 --episodios 100
python benchmarks/experimento_ia.py confirmar --variante F0K3 --grid 15 --engines intermated --gens 40 --semillas 6 --episodios 100
python benchmarks/experimento_ia.py confirmar --variante F0K3 --engines intermated --gens 200 --semillas 4 --episodios 100
```

**Diseño.** La unidad de replicación es el **entrenamiento**: cada configuración se entrena con
varias semillas independientes y cada cerebro resultante se evalúa en un conjunto de semillas que no
interviene en el entrenamiento. El IC 95 % es bootstrap percentil sobre las medias por entrenamiento
(5.000 remuestreos); el de la diferencia, bootstrap de la diferencia de medias. El "original" es
`git show HEAD:snake_neuroevolution.py`, cargado en memoria. Todas las políticas (original,
corregida, voraz y azar) se evalúan en el mismo entorno y **las mismas partidas**. `ORIG_x3` es el
original con 3× generaciones: el control de **igual cómputo**, porque F0K3 juega ~3× partidas por
generación.

| Fase | Semillas de entrenamiento | Semillas de evaluación | Uso |
| --- | --- | --- | --- |
| Desarrollo | 0–5 | 500000–500049 (50) | Elegir variante |
| Confirmación | 100–109 (6 en 15×15, 4 en la larga) | 10000–10099 (100) | Resultados que se reportan |

> **Error propio detectado y corregido durante la fase 2:** `train` (original y corregido) recorta
> las generaciones a `MAX_GENERATIONS = 100`, así que las primeras corridas `ORIG_x3` (120) y la
> prueba larga (200/600) ejecutaron en realidad 100. Esas filas se **descartaron**; el script ahora
> levanta el tope solo en el experimento y registra las generaciones realmente completadas
> (columna "Gen. reales").

### 16.1 Diagnóstico previo (algoritmo original, `HEAD`)

| Hipótesis | Medida | Resultado |
| --- | --- | --- |
| El fitness premia bucles | Serpiente girando en un ciclo 2×2 lejos de la comida | **Sí**: +0,50 de fitness por paso (+200 en 400 pasos); morir de inanición tras 200 pasos ≈ +100 |
| La selección es ruidosa | Spearman entre el fitness de dos episodios del mismo individuo, gen. 20 | **ρ = 0,31** (gen. 5: 0,54); medias reales de la población 0,10–7,10 frutas |
| Pérdida de diversidad | Distancia media entre genomas | 9,59 (inicial) → 6,40 (gen. 20); con el protocolo nuevo, distancia al centroide 6,63 → 1,93 en 40 gen. |
| Capacidad de la red | `advanced` 26→16→3 entrenada **por gradiente solo como diagnóstico** para imitar a la regla voraz (9.718 estados) | 97,8 % de acierto, pero 9,95 frutas en 8×8 (voraz 15,72) y 13,36 en 15×15 (voraz 23,73): la arquitectura y los sensores pueden aproximarla, pero los errores restantes son caros |

### 16.2 Fase de desarrollo (intermated, 8×8, 40 gen., 6 semillas, 50 partidas de evaluación)

| Variante | Qué cambia | Frutas/partida media [IC95] | vs. original |
| --- | --- | --- | --- |
| ORIG | — | 6,58 [5,47–7,71] | — |
| ORIG_x3 | 3× generaciones (100 reales, ver nota) | 7,37 | +0,79 [−0,84; +2,39] |
| F0K1 | protocolo nuevo, 1 partida | 7,04 [5,90–7,89] | +0,46 [−1,07; +1,89] |
| **F0K3** | protocolo nuevo, 3 partidas comunes | **8,30** [7,85–8,75] | **+1,72** [+0,54; +2,91] |
| F1K1 | + fitness basado en potencial | 7,84 [6,80–8,75] | +1,26 [−0,19; +2,67] |
| F1K3 | + fitness basado en potencial, 3 partidas | 7,60 [7,08–8,09] | +1,02 [−0,21; +2,23] |
| F0K3 (repetida*) | — | 8,21 [7,38–9,11] | |
| F0K3X0 | sin cruce (solo mutación, como Such et al. 2017) | 7,52 [6,45–8,61] | |
| F0K3T5 | torneo de 5 | 8,26 [7,59–8,97] | |
| F0K5 | 5 partidas por individuo | 7,75 [6,48–8,95] | |
| *Voraz* | regla sin aprendizaje | *15,26* [13,74–16,84] | |
| *Azar* | | *0,22* | |

\* repetida porque añadir `CROSSOVER_RATE` cambió la secuencia aleatoria.

Decisión: **F0K3** (3 partidas comunes, fitness original). Ni el fitness basado en potencial ni
quitar el cruce ni más presión selectiva ni más partidas mejoraron. La hipótesis del cruce
destructivo (Stanley y Miikkulainen 2002) queda **refutada** en este problema, pese a la caída de
diversidad.

### 16.3 Confirmación: mismas condiciones, semillas nuevas (100 partidas de evaluación)

**Baselines en esas mismas 100 partidas:** voraz 15,72 [14,70–16,77] (8×8) y 23,73 [22,01–25,43]
(15×15); azar 0,24 (8×8) y 0,15 (15×15).

**8×8, 40 generaciones, 10 semillas de entrenamiento por fila.** "Pasos" = pasos simulados
durante el entrenamiento (medida del cómputo).

| Motor | Algoritmo | Gen. reales | Frutas/partida media [IC95] | sd entre runs | min–max | Pasos (media) |
| --- | --- | ---: | --- | ---: | --- | ---: |
| intermated | ORIG | 40 | 7,00 [6,21–7,75] | 1,32 | 5,12–8,44 | 55.114 |
| intermated | ORIG_x3 | 120 | 8,48 [6,98–10,23] | 2,87 | 5,23–15,06 | 198.304 |
| intermated | **F0K3** | 40 | 7,80 [7,02–8,47] | 1,25 | 4,96–9,56 | 145.798 |
| advanced | ORIG | 40 | 8,36 [7,29–9,45] | 1,82 | 6,30–11,93 | 60.712 |
| advanced | ORIG_x3 | 120 | 8,56 [7,67–9,39] | 1,48 | 6,30–10,35 | 208.394 |
| advanced | **F0K3** | 40 | 8,64 [8,19–9,14] | 0,81 | 7,93–9,80 | 164.830 |
| basic | ORIG | 40 | 5,78 [4,80–6,87] | 1,79 | 3,85–8,43 | 64.993 |
| basic | ORIG_x3 | 120 | 8,93 [7,01–10,71] | 3,15 | 3,85–12,03 | 283.119 |
| basic | **F0K3** | 40 | 8,42 [7,58–9,26] | 1,46 | 6,54–11,04 | 221.445 |

| Motor | F0K3 − ORIG (mismas generaciones) | F0K3 − ORIG_x3 (cómputo similar*) |
| --- | --- | --- |
| intermated | +0,81 [−0,23; +1,83] | −0,67 [−2,70; +1,02] |
| advanced | +0,27 [−0,93; +1,40] | +0,08 [−0,88; +1,07] |
| basic | **+2,63 [+1,23; +3,94]** | −0,51 [−2,54; +1,57] |

\* F0K3 simuló el 74–79 % de los pasos de ORIG_x3: el control tuvo algo **más** de cómputo.

**15×15, intermated, 40 generaciones, 6 semillas.**

| Algoritmo | Gen. reales | Frutas/partida media [IC95] | sd | min–max | Pasos (media) |
| --- | ---: | --- | ---: | --- | ---: |
| ORIG | 40 | 9,04 [8,04–10,17] | 1,46 | 7,46–11,07 | 76.960 |
| ORIG_x3 | 120 | 11,62 [10,19–12,97] | 1,91 | 8,77–13,98 | 312.173 |
| **F0K3** | 40 | 13,28 [10,48–15,89] | 3,84 | 7,88–17,72 | 274.645 |

F0K3 − ORIG: **+4,24 [+1,13; +7,20]** · F0K3 − ORIG_x3: +1,65 [−1,55; +4,74] (F0K3 = 88 % de sus pasos).

**8×8, intermated, presupuesto largo, 4 semillas.**

| Algoritmo | Gen. reales | Frutas/partida media [IC95] | sd | min–max | Pasos (media) |
| --- | ---: | --- | ---: | --- | ---: |
| ORIG | 200 | 8,84 [6,52–12,95] | 4,16 | 6,41–15,06 | 442.018 |
| ORIG_x3 | 600 | 8,60 [6,04–11,15] | 3,14 | 5,46–12,35 | 1.507.782 |
| **F0K3** | 200 | 10,20 [8,29–12,41] | 2,36 | 7,64–13,34 | 1.062.658 |

F0K3 − ORIG: +1,36 [−2,99; +5,02] · F0K3 − ORIG_x3: +1,60 [−1,70; +4,96]. El original **no mejora**
de 200 a 600 generaciones (8,84 → 8,60): se estanca. Con n = 4 las diferencias no son
concluyentes.

**Comportamiento del protocolo** (todas las corridas F0K3 de confirmación): el récord **validado**
retrocedió **0** veces. El mejor fitness de *selección* de cada generación sigue bajando en ~46 % de
las transiciones, como en el original, porque cada generación juega semillas distintas: no es
comparable entre generaciones y ya no se presenta como tal (la interfaz muestra "selección" y
"récord validado" por separado).

### 16.4 Conclusiones

1. **Correcciones de medida: confirmadas.** El récord validado no retrocede (0 casos en todas
   las corridas), la élite conserva pesos y evaluaciones, y el rendimiento guardado sale de
   partidas que no intervienen en ninguna decisión.
2. **Aprendizaje a igual cómputo: sin mejora demostrada.** Con las mismas generaciones, F0K3 supera
   al original de forma significativa en `basic` 8×8 (+2,6) e intermated 15×15 (+4,2). Frente al
   control de cómputo similar (ORIG_x3, que simuló algo más de pasos), ninguna diferencia es
   significativa en ningún motor ni tablero (−0,7 a +1,7 frutas; todos los IC incluyen 0). La
   ventaja con las mismas generaciones se explica por jugar ~3× partidas, no por un algoritmo mejor.
3. **Consistencia:** la dispersión entre entrenamientos es menor con F0K3 (sd 0,8–1,5 frente a
   1,5–3,2 de ORIG_x3 en 8×8). Es una observación descriptiva, sin contraste formal.
4. **Frente a las referencias:** todo supera claramente al azar (0,2 frutas) y **nada alcanza a la
   regla voraz**: la mejor media es 10,2 en 8×8 (voraz 15,7) y 13,3 en 15×15 (voraz 23,7).
5. **Estancamiento:** el original no mejora de 200 a 600 generaciones. Con lo medido, la limitación
   no es el número de generaciones a población 25.

## 17. Compatibilidad, estabilidad numérica y reproducibilidad

`python benchmarks/audit_ia.py` → **70 PASA, 0 FALLA** (bloques A, B, C, H, F, G; ~25 s).

- **Los siete especímenes** de `historial/` cargan con sus pesos **exactos**, y la ida y vuelta
  `to_dict` → JSON → `from_dict` no los altera. Los dos `advanced` se identifican como
  `advanced_v1` y deciden igual que el código original de `81aa744` (5.000/5.000 estados). En el
  bloque D (100 partidas, 15×15) pasan de **0,00 frutas** (la red aleatoria por la que se
  sustituían) a **3,63 [3,08–4,18]** (`Advanced-prueba-error-nousar`) y **2,80 [2,18–3,46]**
  (`PRUEBA-ADVA10MIN`, que muere de inanición en el 97 % de las partidas). Los otros cinco
  especímenes dan exactamente las cifras de la Parte I.
- **Modelos antiguos:** los 18 modelos de 9 entradas de `mejores_ias.json` deciden igual que su red
  original; una red sintética de 10 entradas, también (no hay ninguna real guardada). Las redes con
  >20 neuronas o con un número de entradas sin disposición conocida se **rechazan**: antes se
  recortaban o se copiaban en la esquina, cambiando su comportamiento sin avisar.
- **Rechazo explícito** (`ModelError`) de: formas de otra arquitectura, NaN, inf, matriz ausente,
  motor desconocido, texto en vez de números, pesos que no son un objeto. El servidor responde con un
  mensaje de error y **no entrena** sobre un modelo así (entrenar lo sobrescribiría); el historial
  lo muestra con `modelo_error`. Prueba de extremo a extremo con `TestClient` de FastAPI sobre una
  **copia** del historial: el archivo roto quedó intacto.
- **Estabilidad:** el desbordamiento venía de `W_rec @ h` con ReLU sin cota y radio espectral > 1
  (ρ = 1,51 en `PRUEBA-UNO`). Ahora el estado se acota a 10⁶ (el máximo medido en partidas reales es
  ~7) y la salida se comprueba con `np.isfinite`. Si falla, la partida se marca **inválida**
  (fitness −∞): no se elige "recto" en silencio, no entra en élite ni en medias, y se cuenta en el
  evento `gen` (`invalidos`). En `basic`, la sigmoide recorta su argumento a ±500 antes de `exp`.
  Ninguno de estos controles cambió una sola decisión en los especímenes reales (comparado con `HEAD`
  en los 5 especímenes que `HEAD` sabía cargar).
- **Reproducibilidad:** `train(seed=s)` usa `random.Random(s)` y `numpy.random.default_rng(s)`
  propios. Misma semilla → mismos pesos, récord y `eval`, aunque otro código use el generador global
  en medio. La semilla viaja en el mensaje `info` del WebSocket, se puede fijar en la petición
  (`"seed"`) y se guarda en `sesiones.json`.
- **Guardado** (carpeta temporal): `eval`, `validacion` y la semilla se guardan; sin mejora validada
  los pesos **no** cambian aunque suba el récord de un episodio; las generaciones se acumulan;
  un espécimen antiguo con `generaciones = null` continúa sin error.

## 18. Limitaciones y problemas no resueltos

- **Problema principal sin resolver:** ninguna configuración probada iguala a la regla voraz. El
  protocolo nuevo hace las medidas fiables, pero a igual cómputo no aprende mejor que el algoritmo anterior (§16.4). Hipótesis abiertas, ninguna
  verificada: (1) el presupuesto (poblaciones de 25 y ≤ 200 generaciones) es pequeño frente a GA
  que funcionan en RL (Such et al. usan miles de individuos); (2) los errores que comete incluso una
  red que imita a la voraz (§16.1) sugieren que la codificación de sensores dificulta separar
  "seguro" de "mortal" en el siguiente paso; (3) la caída de diversidad (6,6 → 1,9 en 40 gen.)
  apunta a convergencia prematura que ni el torneo de 5 ni quitar el cruce corrigieron.
- **Bucle premiado por el fitness** (+0,5/paso): documentado, no corregido, porque la alternativa no
  mejoró el resultado.
- **Muestras:** 4–10 entrenamientos por configuración. Diferencias por debajo de ~1 fruta no se
  pueden resolver con estos tamaños. Solo se probó 10×10 de forma indirecta (transferencia, Parte I).
- **Especímenes existentes sin `eval`:** se guardaron antes del protocolo; la interfaz lo dice. No
  se reescribieron sus archivos; obtendrán `eval` la próxima vez que se entrenen.
- **Sin reanudación:** la población no se persiste; al detener se guarda el mejor cerebro validado
  de las generaciones completas.
- **Modo borrador (Netlify):** sigue siendo una heurística con datos fijos; no implementa el nuevo
  protocolo. Está rotulado como borrador; solo se actualizaron sus etiquetas de nivel.
- **Interfaz:** `vite build` (normal y `--mode demo`) compila sin errores y el servidor se probó de
  extremo a extremo con `TestClient`, pero **no se revisaron visualmente las vistas en un
  navegador**. No existe una suite `pytest`: las verificaciones están en `audit_ia.py`.
- **Coste de cómputo** (esta máquina, `bench_core.py`, 8×8, pop 25, 20 gen., 3 repeticiones):
  79 ms/gen. el original frente a 395 ms/gen. el corregido (~5×). El contador de pasos de
  `bench_core` solo incluye las partidas de selección, no las de validación ni prueba. Las cifras de
  `README.md` (≈ 380 ms/gen.) son de la máquina del desarrollador con el protocolo anterior; no se
  pudieron reproducir allí.

## 19. Plan de mejora actualizado

| Prioridad | Acción | Motivo |
| --- | --- | --- |
| 1 | Aumentar población y generaciones con evaluación vectorizada (Paso 3 del ROADMAP) | El cuello de botella es el cómputo: el protocolo fiable cuesta 3× |
| 2 | Medir y atacar la convergencia prematura (nichos/especiación, NEAT) | Diversidad 6,6 → 1,9 en 40 gen.; las palancas simples no bastaron |
| 3 | Mostrar la regla voraz en la interfaz como referencia | Contexto honesto del rendimiento |
| 4 | Métricas de comportamiento en `eval` (causa de muerte, frutas/paso) | Separar "no encuentra comida" de "se encierra" |
| 5 | Convertir `audit_ia.py` (A, B, C, H, F, G) en tests `pytest` | Integración continua |
| 6 | Revisar en navegador las vistas de entrenamiento e historial | Solo se comprobó que compilan |

---

## Referencias (Partes I y II)

Todas comprobadas (metadatos vía Crossref o la página del editor/arXiv el 2026-10-10).

1. Holland, J. H. (1975). *Adaptation in Natural and Artificial Systems*. University of Michigan Press. (Referencia clásica; no tiene DOI.)
2. Eiben, A. E., & Smith, J. E. (2015). *Introduction to Evolutionary Computing* (2.ª ed.). Springer. https://doi.org/10.1007/978-3-662-44874-8
3. Miller, B. L., & Goldberg, D. E. (1995). Genetic Algorithms, Tournament Selection, and the Effects of Noise. *Complex Systems*, 9(3), 193–212. https://www.complex-systems.com/abstracts/v09_i03_a02/
4. Jin, Y., & Branke, J. (2005). Evolutionary optimization in uncertain environments—a survey. *IEEE Transactions on Evolutionary Computation*, 9(3), 303–317. https://doi.org/10.1109/TEVC.2005.846356
5. Stanley, K. O., & Miikkulainen, R. (2002). Evolving Neural Networks through Augmenting Topologies. *Evolutionary Computation*, 10(2), 99–127. https://doi.org/10.1162/106365602320169811
6. Such, F. P., Madhavan, V., Conti, E., Lehman, J., Stanley, K. O., & Clune, J. (2017). Deep Neuroevolution: Genetic Algorithms Are a Competitive Alternative for Training Deep Neural Networks for Reinforcement Learning. arXiv:1712.06567. https://arxiv.org/abs/1712.06567
7. He, K., Zhang, X., Ren, S., & Sun, J. (2015). Delving Deep into Rectifiers: Surpassing Human-Level Performance on ImageNet Classification. *ICCV 2015*. https://doi.org/10.1109/ICCV.2015.123
8. Maas, A. L., Hannun, A. Y., & Ng, A. Y. (2013). Rectifier Nonlinearities Improve Neural Network Acoustic Models. ICML 2013 Workshop on Deep Learning for Audio, Speech and Language Processing. https://ai.stanford.edu/~amaas/papers/relu_hybrid_icml2013_final.pdf
9. Ng, A. Y., Harada, D., & Russell, S. (1999). Policy Invariance Under Reward Transformations: Theory and Application to Reward Shaping. *Proc. 16th ICML*, 278–287. https://mlanthology.org/icml/1999/ng1999icml-policy/
10. Kirkpatrick, S., Gelatt, C. D., & Vecchi, M. P. (1983). Optimization by Simulated Annealing. *Science*, 220(4598), 671–680. https://doi.org/10.1126/science.220.4598.671
11. Cybenko, G. (1989). Approximation by superpositions of a sigmoidal function. *Mathematics of Control, Signals, and Systems*, 2(4), 303–314. https://doi.org/10.1007/BF02551274
12. Hornik, K. (1991). Approximation capabilities of multilayer feedforward networks. *Neural Networks*, 4(2), 251–257. https://doi.org/10.1016/0893-6080(91)90009-T
13. Pascanu, R., Mikolov, T., & Bengio, Y. (2013). On the difficulty of training recurrent neural networks. arXiv:1211.5063. https://arxiv.org/abs/1211.5063
14. Agarwal, R., Schwarzer, M., Castro, P. S., Courville, A., & Bellemare, M. G. (2021). Deep Reinforcement Learning at the Edge of the Statistical Precipice. *NeurIPS 2021*. arXiv:2108.13264. https://arxiv.org/abs/2108.13264
15. Efron, B. (1979). Bootstrap Methods: Another Look at the Jackknife. *The Annals of Statistics*, 7(1), 1–26. https://doi.org/10.1214/aos/1176344552
