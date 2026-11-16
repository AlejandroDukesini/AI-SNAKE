# IA-SNAKE — Etapa 1: análisis y propuesta de arquitectura

> **Estado:** aprobada con cambios el 2026-11-16. Las decisiones finales (tablero difícil 16×16,
> CLARK sin preentrenar, longitud inicial 1 en 4×4, etc.) están en [`DECISIONES.md`](DECISIONES.md)
> y prevalecen sobre este documento.
> **Fecha:** 2026-11-16 · **Rama de partida:** `Beta` (limpia, commit `3831cc1`).
> **Especificación de referencia:** System Prompt IA-SNAKE v2.0 (las decisiones que contiene se
> consideran aprobadas; aquí solo se proponen las que deja abiertas).

---

## 1. Inspección del entorno

### 1.1 Recursos disponibles (medidos en esta máquina)

| Recurso | Versión / valor | Uso en el laboratorio |
| --- | --- | --- |
| Windows 11, 8 núcleos | — | Entrenamientos en paralelo por proceso (un modelo o semilla por núcleo) |
| Python | 3.13.14 | Motor, modelos, entrenamiento, servidor |
| NumPy | 2.4.4 | Matrices de percepción, tabla Q, métricas |
| scikit-learn | 1.9.0 (ya instalado) | Clasificador de ARKIS y componente ML de CLARK/MABU |
| FastAPI / uvicorn | 0.162.0 | Servidor autoritativo REST + WebSocket |
| Node / npm | 24.16 / 12.2 | Interfaz React 18 + Vite 6 + Tailwind 4 |
| PyTorch / TensorFlow | **no instalados** | No se necesitan: ningún modelo usa Deep Learning |
| pytest, skops | no instalados | Se proponen como dependencias nuevas (§7) |

### 1.2 Qué hay hoy en el repositorio

52 archivos versionados. El proyecto actual es **otro problema metodológico**: neuroevolución
(algoritmo genético sobre los pesos de redes neuronales NumPy).

| Pieza | Archivo(s) | ¿Encaja en IA-SNAKE? |
| --- | --- | --- |
| Núcleo de neuroevolución (redes, genético, `Snake` con sensores de 26 entradas) | `snake_neuroevolution.py` (≈1.400 líneas) | **No.** Redes neuronales + algoritmo genético no corresponden a ninguna de las cinco metodologías. El motor de juego está mezclado con el cerebro (`Snake` contiene la red), lo que viola el requisito de motor independiente. |
| Servidor FastAPI autoritativo (REST + WS, último fotograma sobrescrito) | `ai_server.py` | **El patrón sí**, el código no: sus rutas sirven la neuroevolución. |
| Persistencia por carpeta y linaje | `storage.py` | **La idea sí** (carpeta por modelo, no perder historial); el formato no (no hay versiones, hash ni import/export). |
| Orquestador dev/prod | `run.py` | **Sí**, casi sin cambios. |
| Auditoría y benchmarks con semillas fijas | `benchmarks/` | **El método sí** (semillas, IC 95 %, comparación con azar y regla voraz); los scripts no. |
| Interfaz React | `src/` (≈3.700 líneas) | **Parcialmente:** `Board.jsx`, `ui.jsx`, `useSocket.js`, `useLocalState.js`, temas y estilos se reutilizan. Las vistas (Entrenar, Historial, Docs) son específicas de neuroevolución. |
| Modo borrador (heurística simulada en el navegador) + despliegues Netlify/Vercel + analítica con consentimiento | `src/lib/demo/`, `netlify.toml`, `vercel.json`, `consent.js`, `analytics.js` | **No.** Un laboratorio que exige evidencia de aprendizaje no puede publicar una simulación del aprendizaje. |
| Datos locales | `historial/` (7 especímenes), `mejores_ias.json`, `probando-ia/` | Son datos del usuario. **No se modifican ni se borran** sin autorización. |

**Conclusión:** se conserva la tecnología y los principios (servidor autoritativo, semillas,
honestidad estadística), pero el dominio se reconstruye desde cero. No es viable “adaptar” el
núcleo actual: la metodología de aprendizaje es incompatible y el motor está acoplado al modelo.

---

