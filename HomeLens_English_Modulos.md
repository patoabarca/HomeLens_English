# HomeLens English

## Especificación de módulos

Versión del 3 de octubre de 2026. Base para organizar el código, conectar sus partes y posteriormente distribuir el desarrollo entre los tres integrantes. Este documento conserva la modularización M0 a M8 trabajada en equipo; no asigna tareas ni responsabilidades a personas.

Los módulos agrupan el código por responsabilidad. Pueden funcionar dentro de una misma aplicación y un mismo contenedor Docker. Python y Streamlit se mantienen como base propuesta; Supabase Auth con ingreso mediante Google, PostgreSQL en Supabase y Google Cloud Text-to-Speech requieren validación técnica.

El detalle de estructuras y funciones está en [Diseño de datos, funciones y carpetas](HomeLens_English_Datos_funciones_y_carpetas.md). Las necesidades y condiciones de aceptación se encuentran en [Historias de usuario](HomeLens_English_Historias_de_usuario.md) y [Requisitos y restricciones](HomeLens_English_Requisitos_y_restricciones.md).

## M0 Configuración y entorno

**Objetivo:** permitir que la aplicación se ejecute con una configuración consistente en las computadoras del equipo.

**Responsabilidades:**

- Definir dependencias y versión de Python.
- Preparar la ejecución con Docker.
- Leer variables de entorno y comprobar la configuración necesaria.
- Proporcionar parámetros de servicios, límites, tiempos de espera y reintentos.
- Configurar los registros técnicos de errores, duración de operaciones y consumo.

**Entradas:** variables de entorno y archivos de configuración.

**Salidas:** configuración validada y servicios de registro disponibles.

**Dependencias:** no depende de los demás módulos; los demás utilizan su configuración.

**Verificación:** la aplicación inicia siguiendo las instrucciones del proyecto. Si falta una configuración obligatoria, informa el problema sin mostrar credenciales.

**Requisitos relacionados:** RNF05, RNF16 y RNF17; soporte para RNF11 y RNF12. Docker constituye una decisión técnica adicional que deberá incorporarse a la siguiente revisión del documento integral.

## M1 Acceso de usuarios

**Objetivo:** identificar a la persona y permitirle acceder únicamente a su información.

**Responsabilidades:**

- Iniciar y cerrar sesión.
- Recuperar una identidad estable del usuario.
- Comprobar que las operaciones protegidas tengan una sesión válida.
- Proporcionar el contexto del usuario a las consultas y al guardado de datos.
- Gestionar la expiración de sesión con un mensaje comprensible.

**Entradas:** resultado del mecanismo de autenticación y estado de sesión.

**Salidas:** contexto de usuario autenticado o indicación de que debe ingresar.

**Dependencias:** M0 y el proveedor de autenticación propuesto.

**Verificación:** dos usuarios ingresan y recuperan sus respectivos historiales; ninguno accede a registros del otro. Cerrar sesión impide continuar realizando operaciones protegidas.

**Historias relacionadas:** HU01 y aspectos de HU12.

**Requisitos relacionados:** RF01 y RF18; RNF04, RNF05 y RNF06.

La separación de datos requiere trabajo conjunto con M7: ocultar información en pantalla no sustituye el control de acceso en el servidor.

## M2 Captura y preparación de imágenes

**Objetivo:** obtener una imagen válida y prepararla para el análisis.

**Responsabilidades:**

- Recibir fotografías de la cámara o archivos cargados y permitir revisión y reemplazo antes del envío.
- Admitir JPEG y PNG reales de hasta 10 000 000 bytes.
- Comprobar formato y decodificación.
- Corregir orientación y ajustar dimensiones cuando corresponda.
- Mantener correspondencia entre la imagen enviada y la mostrada.
- Gestionar limpieza de recursos temporales.

**Entradas:** archivo de imagen y confirmación del usuario.

**Salidas:** imagen preparada y dimensiones para su visualización, o error de validación.

**Dependencias:** M0. Los controles de cámara y carga pertenecen a la vista; el procesamiento de bytes no depende de Streamlit.

**Verificación:** acepta imágenes admitidas y rechaza archivos inválidos antes de llamar a Gemini. Conserva la orientación correcta. Reemplazar una fotografía no inicia automáticamente el análisis.

**Historias relacionadas:** HU02 y entrada de imagen de HU10.

**Requisitos relacionados:** RF02, RF03, RF04 y RF19; RNF07 y RNF15.

## M3 Análisis con Gemini

**Objetivo:** concentrar la comunicación con Gemini y entregar resultados estructurados utilizables por la aplicación.

