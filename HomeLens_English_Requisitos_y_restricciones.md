# HomeLens English

# Capítulo 3 Requisitos y restricciones

Este capítulo reúne los requisitos funcionales, las condiciones de calidad y las restricciones técnicas, manteniendo la relación con HU01 a HU12. El apartado 3.4 registra el estado de las decisiones y el 3.5 resume su trazabilidad.

## 3.1 Requerimientos funcionales

Describen qué debe hacer la aplicación.

RF01 El sistema debe permitir que el usuario se identifique, ingrese a su espacio personal y cierre su sesión. Se propone ingreso con Google mediante Supabase Auth, sujeto a validación técnica. El historial debe quedar asociado a una identidad estable.

Historias relacionadas: HU01.

RF02 El sistema debe permitir tomar una fotografía desde un dispositivo compatible o cargar una imagen existente.

Historias relacionadas: HU02.

RF03 El sistema debe permitir revisar y reemplazar la imagen antes del envío e iniciar el análisis mediante una acción explícita del usuario.

Historias relacionadas: HU02.

RF04 El sistema debe admitir archivos JPEG y PNG de hasta 10 MB, definidos para este proyecto como 10 000 000 bytes. Debe comprobar en el servidor el tamaño, el formato real y que la imagen pueda decodificarse. Si no cumple, debe informar el problema antes de llamar a la IA.

Historias relacionadas: HU02.

RF05 El sistema debe identificar y presentar hasta cinco objetos por fotografía, procurando seleccionar entre tres y cinco cuando sean claramente reconocibles. Debe admitir resultados con menos objetos o sin objetos identificados.

Historias relacionadas: HU03.

RF06 El sistema debe mostrar la ubicación de cada objeto seleccionado mediante un recuadro sobre la imagen analizada.

Historias relacionadas: HU03.

RF07 El sistema debe presentar una tarjeta por objeto con su nombre en inglés, su equivalente en español, una frase de ejemplo en inglés y su traducción.

Historias relacionadas: HU04.

RF08 El sistema debe permitir solicitar y reproducir por separado el audio de la palabra y de la frase en inglés. La reproducción debe iniciarse a pedido del usuario.

Historias relacionadas: HU05.

RF09 El sistema debe ofrecer preguntas sobre los objetos explorados, con tres opciones diferentes y una única respuesta correcta.

Historias relacionadas: HU06.

RF10 El sistema debe permitir seleccionar y confirmar una respuesta, mantener oculta la solución hasta esa confirmación y mostrar el resultado con una explicación breve.

Historias relacionadas: HU06.

RF11 El sistema debe guardar el vocabulario, las traducciones, los ejemplos y las actividades de las exploraciones válidas, asociados al usuario correspondiente.

Historias relacionadas: HU07.

RF12 El sistema debe permitir consultar el contenido guardado en sesiones posteriores, sin exigir una nueva fotografía ni conservar la imagen original.

Historias relacionadas: HU07.

RF13 El sistema debe permitir repetir actividades guardadas y registrar cada nuevo intento sin eliminar los resultados anteriores.

Historias relacionadas: HU08.

RF14 El sistema debe generar desafíos de Find it a partir del vocabulario previamente explorado por el usuario y permitir cambiar de desafío.

Historias relacionadas: HU09.

RF15 El sistema debe permitir presentar una nueva fotografía para verificar si aparece el objeto solicitado en Find it, independientemente de que sea uno de los elementos predominantes de la imagen.

Historias relacionadas: HU10.

RF16 El sistema debe distinguir los resultados de Find it entre “encontrado”, “no encontrado” y “no se puede determinar”. En este último caso, debe permitir repetir la captura sin contabilizarlo como un error del estudiante.

Historias relacionadas: HU10.

RF17 El sistema debe registrar la fecha y el resultado de las prácticas y mostrar un resumen del progreso del usuario. Debe distinguir vocabulario explorado y practicado, sin considerar una palabra aprendida por su sola visualización.

Historias relacionadas: HU06, HU08, HU11.

