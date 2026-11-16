# ARKIS AI LAB — Etapa 2: motor, percepción, recompensas y evolución

> **Estado:** completada y verificada (motor 1.0.0). Rama `nucleo`.
> Reproducir: `python -m pytest` y `python scripts/lineas_base.py --episodios 100`.

## Qué se construyó

| Módulo | Contenido |
| --- | --- |
| `arkis_lab/nucleo/config.py` | Dificultades 4×4 (long. inicial 1), 8×8 y 16×16 (long. inicial 3); velocidad por defecto 10 mov/s |
| `nucleo/motor.py` | `Partida`: movimiento, crecimiento, manzanas con RNG propio, colisión con límite/cuerpo/cuello, victoria sin nueva manzana. `resolver_movimiento` es la **única** definición de las reglas de colisión (la usan motor y percepción) |
| `nucleo/percepcion.py` | Los tres sentidos como instantánea inmutable. Cuerpo: matriz binaria de solo lectura + segmentos ordenados + acciones disponibles + colisión, espacio alcanzable y cola alcanzable por acción. Manzana: x, y, Δx, Δy, dirección relativa, Manhattan. Muros: distancia a los cuatro límites, colisión con límite por acción, espacio libre |
| `nucleo/recompensas.py` | Recompensa configurable con 8 componentes devueltos por separado (Δd, manzana, colisión, supervivencia, repetición, exploración, victoria, fin por ciclo) |
| `nucleo/ciclos.py` | Detector: configuración repetida, posiciones repetidas y secuencia periódica; explorar casillas nuevas cuenta como progreso |
| `nucleo/reloj.py` | Reloj de simulación (pasos / velocidad) y reloj de sesión monotónico sin pausas |
| `nucleo/evolucion.py` | C(E_n) = techo(n·N/8) en aritmética entera; nivel con condición de haber comido; récord histórico por modelo × dificultad que nunca baja |
| `nucleo/entorno.py` | Episodio completo: aplica la regla de los 30 s y un límite técnico (100·N pasos sin manzana, causa distinta). Sin algoritmos de aprendizaje |
| `evaluacion/` | Semillas disjuntas (entrenamiento / validación / prueba), IC 95 % con t de Student, líneas base sin aprendizaje |

Umbrales E_n en casillas: 4×4 → 2, 4, …, 16 · 8×8 → 8, 16, …, 64 · 16×16 → 32, 64, …, 256.

## Evidencia: 51 pruebas, todas pasan

- **Reglas:** colisión con los cuatro límites, con el cuerpo y con el cuello; giro de 180° permitido
  solo con longitud 1; entrar en la cola es legal si no se come; crecimiento; victoria en 4×4 con
  `manzana = None` y partida cerrada.
- **E8 alcanzable en las tres dificultades (prueba constructiva):** una política que sigue un ciclo
  hamiltoniano gana en 4×4, 8×8 y 16×16 dentro del entorno completo, y el detector de ciclos no la
  interrumpe porque siempre recorre casillas nuevas.
- **Percepción:** matriz y segmentos sincronizados en 60 partidas aleatorias; la colisión predicha
  por la percepción coincide con la del motor para cada acción en 30 partidas; ejemplos exactos de
  los tres sentidos; detección de encierro.
- **Ciclos:** un bucle de 2×2 termina por `ciclo` exactamente tras 300 pasos en ciclo a 10 mov/s
  (30 s de juego) y tras 600 a 20 mov/s; el reloj de sesión no cuenta las pausas.
- **Reproducibilidad:** misma semilla + mismas acciones = misma partida; la evaluación se repite
  idéntica.
- **Arquitectura:** una prueba analiza los imports de `nucleo/` y falla si depende de modelos,
  servidor, persistencia, evaluación o entrenamiento.

## Líneas base medidas (sin aprendizaje; 100 semillas de prueba 2000000–2000099)

| Dificultad | Política | Manzanas media [IC 95 %] | Mediana | Ocupación máx. media | Mejor E | Victorias |
| --- | --- | --- | ---: | ---: | :---: | ---: |
| 4×4 | azar | 0,26 [0,17; 0,35] | 0 | 7,9 % | E1 | 0 |
| 4×4 | voraz | 10,68 [10,20; 11,16] | 11 | 73,0 % | E8 | 8 |
| 8×8 | azar | 0,19 [0,10; 0,28] | 0 | 5,0 % | E0 | 0 |
| 8×8 | voraz | 18,46 [17,37; 19,55] | 18 | 33,5 % | E4 | 0 |
| 16×16 | azar | 0,10 [0,04; 0,16] | 0 | 1,2 % | E0 | 0 |
| 16×16 | voraz | 31,73 [29,27; 34,19] | 31,5 | 13,6 % | E2 | 0 |

La regla voraz solo evita la colisión inmediata, así que se encierra: muere contra su cuerpo en la
mayoría de partidas. Es la referencia que un modelo debe superar para afirmar que aprendió algo
más que acercarse a la manzana.

## Rendimiento

El perfilado mostró que el 95 % del tiempo se iba en el flood-fill, sobre todo en leer
`Accion.dx/dy` (propiedades de `Enum`). Con atributos directos y un BFS sobre índices planos, la
evaluación voraz en 16×16 pasó de 160 s a 28 s, con resultados idénticos en las 600 partidas.

## Limitaciones conocidas

- El espacio alcanzable es conservador: trata como obstáculo todo el cuerpo salvo la cabeza,
  aunque la cola se irá liberando.
- Velocidad de entrenamiento y de renderizado se implementan en el servidor (Etapa 6); el núcleo
  ya garantiza que no afectan a las reglas.
