# HomeLens English

## Diseño de datos funciones y carpetas

Guía técnica inicial para comenzar el desarrollo de los módulos M0 a M8. Versión del 3 de octubre de 2026.

Este documento concreta las estructuras compartidas, las funciones públicas y la organización del código acordadas en la modularización. Es una especificación propuesta para implementar y revisar en equipo; las firmas describen contratos y no constituyen código funcional ni una integración ya probada.

Python y Streamlit se mantienen como base propuesta. El acceso con Google mediante Supabase Auth, PostgreSQL en Supabase y Google Cloud Text-to-Speech requieren validación técnica. Gemini será la integración prevista para exploración y Find it. Docker se incorpora al entorno de ejecución. No se distribuyen responsabilidades entre integrantes.

## 1 Acuerdos generales del diseño

Cada módulo tendrá funciones públicas con entradas y salidas explícitas. La interfaz utilizará esas funciones, sin consultar directamente Gemini ni la base de datos. Los modelos compartidos no importarán Streamlit, clientes externos ni repositorios.

Los identificadores internos serán UUID generados por la aplicación. Las fechas se guardarán con zona horaria en UTC y se convertirán para mostrarlas. El user_id será la identidad estable validada por el proveedor de autenticación; nunca se aceptará un user_id escrito por el usuario como prueba de identidad.

Las llamadas externas y los accesos a datos devolverán Resultado[T]. Un resultado exitoso tendrá valor; un fallo tendrá ErrorOperacion. La ausencia de objetos y un resultado indeterminable de Find it son respuestas válidas del dominio, no fallos técnicos.

Las funciones puras de corrección y cálculo no llamarán servicios externos. Las firmas presentadas usan notación Python orientativa; el mecanismo síncrono o asíncrono se decidirá al integrar los clientes con Streamlit, sin alterar estos contratos.

## 2 Estructuras compartidas

### 2.1 Contexto y errores

ContextoUsuario: user_id: UUID; sesion_id: str. Representa una identidad comprobada en el servidor. Las credenciales o tokens necesarios para el proveedor se mantendrán en un contenedor privado de sesión, fuera de los modelos educativos, los registros y las respuestas visibles.

ErrorOperacion: codigo: str; mensaje_usuario: str; reintentable: bool; operacion_id: UUID. Códigos previstos: CONFIGURACION_INVALIDA, SESION_REQUERIDA, ACCESO_DENEGADO, IMAGEN_INVALIDA, LIMITE_ALCANZADO, TIEMPO_AGOTADO, SERVICIO_NO_DISPONIBLE, RESPUESTA_INVALIDA y PERSISTENCIA_FALLIDA.

Resultado[T]: ok: bool; valor: T o None; error: ErrorOperacion o None. Invariante: ok verdadero implica un valor compatible con T, incluido None cuando el contrato lo admite, y ningún error; ok falso implica un error y ningún valor. Los detalles técnicos se registran de forma saneada asociados a operacion_id, sin exponer excepciones completas al usuario.

### 2.2 Imagen y ubicación

ImagenPreparada: contenido: bytes; mime_type: str; ancho: int; alto: int. Se mantiene temporalmente en memoria y no se persiste como parte del historial. La vista usa la misma orientación y proporción que la imagen enviada al modelo. El límite de entrada es 10 000 000 bytes y los tipos admitidos son JPEG y PNG reales.

RecuadroNormalizado: ymin: int; xmin: int; ymax: int; xmax: int. Cada valor está entre 0 y 1000. Se exige ymin < ymax y xmin < xmax. El orden de intercambio es [ymin, xmin, ymax, xmax]. La validación numérica no acredita que el objeto esté correctamente señalado.

RecuadroPantalla: izquierda: float; arriba: float; ancho: float; alto: float. Se calcula para el tamaño efectivo con el que se presenta la imagen. Si la vista agrega márgenes a la imagen, se aplican los desplazamientos correspondientes; no se confunden las dimensiones del contenedor con las de la fotografía.

### 2.3 Exploraciones y objetos