## 2. Decisiones de tecnología (justificadas)

1. **Python para todo lo que aprende o arbitra reglas.** Las reglas del juego, la percepción, las
   recompensas, la evolución y los cinco modelos viven en un solo lugar: el servidor. El navegador
   solo dibuja y envía acciones del usuario (etiquetas, reglas, parámetros). Así es imposible que la
   interfaz y el entrenamiento usen reglas distintas.
2. **scikit-learn** para el aprendizaje supervisado: implementaciones de referencia, auditadas y
   deterministas con `random_state`. Escribir un Random Forest propio añadiría riesgo sin valor
   científico.
3. **Aprendizaje simbólico y Q-Learning implementados a mano** en Python/NumPy: no existe una
   biblioteca estándar que encaje, y su código es corto y auditable línea a línea.
4. **Sin pickle para artefactos.** `joblib/pickle` ejecutan código al cargar: importar un modelo
   ajeno sería un riesgo. Propuesta: `skops` (serialización segura de scikit-learn) para los
   clasificadores y JSON/NPZ para reglas y tablas Q. Cada artefacto lleva un hash SHA-256.
5. **Registros en SQLite por modelo** (biblioteca estándar): miles de episodios con consultas por
   dificultad/versión, escritura transaccional (sin archivos a medio escribir) y sin servidor.
6. **React + Vite + Tailwind** se mantienen: ya están instalados y conocidos.

---

## 3. Arquitectura propuesta

### 3.1 Capas y dependencias

```
                ┌──────────────────────── interfaz React (solo dibuja) ────────────────────────┐
                │ Panel · Simulador · Percepción · Entrenamiento ×5 · Evolución · Comparación │
                └──────────────────────────────┬───────────────────────────────────────────────┘
                                   REST + WebSocket (último fotograma)
                ┌──────────────────────────────▼───────────────────────────────────────────────┐
                │ servidor/   API, sesiones en vivo, colas de entrenamiento (un proceso c/u)  │
                └───────┬───────────────────┬──────────────────────┬──────────────────────────┘
                        │                   │                      │
              entrenamiento/         evaluacion/             persistencia/
              (bucle de episodios    (protocolo, semillas,   (versiones, manifiestos,
               sin algoritmo)         líneas base, IC 95%)    hash, backups, SQLite)
                        │                   │
         ┌──────────────┴───────────────────┴─────────────┐
         │ modelos/  arkis · lerk · bork · clark · mabu    │  ← cada uno con su propio entrenador
         └──────────────┬──────────────────────────────────┘
                        │ solo lee Percepcion, devuelve Decision
         ┌──────────────▼──────────────────────────────────┐
         │ nucleo/  motor · percepcion · recompensas ·      │  ← no importa nada de modelos/
         │          evolucion · ciclos · reloj              │
         └─────────────────────────────────────────────────┘
```

**Regla de dependencias (verificada por un test):** `nucleo/` no importa nada de `modelos/`,
`servidor/` ni `persistencia/`. Ningún modelo importa a otro modelo (CLARK y MABU tienen sus
propios componentes; no reutilizan las instancias de ARKIS/LERK/BORK ni los artefactos entre sí).

### 3.2 Estructura de carpetas

```
ia_snake/
  nucleo/
    motor.py          Tablero, Serpiente, Partida: reglas puras y deterministas (RNG inyectado)
    percepcion.py     Los tres sentidos → objeto Percepcion inmutable
    recompensas.py    Función configurable; devuelve el total y cada componente por separado
    evolucion.py      Ocupación, C(E_n) = techo(n·N/8), nivel de partida e histórico
    ciclos.py         Detector de repetición de estados
    reloj.py          Reloj de simulación determinista + reloj monotónico de sesión
  modelos/
    base.py           Interfaz común Agente (decidir/explicar), sin método de entrenamiento común
    arkis/            caracteristicas.py · clasificador.py · dataset.py · entrenador.py
    lerk/             predicados.py · reglas.py · inferencia.py · induccion.py · rdr.py · entrenador.py
    bork/             estado.py · qtabla.py · entrenador.py
    clark/            componente_ml.py · componente_simbolico.py · componente_rl.py · integrador.py · preentrenar.py
    mabu/             (se diseña en la Etapa 5, tras presentar su arquitectura)
  entrenamiento/      ejecutor de episodios (común) — NO contiene algoritmos de aprendizaje
  evaluacion/         protocolo, semillas, líneas base (azar, voraz), estadísticos
  persistencia/       almacén por modelo, versionado, import/export, backups, validación
  metricas/           métricas comunes y específicas por metodología
  servidor/           FastAPI
scripts/              preentrenar_clark.py · preentrenar_mabu.py · evaluar.py · verificar_artefacto.py
tests/                por capa + tests de independencia metodológica
web/                  interfaz React (migrada de src/)
laboratorio/          datos del usuario (gitignored): un directorio por modelo
preentrenados/        artefactos verificables de CLARK y MABU (versionados en git, con manifiesto)
docs/ia-snake/           arquitectura, decisiones (ADR), manual de usuario, resultados
```