RF18 El sistema debe mostrar estados de carga y mensajes comprensibles ante errores, permitir reintentar cuando corresponda e indicar cómo comenzar cuando no existan datos previos.

Historias relacionadas: HU01, HU08, HU09, HU12.

RF19 El sistema debe informar, antes del envío de una imagen, que será procesada por un servicio externo y explicar el tratamiento previsto para las fotografías.

Historias relacionadas: HU02.

RF20 El sistema debe validar la respuesta del servicio de IA antes de utilizarla. Los resultados incompletos o inválidos no deben guardarse como una exploración correcta.

Historias relacionadas: HU03, HU04, HU06, HU12.

## 3.2 Requerimientos no funcionales

Establecen condiciones de calidad, seguridad, rendimiento y uso. Los valores de rendimiento o calidad que todavía no se midieron quedan pendientes de definición.

### RNF01 Usabilidad móvil

La interfaz debe adaptarse a pantallas verticales y permitir completar los recorridos principales sin desplazamiento horizontal ni controles superpuestos.

Verificación: Pruebas de captura, exploración, audio y práctica desde teléfonos.

### RNF02 Claridad de la interfaz

Los botones, instrucciones, estados de carga y errores deben utilizar lenguaje comprensible para una persona sin conocimientos técnicos.

Verificación: Revisión de las pantallas y pruebas con usuarios.

### RNF03 Accesibilidad básica

Los controles deben tener etiquetas comprensibles, poder operarse mediante teclado y no comunicar resultados únicamente mediante colores. El contenido escrito debe permanecer disponible aunque no se reproduzca audio.

Verificación: Revisión de navegación, etiquetas y presentación de resultados.

### RNF04 Separación de datos

El sistema debe impedir que un usuario consulte o modifique el historial y los resultados de otro. La comprobación de acceso debe realizarse en el servidor. Si se adopta Supabase, se configurarán políticas de acceso por usuario, incluidas RLS cuando corresponda; elegir el servicio no sustituye estas comprobaciones.

Verificación: Pruebas con dos usuarios e intentos de acceso a datos ajenos.

### RNF05 Protección de credenciales

Las claves de las APIs y demás secretos deben permanecer fuera del código publicado, del navegador y de los registros visibles para el usuario.

Verificación: Revisión de configuración, repositorio y respuestas del servidor.

### RNF06 Comunicación segura

La versión desplegada debe utilizar conexiones HTTPS para el acceso del usuario y las comunicaciones con los servicios externos.

Verificación: Verificación de las conexiones utilizadas.

### RNF07 Privacidad de imágenes

La aplicación no debe guardar fotografías en la base de datos ni en almacenamiento permanente. Debe eliminar los archivos temporales de procesamiento al finalizar cada operación, incluso ante fallos, y liberar la copia temporal de visualización al abandonar o reemplazar la exploración o cerrar la sesión. Debe evitar fotografías y datos personales innecesarios en registros técnicos. Se debe definir y verificar un mecanismo de limpieza para sesiones abandonadas o cierres inesperados. El aviso debe distinguir esta política del tratamiento del proveedor externo.

Verificación: Revisar almacenamiento, registros y limpieza en éxito, error, cambio de imagen, cierre de sesión y abandono. La liberación será lógica y no se presentará como garantía de borrado físico inmediato de memoria ni de copias del proveedor.

### RNF08 Persistencia

El vocabulario y los resultados guardados deben mantenerse después del cierre de sesión y del reinicio de la aplicación.

Verificación: Guardar información, cerrar sesión, reiniciar la aplicación y comprobar su recuperación.

### RNF09 Integridad de registros

Una misma confirmación de respuesta no debe generar registros duplicados por pulsaciones repetidas o actualizaciones de pantalla.

Verificación: Pruebas de doble pulsación, recarga y reintento.

### RNF10 Tolerancia a fallos

Una falla del servicio de audio no debe impedir utilizar las funciones de texto. Una falla en un nuevo análisis no debe eliminar el historial previamente guardado.

Verificación: Pruebas simulando errores de los servicios externos.

### RNF11 Rendimiento

El sistema debe medir los tiempos de análisis y generación de audio, establecer tiempos máximos de espera y evitar que una operación quede indefinidamente en carga.