EstadoAnalisis: UTILIZABLE, SIN_OBJETOS_CLAROS o REPETIR_CAPTURA. Las respuestas con lista vacía pueden ser válidas; deben distinguirse de un JSON inválido o un error del proveedor.

ObjetoEducativo: objeto_id: UUID; exploracion_id: UUID; nombre_en: str; nombre_es: str; recuadro: RecuadroNormalizado; frase_en: str; frase_es: str. Una exploración tendrá entre cero y cinco objetos. No se agregan objetos para completar un cupo.

Exploracion: exploracion_id: UUID; user_id: UUID; creada_en: datetime; estado: EstadoAnalisis; objetos: list[ObjetoEducativo]; actividades: list[Actividad]; schema_version: int. Solo se guardan exploraciones educativas válidas y utilizables. Los estados sin contenido se muestran y se contabilizan en las métricas técnicas, sin inventar vocabulario ni generar historial vacío de aprendizaje.

La respuesta de Gemini tendrá un modelo separado llamado RespuestaExploracionIA, con identificadores locales para relacionar objetos y preguntas. Tras validarla, M3 los convierte a UUID y completa las referencias internas. El proveedor no asigna user_id, fechas de registro ni identificadores de persistencia.

### 2.4 Actividades y soluciones

Opcion: opcion_id: str; texto: str. Una actividad tiene exactamente tres opciones, con identificadores y textos distintos después de normalizar espacios y mayúsculas para el control de duplicados.

Actividad: actividad_id: UUID; exploracion_id: UUID; objeto_ids: list[UUID]; pregunta: str; opciones: list[Opcion]; opcion_correcta_id: str; explicacion: str. La opción correcta existe dentro de las opciones y cada objeto relacionado pertenece a la exploración.

ActividadPublica: actividad_id: UUID; pregunta: str; opciones: list[Opcion]. Es la versión que recibe la vista antes de confirmar una respuesta. No incluye solución ni explicación. Ocultar estos campos visualmente no justifica enviar la solución a la vista antes de tiempo.

Una respuesta estructuralmente válida puede contener ambigüedades. La revisión educativa manual comprobará la existencia de una única solución inequívoca y la adecuación de las preguntas.

### 2.5 Desafíos e intentos

DesafioFindIt: desafio_id: UUID; user_id: UUID; objeto_origen_id: UUID; nombre_en: str; nombre_es: str; creado_en: datetime. Se toma de vocabulario propio previamente explorado. El desafío busca la categoría del objeto, no el ejemplar físico ni la ubicación de la fotografía anterior.

EstadoFindIt: ENCONTRADO, NO_ENCONTRADO o INDETERMINABLE. VerificacionFindIt contiene estado y mensaje breve. Un fallo de conexión no se transforma en INDETERMINABLE; sigue siendo un error técnico reintentable cuando corresponda.

IntentoPractica: intento_id: UUID; user_id: UUID; tipo: CUESTIONARIO o FIND_IT; fecha: datetime; actividad_id: UUID o None; desafio_id: UUID o None; opcion_elegida_id: str o None; resultado: CORRECTO, INCORRECTO o INDETERMINABLE; objeto_ids: list[UUID].

En un cuestionario se exige actividad_id y opción elegida; en Find it se exige desafio_id. Los campos del otro tipo quedan vacíos. INDETERMINABLE solo corresponde a Find it. Los datos canónicos y el resultado se reconstruyen en el servidor, sin confiar en referencias o resultados suministrados por la vista.

Cada confirmación crea una clave intento_id que se conserva mientras se resuelve esa misma operación. Doble pulsación, recarga o reintento del guardado reutilizan la clave. Una nueva práctica voluntaria crea una nueva clave. Los fallos técnicos no se guardan como resultados educativos.

### 2.6 Audio progreso y métricas

SolicitudAudio: texto: str; idioma: str; voz: str; velocidad: float. La clave de reutilización incluye esos cuatro valores y la configuración efectiva del proveedor cuando pueda alterar el audio.

