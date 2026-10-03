## HomeLens English

## Propuesta

Propuesta funcional y técnica


## Capítulo 1 Propuesta funcional y técnica

## 1.1 Qué queremos construir

HomeLens English será una aplicación web para aprender vocabulario y expresiones básicas en inglés a partir de fotografías de objetos del hogar.

La persona podrá fotografiar un ambiente o un objeto. La aplicación analizará la imagen y presentará nombres en inglés y español, frases contextualizadas, pronunciación y pequeñas actividades.

No tendrá un catálogo cerrado de 15 objetos ni traducciones cargadas manualmente. El contenido se generará mediante IA, aunque el reconocimiento no será infalible ni abarcará necesariamente cualquier objeto.

## 1.2 Alcance de la primera versión

La primera versión se orienta a personas hispanohablantes que estén aprendiendo inglés básico. La ampliación a otros públicos o idiomas queda fuera del alcance inicial.

La primera versión incluirá tres modos:

| Modo | Qué hará el usuario |
| --- | --- |
| Explorar y aprender | Fotografiar su entorno, consultar objetos reconocidos y escuchar palabras y frases. |
| Practicar | Responder preguntas generadas con los objetos de esa fotografía. |
| Find it | Buscar un objeto solicitado y presentar una nueva fotografía para verificarlo. |

También contará con un historial básico de vocabulario y actividades.

Quedarían para una etapa posterior: video continuo, conversación por micrófono, evaluación de pronunciación, múltiples idiomas y un sistema completo de niveles.

## 1.3 Recorrido principal del usuario

- 1. Abre la aplicación desde el celular o la computadora.

- 2. Toma una fotografía o carga una imagen.

- 3. Revisa la imagen y pulsa “Analizar”.

- 4. Recibe la fotografía con los objetos seleccionados señalados.

- 5. Abre la tarjeta de un objeto para consultar su contenido.

- 6. Escucha la palabra o la frase si lo desea.

- 7. Realiza las actividades y consulta su resultado.

El botón “Analizar” será importante: tomar una foto, abrir una tarjeta o responder una pregunta no debe disparar llamadas involuntarias a la API.

## Selección de objetos

Se buscará presentar entre 3 y 5 objetos por fotografía, priorizando elementos claros, distinguibles y útiles para aprender. Pero no obligaremos al modelo a completar esa cantidad:


- Si hay un solo objeto reconocible, mostrará uno.

- Si la imagen está borrosa, solicitará otra fotografía.

- Si no identifica objetos con suficiente claridad, podrá devolver una lista vacía.

- No deberá inventar elementos para llegar al mínimo.

La cantidad por fotografía limita la información en pantalla, no la variedad total de vocabulario.

## 1.4 Reconocimiento y contenido en una sola llamada

La propuesta será enviar a Gemini una imagen junto con las instrucciones educativas y un esquema de respuesta. En una única llamada se solicitarán los objetos, sus ubicaciones, nombres bilingües, ejemplos y preguntas, mediante una salida estructurada con JSON Schema.

| Bloque | Información |
| --- | --- |
| Estado del análisis | Imagen utilizable, sin objetos claros o necesidad de repetir la captura. |
| Objeto | Identificador, nombre en español y nombre en inglés. |
| Ubicación | Recuadro delimitador dentro de la imagen. |
| Ejemplo | Una oración breve en inglés y su traducción. |
| Actividad | Pregunta, tres opciones, identificador de la respuesta correcta y explicación breve. |

Definiremos las coordenadas con un único criterio: [ymin, xmin, ymax, xmax], normalizadas entre 0 y 1000, para luego adaptarlas al tamaño de la imagen.

Una respuesta con estructura correcta puede contener errores de reconocimiento o de contenido. La aplicación tendrá que validar los datos recibidos, y las pruebas deberán revisar también su calidad.

Entre los controles previstos:

- Máximo de cinco objetos.

- Coordenadas dentro de rango y recuadros válidos.

- Campos obligatorios completos.

- Tres opciones diferentes por pregunta.

- Una respuesta correcta que corresponda a una de esas opciones.

- Exclusión de resultados incompletos o inválidos.

