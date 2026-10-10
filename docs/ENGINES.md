# 🧩 Motores de Red — arquitectura modular seleccionable

> El motor físico, las reglas del Snake, los **26 sensores** y el algoritmo genético son
> **siempre los mismos**. Lo único que cambia entre motores es la topología de la red neuronal y
> cómo su salida se traduce en un giro. Por eso el algoritmo genético no conoce ninguna
> arquitectura: opera sobre `get_weights()` (una lista de matrices) y reconstruye un hijo del
> **mismo** motor con `type(padre)(pesos_hijo)`. Añadir un motor nuevo es escribir una subclase de
> `Brain` — no se toca ni el simulador ni la evolución.

| Motor | Arquitectura | Enfoque | Pesos (ADN) |
| --- | --- | --- | ---: |
| **`advanced`** | 26 → 16 → 3 | Feedforward de 1 capa oculta (LeakyReLU) | 483 |
| **`intermated`** | 26 → 20 → 3 (recurrente) | Capa oculta ReLU con memoria `W_rec` · **por defecto** | 1.003 |
| **`basic`** | 26 → 52 → 26 → 1 | Feedforward ancho, una salida por rangos | 2.809 |
| `advanced_v1` | 26 → 32 → 16 → 3 | **Solo carga**: versión anterior de `advanced` | 1.443 |

Todos comparten entrada (26) y acción de salida (`0` = recto, `1` = izquierda, `2` = derecha), así
que son intercambiables como cerebro de un `Snake`. El código vive en `snake_neuroevolution.py`
(clases `Brain`, `IntermatedNetwork`, `AdvancedNetwork`, `BasicNetwork`, `AdvancedV1Network` +
registros `ENGINES` y `LEGACY_ENGINES`).

> El coste por paso lo domina la percepción (*flood-fill*), idéntica en los tres motores, no el
> forward de la red; por eso la tabla no clasifica la CPU. Qué motor aprende mejor **no está
> demostrado**: con las muestras medidas `advanced` e `intermated` no se distinguen y `basic` queda
> por debajo (ver [`auditoria-cientifica-ia.md`](auditoria-cientifica-ia.md)).

---

## 1. Fundamento y estado real

Qué respalda el método y qué no está demostrado (detalle y referencias en la auditoría):

- **Optimización sin gradiente.** Un algoritmo genético solo necesita **evaluar** y **ordenar**
  políticas, sin derivadas. Evolucionar los pesos de una red es un método establecido (Such et al.,
  2017, *Deep Neuroevolution*; Stanley y Miikkulainen, 2002, NEAT).
- **Representabilidad.** El teorema de aproximación universal (Cybenko 1989; Hornik 1991) garantiza
  que *existe* una red capaz de aproximar una función continua; no que el GA la encuentre ni que 16–20
  neuronas basten. Como diagnóstico, una red `advanced` entrenada para imitar la regla voraz de
  referencia acierta ~98 % de sus decisiones, pero solo logra ~2/3 de sus frutas.
- **Shaping.** La recompensa de acercamiento (+3 / −4) junto al +1 por paso da una señal a quien aún
  no come, pero **premia dar vueltas** (+0,5 por paso en un bucle). Una alternativa basada en
  potencial (Ng, Harada y Russell, 1999) no rindió mejor, así que se conserva la original.
- **Percepción egocéntrica.** Los sensores son invariantes a rotación (verificado), **no a escala**:
  estar a una casilla de la pared vale 0,125 en 8×8 y 0,067 en 15×15. Una política transfiere
  parcialmente entre tableros, con otro rendimiento.
- **Evaluación con azar.** La posición de la manzana es aleatoria, así que una sola partida dice poco
  de un cerebro. La selección usa **3 partidas con semillas comunes** por individuo; el cerebro que
  se guarda es el mejor en **10 semillas de validación fijas**, y su rendimiento se informa en **20
  semillas de prueba** que no intervienen en ninguna decisión.

**Estado medido:** el sistema aprende (muy por encima del azar), pero **sigue por debajo de una regla
voraz sin aprendizaje** (acercarse a la manzana evitando la muerte inmediata). Las cifras, intervalos
y semillas están en [`auditoria-cientifica-ia.md`](auditoria-cientifica-ia.md).

---

## 2. Funcionamiento Técnico por Motor

Los tres reciben el mismo vector de 26 entradas `x` y devuelven una acción. La diferencia está en
las capas intermedias y en la traducción de la salida.

### `intermated` — recurrente 26 → 20 → 3 (por defecto)

```python
h = relu(W1 @ x + b1 + W_rec @ h_prev)        # la capa oculta ve su estado anterior
o = W2 @ h + b2
acción = argmax(o)                             # recto | izquierda | derecha
```