AudioDisponible: contenido: bytes; mime_type: str; generado_en: datetime; reutilizado: bool. Para el prototipo, la caché será temporal y por sesión de usuario, con límites de cantidad o tamaño y caducidad configurables. No se guardan audios en las tablas de historial.

ResumenProgreso: palabras_exploradas: list[PalabraResumen]; total_intentos: int; resultados_por_tipo: dict. PalabraResumen incluye nombre_en, nombre_es, estado EXPLORADA o PRACTICADA y última práctica, si existe.

Se considera practicada una palabra ligada explícitamente a una pregunta confirmada o a un desafío con resultado encontrado o no encontrado. Un desafío indeterminable no cambia por sí solo ese estado. No se declara aprendida ni dominada. Las repeticiones del mismo nombre se agrupan mediante una clave sencilla de texto normalizado; la unificación de sinónimos queda fuera de esta versión.

EventoTecnico: operacion_id; tipo_operacion; fecha; duracion_ms; estado; numero_llamadas; numero_reintentos; uso_reportado; costo_estimado o None. Incluye metadatos de configuración necesarios para reproducir mediciones, sin fotografías, tokens ni respuestas completas. Si el proveedor no reporta un dato, se registra como no disponible; no se inventa.

## 3 Funciones públicas por módulo

### 3.1 M0 Configuración y entorno

Archivo principal: homelens/config.py. Registro técnico: homelens/telemetria.py.

```python
cargar_configuracion() -> Resultado[Configuracion]
```

```python
registrar_evento(evento: EventoTecnico) -> None
```

Configuracion reúne parámetros de servicios, límites, tiempos y caché. No se imprime ni se serializa con secretos en registros. El registro de métricas debe tolerar un fallo sin perder resultados educativos.

Dockerfile, compose.yaml y .dockerignore se ubican en la raíz. .env.example documenta nombres de variables con valores ficticios. .env y las credenciales reales quedan excluidos del repositorio y de la imagen Docker. Los límites definitivos se decidirán con mediciones; el piloto deberá tener un presupuesto provisional antes de llamar a servicios.

### 3.2 M1 Acceso de usuarios

Archivo principal: homelens/acceso.py. Adaptador externo: homelens/integraciones/autenticacion.py.

```python
iniciar_acceso(retorno_permitido: str) -> Resultado[SolicitudAcceso]
```

```python
completar_acceso(respuesta_proveedor: RespuestaAcceso) -> Resultado[ContextoUsuario]
```

```python
obtener_usuario_actual() -> Resultado[ContextoUsuario]
```

```python
cerrar_sesion() -> Resultado[Confirmacion]
```

SolicitudAcceso y RespuestaAcceso representan el mecanismo del proveedor elegido; no presuponen parámetros concretos de OAuth. Los retornos permitidos y la protección de la respuesta de autenticación se implementarán conforme al flujo del proveedor validado. No se guardan contraseñas propias.

Cerrar sesión elimina el contexto privado de acceso, la imagen activa y la caché de audio de esa sesión mediante la coordinación de la aplicación. Cada operación protegida verifica que la identidad siga vigente, aunque la pantalla todavía muestre un usuario.

### 3.3 M2 Captura y preparación

Archivo principal: homelens/imagenes.py.

```python
preparar_imagen(contenido: bytes) -> Resultado[ImagenPreparada]
```

```python
liberar_imagen(estado_imagen: EstadoImagenTemporal) -> None
```

La cámara y el selector de archivo están en la vista; M2 procesa los bytes y no importa Streamlit. Comprueba tamaño y formato antes de preparar. El cierre de recursos se garantiza también ante excepciones. liberar_imagen elimina referencias y temporales propios; no promete borrado físico de memoria ni de copias externas.

### 3.4 M3 Análisis con Gemini

Archivo principal: homelens/analisis.py. Adaptador: homelens/integraciones/gemini.py. Instrucciones: homelens/prompts/.

```python
analizar_exploracion(usuario: ContextoUsuario, imagen: ImagenPreparada, operacion_id: UUID) -> Resultado[Exploracion]
```