| Operación | Entrada | Salida |
| --- | --- | --- |
| Analizar exploración | Imagen preparada e instrucciones educativas. | Objetos, recuadros, nombres bilingües, ejemplos y cuestionario. |
| Verificar Find it | Imagen preparada y objeto solicitado. | Encontrado, no encontrado o no se puede determinar. |

**Responsabilidades:**

- Construir instrucciones y esquema de respuesta.
- Ejecutar una llamada principal por exploración y la verificación específica de Find it.
- Validar campos, cantidad de objetos, coordenadas y estructura de preguntas.
- Controlar tiempos, solicitudes y reintentos.
- Registrar duración y consumo sin guardar fotografías ni claves en los registros.

**Entradas:** imagen preparada, contexto validado del usuario y datos del desafío cuando corresponda.

**Salidas:** exploración o verificación válida, o error controlado. Un resultado sin objetos puede ser válido; una respuesta inválida no se presenta como exploración correcta.

**Dependencias:** M0 y Gemini; recibe imágenes preparadas por M2.

**Verificación:** admite uno, varios o ningún objeto; rechaza respuestas mal estructuradas y recuadros fuera de rango; admite incertidumbre en Find it y no exige que el objeto buscado sea uno de los cinco predominantes.

**Historias relacionadas:** HU03, HU04, HU06, HU10 y HU12.

**Requisitos relacionados:** RF05, RF15, RF16 y RF20; RNF11 a RNF14 y RNF17; RT01 a RT04 y RT07.

La validación automática comprueba estructura y reglas de datos. La precisión visual y la calidad educativa requieren evaluación con el conjunto de pruebas acordado. No se utiliza una confianza inventada por el modelo como medición real.

## M4 Exploración y contenido educativo

**Objetivo:** presentar de forma clara el resultado de una exploración.

**Responsabilidades:**

- Mostrar fotografía y recuadros adaptados al tamaño de visualización.
- Asociar cada recuadro con su tarjeta.
- Mostrar nombres, traducciones y ejemplos.
- Mantener el resultado al cambiar de tarjeta.
- Informar cuando no se identifiquen objetos.

**Entradas:** resultado validado de M3 e imagen temporal activa.

**Salidas:** vista de exploración y selección del contenido que el usuario quiere consultar.

**Dependencias:** resultados de M2 y M3; ofrece acciones para M5 y M6.

**Verificación:** los recuadros mantienen su ubicación al cambiar el tamaño de pantalla y se corresponden con las tarjetas. Navegar no llama nuevamente a Gemini. El historial puede mostrar tarjetas de texto sin la foto original.

**Historias relacionadas:** HU03 y HU04.

**Requisitos relacionados:** RF05, RF06 y RF07; RNF01 a RNF03 y RNF12.

## M5 Audio

**Objetivo:** permitir escuchar palabras y frases en inglés bajo demanda.

**Responsabilidades:**

- Recibir texto válido del contenido seleccionado.
- Buscar un audio reutilizable o solicitar su generación.
- Identificar audios por texto, idioma, voz y velocidad.
- Gestionar la caché temporal y los errores de generación.

**Entradas:** texto, configuración de voz y solicitud explícita.

**Salidas:** audio para reproducir o error comprensible.

**Dependencias:** M0 y Google Cloud Text-to-Speech como servicio propuesto.

**Verificación:** mostrar una tarjeta no genera audio. Pulsar el botón puede generarlo; repetir un audio disponible reutiliza el resultado. Un fallo no impide consultar texto ni realizar actividades.

**Historias relacionadas:** HU05 y aspectos de HU12.

**Requisitos relacionados:** RF08 y RF18; RNF10 a RNF12; RT05.

La especificación técnica propone caché temporal por sesión de usuario, con límites y caducidad configurables. La vista reproduce el audio recibido.

## M6 Prácticas y Find it

**Objetivo:** gestionar las actividades y sus resultados.

| Parte | Responsabilidad |
| --- | --- |
| Cuestionarios | Presentar preguntas, recibir y corregir respuestas y repetir actividades anteriores. |
| Find it | Seleccionar desafíos del vocabulario propio, recibir fotografías y gestionar verificaciones. |

**Responsabilidades:**

- Mantener la solución oculta hasta confirmar y corregir con la respuesta canónica guardada.
- Mostrar explicaciones sin nuevas llamadas a Gemini para corregir cuestionarios.
- Seleccionar y cambiar desafíos sin llamar al modelo.
- Solicitar a M3 la verificación de Find it.
- Tratar la incertidumbre como resultado neutral, sin penalización.
- Guardar intentos mediante M7 y evitar duplicados.

