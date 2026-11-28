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
| Acceso | Integrado en `main` | Google mediante Supabase Auth (`homelens/acceso.py`, `homelens/integraciones/autenticacion.py`) y modo demostración local controlado por `ALLOW_DEMO_LOGIN`. |
| Formatos y tamaño | Integrado en `main` | JPEG y PNG (incluyendo normalización de MPO a JPEG); máximo de 10 000 000 bytes (`homelens/imagenes.py`). Validación de cabecera real, decodificación completa y corrección EXIF. |
| Consumo y reintentos | Integrado en `main`; umbrales finales pendientes | Telemetría y panel privado de consumo para creadores (`homelens/telemetria.py`, `homelens/costos.py`, `homelens/ui/consumo.py`, `sql/migracion_tarea_consumo_ia.sql`) con tarifas versionadas y registro de tokens, llamadas, reintentos y errores HTTP. |
| Rendimiento | Instrumentado; lote final pendiente | Duración en milisegundos registrada por operación en `EventoTecnico` y en el ejecutor A2 (`origin/HLE_Evaluacion`). En la única corrida real del piloto (`Cocina`) la latencia observada de M3 fue 10,40 s; falta medir un lote completo para estimar percentil 90. |
| Eliminación de imágenes | Integrado en `main` | Sin persistencia de fotos en Supabase. Procesamiento en memoria (`io.BytesIO`) y limpieza en `limpiar_datos_exploracion()`, `limpiar_datos_find_it()` y `cerrar_sesion_usuario()` (`homelens/ui/estado.py`). |
| Calidad | Instrumento en `origin/HLE_Evaluacion`; pruebas parciales en copia local | Piloto CVAT de 5 fotos (1 ejecutada con Gemini real en `docs/evaluacion/A4_resultados.md`) y lote final de 30 fotos sintéticas con 541 cajas CVAT validado en A1 (`docs/evaluacion/ENTREGA_DATASET_EVALUACION_FINAL.md`). En copia local fuera de Git se registran dos corridas sobre 3 imágenes (`prueba3_gemini_origin_main_real_20261127` y `prueba3_gemini36_origin_main_real_20261128`); las 27 imágenes restantes y la revisión lingüística humana de esa prueba siguen pendientes. |
| Compatibilidad | Diseño responsivo en `main`; matriz física en cierre | Visor de imagen y tarjetas adaptados a escritorio y pantallas móviles (`@media (max-width: 640px)` en `homelens/ui/exploracion.py` y `homelens/ui/progreso.py`). |
| Base de datos | Integrada en `main` | PostgreSQL en Supabase con RLS no recursiva (`sql/migracion_tarea_7_historial.sql`, `sql/migracion_tarea_10_intentos_practica.sql`, `sql/migracion_tarea_consumo_ia.sql`) y almacén en memoria por sesión para modo demo (`homelens/datos/supabase.py`). |

También deberán confirmarse la consigna académica, el plazo de entrega, el presupuesto, el alojamiento, la configuración de los servicios y la viabilidad móvil de Streamlit. La elección de un modelo concreto y su configuración quedará registrada durante el prototipo. Si una decisión modifica el alcance, se actualizarán en conjunto la propuesta, las historias y los requisitos afectados.

### 3.4.1 Evidencia sobre versiones de Gemini, pruebas y diferencias de alcance

Para evitar confusiones entre lo que exige un requisito, lo que configura `main` por defecto y lo que se probó en distintas ramas, se deja constancia de la evidencia verificada sobre `origin/main` (`d4aa17a`) y `origin/HLE_Evaluacion` (`9eee4e5`):