```python
verificar_find_it(usuario: ContextoUsuario, imagen: ImagenPreparada, desafio: DesafioFindIt, operacion_id: UUID) -> Resultado[VerificacionFindIt]
```

M3 utiliza modelos de respuesta externos y validadores internos. Aplica controles de consumo antes de cada llamada; los reintentos comparten operacion_id y cuentan individualmente. No guarda directamente en la base de datos. En Find it se comprueba que el desafío pertenece al usuario antes de enviarlo.

La configuración del cliente vive en la integración; el prompt y el esquema se versionan. Ajustar instrucciones no debe obligar a modificar la vista o el repositorio. La selección o navegación de tarjetas no invoca estas funciones.

### 3.5 M4 Exploración y contenido

Archivo principal: homelens/exploracion.py. Vista: homelens/ui/exploracion.py.

```python
adaptar_recuadro(recuadro: RecuadroNormalizado, ancho_visible: int, alto_visible: int) -> RecuadroPantalla
```

```python
construir_tarjetas(exploracion: Exploracion) -> list[TarjetaObjeto]
```

```python
mostrar_exploracion(exploracion: Exploracion, imagen: ImagenPreparada) -> AccionExploracion | None
```

Las dos primeras funciones son puras; mostrar_exploracion pertenece a la vista. AccionExploracion indica una intención, por ejemplo escuchar palabra, escuchar frase o iniciar práctica, con el identificador del objeto correspondiente. La coordinación resuelve esa intención mediante M5 o M6.

La vista de historial muestra tarjetas de texto sin exigir fotografía. No debe intentar dibujar recuadros sobre una imagen que ya fue eliminada.

### 3.6 M5 Audio

Archivo principal: homelens/audio.py. Adaptador: homelens/integraciones/tts.py.

```python
obtener_audio(usuario: ContextoUsuario, solicitud: SolicitudAudio, operacion_id: UUID) -> Resultado[AudioDisponible]
```

```python
limpiar_cache_audio(sesion_id: str) -> None
```

Solo se acepta texto de una palabra o frase válida del contenido del usuario; la coordinación lo resuelve desde su identificador. Una petición arbitraria de texto no se expone como función libre en la pantalla. Los aciertos de caché no generan una llamada TTS. La reproducción efectiva la realiza la vista con el audio recibido.

### 3.7 M6 Prácticas y Find it

Archivo principal: homelens/practicas.py. Las vistas se ubican en homelens/ui/practicas.py y homelens/ui/find_it.py.

```python
obtener_actividad_publica(usuario: ContextoUsuario, actividad_id: UUID) -> Resultado[ActividadPublica]
```

```python
responder_actividad(usuario: ContextoUsuario, actividad_id: UUID, opcion_id: str, intento_id: UUID) -> Resultado[ResultadoPractica]
```

```python
crear_desafio(usuario: ContextoUsuario, excluir_objeto_id: UUID | None = None) -> Resultado[DesafioFindIt]
```

```python
resolver_desafio(usuario: ContextoUsuario, desafio_id: UUID, imagen: ImagenPreparada, intento_id: UUID) -> Resultado[ResultadoPractica]
```

M6 recupera actividad o desafío mediante M7, verifica pertenencia y calcula el resultado. responder_actividad usa la solución canónica sin consultar al modelo. resolver_desafio solicita a M3 la verificación y traduce sus estados a resultados educativos. M6 guarda el intento mediante M7 antes de declararlo registrado.

ResultadoPractica incluye intento_id, resultado, explicación y registrado: bool. Si falla el guardado, se mantiene el resultado pendiente de esa operación y se ofrece reintentar solo su registro con la misma clave. No se vuelve a llamar a Gemini para persistir una verificación ya obtenida. La recuperación tras una recarga requiere conservar el resultado pendiente en el estado de sesión; si se pierde ese estado antes de guardarlo, se informa que no quedó registrado.

Antes de resolver un intento ya persistido, M6 lo recupera y devuelve el mismo resultado. Durante una operación en curso, la coordinación bloquea nuevas confirmaciones con su clave. Cambiar de desafío permite excluir la categoría anterior cuando exista otra; si no hay alternativa, lo informa. Elegir un desafío no llama a Gemini.

