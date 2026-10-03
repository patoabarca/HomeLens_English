# HomeLens English

# Capítulo 2 Historias de usuario y criterios de aceptación

Cada historia describe una necesidad del usuario y sus criterios de aceptación. Esta versión conserva las doce historias originales e incorpora los ajustes de acceso, formatos y privacidad. Las elecciones tecnológicas se detallan en la propuesta integral y en el documento de requisitos y restricciones. No se asignan tareas ni responsabilidades.

## HU01 Acceder a mi espacio personal

Como persona que aprende inglés, quiero ingresar a un espacio personal para conservar mi vocabulario y continuar mis prácticas en distintas sesiones.

**Criterios de aceptación**

- El usuario puede identificarse e ingresar a su espacio.

- Solo puede consultar su propio historial y sus resultados.

- Al cerrar la sesión y volver a ingresar, conserva la información guardada.

- Si todavía no tiene actividad, se muestra una indicación para comenzar a explorar.

Decisión técnica propuesta para validar: ingreso con Google mediante Supabase Auth. Una demostración con identificación local requerirá documentar su alcance reducido y no se considerará equivalente al acceso personal aquí definido.

## HU02 Tomar o cargar una fotografía

Como usuario, quiero tomar una fotografía o cargar una imagen de mi casa para utilizar los objetos que aparecen en ella como material de aprendizaje.

**Criterios de aceptación**

- Puede tomar una fotografía desde un dispositivo compatible o cargar una imagen.

- Puede revisar la imagen y reemplazarla antes de enviarla.

- El análisis comienza únicamente cuando pulsa “Analizar”.

- Se admiten archivos JPEG y PNG de hasta 10 MB. Si el formato real o el tamaño no cumplen, recibe un mensaje que le permite corregir el problema.

- Antes del envío, se informa que la imagen será procesada por un servicio externo y se explica su tratamiento temporal y la ausencia de fotografías en el historial.

## HU03 Explorar objetos de una fotografía

Como usuario, quiero que la aplicación identifique y señale objetos visibles para conocer cómo se llaman en inglés y relacionarlos con mi entorno.

**Criterios de aceptación**

- La aplicación presenta un máximo de cinco objetos, priorizando entre tres y cinco cuando la imagen lo permita.

- Si solo puede identificar uno o dos, muestra esos objetos sin completar la cantidad con elementos inventados.

- Cada objeto presentado tiene un nombre en inglés, su equivalente en español y un recuadro que indica su ubicación.

- Si no puede identificar objetos claramente, informa la situación y permite intentar con otra imagen.

- El vocabulario no está limitado a un catálogo manual de quince objetos.

## HU04 Consultar ejemplos de uso

Como usuario, quiero abrir la información de un objeto reconocido y ver una frase sencilla para aprender a utilizar esa palabra en inglés.

**Criterios de aceptación**

- Cada objeto tiene una tarjeta con su nombre en ambos idiomas.

- La tarjeta incluye una frase breve en inglés y su traducción al español.

- El contenido corresponde a un nivel inicial.

- Las frases no afirman detalles de la escena que no puedan comprobarse.

- Al abrir o cambiar de tarjeta, el análisis y el contenido disponible se mantienen.

## HU05 Escuchar palabras y frases

Como usuario, quiero escuchar la pronunciación de una palabra o una frase para familiarizarme con su sonido en inglés.

**Criterios de aceptación**

- Puede elegir entre “Escuchar palabra” y “Escuchar frase”.

- El audio se solicita únicamente cuando pulsa el botón correspondiente.

- Puede volver a reproducir la palabra o la frase seleccionada.

- Mientras se prepara el audio, se muestra una indicación de carga.

- Si la reproducción falla, puede seguir consultando el contenido y realizando actividades.

## HU06 Practicar con preguntas

Como usuario, quiero responder preguntas relacionadas con los objetos explorados para comprobar si comprendí el vocabulario.

**Criterios de aceptación**

- Las preguntas se relacionan con los objetos de la exploración.

- Cada pregunta tiene tres opciones diferentes y una única respuesta correcta.

- La solución permanece oculta hasta que el usuario confirma su respuesta.

- La aplicación indica si acertó y presenta una explicación breve.

- El resultado queda asociado al usuario.

## HU07 Consultar mi vocabulario en otra sesión

Como usuario, quiero volver a consultar las palabras y los ejemplos que exploré para repasar sin tener que fotografiar nuevamente los objetos.

**Criterios de aceptación**

- El vocabulario de una exploración válida se guarda asociado al usuario.

