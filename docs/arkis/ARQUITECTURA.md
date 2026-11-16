# ARKIS AI LAB — Documentación técnica

> Describe el código tal como está. Las decisiones del director están en
> [DECISIONES.md](DECISIONES.md); el análisis inicial, en [ETAPA-1-ANALISIS.md](ETAPA-1-ANALISIS.md);
> la evidencia del motor, en [ETAPA-2-MOTOR.md](ETAPA-2-MOTOR.md).

## 1. Capas

```
src/ (React)  ──REST──▶  arkis_lab/servidor  ──▶  modelos/{arkis,lerk,bork,clark}  ──▶  nucleo/
  solo dibuja            sesiones, trabajos          cada uno con su entrenador          reglas puras
                                │                              │
                         persistencia/  ◀──────────────────────┘     evaluacion/ (semillas, IC 95 %)
```

- **`nucleo/`** no importa nada del resto (lo comprueba `test_el_nucleo_no_depende_de_modelos_ni_servidor`).
- **Modelos:** solo comparten la forma de actuar (`Agente.decidir(percepcion) -> Decision`). No hay un
  método de entrenamiento común: cada servicio tiene los suyos.
- **CLARK** reutiliza el **código** de los algoritmos de LERK (motor simbólico) y BORK (tabla Q),
  pero tiene **sus propias** instancias, datos y artefactos (`test_clark_no_comparte_nada_con_lerk_ni_bork`).

## 2. Núcleo

| Módulo | Responsabilidad |
| --- | --- |
| `config.py` | Dificultades (4×4 long. 1, 8×8 long. 3, 16×16 long. 3), velocidad por defecto 10 mov/s, 30 s |
| `motor.py` | `Partida`; `resolver_movimiento` es la única definición de las colisiones (la usan motor y percepción) |
| `percepcion.py` | `percibir(partida)` → `Percepcion` inmutable con los tres sentidos. Flood-fill perezoso sobre índices planos |
| `recompensas.py` | `ConfigRecompensa` y `calcular_recompensa` → total + 8 componentes |
| `ciclos.py` | Detector: configuración repetida, posiciones repetidas, secuencia periódica (solo sin casillas nuevas) |
| `reloj.py` | `RelojSimulacion` (pasos/velocidad, para la regla de 30 s) y `RelojSesion` (monotónico, sin pausas) |
| `evolucion.py` | `umbral_casillas(n, N) = techo(n·N/8)`, nivel con condición de haber comido, `RecordHistorico` |
| `entorno.py` | Episodio completo: aplica ciclo (30 s de juego) y límite técnico (100·N pasos sin manzana) |

## 3. Modelos

### ARKIS (`modelos/arkis/`)
- `caracteristicas.py`: 27 rasgos (6 por acción + Δx, Δy, ocupación) y `transformar_caracteristicas`
  (simetría aplicada al vector, exacta respecto a recalcular desde el tablero transformado).
- `clasificador.py`: `entrenar()` con validación `GroupKFold` por episodio (aumento solo dentro de
  cada pliegue), métricas fuera de pliegue, importancias y árbol explicativo de profundidad 4.
  `ArkisAgente` enmascara las acciones no disponibles.
- `servicio.py`: versiones (`modelo.skops`, `metricas.json`, `arbol.txt`, `dataset.json`), modo
  automático (reentrena con lo aprobado y evalúa) y recopilación activa sin etiquetar.
- Las etiquetas vienen solo del usuario (`modelos/ejemplos.py`: orígenes demostración, captura y
  corrección; corregir exige volver a aprobar; papelera).

### LERK (`modelos/lerk/`)
- `predicados.py`: 10 predicados por acción candidata X.
- `conocimiento.py`: `Regla` (condiciones, conclusión preferir/prohibir/anular, acción opcional,
  prioridad, origen, padre, soporte/aciertos → confianza de Laplace), `BaseConocimiento` e inferencia
  con la resolución de conflictos documentada en el propio módulo.