### 3.8 M7 Persistencia e historial

Contrato: homelens/datos/repositorio.py. Implementación propuesta: homelens/datos/supabase_repo.py.

```python
guardar_exploracion(usuario: ContextoUsuario, exploracion: Exploracion) -> Resultado[UUID]
```

```python
listar_exploraciones(usuario: ContextoUsuario, limite: int, cursor: str | None) -> Resultado[Pagina[ExploracionResumen]]
```

```python
obtener_exploracion(usuario: ContextoUsuario, exploracion_id: UUID) -> Resultado[Exploracion]
```

```python
obtener_actividad(usuario: ContextoUsuario, actividad_id: UUID) -> Resultado[Actividad]
```

```python
listar_vocabulario(usuario: ContextoUsuario) -> Resultado[list[ObjetoEducativo]]
```

```python
guardar_desafio(usuario: ContextoUsuario, desafio: DesafioFindIt) -> Resultado[UUID]
```

```python
obtener_desafio(usuario: ContextoUsuario, desafio_id: UUID) -> Resultado[DesafioFindIt]
```

```python
guardar_intento(usuario: ContextoUsuario, intento: IntentoPractica) -> Resultado[Confirmacion]
```

```python
obtener_intento(usuario: ContextoUsuario, intento_id: UUID) -> Resultado[IntentoPractica | None]
```

```python
listar_intentos(usuario: ContextoUsuario, desde: datetime | None = None) -> Resultado[list[IntentoPractica]]
```

Ninguna consulta omite la comprobación de pertenencia. Las relaciones entre exploración, objeto, actividad y desafío se validan en el servidor y se respaldan mediante restricciones de base de datos. En Supabase se configurarán políticas de acceso acordes con el mecanismo usado; el filtrado por user_id no reemplaza la autorización. Si una credencial de servidor evita esas políticas, la capa de datos deberá mantener las comprobaciones y no exponerla.

La exploración, sus objetos y sus actividades se guardan de forma atómica mediante una operación transaccional de base de datos. No se considera guardada si solo se insertó una parte. El identificador de exploración evita duplicarla al reintentar. intento_id es único; la misma clave y el mismo contenido devuelven confirmación sin duplicar, mientras que contenido diferente con la misma clave produce error.

### 3.9 M8 Progreso

Archivo principal: homelens/progreso.py. Vista: homelens/ui/progreso.py.

```python
obtener_progreso(usuario: ContextoUsuario) -> Resultado[ResumenProgreso]
```

```python
calcular_progreso(vocabulario: list[ObjetoEducativo], intentos: list[IntentoPractica]) -> ResumenProgreso
```

La primera coordina consultas con M7; la segunda es pura. Cuestionarios y Find it se presentan por separado. Los resultados indeterminables se informan aparte y se excluyen del denominador de aciertos sobre intentos evaluables. Si no hay intentos evaluables, se muestra sin datos; no se inventa un porcentaje de cero o de cien.

## 4 Persistencia propuesta

Las estructuras compartidas no obligan a usar una tabla por cada modelo. La siguiente propuesta separa los registros principales y mantiene opciones y ejemplos sencillos en campos estructurados cuando corresponda. El SQL definitivo se elaborará después de validar la integración de acceso y datos.

| Tabla | Contenido y relaciones |
| --- | --- |
| exploraciones | id, user_id, fecha, estado y versión de esquema. Raíz de objetos y actividades. |
| objetos | id, exploracion_id, nombres, ejemplos y recuadro estructurado. |
| actividades | id, exploracion_id, pregunta, opciones estructuradas, opción correcta y explicación. |
| actividad_objetos | actividad_id y objeto_id. Permite relacionar una pregunta con uno o varios objetos. |
| desafios_find_it | id, user_id, objeto_origen_id, nombres del objeto solicitado y fecha. |
| intentos | id, user_id, tipo, actividad_id o desafio_id, opción elegida, resultado y fecha. |

