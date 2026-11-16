/* Documentación dentro del laboratorio. Resume docs/ del repositorio. */
import { Panel } from '../components/ui';

const SECCIONES = [
  ['Ver el entrenamiento en vivo', <>
    <p>En Entrenamiento verás al modelo jugar mientras entrena o se evalúa. Cada movimiento es su <b>decisión real</b>, enviada por el servidor; no hay animaciones simuladas. Se muestran su explicación, si se acerca o se aleja de la manzana, las colisiones, las manzanas, la longitud, la ocupación, el nivel E, la recompensa (solo en BORK y CLARK) y la comparación entre episodios.</p>
    <p>Puedes pausar, reanudar, detener y cambiar el ritmo (pasos por segundo). El ritmo solo añade esperas entre pasos: el modelo aprende exactamente lo mismo. El refresco de pantalla es independiente.</p>
  </>],
  ['Qué es IA-SNAKE', <>
    <p>Un laboratorio donde cinco modelos resuelven el mismo Snake con metodologías de aprendizaje distintas: <b>ARKIS</b> (Machine Learning supervisado), <b>LERK</b> (aprendizaje simbólico), <b>BORK</b> (aprendizaje por refuerzo), <b>CLARK</b> (híbrido de referencia) y <b>MABU</b> (híbrido experimental, pendiente de la Etapa 5).</p>
    <p>El servidor Python es la única autoridad: reglas, percepción, recompensas, evolución y modelos viven allí. La web solo dibuja y envía tus decisiones. Ningún modelo usa redes neuronales ni Deep Learning.</p>
  </>],
  ['Entorno', <>
    <p>Tableros: Fácil 4×4 (16 casillas, longitud inicial 1), Medio 8×8 (64, longitud 3) y Difícil 16×16 (256, longitud 3). El difícil es par por decisión del director: así existe un recorrido que siempre gana y E8 es demostrable (hay una prueba automática que lo demuestra en los tres tableros).</p>
    <p>Chocar con un límite o con el cuerpo termina la partida. Con longitud ≥ 2, girar 180° es chocar con el cuello. Al ocupar todas las casillas se declara la victoria y no aparece otra manzana.</p>
    <p>Velocidades separadas: <b>velocidad del juego</b> (mov/s; define el tiempo de juego), <b>velocidad de entrenamiento</b> (sin dibujar, tan rápido como permita la CPU), <b>aceleración del render</b> (×1…×20 agrupa pasos por fotograma) y <b>tiempo real activo</b> (reloj monotónico, sin pausas). Ninguna altera las reglas ni el aprendizaje.</p>
  </>],
  ['Los tres sentidos', <>
    <p><b>Cuerpo:</b> matriz binaria (0 libre, 1 ocupada) sincronizada con la lista ordenada de segmentos; cabeza, cola, longitud, dirección, casillas libres, acciones disponibles y, por acción, colisión, espacio alcanzable y si la cola es alcanzable.</p>
    <p><b>Manzana:</b> coordenadas, Δx, Δy, dirección relativa y distancia Manhattan d = |x_m − x_c| + |y_m − y_c|. Es visible para todos: no se predice.</p>
    <p><b>Muros:</b> distancia a cada límite, colisión inmediata con límite por acción y espacio libre.</p>
  </>],
  ['Recompensa (solo para los componentes de refuerzo)', <>
    <p>Común para BORK, CLARK-C y MABU: manzana +10, colisión −10, distancia 0,1·Δd (Δd = d_anterior − d_actual), supervivencia −0,01 por paso, configuración repetida −0,5, casilla nueva +0,02, victoria +50, fin por ciclo −5. Cada componente se registra por separado y todo es configurable en el panel de BORK. Acercarse nunca compensa un choque, así que el modelo puede aprender a no ir en línea recta cuando eso lo encierra. ARKIS y LERK nunca reciben actualizaciones Q.</p>
  </>],
  ['Ciclos y regla de los 30 segundos', <>
    <p>El detector marca «en ciclo» si, desde la última manzana, se repite la configuración completa (cuerpo + manzana), o si en una ventana no hay casillas nuevas y hay pocas posiciones distintas o una secuencia periódica de acciones. Explorar casillas nuevas sin comer no es un ciclo.</p>
    <p>La partida termina tras 30 s de <b>tiempo de juego</b> en ciclo: 30 × velocidad del juego en pasos (300 a 10 mov/s). Así es reproducible y no depende del ordenador. Hay además un límite técnico de seguridad (100·N pasos sin manzana) con causa propia.</p>
  </>],
  ['Evolución E0–E8', <>
    <p>Ocupación = longitud / casillas × 100. C(E_n) = techo(n·N/8). E1…E8 = 12,5 % … 100 %. Llegar a E1 o más exige haber comido al menos una manzana. El récord histórico (mejor nivel de cualquier episodio) se guarda por modelo y dificultad y nunca baja.</p>
  </>],
  ['ARKIS · Machine Learning supervisado', <>
    <p><b>Random Forest</b> (scikit-learn) sobre 27 características calculadas de los tres sentidos. Una <b>etiqueta</b> es la respuesta que le das al modelo: la acción correcta en una situación. ARKIS solo aprende de etiquetas tuyas: el etiquetado guiado (Entrenamiento → ARKIS → Etiquetar), las demostraciones del Simulador, las correcciones y las capturas. Solo se entrena con ejemplos revisados. Una etiqueta no es una recompensa: no dice «bien» o «mal», dice cuál era la respuesta correcta.</p>
    <p>La validación agrupa por episodio (GroupKFold) para que pasos casi idénticos no caigan a la vez en entrenamiento y prueba. Métricas: accuracy, precision, recall, F1, matriz de confusión y errores navegables. Aumento opcional por las 8 simetrías del tablero (exactas: giran el ejemplo y su etiqueta). El modo automático reentrena con lo aprobado y se evalúa; nunca etiqueta solo. «Recopilar dudas» guarda sin etiqueta las situaciones donde duda, para que tú las etiquetes.</p>
  </>],
  ['LERK · Aprendizaje simbólico', <>
    <p>Hechos por acción (libre, acerca, encierro, cola_alcanzable, borde…) y reglas con variable X: «SI libre(X) Y acerca(X) Y NO encierro(X) ENTONCES preferir X». Lo aprendido en una dirección vale para todas.</p>
    <p>Adquiere conocimiento por cuatro vías: <b>inducción</b> por cobertura secuencial (familia CN2/RIPPER) desde tus casos; <b>experiencia</b>: juega, el simulador aporta hechos objetivos (morir en ≤ 4 pasos, comer, acercarse y sobrevivir) y se inducen prohibiciones y preferencias; <b>corrección</b> con Ripple-Down Rules: crea una excepción a la regla responsable; y <b>generalización</b>: quita condiciones mientras no baje la precisión. Resolución de conflictos: prohibición › preferencia (salvo prioridad mayor) › prioridad › especificidad › confianza de Laplace. Cada decisión muestra su cadena de inferencia. LERK empieza vacío.</p>
  </>],
  ['BORK · Q-Learning tabular', <>
    <p>Q(s,a) ← Q(s,a) + α[r + γ·max Q(s′,a′) − Q(s,a)], ε-greedy con decaimiento. Estado compacto: peligro, encierro y cola alcanzable para cada una de las 4 acciones + signo de Δx y Δy de la manzana (36 864 estados posibles). No se tabula el tablero completo.</p>
    <p>Riesgo de compresión: tableros distintos comparten estado. Se mide con la desviación típica de los retornos dentro de cada par (s,a) y con una representación básica (144 estados) para ablación. Configurables: α, γ, ε inicial/final, decaimiento, episodios, recompensas y velocidad.</p>
  </>],
  ['CLARK · híbrido de referencia', <>
    <p>Tres componentes propios: A, un Random Forest que estima P(acción buena); B, una base de reglas con vetos y preferencias; C, una tabla Q. Integración fija: los vetos de B, después tu conocimiento explícito (si lo hay) y después w_A·P + w_B·preferencia + w_C·softmax(Q). Cada decisión muestra las tres opiniones, el acuerdo de cada componente con la final y los conflictos.</p>
    <p>Empieza sin entrenar (decisión D4). En el modo automático cada componente aprende a su manera. Tus correcciones llegan a A y B, nunca a la tabla Q. No comparte reglas, tabla ni datos con LERK o BORK.</p>
  </>],
  ['MABU', <><p>Pendiente. Según la especificación, su arquitectura se presenta para aprobación en la Etapa 5 y su preentrenamiento, real y verificable, se hace al final. No existe ningún artefacto de MABU todavía.</p></>],
  ['Estados con evidencia', <>
    <p><b>Sin entrenar</b> (no hay versión) · <b>Entrenado</b> (hay una versión con datos y configuración registrados) · <b>Evaluado</b> (jugó con semillas fijas de validación o prueba) · <b>Validado</b> (su IC 95 % de manzanas supera al del azar en las mismas semillas) · <b>Preentrenado</b> (reservado para MABU, con manifiesto y verificación).</p>
  </>],
  ['Persistencia', <>
    <p>Cada modelo tiene su carpeta en <code>laboratorio/&lt;modelo&gt;/</code>: versiones inmutables con hash SHA-256, datos de trabajo con copia de seguridad, y una base SQLite con episodios, sesiones y récord. Reentrenar crea una versión nueva; restaurar solo mueve el puntero. Si una versión está corrupta, se usa la última válida. Exportar e importar usan .zip con hashes verificados. Los modelos de scikit-learn se guardan con skops (sin pickle), y un artefacto importado no se carga hasta que confirmas que confías en su origen.</p>
  </>],
  ['Flujo recomendado', <>
    <ol className="list-decimal ml-5 space-y-1">
      <li><b>ARKIS:</b> Simulador → Demostrar con ARKIS → juega varias partidas. Entrenamiento → revisa y aprueba → Entrenar → mira la validación → Evaluar.</li>
      <li><b>LERK:</b> Entrenamiento → «Aprender jugando», o crea reglas tú. Simulador → Observar a LERK → corrige sus decisiones → Validar con tus casos.</li>
      <li><b>BORK:</b> ajusta α, γ, ε y las recompensas → Entrenar 500–2000 episodios → mira la curva → Evaluar.</li>
      <li><b>CLARK:</b> Entrenar 200+ episodios → observa las tres opiniones en el Simulador → corrige cuando discrepes.</li>
      <li><b>Comparación:</b> mismas semillas para todos y las líneas base.</li>
    </ol>
  </>],
];

export default function DocsView() {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {SECCIONES.map(([t, c]) => (
        <Panel key={t} titulo={t}><div className="text-sm leading-relaxed space-y-2 text-ink/90">{c}</div></Panel>
      ))}
    </div>
  );
}