- **Cómo procesa:** una única capa oculta de 20 neuronas ReLU **con memoria**: `W_rec` realimenta
  el estado oculto del turno anterior, de modo que la red "recuerda por dónde venía" dentro de una
  partida. `W_rec` nace a cero (se comporta como *feedforward*) y la mutación la introduce poco a
  poco, así que al nacer decide igual que una feedforward.
- **Pesos:** 1.003. El estado oculto se acota a `H_MAX` = 10⁶ para que una `W_rec` expansiva no
  desborde a inf/NaN (los estados medidos en especímenes reales no pasan de ~10).
- **Compatibilidad:** es el único motor con especímenes de versiones anteriores. Las redes antiguas
  de 9 o 10 entradas se cargan colocando cada peso en la posición de su mismo sensor: deciden igual
  que la red original (verificado en los 18 modelos de `mejores_ias.json`). Formas que no se pueden
  convertir sin cambiar el comportamiento se rechazan con un error explícito.

### `advanced` — feedforward compacto de una capa 26 → 16 → 3

```python
h = leaky_relu(W1 @ x + b1)   # 16 neuronas
o = W2 @ h + b2               # 3 salidas
acción = argmax(o)            # recto | izquierda | derecha
```

- **Cómo procesa:** una **sola** capa oculta de 16 neuronas (LeakyReLU) mapea los 26 sensores a la
  decisión. Se simplificó desde la versión profunda anterior (26 → 32 → 16 → 3) con la hipótesis de
  que menos pesos facilitan la búsqueda; esa hipótesis no está medida frente a la versión anterior.
- **Pesos:** 483. LeakyReLU evita que una neurona quede a cero para siempre.
- **Versión anterior (`advanced_v1`):** los especímenes guardados con 26 → 32 → 16 → 3 se cargan con
  sus pesos reales y deciden igual que el código de `81aa744` (verificado). Antes se sustituían en
  silencio por una red aleatoria. Al continuar su linaje conservan esa arquitectura. Ver
  [`CHANGELOG.md`](../CHANGELOG.md).

### `basic` — feedforward ancho 26 → 52 → 26 → 1

```python
h1 = relu(W1 @ x  + b1)              # 52 = el doble de la entrada (regla clásica)
h2 = relu(W2 @ h1 + b2)              # 26
v  = sigmoide(W3 @ h2 + b3)          # UNA sola salida, aplastada a [0, 1]
acción = izquierda si v < 1/3, derecha si v > 2/3, recto en otro caso
```

- **Cómo procesa:** sigue la regla teórica tradicional de que la primera capa oculta **duplica** la
  entrada. Con una única salida, el giro se decide por **rangos** sobre su valor.
- **Pesos:** 2.809, el espacio de búsqueda más grande. La sigmoide recorta su entrada a ±500 antes
  de `exp` (evita el desbordamiento sin cambiar ninguna decisión).
- **Medido:** en entrenamientos cortos con varias semillas rinde por debajo de los otros dos motores
  (ver la auditoría). No se ha medido en entrenamientos largos.

---

## 3. Guía de Uso — cómo alternar entre motores

**Desde la aplicación** (`npm run dev`):

1. Ve a la vista **Entrenar IA**.
2. Escribe un **nombre nuevo** (un espécimen desde cero).
3. En **Motor de red**, elige `Advanced`, `Intermated` o `Basic`. Debajo verás su arquitectura y su
   perfil de CPU / mutación.
4. Ajusta agentes, generaciones y herencias, y pulsa **Entrenar**.

- **Continuar un linaje** conserva su motor: si el nombre ya existe, el selector se bloquea y
  muestra la arquitectura heredada. No se puede cambiar la arquitectura de una IA a medias sin tirar
  lo aprendido (los pesos de una topología no encajan en otra).
- El **Historial** muestra el motor de cada espécimen (`· motor advanced`).
- La documentación interactiva de los motores está también **dentro de la app**, en la vista
  **Documentación → El Cerebro**.

**Desde la API** (para scripts o integraciones):

```jsonc
// WebSocket /ws/train — primer mensaje
{ "action": "start", "nombre": "Mi-IA-Nueva", "engine": "advanced",
  "generations": 30, "agents": 50, "elite": 3, "grid": 8 }
```

```bash
# Motores disponibles y el de por defecto
GET /api/config   ->   { "engines": [...], "default_engine": "intermated" }
```

**Desde Python** (directo al núcleo):

```python
import snake_neuroevolution as ml
resultado = ml.train(generations=30, pop_size=50, engine="advanced")
print(resultado["engine"])        # 'advanced'
```
