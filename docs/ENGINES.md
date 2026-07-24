# 🧩 Motores de Red — arquitectura modular seleccionable

> El motor físico, las reglas del Snake, los **26 sensores** y el algoritmo genético son
> **siempre los mismos**. Lo único que cambia entre motores es la topología de la red neuronal y
> cómo su salida se traduce en un giro. Por eso el algoritmo genético no conoce ninguna
> arquitectura: opera sobre `get_weights()` (una lista de matrices) y reconstruye un hijo del
> **mismo** motor con `type(padre)(pesos_hijo)`. Añadir un motor nuevo es escribir una subclase de
> `Brain` — no se toca ni el simulador ni la evolución.

| Motor | Arquitectura | Enfoque | Pesos (ADN) | CPU | Mutación |
| --- | --- | --- | ---: | --- | --- |
| **`advanced`** | 26 → 16 → 3 | Feedforward compacto de 1 capa (LeakyReLU) | ≈ 483 | Baja-media | Rápida (espacio de búsqueda pequeño) |
| **`intermated`** | 26 → 20 → 3 (recurrente) | Algoritmo genético clásico · **por defecto** | ≈ 1.003 | Baja | Muy eficiente |
| **`basic`** | 26 → 52 → 26 → 1 | Teórico / expansivo | ≈ 2.809 | Alta | Lenta (más genes que ajustar) |

Todos comparten entrada (26) y acción de salida (`0` = recto, `1` = izquierda, `2` = derecha), así
que son intercambiables como cerebro de un `Snake`. El código vive en `snake_neuroevolution.py`
(clases `Brain`, `IntermatedNetwork`, `AdvancedNetwork`, `BasicNetwork` + registro `ENGINES`).

---

## 1. Análisis de Viabilidad — por qué funciona en el mundo real

Que una IA aprenda a jugar Snake por neuroevolución **no es una casualidad ni un truco**: se apoya
en resultados establecidos de optimización y aprendizaje automático.

- **Optimización sin gradiente.** Snake es un problema de control con recompensa dispersa (comer
  ocurre pocas veces y tarde). El descenso de gradiente necesita una señal diferenciable que aquí
  no existe de forma natural. Los **algoritmos genéticos** son un optimizador *black-box* diseñado
  justamente para ese régimen: no requieren derivadas, solo poder **evaluar** una política y
  **ordenarla** frente a otras. La neuroevolución (evolucionar los pesos de una red) es una familia
  con décadas de uso: control, robótica, antenas evolucionadas por la NASA y algoritmos como NEAT.

- **Capacidad de representación (teorema de aproximación universal).** Una red con una capa oculta
  suficiente puede aproximar cualquier función continua. La política que buscamos —de 26 sensores a
  un giro— es una de esas funciones, luego **es representable**. El GA no tiene que "inventar" nada
  imposible: solo encontrar, en el espacio de pesos, un punto que codifique una buena política.

- **El paisaje de fitness es navegable gracias al *shaping*.** Una recompensa que solo premie comer
  sería casi plana (la mayoría de partidas iniciales mueren sin comer), y la evolución avanzaría a
  ciegas. La **recompensa densa de acercamiento** convierte esa señal dispersa en un gradiente de
  fitness continuo —premia acercarse a la manzana, penaliza (algo más) alejarse—, de modo que hay
  una pendiente que subir desde el primer día. Es lo que hace el aprendizaje **empíricamente**
  rápido: un entrenamiento corto sube de N0 a N2–N3 (medido).

- **La percepción egocéntrica reduce el problema.** Los sensores son relativos a hacia dónde mira
  la serpiente y están **normalizados** por el tamaño del tablero. Eso da invarianza a traslación,
  rotación y escala: una política aprendida en 8×8 sigue siendo válida en 15×15. Reducir la
  dimensión efectiva del problema es precisamente lo que hace tratable la búsqueda evolutiva.

- **La selección + herencia es ascenso estocástico con memoria poblacional.** El elitismo conserva
  lo mejor (nunca se retrocede), el torneo presiona hacia lo bueno sin colapsar la diversidad, y la
  mutación adaptativa (recocido) pasa de explorar a afinar cuando la población se estanca. Es un
  optimizador robusto frente a óptimos locales pobres.