### 3.3 Interfaz común de los modelos

Solo se comparte la **forma de actuar**, nunca la forma de aprender (requisito §13):

```
Agente
  nombre, metodologia, estado_evidencia        # sin_entrenar | entrenado | evaluado | validado | preentrenado | experimentacion
  decidir(percepcion) -> Decision              # accion + puntuaciones por acción + explicación
  explicar(decision) -> texto/estructura       # cada modelo explica a su manera
```

El entrenamiento es propio de cada modelo (`arkis.entrenador`, `lerk.entrenador`, …). El ejecutor
de episodios común solo juega partidas y entrega transiciones; quien decide qué hacer con ellas es
el entrenador de cada modelo. Un test comprueba que ARKIS y LERK nunca reciben una actualización Q.

---

## 4. Núcleo: motor, sentidos, recompensa, ciclos y evolución

### 4.1 Motor

- Tableros 4×4 (16), 8×8 (64), 15×15 (**225**). Acciones absolutas: arriba, abajo, izquierda,
  derecha.
- Un paso: mover la cabeza → comprobar límite → comprobar cuerpo (la cola que se va a mover no
  cuenta como obstáculo salvo que se coma) → crecer si come → generar manzana en una casilla libre
  con el RNG de la partida.
- Moverse en sentido opuesto a la dirección actual equivale a chocar con el cuello (regla física
  real); la percepción marca esa acción como **no disponible** para que los modelos puedan
  evitarla.
- Victoria: longitud = N casillas → fin, E8, sin nueva manzana.
- Toda la aleatoriedad pasa por un `random.Random(semilla)` propio de la partida: misma semilla +
  mismas acciones = misma partida, bit a bit.

### 4.2 Los tres sentidos (`Percepcion`, inmutable)

| Sentido | Contenido |
| --- | --- |
| **Cuerpo** | matriz binaria N×N; segmentos ordenados cabeza→cola; cabeza, cola, longitud, dirección; casillas libres; acciones disponibles; colisión inmediata por acción; espacio alcanzable por acción (flood-fill); si la cola es alcanzable tras cada acción |
| **Manzana** | x, y, Δx, Δy, dirección relativa, distancia Manhattan `|xm−xc| + |ym−yc|` |
| **Muros** | distancia a los cuatro límites; colisión con límite por acción; espacio libre |

La matriz se deriva de la lista ordenada en el mismo paso; un invariante (comprobado en tests y,
en modo depuración, en cada paso) garantiza que ambas coinciden. Cada modelo construye **su propia
representación** a partir de la percepción común (vector de características, predicados o estado
compacto); la percepción no favorece a ninguno.

### 4.3 Recompensa común (BORK, CLARK-RL, MABU-RL)

Configurable, con cada componente registrado por separado. Valores iniciales propuestos (se
ajustarán con experimentos documentados, no a ojo):

| Componente | Valor inicial | Nota |
| --- | ---: | --- |
| Manzana | +10 | Significativa |
| Colisión (límite o cuerpo) | −10 | Importante |
| Acercamiento / alejamiento | `k·(d_anterior − d_actual)`, k = 0,1 | Basado en Δd; con γ≈1 equivale a *shaping* por potencial (Ng et al., 1999), que no cambia la política óptima |
| Supervivencia por paso | −0,01 | Pequeña presión contra dar vueltas |
| Estado repetido desde la última manzana | −0,5 | Penaliza ciclos improductivos |
| Casilla nueva desde la última manzana | +0,02 | Exploración |
| Victoria (E8) | +50 | Finalización exitosa |