**Entradas:** actividad, opción elegida, vocabulario anterior y nueva imagen cuando corresponda.

**Salidas:** resultado de práctica y registro del intento.

**Dependencias:** M1, M3 y M7; utiliza M2 para imágenes de Find it.

**Verificación:** corrige localmente, conserva intentos anteriores al repetir y no duplica una confirmación. Los casos indeterminables no se contabilizan como errores. Reintentar un guardado fallido reutiliza el resultado obtenido y no vuelve a verificar la fotografía.

**Historias relacionadas:** HU06, HU08, HU09, HU10 y HU12.

**Requisitos relacionados:** RF09, RF10 y RF13 a RF18; RNF09 y RNF12; RT06 y RT07.

Cada práctica voluntaria nueva genera una nueva clave de intento. Doble pulsación o reintento de la misma operación mantiene su clave. Los errores técnicos no se guardan como resultados educativos.

## M7 Persistencia e historial

**Objetivo:** guardar y recuperar información propia de cada usuario entre sesiones.

**Responsabilidades:**

- Guardar exploraciones utilizables, objetos, traducciones, ejemplos y actividades con sus soluciones.
- Registrar fechas y resultados de intentos.
- Recuperar historial y vocabulario para repaso.
- Aplicar controles de acceso y pertenencia de registros.
- Evitar duplicados y guardados parciales.
- Mantener datos tras reinicios.

**Entradas:** contexto del usuario y datos validados de exploraciones y prácticas.

**Salidas:** confirmaciones de guardado, historial y datos para actividades y progreso.

**Dependencias:** M0, identidad de M1 y base seleccionada.

**Verificación:** cerrar sesión o reiniciar no borra historial. Un usuario no consulta ni modifica datos de otro. La exploración y sus componentes se guardan atómicamente; el reintento no duplica registros. Las fotografías no forman parte del historial.

**Historias relacionadas:** HU07 y soporte para HU01, HU06 y HU08 a HU11.

**Requisitos relacionados:** RF11 a RF14 y RF17; RNF04 y RNF07 a RNF09; RT09.

Se propone PostgreSQL en Supabase. SQLite queda como contingencia de demostración con revisión independiente del acceso y del alcance. El contrato del repositorio permite cambiar el almacenamiento sin trasladar consultas a la interfaz.

## M8 Progreso

**Objetivo:** mostrar vocabulario explorado y resultados de prácticas.

**Responsabilidades:**

- Consultar vocabulario e intentos.
- Distinguir palabras exploradas y practicadas.
- Mostrar fechas y resultados.
- Separar cuestionarios y Find it.
- Excluir casos indeterminables del cómputo de errores y aciertos evaluables.
- Mostrar un estado inicial cuando no hay actividad.

**Entradas:** vocabulario e historial recuperados con M7.

**Salidas:** resumen de progreso.

**Dependencias:** M1 y M7.

**Verificación:** el resumen coincide con los registros. Una palabra solo mostrada permanece explorada. Repetir prácticas mantiene resultados anteriores. No se declara una palabra aprendida por verla o practicarla una sola vez.

**Historias relacionadas:** HU11.

**Requisitos relacionados:** RF17 y RF18; RNF01 a RNF04.

Una palabra se considera practicada si está relacionada explícitamente con una pregunta confirmada o un desafío evaluable. INDETERMINABLE no cambia por sí solo ese estado. Si no hay intentos evaluables, se muestra sin datos de aciertos.

## Interfaz y responsabilidades transversales

La interfaz Streamlit recoge acciones y presenta resultados. Las pantallas delegan llamadas, correcciones y consultas a los módulos; el estado temporal de sesión no sustituye la base de datos ni los controles de autorización.

HU12, privacidad, seguridad y consumo atraviesan varios módulos. Cada operación devuelve un resultado utilizable o un error comprensible; las claves permanecen protegidas; los fallos de una operación no borran datos previos y las llamadas externas ocurren únicamente cuando el recorrido las necesita.

La imagen se conserva temporalmente para visualizar la exploración activa y se libera al salir, reemplazarla o cerrar sesión. Los temporales de procesamiento se limpian al finalizar, también ante fallos. Debe verificarse el comportamiento ante abandono o desconexión. La aplicación no promete controlar la retención que realicen servicios externos.

## Conexiones principales