No presentaremos un porcentaje de “confianza” inventado por el modelo como si fuera una medición real.

## 1.5 Traducción y actividades

Gemini generará directamente los nombres en ambos idiomas y las frases. No necesitaremos un diccionario manual ni una API adicional de traducción en esta primera versión.

Las instrucciones deberán pedir:

- Inglés sencillo y frases breves.

- Traducciones naturales.

- Vocabulario coherente en toda la actividad.


- Preguntas con una sola respuesta claramente correcta.

- No afirmar detalles que la imagen no permite observar.

Por ejemplo, si no es evidente que la foto corresponde a una cocina, es preferible generar “This is a coffee maker” antes que asegurar dónde está.

El cuestionario llegará con el análisis inicial, pero la respuesta correcta permanecerá oculta hasta que la

persona responda. La corrección se realizará en la aplicación, sin consultar nuevamente a Gemini.

## 1.6 Pronunciación bajo demanda

La voz se generará únicamente cuando el usuario pulse “Escuchar palabra” o “Escuchar frase”. El servicio propuesto es Google Cloud Text-to-Speech, que convierte texto en audio.

Para evitar llamadas repetidas, guardaremos temporalmente los audios ya generados. La reutilización tendrá en cuenta el texto, el idioma, la voz y la velocidad elegida.

Si falla el audio, el resto de la actividad seguirá disponible. Escuchar no será un requisito para continuar.

## 1.7 Cómo funcionará Find it

Para que el juego tenga sentido en la casa de cada persona, inicialmente utilizará objetos que ya aparecieron en sus exploraciones. Por ejemplo:

- 1. La aplicación selecciona una palabra del historial: “Find a lamp”.

- 2. La persona busca una lámpara y toma una nueva fotografía.

- 3. Una llamada a Gemini verifica específicamente si aparece el objeto solicitado.

- 4. La aplicación muestra el resultado.

Esta verificación será independiente del límite de cinco objetos: la lámpara podría estar presente sin ser uno de los elementos predominantes de la escena.

Las respuestas posibles serán:

- Encontrado: se identifica el objeto solicitado.

- No encontrado: no se observa en la fotografía.

- No se puede determinar: la imagen no permite comprobarlo.

La incertidumbre del modelo no debería penalizarse como un error del estudiante. También habrá una

opción para cambiar de desafío.

## 1.8 Diseño centrado en celulares

La interfaz priorizará pantallas verticales, con:

- Una sola columna.

- Botones grandes y textos breves.

- Fotografía ajustada al ancho disponible.

- Tarjetas desplegables para no mostrar todo simultáneamente.

- Indicadores claros durante el análisis y la generación de audio.

- Alternativa de cargar una imagen si la cámara no funciona.

Streamlit dispone de st.camera_input para obtener fotografías, por lo que puede servir para el prototipo. No

obstante, comprobaremos su comportamiento en teléfonos reales antes de dar por definitiva la interfaz.

## 1.9 Organización técnica

La organización técnica propuesta contempla los siguientes módulos:


| Módulo | Función |
| --- | --- |
| Interfaz y captura | Pantallas, cámara, carga de imágenes y navegación. |
| Preparación de imágenes | Corregir orientación, comprobar formato y ajustar tamaño. |
| Integración con Gemini | Construir instrucciones, enviar solicitudes y validar respuestas. |
|   | Aprendizaje y juegos Mostrar tarjetas, corregir actividades y gestionar Find it. |
| Audio | Solicitar pronunciación y reutilizar audios disponibles. |
| Historial | Guardar vocabulario y resultados. |
| Configuración y pruebas | Proteger claves, controlar consumo y evaluar funcionamiento. |

Python y Streamlit se mantienen como base propuesta del prototipo. Se propone Supabase Auth con ingreso mediante Google y PostgreSQL en Supabase para la persistencia. La integración completa, su comportamiento en móviles y el alojamiento deberán validarse antes de confirmar la arquitectura.

No será necesario entrenar un modelo propio para esta arquitectura. Su adecuación académica dependerá de la consigna: el aporte del equipo estará en diseñar, integrar, controlar y evaluar el sistema.

## 1.10 Datos privacidad y consumo

Guardaríamos inicialmente:

- Palabras exploradas y ejemplos.

- Actividades realizadas y resultados.

- Fecha de práctica.

- Estado de repaso del vocabulario.

No marcaríamos una palabra como “aprendida” solo por verla una vez. Podríamos distinguir entre explorada y practicada, dejando una evaluación más completa para después.

Las fotografías no se guardarán en la base de datos ni en almacenamiento permanente de la aplicación. Los archivos temporales de procesamiento se eliminarán al finalizar la operación, también ante errores. Solo se mantendrá la copia temporal necesaria para visualizar la exploración activa; se liberará al abandonarla, reemplazarla o cerrar la sesión. Antes del envío se informará sobre el procesamiento externo y se recomendará evitar personas, documentos y datos personales. Esta política corresponde a la aplicación y no garantiza la eliminación de copias bajo control del proveedor externo.

## Además:

- Las claves permanecerán en el servidor, nunca en el navegador ni en GitHub.

- Cada usuario deberá tener su historial separado.

- Habrá límites de solicitudes y reintentos.

- Cambiar de tarjeta o repetir una reproducción disponible no repetirá el análisis.


- Se medirán consumo y tiempos reales antes de prometer costos o velocidad.

La llamada unificada busca reducir solicitudes y esperas, pero la mejora concreta debe comprobarse con pruebas.

## 1.11 Cómo comprobaremos que funciona

Prepararemos fotografías de distintos hogares, ambientes y condiciones, incluyendo imágenes difíciles y objetos que no deberían reconocerse. Evaluaremos:

- Reconocimiento: si los objetos presentados realmente están en la imagen y están bien nombrados.

- Ubicación: si los recuadros corresponden al objeto.

- Contenido: si las traducciones, frases y respuestas son correctas.

- Incertidumbre: si solicita otra imagen cuando corresponde.

- Experiencia móvil: si resulta sencillo capturar, leer, escuchar y responder.

- Eficiencia: llamadas por actividad, tiempos de respuesta y consumo.

- Find it: aciertos y errores al verificar el objeto solicitado.

Como el sistema seleccionará pocos objetos, no sería justo considerarlo incorrecto por omitir todos los elementos secundarios de una habitación. Evaluaremos principalmente la calidad de lo seleccionado; la búsqueda específica se medirá por separado.

## 1.12 Etapas para avanzar

| Etapa | Resultado esperado |
| --- | --- |
| 1 Validación de la propuesta | Confirmar consigna, destinatarios, alcance y presupuesto. |
| 2 Prueba técnica | Una fotografía produce una respuesta estructurada válida y un audio bajo demanda. |
|   | 3 Recorrido principal Capturar, analizar, consultar tarjetas y responder actividades desde el celular. |
| 4 Juego e historial | Incorporar Find it, progreso y reutilización de audios. |
| 5 Evaluación y entrega | Medir resultados, corregir fallas y preparar documentación y demostración. |

El proyecto queda planteado como una aplicación de aprendizaje visual, con vocabulario abierto, pocas tarjetas por imagen, una llamada principal a Gemini y audio bajo demanda.

Antes de pasar al código, quedará pendiente confirmar la consigna del trabajo final y el plazo de desarrollo.

## 1.13 Acceso persistencia y tratamiento de imágenes

La arquitectura principal propuesta combina ingreso con Google mediante Supabase Auth y una base PostgreSQL en Supabase. Antes de confirmarla se comprobará el recorrido de inicio y cierre de sesión, recuperación del historial y separación de datos entre dos usuarios desde la interfaz elegida. No se desarrollará un sistema propio de contraseñas para la primera versión.

SQLite se conserva como alternativa para una demostración si la integración principal no resulta viable en el plazo disponible. Almacenamiento e identidad son decisiones independientes: un identificador local no


equivale a una cuenta autenticada ni garantiza recuperación desde otro dispositivo. Si se adopta una sesión simple, se deberá declarar la reducción de alcance y revisar HU01, RF01 y RNF04; no se considerarán cumplidos automáticamente.