Como la distancia es solo un componente pequeño frente a la colisión y al encierro, la serpiente
puede aprender que acercarse en línea recta a veces es peor. Las recompensas **no** se comparan
entre algoritmos: la comparación usa métricas de juego (manzanas, ocupación, nivel E).

### 4.4 Detector de ciclos y regla de los 30 segundos

El detector marca “en ciclo” cuando, desde la última manzana, se cumple alguna de:

- **Configuración repetida:** el hash (cuerpo completo + manzana + dirección) ya apareció. Para una
  política determinista esto es una prueba de bucle infinito.
- **Posiciones repetidas:** en una ventana de W pasos la cabeza visita pocas casillas distintas
  (proporción de casillas únicas < umbral).
- **Secuencia periódica de acciones:** las últimas acciones forman un patrón que se repite con
  periodo p.

El temporizador de 30 s **solo avanza mientras el detector diga “en ciclo”** y se reinicia al comer
o al recuperar progreso (casillas o configuraciones nuevas). Así no se confunde explorar sin comer
con estar atrapado. El tiempo en pausa nunca cuenta. Cómo se mide el tiempo es la **decisión D2**
(§9). Además se propone un límite técnico de seguridad muy holgado (p. ej. 100·N pasos sin
manzana), registrado como causa de fin distinta, para que ningún proceso quede colgado.

### 4.5 Evolución E0–E8

`C(E_n) = techo(n·N/8)` casillas:

| n | 4×4 (16) | 8×8 (64) | 15×15 (225) |
| --- | ---: | ---: | ---: |
| E1 | 2 | 8 | 29 |
| E2 | 4 | 16 | 57 |
| E3 | 6 | 24 | 85 |
| E4 | 8 | 32 | 113 |
| E5 | 10 | 40 | 141 |
| E6 | 12 | 48 | 169 |
| E7 | 14 | 56 | 197 |
| E8 | 16 | 64 | 225 |

Nivel de partida = mayor n con longitud ≥ C(E_n). Récord histórico = máximo sobre episodios
válidos, por **modelo × dificultad**, en una tabla de solo-inserción (nunca se reduce). Hay un
conflicto entre la longitud inicial y la definición de E0 en 4×4 (**decisión D3**).

---

## 5. Los cinco modelos

### 5.1 ARKIS — aprendizaje supervisado

**Algoritmo recomendado: Random Forest** (scikit-learn), frente a:

| Opción | A favor | En contra |
| --- | --- | --- |
| **Random Forest** ✔ | Robusto con pocos ejemplos y clases desbalanceadas (`class_weight`); da probabilidades por acción; importancia de características; poco ajuste fino | Menos legible que un solo árbol |
| Árbol de decisión | Totalmente interpretable | Inestable: pequeños cambios en los datos cambian el árbol; sobreajusta |
| k-NN | “Aprende” al instante cada etiqueta | Sensible a la escala; lento al predecir con muchos ejemplos; sin importancias |
| SVM | Buen margen con datos limpios | Escala mal en datos y no da probabilidades calibradas sin coste extra |

Se mostrará además un árbol de decisión como **vista explicativa** del mismo conjunto, sin que
decida.

- **Características:** peligro por acción, espacio alcanzable por acción (normalizado), cola
  alcanzable por acción, Δx/Δy y dirección de la manzana, distancias a muros, dirección actual,
  ocupación. Todo calculado desde la percepción común.
- **Clases:** las 4 acciones. Las acciones no disponibles se enmascaran al decidir.
- **Flujo del usuario:** pausar → ver la situación y las acciones disponibles → elegir acción →
  guardar ejemplo (con semilla, paso y versión del motor) → aprobar conjunto → entrenar → validar →
  corregir → reentrenar. Las correcciones crean una versión nueva del conjunto; la anterior se
  conserva.