| Conexión | Acuerdo |
| --- | --- |
| M2 a M3 | Imagen preparada con orientación y dimensiones coherentes. |
| M3 a M4 | Exploración validada, objetos y recuadros vinculados. |
| M3 a M6 | Preguntas con solución canónica para corrección local. |
| M6 a M3 | Objeto específico e imagen nueva para Find it. |
| M6 a M7 | Intentos con clave estable para evitar duplicados. |
| M7 a M8 | Vocabulario e intentos para calcular progreso. |
| M1 a operaciones protegidas | Identidad comprobada y control de pertenencia. |

## Orden inicial de desarrollo

| Etapa | Resultado |
| --- | --- |
| 1 Entorno y contratos | M0 y estructuras compartidas. |
| 2 Exploración mínima | M2, M3 y M4 conectados; primero con datos ficticios y después con Gemini. |
| 3 Acceso y datos | M1 y M7: guardar y recuperar con separación entre dos usuarios. |
| 4 Audio y cuestionarios | M5 y primera parte de M6, con registro de intentos. |
| 5 Find it y repaso | Completar M6 con vocabulario e historial persistidos. |
| 6 Progreso y evaluación | M8 y pruebas de calidad, privacidad, compatibilidad, tiempos y consumo. |

El entorno con Docker y los contratos se preparan primero. La prueba temprana de autenticación y persistencia permitirá confirmar las tecnologías propuestas antes de ampliar las funcionalidades.


---

## M9 (módulo anexo) Evaluación académica, dataset y reproducibilidad

**Actualización del 20 de octubre de 2026.** Este módulo es un **anexo metodológico** a la especificación M0–M8: no reemplaza ni modifica los módulos funcionales, sus contratos, las historias de usuario ni los requisitos de la aplicación. Reúne tareas necesarias para evaluar HomeLens English como trabajo final de la Diplomatura en IA. Su trabajo se realiza en paralelo al desarrollo de las partes 5 a 15.

**Objetivo:** construir un proceso verificable y reproducible para seleccionar imágenes, ejecutar experimentos comparativos con Gemini, medir la calidad y el rendimiento de HomeLens y documentar los resultados para la entrega académica.

**Distinción fundamental:** HomeLens **no entrena ni ajusta los pesos de Gemini** para aprender un conjunto cerrado de objetos. Utiliza un modelo multimodal previamente entrenado. Las fotografías constituyen un **dataset de evaluación** de reconocimiento, ubicación y generación educativa; las mejoras que se estudien se refieren al diseño de prompts, el esquema de salida, las validaciones y la integración. La comparación de prompts no equivale a entrenamiento de modelos. Esta estrategia deberá consultarse con el docente si exige específicamente entrenamiento propio.

### M9.1 Dataset de evaluación (A1)

**Fuente propuesta:** un único dataset público, **Open Images V7**. Se seleccionarán fotografías reales de objetos y, en lo posible, escenas domésticas de distintas características. Las categorías de Open Images se utilizarán para **buscar y organizar imágenes**, no como límite del vocabulario que Gemini puede reconocer.

**Procedimiento planificado:**

1. Establecer criterios de selección y buscar aproximadamente **200 fotografías candidatas**, sujetas a disponibilidad y condiciones de uso del dataset.
2. Revisar su pertinencia, diversidad, calidad, autorizaciones/licencias y anotaciones antes de seleccionar un **objetivo de 120 fotografías**.
3. Reservar **20 fotografías para desarrollo/piloto** y **100 para evaluación final**. Evitar que fotografías repetidas, casi idénticas o de una misma escena estén en ambos conjuntos.
4. Documentar ambientes, objetos observables, complejidad, iluminación, presencia de objetos parcialmente ocultos, identificadores, referencias de procedencia y anotaciones disponibles.
5. Auditar manualmente las etiquetas y los recuadros utilizados como referencia: que un objeto no aparezca anotado no demuestra que esté ausente de la fotografía. No se considerarán errores automáticamente las omisiones de objetos secundarios cuando la aplicación selecciona hasta cinco.
6. Conservar un registro de descartes y de las decisiones de selección. Si el objetivo de distribución no puede alcanzarse con las imágenes admisibles, justificar el tamaño y la composición final en lugar de forzar ejemplos inadecuados.

**Privacidad y licencias:** el repositorio público no incluirá por defecto los archivos de imágenes; conservará metadatos sin información personal, referencias e instrucciones reproducibles de obtención. Antes de reproducir o redistribuir imágenes se comprobarán las condiciones de licencia/atribución de cada caso. Las fotografías de las personas usuarias de HomeLens no forman parte del dataset académico.

### M9.2 Diseño experimental y comparación (A2)

**Alternativas propuestas:**