- Al volver a ingresar, puede consultar las palabras, sus traducciones y los ejemplos guardados.

- El historial permanece disponible aunque no se conserve la fotografía original.

- Puede consultar el contenido guardado sin cargar una nueva imagen.

- El historial conserva vocabulario y actividad; no supone recordar el aspecto ni la ubicación de un objeto particular.

## HU08 Repasar vocabulario anterior

Como usuario, quiero practicar con contenido de mis exploraciones anteriores para reforzar lo que ya estuve estudiando.

**Criterios de aceptación**

- Puede acceder a actividades guardadas de exploraciones anteriores.

- Puede volver a responderlas sin tomar una nueva fotografía.

- Cada práctica registra su fecha y resultado.

- Repetir una actividad no elimina los resultados anteriores.

- Si todavía no hay actividades disponibles, la aplicación invita a realizar una exploración.

## HU09 Iniciar un desafío Find it

Como usuario, quiero recibir el desafío de buscar un objeto nombrado en inglés para practicar la asociación entre una palabra y un objeto real.

**Criterios de aceptación**

- El desafío utiliza vocabulario que ya apareció en las exploraciones del usuario.

- La consigna se presenta en inglés, por ejemplo: “Find a lamp”.

- El usuario puede solicitar otro desafío si no puede buscar ese objeto.

- Si no tiene vocabulario guardado, se le indica que primero debe realizar una exploración.

- Puede elegir o cambiar el desafío sin presentar una fotografía.

## HU10 Comprobar el objeto encontrado

Como usuario, quiero presentar una nueva fotografía durante el desafío para comprobar si encontré el objeto solicitado.

**Criterios de aceptación**

- Puede tomar o cargar una imagen y confirmar su envío.

- La aplicación busca específicamente el objeto solicitado, aunque no sea uno de los cinco elementos predominantes.

- El resultado distingue entre encontrado, no encontrado y no se puede determinar.

- Si la imagen no permite comprobarlo, se solicita otra fotografía sin registrar la incertidumbre como un error del estudiante.

- Puede volver a intentarlo o cambiar de desafío.

## HU11 Consultar mi progreso

Como usuario, quiero ver el vocabulario explorado y los resultados de mis prácticas para reconocer mis avances y decidir qué repasar.

**Criterios de aceptación**

- Puede consultar las palabras exploradas y cuáles practicó.

- Puede ver las fechas y los resultados de sus actividades.

- Una palabra no se considera “aprendida” únicamente por haber sido mostrada.

- Los estados iniciales distinguen entre explorada y practicada.

- La información se mantiene disponible entre sesiones.

## HU12 Entender los errores y volver a intentar

Como usuario, quiero recibir mensajes claros cuando una operación no pueda completarse para saber cómo continuar sin perder lo que ya estaba haciendo.

**Criterios de aceptación**

- Durante el análisis o la generación de audio, se muestra que la operación está en curso.

- Se evita enviar varias veces la misma solicitud por pulsaciones repetidas.

- Si falla el servicio, recibe un mensaje comprensible y una opción para reintentar.

- Una respuesta incompleta o inválida no se guarda como una exploración correcta.

- Un error de audio no elimina el análisis ni las actividades disponibles.

## Condiciones técnicas y de calidad

Estas condiciones afectan a varias historias y se desarrollan en el documento de requisitos y restricciones. Se mantienen separadas de los criterios centrados en el comportamiento del usuario.

Uso desde celulares. Pantallas verticales, botones accesibles, imágenes adaptadas y contenido legible.

Análisis unificado. Una llamada principal a Gemini por fotografía para obtener objetos, coordenadas, traducciones, frases y preguntas mediante una salida estructurada.

Validación de resultados. Comprobar campos, recuadros, cantidad de objetos y coherencia de las opciones antes de mostrar o guardar el contenido.

Audio bajo demanda. Generar voz solo cuando se solicite y reutilizar audios disponibles, teniendo en cuenta texto, idioma, voz y velocidad.

Persistencia. Conservar vocabulario, actividades y resultados en un almacenamiento que permanezca entre sesiones.

Privacidad. Separar la información de cada usuario; no guardar fotografías permanentemente; limpiar los temporales de procesamiento al finalizar y liberar la copia de visualización al abandonar o reemplazar la exploración o cerrar la sesión.

Control del consumo. Evitar nuevas llamadas a Gemini al navegar entre tarjetas, consultar contenido guardado, seleccionar desafíos o corregir respuestas. La corrección utiliza la solución recibida con la actividad.

Protección de claves. Mantener las credenciales de los servicios en el servidor.