Los objetos practicados se derivan de las relaciones de la actividad o del desafío canónico. objeto_ids del modelo de intento es una proyección para cálculo, no un dato libre que la vista pueda alterar. Se usan claves foráneas, unicidad y comprobaciones del tipo de intento; las verificaciones entre relaciones también impiden enlazar registros de otros usuarios.

No se incluyen fotos, claves, tokens ni audios en estas tablas. Los registros técnicos tienen un destino separado del historial educativo. La base de datos no mantiene una tabla propia de contraseñas. Si se adopta SQLite para una demostración, su adaptador implementará el mismo contrato de repositorio y su archivo tendrá un volumen persistente; la autenticación y el alcance se revisarán por separado.

## 5 Carpetas y archivos

| Ruta relativa | Responsabilidad |
| --- | --- |
| app.py | Entrada de Streamlit y coordinación de pantallas. Delega los recorridos a los módulos. |
| homelens/modelos.py | Estructuras y estados de dominio compartidos. Sin dependencias de interfaz o servicios. |
| homelens/errores.py | Resultado, ErrorOperacion y códigos comunes. |
| homelens/config.py y telemetria.py | M0: configuración y eventos técnicos. |
| homelens/acceso.py | M1: acceso y contexto de identidad. |
| homelens/imagenes.py | M2: preparación y liberación de imágenes. |
| homelens/analisis.py | M3: exploración y verificación con sus validaciones. |
| homelens/exploracion.py | M4: tarjetas y adaptación de recuadros. |
| homelens/audio.py | M5: obtención y caché temporal de audio. |
| homelens/practicas.py | M6: cuestionarios, desafíos y registro de intentos. |
| homelens/progreso.py | M8: consulta y cálculo del progreso. |
| homelens/datos/ | M7: repositorio.py y supabase_repo.py. sqlite_repo.py solo si se adopta la contingencia. |
| homelens/integraciones/ | autenticacion.py, gemini.py y tts.py. Encapsulan los clientes externos. |
| homelens/prompts/ | exploracion.txt y find_it.txt; instrucciones versionadas. |
| homelens/esquemas_ia.py | Modelos de respuesta del proveedor separados del dominio y de persistencia. |
| homelens/ui/ | acceso.py, captura.py, exploracion.py, practicas.py, find_it.py, historial.py y progreso.py. |
| homelens/ui/estado.py | Estado por sesión, operaciones pendientes, acciones e invalidación al cambiar usuario. |
| migrations/ | SQL versionado: tablas, restricciones y políticas de acceso. |
| tests/ | Casos de validación, corrección, pertenencia e idempotencia; simulaciones de servicios externos. |
| evaluacion/ | Rúbrica, manifiesto de casos y resultados manuales. Fotografías autorizadas se gestionan aparte. |
| docs/ | Acuerdos técnicos y guía del equipo. |
| Dockerfile y compose.yaml | Construcción y ejecución del entorno compartido. |
| .dockerignore y .gitignore | Exclusión de secretos, temporales y materiales locales. |
| .env.example | Nombres de configuración con valores ficticios. |
| pyproject.toml y archivo de bloqueo | Dependencias y versiones reproducibles; herramienta de gestión pendiente de elección. |
| README.md | Instalación, configuración, ejecución y recorrido de demostración. |

Los paquetes Python incorporarán sus archivos __init__.py. Las rutas describen el código que se creará; este documento no afirma que esos archivos ya existan. No se agregan capas separadas por cada función ni un contenedor por cada módulo.

## 6 Recorridos y coordinación

### 6.1 Explorar y guardar

1. La vista obtiene el usuario mediante M1 y recibe los bytes de la imagen. M2 valida y prepara. La vista permite revisar sin llamar a Gemini.

2. Al confirmar Analizar, la coordinación asigna operacion_id, marca la operación en curso y llama una vez a M3, con reintentos controlados si corresponden.

3. Una respuesta inválida se informa como error; una respuesta sin objetos o que requiere nueva captura se muestra sin generar vocabulario. Una exploración utilizable se conserva en el estado de sesión y se envía a M7.