- **A — Baseline:** Gemini con instrucciones sencillas de reconocimiento y generación educativa, con una salida normalizada para poder comparar los resultados.
- **B — HomeLens:** el **mismo modelo** con instrucciones pedagógicas especializadas, salida estructurada y validaciones del sistema.

Se compararán las alternativas con las mismas imágenes reservadas, el modelo y versión identificados y parámetros de generación comparables. Se registrarán las diferencias de prompt y esquema; la calidad semántica del modelo se medirá por separado de las respuestas rechazadas por las validaciones de la aplicación. El piloto se utilizará para definir criterios y corregir las instrucciones; después se congelarán las configuraciones para la evaluación final. No se usará el conjunto final para iterar el prompt.

**Control operativo:** estimar cuota y costo antes de ejecutar. Comparar dos configuraciones en 100 fotografías supone al menos **200 llamadas de análisis** si se hace una llamada por imagen y alternativa, sin contar piloto, repeticiones, fallos ni reintentos. Los ensayos reales no se consideran hechos hasta ejecutarlos y guardar evidencia.

### M9.3 Métricas, análisis de errores y reporte (A3)

**Dimensiones mínimas previstas:**

| Dimensión | Qué se registrará |
| --- | --- |
| Reconocimiento | Precisión de los objetos *mostrados* (presencia y nombre correctos), resultados vacíos y capturas para repetir. |
| Localización | Revisión visual de recuadros frente a referencias verificadas; IoU solo donde la anotación sea adecuada. |
| Calidad educativa | Corrección de traducciones, naturalidad y adecuación del inglés básico; coherencia de ejemplos. |
| Cuestionarios | Tres opciones distintas, respuesta correcta inequívoca y explicación consistente. |
| Robustez | Errores por condiciones de imagen, rechazos estructurales, fallos de servicio y casos inciertos. |
| Eficiencia | Tiempo de respuesta, tokens informados, reintentos, llamadas y costo estimado bajo supuestos explícitos. |
| Find it (cuando esté implementado) | Encontrado / no encontrado / indeterminable, con referencia manual y análisis de falsos positivos y negativos. |

Los resultados se desagregarán por ambiente y dificultad cuando el tamaño de muestra lo permita. No se presentarán porcentajes de confianza inventados por el modelo. La evaluación humana tendrá criterios y registro de quién revisó cada caso; se conservarán desacuerdos y decisiones finales. Las pruebas unitarias de esquema y estructura se informarán **separadamente** de las métricas empíricas de reconocimiento.

### M9.4 Documentación y reproducibilidad (A4)

**Entregables del anexo:** protocolo de selección y evaluación, manifiesto del dataset, scripts/notebooks de experimentación, prompts y configuración versionados, resultados tabulados, gráficos, análisis de errores, decisiones importantes, informe académico breve y evidencias de demostración.

**Ubicación sugerida, sujeta a acuerdo del equipo (no indica carpetas ya creadas):**

```text
HomeLens_English/
├── data/
│   └── evaluacion/
│       └── metadata.csv         # identificadores y anotaciones, sin fotos privadas
├── experiments/
│   └── comparar_gemini.py       # experimento independiente de la app
└── docs/
    ├── evaluacion/
    │   ├── protocolo.md
    │   ├── resultados.md
    │   └── graficos/
    ├── decisiones.md
    └── informe_final.md
```

**Entradas:** imágenes seleccionadas y sus anotaciones auditadas, versiones de M2/M3, prompts versionados, parámetros del modelo y criterios de revisión.

**Salidas:** datos de evaluación reproducibles, resultados comparativos, métricas, evidencia de errores y documentación de la defensa.

**Dependencias:** reutiliza M0 (configuración y telemetría), M2 (preparación de imágenes) y M3 (análisis); incorpora pruebas de M4, M5, M6, M7 y M8 cuando estén implementados. **No es una dependencia obligatoria de ejecución** de la aplicación para el usuario final.

**Verificación:** otra persona puede identificar el origen y la selección de imágenes, reproducir las condiciones experimentales hasta donde lo permitan las APIs y licencias, comprender las métricas y revisar resultados y límites sin acceder a claves ni datos sensibles.

**Relación con requisitos y entregas:** no se crean códigos HU/RF/RNF nuevos ni se considera satisfecho ningún requisito funcional por existir este anexo. Los aportes se consolidarán en la **parte 15, Evaluación y entrega**. La asignación individual de actividades A1–A4 figura en el anexo de **Distribución del trabajo por entregas**.

**Estado al crear este anexo:** planificación de M9; el dataset seleccionado, los experimentos, sus métricas y el informe todavía **no se consideran ejecutados ni validados**.
