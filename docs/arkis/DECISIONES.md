# ARKIS AI LAB — Decisiones aprobadas

Registro de decisiones del director del proyecto. Prevalecen sobre la especificación v2.0
cuando la modifican. No se reabren sin una nueva instrucción.

| # | Fecha | Decisión | Efecto en el código |
| --- | --- | --- | --- |
| D0 | 2026-11-16 | **Difícil = 16×16 (256 casillas)** en lugar de 15×15 (225). Un tablero par admite un ciclo hamiltoniano: existe una estrategia que siempre gana y E8 es demostrable. *(En 15×15 completar no era imposible —basta un camino hamiltoniano—, pero no existe ciclo que garantice la victoria.)* | `nucleo/config.py`; `test_e8_es_alcanzable_en_las_tres_dificultades` |
| D1 | 2026-11-16 | **Flujo de ramas:** una rama por pieza (`nucleo`, `arkis`, `lerk`, `bork`, `clark`, `mabu`, …). Cuando la pieza funciona y sus pruebas pasan se fusiona en `Beta`; de `Beta`, tras las pruebas integrales, pasa a `Principal` (producción). El código de neuroevolución queda en la etiqueta `v2-neuroevolucion`; los datos locales (`historial/`, `mejores_ias.json`, `probando-ia/`) no se tocan. | Proceso de git |
| D2 | 2026-11-16 | **Regla de los 30 s en tiempo de juego:** límite = 30 × velocidad de movimiento (mov/s). Acelerar el entrenamiento o el renderizado no la altera. El reloj monotónico solo mide el tiempo real activo (sin pausas). | `nucleo/reloj.py`, `nucleo/entorno.py` |
| D3 | 2026-11-16 | **Longitud inicial 1 en Fácil (4×4)**; 3 en Medio y Difícil. E ≥ 1 exige haber comido al menos una manzana. Con longitud 1 se permite girar 180° (no hay cuello). | `nucleo/config.py`, `nucleo/evolucion.py` |
| D4 | 2026-11-16 | **CLARK no se preentrena**: empieza sin entrenar y se entrena como los demás. **Solo MABU se preentrena, al final.** Prioridad: ARKIS, LERK, BORK y CLARK listos para entrenar. | Plan de etapas |
| D5 | 2026-11-16 | **ARKIS usa Random Forest**; un árbol de decisión solo como vista explicativa. | Etapa 3 |

## Notas de diseño tomadas durante la implementación

Decisiones técnicas que no cambian la especificación, documentadas para que puedan revisarse.

| Fecha | Nota |
| --- | --- |
| 2026-11-16 | Los paneles de entrenamiento se construyeron en la rama `laboratorio` (junto con el servidor), no en cada rama de modelo: comparten la misma aplicación React y así se evitaron conflictos entre ramas. Cada modelo sí llegó a `Beta` con sus pruebas. |
| 2026-11-16 | CLARK reutiliza el **código** de los algoritmos de LERK y BORK, nunca sus instancias, reglas, tablas ni datos (hay una prueba que lo verifica). |
| 2026-11-16 | Integración de CLARK, paso 1b: si una regla del usuario o una corrección suya prefiere acciones permitidas, la elección se limita a ellas. Sin esto, con pesos fijos, una corrección apenas influía frente a la tabla Q y CLARK no cambiaba de decisión. |
| 2026-11-16 | BORK usa las 4 acciones absolutas (como pide la especificación), no acciones relativas. Con longitud 1 se permite girar 180°. |
| 2026-11-16 | El «resultado bueno» que usan LERK (experiencia) y CLARK-A es: no morir en ≤ 4 pasos y (comer o acercarse). Es un criterio objetivo del simulador, nunca una predicción del modelo. |
| 2026-11-16 | Los modelos de scikit-learn se guardan con skops; `sklearn.tree._tree.Tree` solo se acepta con el hash verificado o con tu confirmación si es importado. |