- **Aumento de datos opcional y declarado:** rotaciones/reflexiones del tablero (8 simetrías)
  aplicadas al ejemplo **y a su etiqueta**. No es auto-etiquetado: transforma una decisión humana
  de forma geométricamente exacta. Se marca su procedencia.
- **Sin fuga de datos:** la división entrenamiento/prueba es **por episodio** (`GroupKFold`), no
  por paso, porque pasos consecutivos son casi idénticos. Los ejemplos aumentados nunca cruzan la
  frontera.
- **Prohibido:** etiquetar con las predicciones del propio ARKIS.
- **Métricas:** ejemplos recogidos/etiquetados, distribución de clases, accuracy, precision,
  recall y F1 (macro y por clase), matriz de confusión, errores concretos navegables, rendimiento
  en simulación con semillas fijas.

### 5.2 LERK — aprendizaje simbólico

Tres mecanismos reales de adquisición de conocimiento, sobre una base de hechos simbólica:

1. **Hechos:** predicados calculados desde la percepción: `manzana_a(derecha)`,
   `libre(arriba)`, `encierro(izquierda)` (espacio alcanzable < longitud), `cola_alcanzable(abajo)`,
   `cerca_de_muro(…)`, etc.
2. **Inducción de reglas por cobertura secuencial** (familia CN2/RIPPER): a partir de ejemplos
   etiquetados aprende listas de reglas `SI condiciones ENTONCES acción`, generaliza eliminando
   condiciones mientras la precisión (estimación de Laplace) se mantenga y especializa cuando cubre
   ejemplos negativos.
3. **Ripple-Down Rules (RDR) para excepciones:** cuando el usuario corrige una inferencia, el
   sistema crea una regla-excepción ligada al caso que la motivó (`SI … ENTONCES derecha, EXCEPTO SI
   encierro(derecha) ENTONCES …`). Es el mecanismo clásico de adquisición de conocimiento con
   excepciones sin reescribir la base.
4. **Aprendizaje por explicación del fracaso** (modo automático): LERK juega; cuando una acción
   lleva a la muerte, el simulador aporta el hecho objetivo (“esta acción en este contexto causó
   colisión en ≤ k pasos”). Esas observaciones —no las predicciones de LERK— alimentan la inducción
   de reglas negativas (`NO derecha SI …`).

- **Motor de inferencia:** encadenamiento hacia delante; resolución de conflictos por prioridad
  del usuario → especificidad → precisión observada; las reglas de prohibición derrotan a las de
  preferencia.
- **Cada regla guarda:** origen (usuario / inducida / excepción / fracaso), soporte, cobertura,
  precisión, fecha y versión. Las reglas del usuario se distinguen siempre de las aprendidas, de
  modo que se puede demostrar que LERK **adquiere** conocimiento: comienza vacío y su base crece con
  evidencia.
- **Explicación:** cada decisión muestra la cadena hechos → reglas disparadas → conflictos →
  regla ganadora.
- **Interfaz:** crear/modificar/eliminar reglas, priorizar, validar contra un conjunto de casos,
  ver conflictos, ver qué se aprendió en cada sesión.

### 5.3 BORK — Q-Learning tabular

`Q(s,a) ← Q(s,a) + α[r + γ·max Q(s',a') − Q(s,a)]`, política ε-greedy con decaimiento.

**Estado compacto propuesto** (relativo a la dirección actual para compartir experiencia entre
orientaciones; las acciones se traducen de vuelta a absolutas):

| Rasgo | Valores |
| --- | ---: |
| Peligro inmediato (frente, izquierda, derecha) | 2³ |
| Encierro por acción: espacio alcanzable < longitud | 2³ |
| Dirección de la manzana (8 sectores) | 8 |
| Cola alcanzable tras cada acción | 2³ |
| **Total** | 32.768 estados × 3 acciones, la mayoría inalcanzables |

- **Riesgo de compresión (aliasing):** estados reales distintos caen en la misma celda. Se medirá
  explícitamente: (a) estados visitados vs. posibles, (b) varianza de retornos dentro de una misma
  celda, (c) ablación: rendimiento con y sin los rasgos de encierro y cola.
- **Configurable:** α, γ, ε inicial, ε final, decaimiento, episodios, cada recompensa y penalización,
  velocidad.
