# IA-SNAKE — Manual de participación del usuario

Eres el director del laboratorio: tú etiquetas, escribes reglas, corriges, configuras y apruebas.
Este manual explica qué puedes hacer en cada pantalla.

## Arranque

```bash
pip install -r requirements.txt
npm install
npm run dev:all      # abre http://localhost:5173
```

## Pantallas

| Pestaña | Para qué |
| --- | --- |
| **Panel** | Los cinco modelos: metodología, estado con evidencia, versión, récord E por dificultad y última evaluación |
| **Simulador** | Observar a un modelo, demostrarle acciones o jugar tú. Muestra los tres sentidos, la explicación de cada decisión, la recompensa del último paso, el tiempo en ciclo y la escala E0–E8 |
| **Entrenamiento** | Un panel distinto para cada modelo, más la evaluación, el historial, las versiones y la exportación/importación |
| **Evolución** | Récord E0–E8 de cada modelo en cada dificultad |
| **Comparación** | Todos los modelos y las líneas base en las mismas partidas de prueba |
| **Documentación** | Resumen técnico dentro de la web |

## Simulador

- **Modo Observar:** elige modelo, dificultad, velocidad del juego y, si quieres, una semilla.
  «Reproducir» avanza a la velocidad del juego; ×2…×20 agrupa pasos por fotograma sin cambiar las
  reglas. «Pausar» detiene también el reloj de tiempo real activo.
- **Corregir:** en modo Observar, si no estás de acuerdo, pulsa la flecha correcta:
  - ARKIS → se guarda como ejemplo (pendiente de tu aprobación).
  - LERK → excepción Ripple-Down a la regla responsable (y regla nueva si hace falta).
  - CLARK → llega a su componente ML y a su componente simbólico; la tabla Q no se toca.
  - BORK → no admite correcciones: solo aprende de recompensas.
- **Capturar para ARKIS:** guarda la situación sin etiqueta, para etiquetarla después.
- **Modo Demostrar** (ARKIS o LERK): juegas con flechas o WASD; cada movimiento es un ejemplo
  etiquetado. Las acciones no disponibles (giro de 180°) están deshabilitadas.
- **Modo Jugar:** juegas sin guardar nada.

## Ver el entrenamiento en vivo

En Entrenamiento, el recuadro «Entrenamiento en vivo» muestra al modelo jugando mientras entrena
o se evalúa. Todo viene del servidor: es su decisión real en cada paso.

- **Antes de lanzar:** elige el ritmo (Máximo, 200, 50, 15 o 4 pasos/s). Ir más lento solo añade
  esperas: el modelo aprende exactamente lo mismo (hay una prueba que lo comprueba).
- **Mientras corre:** Pausar / Reanudar / Detener, cambiar el ritmo y el refresco de pantalla
  (Fluido, Normal o Ahorro; solo cambia cada cuánto se pide el último paso).
- **Qué verás:** el tablero; la acción y si se acerca, se aleja, come o choca; manzanas, longitud,
  ocupación, pasos y nivel E; la explicación según la metodología (probabilidades de ARKIS,
  cadena de reglas de LERK, valores Q antes y después de BORK, opinión de cada componente de
  CLARK y si su favorita habría chocado); la recompensa solo en BORK y CLARK; y la comparación
  entre episodios (gráfica, primeros frente a últimos, mejor episodio, tabla).

## ARKIS (Machine Learning)

0. En Entrenamiento → ARKIS, pestaña «Etiquetar», sigue los pasos guiados: observa la situación
   (cabeza, cuerpo, manzana, dirección y qué pasa con cada acción), elige la acción correcta y
   pulsa «Guardar ejemplo y mover» (o «Mover sin guardar» para saltar una situación).
1. También puedes crear ejemplos en el Simulador (Demostrar, Corregir o Capturar).
2. En Entrenamiento → ARKIS, revisa los ejemplos: cambia la etiqueta con las flechas, apruébalos o
   envíalos a la papelera (se pueden restaurar). Corregir una etiqueta exige volver a aprobarla.
3. Entrena: semilla, número de árboles y simetrías (8 variantes exactas de cada ejemplo).
4. Lee la validación: accuracy, precision, recall, F1, matriz de confusión. Los ejemplos mal
   clasificados aparecen en rojo en el filtro «Todos».
5. «Reentrenar y evaluar» (modo automático) usa solo lo ya aprobado. «Recopilar dudas» hace que
   ARKIS juegue y guarde sin etiqueta las situaciones donde duda.

Consejo: la validación necesita ejemplos de al menos 2 partidas distintas; con ~20 partidas
demostradas ya se ven resultados. Varía tu forma de jugar: ARKIS imitará lo que le enseñes.

## LERK (simbólico)

- **Crear regla:** pulsa predicados (verde = debe cumplirse, rojo = NO), elige conclusión, acción
  opcional, prioridad y, si es una excepción, su regla padre.
- **Modificar:** prioridad, activar/desactivar, eliminar (en cascada con sus excepciones).
- **Casos:** juega en Simulador → Demostrar con LERK.
- **Inducir reglas de mis casos**, **Validar** (exactitud y cobertura en tus casos),
  **Generalizar** (con tolerancia) y **Conflictos**.
- **Aprender jugando:** episodios con exploración ε; induce prohibiciones y preferencias de los
  resultados objetivos. Tus reglas y correcciones no se tocan.
- Cada cambio crea una versión: puedes volver a cualquier estado anterior.

## BORK (refuerzo)

- Ajusta α, γ, ε inicial/final, el decaimiento, la representación del estado y cada recompensa. Guarda.
- Entrena N episodios (dificultad, semilla, velocidad del juego). Sigue la curva (manzanas, retorno, ε).
- Inspecciona los estados más visitados de la tabla Q.
- «Reiniciar tabla» empieza de cero sin borrar las versiones anteriores. Para cambiar la
  representación del estado hay que reiniciar.

## CLARK (híbrido de referencia)

- Ajusta los pesos w_A, w_B, w_C, τ, α, γ y ε. Entrena en modo automático.
- En el Simulador verás, para cada acción, las tres opiniones, los vetos, la puntuación total y qué
  componentes estaban de acuerdo.

## Evaluar, versiones y datos

- **Evaluar:** partidas con semillas fijas de validación o prueba. El modelo pasa a «validado» si
  su IC 95 % supera al del azar en las mismas semillas.
- **Versiones:** restaurar cambia la versión actual sin borrar ninguna.
- **Exportar / Importar** (.zip con hashes). Un modelo ML importado queda bloqueado hasta que
  pulses «Confío en el origen del artefacto importado».
- **Copia de seguridad:** `laboratorio/_copias/`.

## Qué no hace el laboratorio (a propósito)

- No genera etiquetas de ARKIS con sus propias predicciones.
- No compara recompensas entre algoritmos.
- No presenta a MABU como existente: está pendiente de la Etapa 5.