**Conclusión:** el problema es representable, el paisaje es navegable y el optimizador es adecuado
al régimen sin-gradiente. Por eso funciona — y por eso las cifras del proyecto son medibles, no
declarativas (ver `ARCHITECTURE.md`, Parte II).

---

## 2. Funcionamiento Técnico por Motor

Los tres reciben el mismo vector de 26 entradas `x` y devuelven una acción. La diferencia está en
las capas intermedias y en la traducción de la salida.

### `intermated` — recurrente 26 → 20 → 3 (por defecto)

```python
h = tanh_relu(W1 @ x + b1 + W_rec @ h_prev)   # la capa oculta ve su estado anterior
o = W2 @ h + b2
acción = argmax(o)                             # recto | izquierda | derecha
```

- **Cómo procesa:** una única capa oculta de 20 neuronas ReLU **con memoria**: `W_rec` realimenta
  el estado oculto del turno anterior, de modo que la red "recuerda por dónde venía" dentro de una
  partida. `W_rec` nace a cero (se comporta como *feedforward*) y la mutación la introduce poco a
  poco, así que la memoria no degrada lo aprendido.
- **Memoria / CPU:** el ADN más pequeño (≈ 1.000 pesos) → **CPU muy baja** por inferencia.
- **Impacto en la mutación:** menos genes = **espacio de búsqueda más pequeño** = el GA converge
  con menos evaluaciones. Es el motor más eficiente para evolucionar, y el único con especímenes
  previos (conserva la carga adaptativa que reescala modelos antiguos sin regresión).

### `advanced` — feedforward compacto de una capa 26 → 16 → 3

```python
h = leaky_relu(W1 @ x + b1)   # 16 neuronas
o = W2 @ h + b2               # 3 salidas
acción = argmax(o)            # recto | izquierda | derecha
```

- **Cómo procesa:** una **sola** capa oculta de 16 neuronas (LeakyReLU) mapea los 26 sensores a la
  decisión. Se simplificó desde la versión profunda anterior (26 → 16 → 16 → 3): en neuroevolución
  la profundidad **estorba** — cada capa extra agranda el espacio de búsqueda y la mutación compone
  ruido capa a capa, de modo que una red profunda evoluciona más lento y peor en tiempo limitado.
- **Memoria / CPU:** ≈ 483 pesos. El coste por paso lo domina la percepción (flood-fill), idéntica
  en los tres motores, no este forward; la ganancia real está en **más evaluaciones por segundo**.
- **Impacto en la mutación:** un espacio de búsqueda **pequeño** hace que el genético **converja con
  menos evaluaciones**; LeakyReLU evita neuronas muertas (que una red evolucionada no revive con
  facilidad). El problema de la versión profunda no era la CPU, era la evolvabilidad — y una sola
  capa la corrige. Ver [`CHANGELOG.md`](../CHANGELOG.md).

### `basic` — feedforward ancho 26 → 52 → 26 → 1

```python
h1 = relu(W1 @ x  + b1)              # 52 = el doble de la entrada (regla clásica)
h2 = relu(W2 @ h1 + b2)              # 26
v  = sigmoide(W3 @ h2 + b3)          # UNA sola salida, aplastada a [0, 1]
acción = izquierda si v < 1/3, derecha si v > 2/3, recto en otro caso
```

- **Cómo procesa:** sigue la regla teórica tradicional de que la primera capa oculta **duplica** la
  entrada. Con una única salida, el giro se decide por **rangos** sobre su valor.
- **Memoria / CPU:** el ADN más grande (≈ 2.809 pesos) → **CPU alta**.
- **Impacto en la mutación:** el espacio de búsqueda es enorme, así que el GA **muta más lento** (hay
  muchos más genes que ajustar) y es más propenso a la deriva. Su valor es teórico y comparativo:
  máxima expresividad, útil como referencia frente a los otros dos.

> **Regla general:** más pesos = más expresividad y más CPU, pero un espacio de búsqueda mayor que
> el GA tarda más en recorrer. `intermated` prioriza velocidad de evolución; `advanced`, calidad de
> política; `basic`, expresividad teórica.

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