- **Registro por episodio:** retorno (y por componente), manzanas, pasos, causa de fin, ε, estados
  nuevos visitados, cobertura de la tabla.

### 5.4 CLARK — híbrido de referencia (preentrenado)

| Componente | Procesa | Produce |
| --- | --- | --- |
| A · ML (Random Forest propio de CLARK) | vector de características | probabilidad estimada de que cada acción sea buena (ver D4) |
| B · Simbólico (base de reglas propia, inducida + RDR) | predicados | vetos (acciones prohibidas) y preferencias con su explicación |
| C · RL (tabla Q propia) | estado compacto | valor Q por acción |

**Integración (fija y documentada, propia de la referencia):**

1. B veta las acciones prohibidas (seguridad primero). Si vetara todas, se ignoran los vetos de
   menor confianza y se registra el conflicto.
2. Puntuación de cada acción permitida: `w_A·P_ML + w_B·preferencia + w_C·softmax(Q)`, con pesos
   publicados en el manifiesto.
3. Conflicto = los componentes eligen acciones distintas: se registra quién ganó y por qué.
4. Cada decisión expone las tres opiniones y la final.

**Preentrenamiento reproducible:** `scripts/preentrenar_clark.py --semilla S` genera los datos,
entrena A, B y C, integra, evalúa con semillas de prueba separadas y guarda en `preentrenados/clark/`
un manifiesto con: commit, configuración, semillas, hash de cada dato y artefacto, métricas, tiempo y
comando exacto. `verificar_artefacto.py` vuelve a ejecutarlo y comprueba que el hash coincide.
CLARK solo se rotula “preentrenado” si ese manifiesto existe y la verificación pasa.

### 5.5 MABU — híbrido experimental (adelanto, no para aprobación todavía)

La arquitectura de MABU se presentará en la Etapa 5, como pide la especificación. Adelanto de la
dirección para que se tenga en cuenta al diseñar la persistencia:

- Mismos tres tipos de componentes, **con datos, semillas y artefactos propios** (no copia de CLARK).
- Diferencia experimental candidata: el árbitro no usa pesos fijos, sino que ajusta la confianza
  de cada componente según su fiabilidad medida por contexto (registrada y reversible).
- Aprendizaje continuo con **versiones inmutables**: cada sesión produce una versión nueva;
  comparar versión inicial vs. actual con las mismas semillas; volver a cualquier versión; exportar.
- Toda transferencia CLARK → MABU será un experimento explícito, registrado con su propio
  manifiesto.

---

## 6. Entrenamiento, evaluación y persistencia

### 6.1 Entrenamiento por metodología

| Modelo | Manual | Automático |
| --- | --- | --- |
| ARKIS | El usuario etiqueta situaciones | Reentrena con conjuntos **aprobados**; evalúa en simulación |
| LERK | El usuario crea reglas, corrige inferencias (RDR) | Juega, registra fracasos objetivos, induce reglas |
| BORK | El usuario fija parámetros y observa episodios | Actualiza la tabla Q episodio a episodio |
| CLARK / MABU | Inspección de componentes, correcciones simbólicas, parámetros | Cada componente con su propio mecanismo |

Velocidades separadas: **movimiento** (pasos por segundo de juego), **entrenamiento** (sin
renderizar, tan rápido como permita la CPU), **renderizado** (fotogramas enviados; se descartan los
que no da tiempo a dibujar) y **tiempo real** transcurrido. Ninguna altera α, γ, ε ni la recompensa:
el aprendizaje se calcula por paso, no por segundo.

### 6.2 Protocolo de evaluación

- Semillas de entrenamiento, validación y prueba disjuntas y fijas por dificultad.
- Por modelo y dificultad: media, mediana, desviación típica e IC 95 % de manzanas, ocupación
  máxima, nivel E, pasos, causa de fin; victorias/derrotas.
- Líneas base sin aprendizaje: **azar** y **regla voraz segura**. Un modelo no se declara “útil”
  si no supera al azar con significación, y se informa siempre su posición frente a la voraz.
- Métricas propias: ARKIS (F1, matriz de confusión), LERK (nº de reglas, cobertura, precisión,
  conflictos), BORK (curva de aprendizaje, cobertura de la tabla, aliasing), CLARK/MABU (acuerdo
  entre componentes, vetos, quién decide).