4. M7 guarda atómicamente la exploración. Si falla, se muestra que el contenido está disponible temporalmente pero no quedó guardado; reintentar persistencia no repite el análisis.

5. M4 muestra la exploración y la copia temporal de la imagen. Navegar, escuchar o practicar utiliza el resultado existente. Al salir o reemplazarla, se liberan sus recursos temporales.

### 6.2 Responder y repasar

1. M6 recupera la actividad propia y entrega ActividadPublica. Al confirmar, la vista conserva intento_id y la opción elegida para esa operación.

2. M6 valida la opción, calcula la respuesta y guarda con M7. Repetir la misma confirmación recupera el mismo intento; iniciar otra práctica genera otra clave.

3. El resultado y la explicación se muestran después de confirmar. El repaso recupera contenido persistido; no necesita fotografías ni una nueva generación.

### 6.3 Buscar con Find it

1. M6 selecciona vocabulario del usuario y guarda un desafío. La consigna usa su categoría en inglés.

2. M2 prepara la foto nueva. Al confirmar, M6 recupera el desafío propio y M3 verifica específicamente la categoría solicitada.

3. M6 registra encontrado, no encontrado o indeterminable mediante M7. Ante incertidumbre se permite otra captura con una nueva clave de intento sin sumar un error al estudiante.

4. Un fallo de servicio se informa como fallo técnico. Si la respuesta válida ya existe y falla solo el guardado, el reintento utiliza ese resultado pendiente sin repetir la llamada.

### 6.4 Sesión y recursos

El estado de interfaz será por sesión de usuario, no global entre usuarios. Mantendrá imagen activa, exploración disponible, selección de tarjeta, actividad o desafío y operaciones pendientes. No será la fuente definitiva del historial ni de la autorización.

Cambiar de usuario o cerrar sesión invalida los datos temporales de esa sesión. El diseño prioriza bytes en memoria y evita archivos de imagen en disco. Si una biblioteca requiere temporales, se cierran y eliminan con un bloque de limpieza incluso ante fallos; se comprobará el comportamiento de abandono y desconexión en la prueba móvil. No se promete persistir imágenes para recuperarlas tras reinicios.

## 7 Primeras verificaciones y secuencia de implementación

| Paso | Resultado verificable |
| --- | --- |
| 1 Modelos y entorno | Estructuras compartidas acordadas; aplicación mínima inicia en Docker; configuración faltante se informa sin secretos. |
| 2 Flujo simulado | Una respuesta ficticia permite cargar imagen, mostrar recuadros y tarjetas y corregir una pregunta sin APIs. |
| 3 Prueba de Gemini | Una imagen produce el esquema previsto; casos inválidos, vacíos y coordenadas fuera de rango se manejan explícitamente. |
| 4 Acceso y persistencia | Dos usuarios guardan y recuperan registros propios; el acceso ajeno falla; el guardado parcial y duplicado se evita. |
| 5 Audio y prácticas | El audio solo se genera por solicitud; caché y fallos se prueban; confirmar dos veces no duplica intentos. |
| 6 Find it y progreso | Se prueban objeto presente, ausente e indeterminable; un reintento de persistencia no vuelve a verificar la imagen. |
| 7 Evaluación integral | Calidad educativa, reconocimiento, dispositivos, tiempos y consumo se miden con el método acordado. |

Las pruebas automatizadas prioritarias cubren validación de imágenes y respuestas, corrección local, autorización de datos, idempotencia y cálculo del progreso. Los servicios externos se simulan para probar fallos sin gastar por cada ejecución. La precisión visual, el contenido y la usabilidad se revisan además de forma manual.

Quedan por validar el mecanismo concreto de acceso en Streamlit, alojamiento, versión del modelo, cliente y dependencias, límites y tiempos de corte, caducidad de caché y matriz de dispositivos. Estas decisiones podrán modificar adaptadores o configuración; cualquier cambio que afecte al comportamiento del usuario también actualizará las historias y los requisitos.