Verificación: Prueba inicial con 15–20 fotografías variadas; medir exploración, Find it y audio por separado y registrar duración, éxito, fallo y reintentos. Calcular el percentil 90 como referencia inicial. Los objetivos de respuesta y los tiempos de corte se definirán separadamente tras la prueba; se simularán demoras para comprobar que la interfaz deja de mostrar carga indefinida.

### RNF12 Eficiencia de consumo

El sistema debe evitar solicitudes duplicadas, reutilizar resultados disponibles y limitar las solicitudes y los reintentos automáticos.

Verificación: Registrar llamadas, reintentos, uso reportado y costo estimado por exploración, Find it y audio. Medir una muestra fija antes de acordar cuotas por usuario, presupuesto global y máximo de reintentos. Las pruebas también tendrán un tope provisional de gasto acordado antes de ejecutarlas.

### RNF13 Calidad del contenido educativo

Las traducciones y frases deben ser coherentes con el objeto identificado y adecuadas para inglés inicial. Las actividades deben tener una única solución inequívoca.

Verificación: Revisión manual del contenido de un conjunto fijo de 20–30 fotografías, con rúbrica de 1 a 5 para traducción, naturalidad y nivel inicial. Las preguntas se revisarán además con controles de opciones distintas y solución única. Los umbrales se acordarán tras el piloto y antes de la evaluación final, según el método de evaluación de la propuesta integral.

### RNF14 Calidad del reconocimiento

El sistema debe evaluarse con fotografías de diferentes ambientes, luces y ángulos, revisando los objetos seleccionados, sus nombres y sus recuadros.

Verificación: Conjunto fijo de 20–30 fotografías con resultados revisados manualmente. Medir presencia y nombre correcto de los objetos mostrados, y evaluar por separado sus recuadros. No penalizar la omisión de objetos secundarios. Incluir en Find it casos presentes, ausentes e indeterminables; documentar desacuerdos entre evaluadores.

### RNF15 Compatibilidad

Los recorridos principales deben funcionar en los navegadores móviles y de escritorio definidos para el proyecto. Cuando no pueda utilizarse la cámara, debe estar disponible la carga de imágenes.

Verificación: Matriz mínima propuesta: Android con Chrome, iPhone con Safari y computadora con Chrome. Registrar dispositivo, sistema, versión del navegador, fecha y resultado de cada recorrido. Confirmar disponibilidad de los equipos antes de cerrar la matriz; los casos no probados quedarán identificados.

### RNF16 Mantenibilidad

El código debe separar la interfaz, las integraciones de IA y audio, la lógica de actividades y el acceso a datos, para facilitar cambios y correcciones.

Verificación: Revisión de la organización del proyecto y de sus dependencias.

### RNF17 Seguimiento técnico

El sistema debe registrar errores, duración de operaciones y cantidad de llamadas a servicios externos, sin registrar claves ni fotografías.

Verificación: Inspección de registros durante pruebas normales y con fallos.

## 3.3 Restricciones técnicas

Estas condiciones orientan la implementación y complementan los requerimientos anteriores. Se conserva el carácter de propuesta en las tecnologías que aún requieren validación.

RT01 Utilizar Gemini mediante API para el análisis visual y la generación del contenido bilingüe y educativo.

RT02 Obtener objetos, coordenadas, traducciones, frases y preguntas mediante una llamada principal por fotografía de exploración, con una salida estructurada. Los reintentos controlados por fallos se contabilizarán por separado.

RT03 Utilizar el orden de coordenadas [ymin, xmin, ymax, xmax], normalizadas entre 0 y 1000, y comprobar su validez antes de dibujar los recuadros.

RT04 Generar los nombres y las traducciones dinámicamente, sin depender de un catálogo manual cerrado de objetos. Esto no implica garantizar el reconocimiento de cualquier objeto.

RT05 Utilizar Google Cloud Text-to-Speech como servicio de voz propuesto, con generación bajo demanda y reutilización temporal según texto, idioma, voz y velocidad.