### 6.3 Estados con evidencia

| Estado | Evidencia exigida |
| --- | --- |
| sin entrenar | artefacto vacío y versión 0 |
| entrenado | sesión de entrenamiento registrada con datos/configuración/semilla |
| evaluado | evaluación con semillas de prueba guardada |
| validado | supera al azar con IC 95 % y pasa sus tests de metodología |
| preentrenado | manifiesto + verificación de hash reproducida |
| en experimentación | versión derivada de otra, con experimento registrado |

### 6.4 Persistencia (por modelo, independiente)

```
laboratorio/<modelo>/
  manifiesto.json          versión actual, estado, hashes
  versiones/v0001/ …       artefactos inmutables (skops / JSON / NPZ) + config + métricas
  datos/                   ejemplos (JSONL) y conjuntos aprobados con versión
  registros.sqlite         episodios, sesiones, récord E por dificultad (solo inserción)
  copias/                  backups automáticos antes de cada entrenamiento
```

Guardado atómico (archivo temporal + renombrado), validación de esquema y hash al cargar,
exportación/importación en `.zip` con manifiesto, recuperación a la última versión válida si un
artefacto está corrupto. Reentrenar **crea una versión nueva**; nunca sobrescribe.

---

## 7. Dependencias

| Nueva | Motivo |
| --- | --- |
| `scikit-learn` (ya instalado, se añade a `requirements.txt`) | Random Forest y métricas |
| `skops` | Serialización segura de modelos scikit-learn (sin pickle) |
| `pytest` (desarrollo) | Pruebas por capa |

Se retira del núcleo: redes neuronales y algoritmo genético. No se introduce Deep Learning.

---

## 8. Riesgos identificados

| # | Riesgo | Impacto | Mitigación |
| --- | --- | --- | --- |
| R1 | **E8 en 15×15 probablemente inalcanzable** para estos métodos con estados compactos (en 225 casillas, además, no existe ciclo hamiltoniano por ser impar) | Expectativas | Se informará lo medido; 4×4 es donde E8 es realista |
| R2 | ARKIS necesita cientos o miles de etiquetas humanas para rendir | Avance lento | Simetrías declaradas, etiquetado rápido con teclado, curva de aprendizaje vs. nº de ejemplos |
| R3 | Aliasing del estado de BORK | Políticas mediocres | Medición explícita y ablaciones (§5.3) |
| R4 | Origen de las etiquetas para preentrenar CLARK/MABU | Honestidad científica | Decisión D4 |
| R5 | Regla de 30 s con reloj real hace irreproducible el entrenamiento acelerado | Reproducibilidad | Decisión D2 |
| R6 | Rendimiento de Python puro (flood-fill por paso) | Entrenamientos largos | Flood-fill acotado, procesos en paralelo, perfilado en la Etapa 2 |
| R7 | Cargar artefactos con pickle | Seguridad | `skops` + JSON + hash |
| R8 | Alcance grande | Funciones a medias | Etapas cerradas, cada una con tests antes de pasar a la siguiente |
| R9 | Pérdida de datos antiguos | Irreversible | `historial/` y `mejores_ias.json` no se tocan |

---

## 9. Decisiones pendientes

### D1 · Destino del proyecto actual (neuroevolución, modo borrador, despliegues)

| Opción | Ventajas | Limitaciones |
| --- | --- | --- |
| **A. Etiquetar y reconstruir** ✔ | Se crea la etiqueta `v2-neuroevolucion` y la rama `arkis-lab`; se retira el código antiguo del árbol (sigue en git) y se reconstruye limpio | Las demos Netlify/Vercel dejan de actualizarse |
| B. Convivencia en `legacy/` | Todo visible en la misma rama | Dos sistemas, dos servidores, confusión metodológica |
| C. Borrado sin etiqueta | Más simple | Se pierde un punto de retorno claro |

Recomiendo **A**. Los datos locales (`historial/`, `mejores_ias.json`, `probando-ia/`) no se tocan.
El modo borrador y la analítica se retiran: el laboratorio necesita el servidor Python.

