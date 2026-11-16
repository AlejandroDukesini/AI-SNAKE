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