RT06 Corregir las preguntas con la solución recibida junto con la actividad, sin realizar una nueva consulta al modelo.

RT07 Verificar cada fotografía de Find it mediante una solicitud específica para buscar el objeto del desafío.

RT08 Utilizar Python y Streamlit como base propuesta del prototipo, validando su funcionamiento en celulares antes de confirmar la interfaz definitiva.

RT09 Mantener el historial en almacenamiento persistente, independiente de la memoria temporal de la sesión. Se propone PostgreSQL en Supabase, vinculado a la identidad de Supabase Auth, sujeto a una prueba de integración. SQLite queda como alternativa de demostración; su elección no resuelve por sí sola la autenticación ni autoriza a reducir las garantías de acceso sin revisar el alcance.

## 3.4 Registro de decisiones y validaciones pendientes

Acordado indica la base de esta versión documental. Propuesto para validar indica una opción principal que aún requiere prueba o confirmación. Pendiente de medición indica que el método está definido, pero todavía no se fijaron valores. Ningún estado significa que la implementación o las pruebas ya estén terminadas.

| Decisión | Estado | Definición y condición de cierre |
| --- | --- | --- |
| Acceso | Propuesto para validar | Google mediante Supabase Auth. Verificar inicio, cierre, identidad estable y acceso al historial. |
| Formatos y tamaño | Acordado | JPEG y PNG; máximo de 10 000 000 bytes. Validar contenido real y decodificación. |
| Consumo y reintentos | Pendiente de medición | Medir por operación; fijar presupuesto de prueba antes del piloto y cuotas finales después. |
| Rendimiento | Pendiente de medición | Tanda inicial de 15–20 fotos; separar percentil 90, objetivo de respuesta y tiempo de corte. |
| Eliminación de imágenes | Acordado con validación técnica | Sin persistencia de fotos. Limpieza al finalizar el procesamiento y al terminar la visualización. Validar respaldo para abandono o cierre inesperado. |
| Calidad | Método acordado y umbrales pendientes | Conjunto de 20–30 fotos; revisión visual, rúbrica educativa y casos de Find it. Fijar umbrales antes de evaluación final. |
| Compatibilidad | Propuesto para validar | Android con Chrome, iPhone con Safari y computadora con Chrome. Confirmar equipos y registrar versiones. |
| Base de datos | Propuesto para validar | PostgreSQL en Supabase. SQLite queda como contingencia de demo con revisión del alcance de identidad. |

También deberán confirmarse la consigna académica, el plazo de entrega, el presupuesto, el alojamiento, la configuración de los servicios y la viabilidad móvil de Streamlit. La elección de un modelo concreto y su configuración quedará registrada durante el prototipo. Si una decisión modifica el alcance, se actualizarán en conjunto la propuesta, las historias y los requisitos afectados.

## 3.5 Relación entre historias y requisitos funcionales

| Código | Necesidad | Requisitos funcionales relacionados |
| --- | --- | --- |
| HU01 | Espacio personal | RF01 y RF18 |
| HU02 | Capturar o cargar | RF02, RF03, RF04 y RF19 |
| HU03 | Explorar objetos | RF05, RF06 y RF20 |
| HU04 | Consultar ejemplos | RF07 y RF20 |
| HU05 | Escuchar contenido | RF08 |
| HU06 | Responder preguntas | RF09, RF10, RF17 y RF20 |
| HU07 | Recuperar vocabulario | RF11 y RF12 |
| HU08 | Repetir prácticas | RF13, RF17 y RF18 |
| HU09 | Iniciar Find it | RF14 y RF18 |
| HU10 | Verificar el objeto | RF15 y RF16 |
| HU11 | Consultar progreso | RF17 |
| HU12 | Resolver errores | RF18 y RF20 |

Los requisitos no funcionales y las restricciones técnicas son transversales. Por ejemplo, RNF04 condiciona todas las funciones que acceden a datos personales; RNF07 afecta los recorridos con fotografías; RT02 define la llamada principal de exploración y RT07 la verificación específica de Find it. La organización por módulos de la propuesta integral es una propuesta técnica y no una asignación de trabajo.