- `aprendizaje.py`: `inducir` (cobertura secuencial), `aprender_de_experiencia` (resultados del
  simulador con horizonte K = 4), `corregir` (Ripple-Down Rules con lista de diferencias),
  `generalizar` (eliminación de condiciones con tolerancia), `validar`, `conflictos`.
- Cada modificación de la base crea una versión (`base.json`).

### BORK (`modelos/bork/`)
- `qlearning.py`: estado `peligro|encierro|cola|manzana` (o `peligro|manzana` en la ablación),
  `TablaQ` dispersa con visitas y estadística de retornos por (s,a) (Welford) para medir el aliasing,
  `entrenar_episodio` (el límite técnico se trata como truncamiento, con bootstrap).
- `servicio.py`: configuración validada, curva por episodio, inspección de la tabla, reinicio sin
  borrar versiones.

### CLARK (`modelos/clark/`)
- `hibrido.py`: `rasgos_accion` (8 rasgos), `ConfigClark` (pesos, τ, α, γ, ε), `ClarkAgente` con la
  integración: vetos de B → restricción por conocimiento del usuario → w_A·P + w_B·pref + w_C·softmax(Q/τ).
- `servicio.py`: entrenamiento automático (Q en línea; RF y reglas por bloques sobre la experiencia
  etiquetada por resultados objetivos) y corrección manual (llega a A y B, nunca a C).

### Utilidades
- `bosque_rapido.py`: recorre los árboles de un `RandomForestClassifier` ya entrenado; da
  probabilidades idénticas a `predict_proba` (prueba con igualdad exacta) y es ~20× más rápido para
  pocas filas. El artefacto guardado sigue siendo el modelo de scikit-learn.
- `situacion.py`: tablero serializable y las 8 simetrías del cuadrado.

## 4. Persistencia (`persistencia/`)

```
laboratorio/<modelo>/manifiesto.json     versión actual, estado, lista de versiones
                    versiones/vNNNN/      artefactos + meta.json (SHA-256, motivo, métricas, padre)
                    datos/*.json          datos de trabajo (+ .bak)
                    registros.sqlite      episodios · sesiones · record · eventos
laboratorio/_copias/                      copias de seguridad .zip
```

Escritura atómica (temporal + `os.replace`). Si un hash no cuadra o falta un archivo, se usa la
versión válida anterior y se registra un evento de recuperación. Si el manifiesto está corrupto, se
reconstruye desde las versiones. La importación añade versiones nuevas y no borra nada. Con skops,
`sklearn.tree._tree.Tree` se acepta solo con el hash verificado; los artefactos importados exigen
confirmación explícita (`/api/modelos/{m}/confiar`).

## 5. Servidor (`servidor/`)

- `sesiones.py`: modos observar / demostrar / jugar. Cada fotograma incluye la partida, la
  percepción completa, la decisión con su explicación, el último paso (recompensa por componentes,
  ciclo), la evolución (nivel actual, máximo de la partida, umbrales, récord) y los tiempos (de juego,
  real activo, en ciclo).
- `trabajos.py`: un trabajo en segundo plano por modelo, con progreso y cancelación.
- `app.py`: API REST. Rutas comunes (`/api/modelos/*`, `/api/trabajos/*`, `/api/comparar`,
  `/api/sesiones/*`) y específicas (`/api/arkis/*`, `/api/lerk/*`, `/api/bork/*`, `/api/clark/*`).

## 6. Evaluación (`evaluacion/`)

Semillas disjuntas: entrenamiento 0…, validación 1 000 000…, prueba 2 000 000…. `estadistico`
calcula media, mediana, desviación típica e IC 95 % con t de Student. Las líneas base (azar y voraz
segura) no aprenden y sirven de referencia. La comparación usa solo métricas de juego.

## 7. Pruebas

`python -m pytest` (108 pruebas). Por capa: motor, percepción, recompensas/evolución,
entorno/ciclos, persistencia, ARKIS, LERK, BORK, CLARK y servidor. Las pruebas de aprendizaje
comprueban, para cada metodología, que el modelo sin entrenar no sabe jugar y que, tras entrenar con
su propio mecanismo, su IC 95 % supera al del azar en semillas de validación.