Se admitirán JPEG y PNG de hasta 10 MB por archivo, equivalentes a 10 000 000 bytes. Se validará el contenido real antes del envío; cambiar la extensión no vuelve válido un archivo. Otros formatos quedan fuera del alcance inicial y la aplicación informará cómo continuar con un archivo admitido. La preparación corregirá orientación y ajustará tamaño sin perder la correspondencia entre la imagen analizada y los recuadros mostrados.

No se utilizará almacenamiento permanente de imágenes en la primera versión. La copia de visualización se mantendrá solo durante la exploración activa. La limpieza deberá contemplar también errores y sesiones abandonadas; su mecanismo y plazo de respaldo para cierres inesperados se validarán en el prototipo. No se habilitará por defecto la conservación de fotografías para depuración durante 24 o 48 horas.

## 1.14 Método de evaluación y medición

Se preparará un conjunto fijo de 20–30 fotografías con diversidad de ambientes, iluminación y ángulos, incluyendo imágenes borrosas, escenas ambiguas y pocos objetos. Se identificarán las imágenes y se documentará la referencia manual. Los materiales de evaluación se conservarán separados de las fotografías de usuarios, con autorización de uso y sin datos personales innecesarios.

Una prueba piloto permitirá ajustar instrucciones y detectar problemas. Los umbrales de aceptación se acordarán después del piloto y antes de la evaluación final. Se reservarán casos que no se hayan utilizado para ajustar el sistema y se identificarán los resultados de piloto y evaluación final. No se afirmará que los valores de calidad ya fueron alcanzados.

- Reconocimiento: calcular objetos mostrados presentes y correctamente nombrados dividido por el total de objetos mostrados. Si no hay objetos mostrados, la precisión no se calculará como un acierto; se registrará el caso por separado. La cantidad de resultados vacíos o solicitudes de nueva imagen también se informará.

- Ubicación: revisar cada recuadro como correcto, parcial o incorrecto según encierre el objeto y permita asociarlo sin ambigüedad. La validación numérica del servidor no reemplaza esta revisión visual.

- Contenido: puntuar por separado traducción, naturalidad y adecuación al nivel inicial, registrando los errores y ejemplos que justifican cada valoración.

- Cuestionario: comprobar tres opciones distintas, una única solución inequívoca y una explicación coherente. Estos controles se reportarán por separado para evitar que un promedio oculte preguntas inválidas.

- Find it: comparar la respuesta del sistema con una referencia manual en casos con objeto presente, ausente e imagen indeterminable. Registrar falsos positivos, falsos negativos y uso de la respuesta de incertidumbre. No penalizar al estudiante por un resultado indeterminable.

- Revisión: cada evaluación tendrá identificación del caso, resultado, observaciones y persona revisora. Los desacuerdos se revisarán y se documentará el criterio final.

| Puntuación | Criterio orientativo para cada dimensión educativa |
| --- | --- |
| 1 | Incorrecto o inadecuado; no resulta utilizable. |
| 2 | Contiene errores importantes y requiere cambios sustanciales. |
| 3 | Es comprensible, pero necesita correcciones antes de utilizarse. |


Para rendimiento se realizará una tanda inicial con 15–20 fotografías del conjunto de prueba. Se registrarán tiempos de exploración, verificación de Find it y audio por separado, con condiciones de red, tamaño de imagen, configuración, fallos y reintentos. El percentil 90 será una referencia del prototipo, no una garantía general. El tiempo objetivo de respuesta y el tiempo máximo de corte se definirán como valores distintos.

Para consumo se registrarán solicitudes y uso informado por cada servicio. Se estimarán costos por exploración, verificación de Find it y generación de audio con las tarifas aplicables a la configuración usada, anotando fecha y supuestos. La reproducción de un audio reutilizado se distinguirá de una nueva generación. Antes del piloto se fijará un presupuesto provisional de prueba; con los resultados se acordarán las cuotas por usuario, el tope global y el máximo de reintentos.

La matriz mínima propuesta comprende Android con Chrome, iPhone con Safari y computadora con Chrome. En cada combinación se probarán acceso, captura o carga, exploración con recuadros, audio, cuestionario, historial y Find it. Se documentarán versiones y limitaciones; no se declarará compatible una combinación

que no se haya probado.


del capítulo 1 es una propuesta técnica y no una asignación de trabajo.
