# IA-SNAKE — Resultados medidos

> Reproducir: `python scripts/medir_modelos.py --dificultad medio` (y `--dificultad facil`).
> Cada modelo se entrena **desde cero** en un directorio temporal con semillas fijas y se evalúa en
> 50 partidas con semillas de **prueba** (2 000 000–2 000 049) que nunca se usan para entrenar.
> Dos ejecuciones dieron cifras idénticas. Fecha: 2026-11-16 · motor 1.0.0.

## 8×8 (Medio)

| Modelo | Entrenamiento | Manzanas media [IC 95 %] | Mediana | Mejor E | Victorias |
| --- | --- | --- | ---: | :---: | ---: |
| Línea base: azar | sin aprendizaje | 0,22 [0,09; 0,35] | 0 | E0 | 0 |
| Línea base: voraz | sin aprendizaje | 18,98 [17,30; 20,66] | 18 | E4 | 0 |
| ARKIS | 3 828 ejemplos de un profesor sintético | 17,42 [15,93; 18,91] | 18 | E4 | 0 |
| LERK sin entrenar | base vacía | 0,22 [0,09; 0,35] | 0 | E0 | 0 |
| **LERK** | 100 episodios de experiencia | **44,26 [41,58; 46,94]** | 45 | **E8** | 2 |
| BORK | 1 500 episodios de Q-Learning | 20,02 [18,43; 21,61] | 19,5 | E4 | 0 |
| CLARK | 300 episodios | 21,40 [19,69; 23,11] | 20,5 | E5 | 0 |

## 4×4 (Fácil)

| Modelo | Entrenamiento | Manzanas media [IC 95 %] | Mediana | Mejor E | Victorias |
| --- | --- | --- | ---: | :---: | ---: |
| Línea base: azar | sin aprendizaje | 0,10 [0,02; 0,18] | 0 | E1 | 0 |
| Línea base: voraz | sin aprendizaje | 10,60 [9,90; 11,30] | 11 | E8 | 3 |
| ARKIS | 985 ejemplos de un profesor sintético | 10,42 [9,75; 11,09] | 10,5 | E8 | 5 |
| LERK | 100 episodios de experiencia | 8,50 [7,84; 9,16] | 8 | E8 | 5 |
| BORK | 1 500 episodios | 10,18 [9,54; 10,82] | 10 | E8 | 1 |
| CLARK | 300 episodios | 11,02 [10,23; 11,81] | 11 | E8 | **10** |

## Lectura

- **Todos los modelos aprenden con su propia metodología**: sin entrenar no superan al azar, y
  después lo superan con intervalos que no se solapan.
- **ARKIS imita a su profesor.** Con la política voraz como «usuario» sintético, queda a su altura
  (17,4 frente a 19,0 en 8×8, con IC solapados). Con tus etiquetas reflejará tu forma de jugar: esta
  cifra solo verifica que el mecanismo aprende, no la calidad de tus etiquetas.
- **LERK en 8×8 es el resultado más fuerte, y tiene una explicación concreta.** De su experiencia
  indujo, con confianza 0,99, la regla «SI NO cola_alcanzable(X) ENTONCES prohibir X», además de
  preferencias por acercarse lejos de los bordes. Es la heurística conocida de «voraz + seguridad
  de cola». La adquirió solo, a partir de resultados del simulador, pero **su fuerza depende del
  predicado `cola_alcanzable`, que calcula la percepción**: LERK aprendió a usarlo, no lo inventó.
  En 4×4 rinde menos que la voraz en media: allí ese veto es demasiado conservador.
- **BORK y CLARK** superan ligeramente a la voraz en 8×8 (IC solapados: diferencia no
  concluyente). CLARK es el más regular en 4×4 (10 victorias de 50).
- **E8:** se alcanza en 4×4 con todos los modelos entrenados; en 8×8 solo LERK (2 de 50).
  16×16 no se ha medido con entrenamiento completo (es lento en Python puro).

## Límites de estas cifras

- Un solo entrenamiento por modelo (semilla 0): no mide la variación entre entrenamientos.
- Presupuestos de entrenamiento distintos por modelo (son metodologías distintas); las cifras
  comparan resultados de juego, no eficiencia.
- Las recompensas no se comparan entre modelos.