1. **Versión de Gemini — requisito vs. configuración predeterminada vs. pruebas:**
   - **Requisito obligatorio (`RT01`):** exige utilizar la API de Gemini con salida estructurada para el análisis visual y el contenido educativo bilingüe, sin fijar normativamente una única versión del modelo.
   - **Configuración predeterminada en `main`:** tanto `.env.example` (`GEMINI_MODEL=gemini-2.5-flash`) como `cargar_configuracion()` en `homelens/config.py` (`os.getenv("GEMINI_MODEL", "gemini-2.5-flash")`) establecen **`gemini-2.5-flash`** como valor por defecto cuando la aplicación carga su configuración sin que el entorno local lo sobrescriba. Por su parte, el parámetro de respaldo del constructor `AdaptadorGemini.__init__` (`homelens/integraciones/gemini.py`) y `homelens/telemetria.py` es `"gemini-3.6-flash"`, y `homelens/costos.py` mantiene tarifas versionadas para ambos modelos (`gemini-2.5-flash` y `gemini-3.6-flash`). En `main`, `AdaptadorGemini` envía `temperature=0.2` para cualquier modelo configurado, mientras que la adaptación que omite `temperature` específicamente para `gemini-3.6-flash` se encuentra únicamente en la rama `origin/HLE_Evaluacion`.
   - **Modelos utilizados en corridas documentadas:**
     - En la aplicación sobre `main`, la verificación real del circuito completo de exploración y persistencia en `public.consumo_gemini` se ejecutó configurando `gemini-3.6-flash` en el `.env` local (1 llamada API, 1.712 tokens de entrada, 539 de salida, 832 de razonamiento y 3.083 totales).
     - En la rama `origin/HLE_Evaluacion`, la corrida real con revisión humana completa frente a CVAT (`gemini36_piloto_cocina_una_v2`, documentada en `docs/evaluacion/A4_resultados.md`) utilizó `gemini-3.6-flash` sobre **1 fotografía sintética piloto** (`Cocina`).
     - Sobre el subconjunto de **3 imágenes** (`cvat_evaluacion_sintetica_lucas_v1_1`, `cvat_evaluacion_sintetica_lucas_v1_6` y `cvat_evaluacion_sintetica_lucas_v1_26`) del lote final de 30 imágenes sintéticas, en la copia local de evaluación fuera de Git (`data/evaluacion/resultados/`) se registran dos corridas reales:
       1. `prueba3_gemini_origin_main_real_20261127`: modelo **`gemini-2.5-flash`** (`temperature=0.2`, `max_reintentos=0`), con **3 imágenes distintas intentadas** y **3 intentos en total** (1 intento por imagen, sin reintentos). Obtuvo **0 respuestas válidas** y **3 fallidas** (`estado="fallida_api"`, `error_codigo="SERVICIO_NO_DISPONIBLE"`, `error_transporte`). En su informe A3 (`informe_174461dcf9fd/resumen.json`), todas las métricas frente a CVAT quedaron en `null` por no existir respuestas válidas (`0/0`).
       2. `prueba3_gemini36_origin_main_real_20261128`: modelo **`gemini-3.6-flash`**, sobre las mismas **3 imágenes distintas** con **3 intentos en total** (1 intento por imagen), donde las **3 obtuvieron respuesta válida** (`3/3`, latencia promedio 11,28 s) y se calcularon métricas automáticas preliminares frente a CVAT (13 detecciones sobre 56 referencias CVAT, 12 emparejadas con IoU promedio 0,8725 y 1 pendiente de identificación; los 13 objetos permanecen pendientes de revisión lingüística humana). Las restantes 27 imágenes del lote final permanecen `no_ejecutadas`.