### D2 · Cómo se mide la regla de los 30 segundos

| Opción | Ventajas | Limitaciones |
| --- | --- | --- |
| **A. Tiempo de juego simulado** ✔: 30 s = 30 × velocidad de movimiento de referencia (p. ej. 10 mov/s → 300 pasos en ciclo). En una partida en vivo a 1× coincide con el reloj; el reloj monotónico se usa para medir y mostrar el tiempo real activo (sin pausas) | Determinista y reproducible; no depende del ordenador ni del renderizado; no altera el aprendizaje al acelerar | En partidas aceleradas, “30 s” no son 30 s de pared |
| B. Reloj de pared literal siempre | Literal | A 50.000 pasos/s, 30 s = 1,5 millones de pasos en bucle; el resultado depende de la velocidad de la CPU: el mismo experimento da resultados distintos |

Recomiendo **A**: es la única forma de cumplir a la vez “no permitir que acelerar altere las reglas”
y la reproducibilidad.

### D3 · Longitud inicial y significado de E0

Con longitud inicial 3, en 4×4 la serpiente ya ocupa el 18,75 % (≥ C(E1) = 2) sin haber comido.

| Opción | Ventajas | Limitaciones |
| --- | --- | --- |
| **A. Longitud inicial 3 (cabeza, cuerpo, cola) en todos los tableros; E ≥ 1 exige haber comido al menos una manzana; E0 = no alcanzar E1 o terminar por la regla de los 30 s sin comer** ✔ | Cuerpo completo desde el inicio; ningún nivel se regala | En 4×4 la primera manzana salta de E0 a E2 (longitud 4) |
| B. Longitud inicial 2 + la misma condición | Progresión más fina en 4×4 | No hay “cuerpo” entre cabeza y cola al inicio |
| C. Longitud inicial 1 | Sin conflicto | Sin cuerpo ni cola; contradice el modelo del cuerpo |

### D4 · Origen de las etiquetas para los componentes ML y simbólico de CLARK y MABU

ARKIS aprende de etiquetas del usuario. Pero CLARK/MABU deben llegar preentrenados antes de
cualquier sesión, así que necesitan una fuente de datos reproducible:

| Opción | Ventajas | Limitaciones |
| --- | --- | --- |
| **A. Etiquetas por resultado del simulador** ✔: se juega con una política exploratoria registrada y se etiqueta cada acción por lo que **ocurrió de verdad** (colisión en ≤ k pasos, encierro, comer, acercarse). El componente ML aprende a *estimar* la calidad de cada acción; el simbólico induce reglas de esos hechos | Verdad objetiva del entorno, no opinión ni predicción del propio modelo; totalmente reproducible | Las etiquetas dependen de k y de la política exploratoria (ambas se documentan) |
| B. Planificador-maestro algorítmico (búsqueda A* + comprobación de cola) | Etiquetas de alta calidad | El modelo imita a un programa escrito a mano: su techo es ese programa |
| C. Solo demostraciones del usuario | Máxima participación humana | CLARK/MABU no podrían estar preentrenados al entregarse |

### D5 · Algoritmo de ARKIS

Recomiendo **Random Forest** (§5.1), con un árbol de decisión solo como vista explicativa.
Alternativa si se prioriza la legibilidad total: un único árbol de decisión.

---

## 10. Plan tras la aprobación (Etapa 2 en adelante)

| Etapa | Entregable verificable |
| --- | --- |
| 2 · Motor | `nucleo/` con tests: reglas, colisiones, crecimiento, victoria, sincronía matriz-segmentos, recompensa por componente, C(E_n) en las tres dificultades, detector de ciclos, reloj; líneas base azar/voraz medidas |
| 3 · Individuales | ARKIS, LERK, BORK, cada uno con test de independencia metodológica y evaluación con semillas |
| 4 · CLARK | Preentrenamiento + manifiesto + verificación de hash |
| 5 · MABU | Propuesta de arquitectura → aprobación → preentrenamiento → aprendizaje continuo |
| 6 · Laboratorio | Interfaz, persistencia completa, comparación, historial |
| 7 · Validación | Pruebas integrales, README, documentación técnica, manual del usuario, `CAMBIOS.txt` |