2. **Distinción entre los tres niveles de validación del proyecto:**
   - **Pruebas automáticas del software (`tests/`):** como registro histórico verificado al ejecutar `python -X utf8 -m pytest -q` localmente sobre `origin/main` en el commit `d4aa17a` (PR #13), la suite aprobó **257 pruebas** (y 6 subtests) que verifican modelos, preparación de imágenes, validaciones de M3, visor responsivo, caché y aislamiento de audio, cuestionarios, Find It, cálculo y pantalla de progreso, políticas RLS y panel de consumo usando clientes simulados (`MagicMock` y fixtures locales), sin realizar llamadas reales a Gemini ni a Google Cloud TTS. En `origin/HLE_Evaluacion` existen además `tests/test_evaluacion_a1.py` y `tests/test_evaluacion_a2_a3.py`, junto con simulaciones de circuito mediante `scripts/evaluacion/fixtures/respuesta_simulada.json` que prueban el código de evaluación pero no miden a Gemini.
   - **Corridas reales con Gemini:** comprenden la operación real verificada en Supabase para el panel de consumo en `main`, la corrida real autorizada de 1 fotografía piloto (`Cocina`) publicada en `origin/HLE_Evaluacion` (`docs/evaluacion/A4_resultados.md`) y las dos corridas reales sobre 3 imágenes conservadas en la copia local de evaluación (`prueba3_gemini_origin_main_real_20261127` con 0/3 respuestas válidas en `gemini-2.5-flash` y `prueba3_gemini36_origin_main_real_20261128` con 3/3 respuestas válidas en `gemini-3.6-flash`). Los archivos crudos bajo `data/evaluacion/resultados/` están excluidos de Git; las 4 fotos restantes del piloto y 27 de las 30 fotos finales no tienen corridas reales ejecutadas.
   - **Métricas empíricas frente a anotaciones humanas (CVAT):** en `origin/HLE_Evaluacion` (`docs/evaluacion/A4_resultados.md`), la comparación con revisión humana de la foto piloto `Cocina` contra sus 5 cajas manuales de CVAT arrojó 4/4 detecciones identificadas correctamente (100 %), cobertura de 2/5 referencias CVAT (40 %), IoU promedio de 0,7459 sobre los 2 pares confirmados (ambos con $\text{IoU} \ge 0{,}50$), 4/4 en traducción y gramática EN/ES, y 3/3 en pertinencia revisada con 1 frase pendiente en ambos idiomas. En la copia local de evaluación, `prueba3_gemini_origin_main_real_20261127` tiene todas las métricas CVAT en `null` (por 0 respuestas válidas), mientras que `prueba3_gemini36_origin_main_real_20261128` cuenta con métricas geométricas automáticas preliminares sobre 3 imágenes (12/12 resueltas con precisión provisional de 100 %, cobertura 12/56 = 21,43 %, IoU promedio 0,8725 con 12/12 pares $\ge 0{,}50$, 1 identificación pendiente y 13 revisiones lingüísticas pendientes).

3. **Observaciones de alcance entre requisitos e implementación actual en `main`:**
   - **`RF05` / `HU03` (Validación de interior doméstico):** `homelens/analisis.py` y `homelens/prompts/exploracion.txt` validan primero que la fotografía muestre un interior doméstico; si es un exterior u otro entorno fuera del hogar, devuelven el estado `FUERA_DE_ALCANCE` con listas vacías de objetos y actividades.
   - **`RF14` / `HU09` (Catálogo base en Find It):** mientras `RF14` indica generar desafíos a partir del vocabulario previamente explorado por el usuario, `homelens/practicas.py` y `homelens/ui/find_it.py` combinan el vocabulario explorado del usuario con 6 objetos domésticos predeterminados (`Coffee Mug`, `Book`, `Chair`, `Lamp`, `Keys`, `Spoon`) para permitir jugar incluso sin exploraciones guardadas, y persisten directamente los intentos en `public.intentos_practica` sin utilizar una tabla `desafios_find_it` separada. Se señala esta diferencia para confirmación formal del equipo.
   - **`RF08` / `RT05` (Activación de Google Cloud TTS):** el módulo M5 (`homelens/audio.py`, `homelens/integraciones/tts.py`, `homelens/ui/audio.py`) implementa la generación bajo demanda, las tres velocidades de frase y la caché por sesión, pero mantiene las llamadas reales bloqueadas por defecto hasta habilitar `GOOGLE_TTS_ENABLED=true` y credenciales ADC en el entorno (`docs/TAREA8_AUDIO_BAJO_DEMANDA.md`).

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
