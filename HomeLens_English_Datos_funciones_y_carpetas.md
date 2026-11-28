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

EstadoAnalisis: `UTILIZABLE`, `SIN_OBJETOS_CLAROS`, `REPETIR_CAPTURA` o `FUERA_DE_ALCANCE` (definido en `homelens/modelos.py`). Las respuestas sin objetos (`SIN_OBJETOS_CLAROS`, `REPETIR_CAPTURA` o `FUERA_DE_ALCANCE` cuando la imagen no corresponde a un interior doméstico) son estados válidos del dominio; deben distinguirse de un JSON inválido o un error del proveedor.

ObjetoEducativo: `objeto_id: UUID`; `exploracion_id: UUID`; `nombre_en: str`; `nombre_es: str`; `recuadro: RecuadroNormalizado`; `frase_en: str`; `frase_es: str`. Una exploración utilizable tiene entre uno y cinco objetos. No se agregan objetos para completar un cupo.

Exploracion: `exploracion_id: UUID`; `user_id: UUID`; `creada_en: datetime`; `estado: EstadoAnalisis`; `objetos: list[ObjetoEducativo]`; `actividades: list[Actividad]`; `schema_version: int`. Solo se guardan exploraciones educativas con estado `UTILIZABLE`. Los estados sin contenido se muestran y se contabilizan en las métricas técnicas, sin inventar vocabulario ni generar historial vacío de aprendizaje.

**Dónde se define el esquema JSON solicitado a Gemini y dónde se valida en Python:**
- **Definición del esquema JSON pedido a Gemini:** en `homelens/esquemas_ia.py` se declaran los modelos Pydantic `RespuestaExploracionIA` (compuesto por `ObjetoIA`, `RecuadroIA`, `ActividadIA` y `OpcionIA`) para la exploración visual, y `RespuestaFindItIA` para la verificación de desafíos Find It. En `homelens/integraciones/gemini.py`, `AdaptadorGemini._ejecutar_llamada_multimodal` pasa ese modelo en `types.GenerateContentConfig(response_mime_type="application/json", response_schema=esquema_respuesta, system_instruction=instrucciones)` junto con las instrucciones versionadas de `homelens/prompts/exploracion.txt` o `homelens/prompts/find_it.txt`.
- **Validación de la respuesta en Python:** se realiza en dos etapas complementarias:
  1. *Validación estructural del JSON:* dentro de `AdaptadorGemini._ejecutar_llamada_multimodal` (`homelens/integraciones/gemini.py`), `esquema_respuesta.model_validate_json(texto_respuesta)` verifica que el texto retornado por Gemini cumpla los tipos y campos obligatorios del esquema Pydantic.
  2. *Validación geométrica, semántica y de dominio:* en `analizar_exploracion` y `verificar_find_it` (`homelens/analisis.py`) se comprueba que el estado pertenezca a `EstadoAnalisis` o `EstadoFindIt`, que los estados sin objetos no traigan elementos, que una exploración `UTILIZABLE` tenga entre 1 y 5 objetos con identificadores locales únicos, que cada recuadro cumpla `0 <= ymin < ymax <= 1000` y `0 <= xmin < xmax <= 1000` al instanciar `RecuadroNormalizado` (`homelens/modelos.py`), y que cada actividad tenga entre 1 y 2 preguntas con exactamente 3 opciones distintas, `opcion_correcta_id` existente y referencias válidas en `objetos_relacionados`. Recién superadas estas comprobaciones, `homelens/analisis.py` genera los `UUID` de dominio y construye `Exploracion` o `VerificacionFindIt`.

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

Archivo principal: `homelens/config.py`. Registro técnico: `homelens/telemetria.py`. Cálculo de costos y tarifas: `homelens/costos.py`. Vista privada de consumo para creadores: `homelens/ui/consumo.py`.

```python
cargar_configuracion(ruta_env: str | None = None) -> Resultado[Configuracion]
```

```python
es_creador_autorizado(usuario: ContextoUsuario | None, config: Configuracion | None = None) -> bool
```

```python
obtener_nombre_creador(user_id: UUID | None, config: Configuracion | None = None) -> str
```

```python
registrar_evento(evento: EventoTecnico, repositorio: Any | None = None, usuario: ContextoUsuario | None = None) -> None
```

```python
calcular_costo_gemini(modelo: str, prompt_tokens: int | None, candidates_tokens: int | None, thoughts_tokens: int | None = None, cached_tokens: int | None = None, total_tokens: int | None = None, fecha: datetime | None = None) -> ResultadoCalculoCosto
```

Configuracion reúne parámetros de servicios, límites, tiempos y caché. No se imprime ni se serializa con secretos en registros. El registro de métricas debe tolerar un fallo sin perder resultados educativos.

Dockerfile, compose.yaml y .dockerignore se ubican en la raíz. .env.example documenta nombres de variables con valores ficticios. .env y las credenciales reales quedan excluidos del repositorio y de la imagen Docker. Los límites definitivos se decidirán con mediciones; el piloto deberá tener un presupuesto provisional antes de llamar a servicios.

### 3.2 M1 Acceso de usuarios

Archivo principal: `homelens/acceso.py`. Adaptador externo: `homelens/integraciones/autenticacion.py`. Vista: `homelens/ui/acceso.py`.

```python
iniciar_acceso(retorno_permitido: str, config: Configuracion | None = None, adaptador: AdaptadorAutenticacion | None = None) -> Resultado[SolicitudAcceso]
```

```python
completar_acceso(respuesta_proveedor: RespuestaAcceso, config: Configuracion | None = None, adaptador: AdaptadorAutenticacion | None = None, retorno_permitido: str | None = None) -> Resultado[ContextoUsuario]
```

```python
obtener_usuario_actual(sesion_id: str | None = None, config: Configuracion | None = None, adaptador: AdaptadorAutenticacion | None = None) -> Resultado[ContextoUsuario]
```

```python
cerrar_sesion(sesion_id: str | None = None, config: Configuracion | None = None, adaptador: AdaptadorAutenticacion | None = None) -> Resultado[Confirmacion]
```

```python
activar_modo_demo(config: Configuracion | None = None) -> Resultado[ContextoUsuario]
```

```python
verificar_acceso_operacion(usuario: ContextoUsuario | None, config: Configuracion | None = None, adaptador: AdaptadorAutenticacion | None = None) -> Resultado[ContextoUsuario]
```

SolicitudAcceso y RespuestaAcceso representan el mecanismo del proveedor elegido; no presuponen parámetros concretos de OAuth. Los retornos permitidos y la protección de la respuesta de autenticación se implementarán conforme al flujo del proveedor validado. No se guardan contraseñas propias.

Cerrar sesión elimina el contexto privado de acceso, la imagen activa y la caché de audio de esa sesión mediante la coordinación de la aplicación (`cerrar_sesion_usuario` en `homelens/ui/estado.py`). Cada operación protegida verifica que la identidad siga vigente, aunque la pantalla todavía muestre un usuario.

### 3.3 M2 Captura y preparación

Archivo principal: `homelens/imagenes.py`. Vista de captura: `homelens/ui/captura.py` (`renderizar_pantalla_captura`).

```python
preparar_imagen(contenido: bytes, max_bytes: int = 10_000_000, max_dimension_px: int | None = None) -> Resultado[ImagenPreparada]
```

```python
liberar_imagen(referencia: Any) -> None
```

La cámara y el selector de archivo están en la vista; M2 procesa los bytes y no importa Streamlit. Comprueba tamaño y formato antes de preparar. El cierre de recursos se garantiza también ante excepciones. liberar_imagen elimina referencias y temporales propios; no promete borrado físico de memoria ni de copias externas.

### 3.4 M3 Análisis con Gemini

Archivo principal: `homelens/analisis.py`. Adaptador: `homelens/integraciones/gemini.py` (`AdaptadorGemini.analizar_imagen_exploracion` y `AdaptadorGemini.verificar_imagen_find_it`). Esquemas JSON: `homelens/esquemas_ia.py`. Instrucciones: `homelens/prompts/exploracion.txt` y `homelens/prompts/find_it.txt`.

```python
analizar_exploracion(usuario: ContextoUsuario, imagen: ImagenPreparada, operacion_id: UUID, adaptador: AdaptadorGemini | None = None, repositorio: Any | None = None) -> Resultado[Exploracion]
```

```python
verificar_find_it(usuario: ContextoUsuario, imagen: ImagenPreparada, desafio: DesafioFindIt, operacion_id: UUID | None = None, adaptador: AdaptadorGemini | None = None, repositorio: Any | None = None) -> Resultado[VerificacionFindIt]
```

```python
obtener_actividades_publicas(actividades: list[Actividad]) -> list[ActividadPublica]
```

M3 utiliza modelos de respuesta externos y validadores internos. Aplica controles de consumo antes de cada llamada; los reintentos comparten operacion_id y cuentan individualmente. No guarda directamente exploraciones educativas en la base de datos. En Find it se comprueba la sesión activa y el desafío antes de enviarlo.

La configuración del cliente vive en la integración; el prompt y el esquema se versionan. Ajustar instrucciones no debe obligar a modificar la vista o el repositorio. La selección o navegación de tarjetas no invoca estas funciones.

### 3.5 M4 Exploración y contenido

Archivo principal: `homelens/exploracion.py`. Vista: `homelens/ui/exploracion.py`.

```python
adaptar_recuadro(recuadro: RecuadroNormalizado, ancho_visible: int, alto_visible: int) -> RecuadroPantalla
```

```python
calcular_coordenadas_recuadro(recuadro: RecuadroNormalizado, ancho_imagen: int, alto_imagen: int) -> tuple[int, int, int, int]
```

```python
dibujar_recuadros(imagen: ImagenPreparada, objetos: list[ObjetoEducativo], objeto_seleccionado_id: UUID | None = None) -> bytes
```

```python
construir_tarjetas(exploracion: Exploracion, ancho_visible: int | None = None, alto_visible: int | None = None) -> list[TarjetaObjeto]
```

```python
mostrar_exploracion(exploracion: Exploracion, imagen: ImagenPreparada | None = None) -> None
```

Las funciones de `homelens/exploracion.py` son puras (incluyendo el alias `generar_imagen_anotada = dibujar_recuadros`); `mostrar_exploracion` pertenece a la vista (`homelens/ui/exploracion.py`) y coordina en pantalla la selección de objetos («Ver todos» / «Enfocar»), los controles de pronunciación (`mostrar_controles_audio` de `homelens/ui/audio.py`), el botón de guardado en el historial y el acceso al cuestionario interactivo.

La vista de historial muestra tarjetas de texto sin exigir fotografía (`imagen=None`). No intenta dibujar recuadros sobre una imagen que ya fue liberada.

### 3.6 M5 Audio

Archivo principal: `homelens/audio.py`. Adaptador: `homelens/integraciones/tts.py` (`AdaptadorTTS.sintetizar`). Vista: `homelens/ui/audio.py` (`mostrar_controles_audio`, `limpiar_audio_sesion_ui`).

```python
obtener_audio(usuario: ContextoUsuario, solicitud: SolicitudAudio, operacion_id: UUID, adaptador: AdaptadorTTS | None = None) -> Resultado[AudioDisponible]
```

```python
tiene_audio_en_cache(usuario: ContextoUsuario, solicitud: SolicitudAudio) -> bool
```

```python
limpiar_cache_audio(sesion_id: str) -> None
```

```python
limpiar_toda_cache_audio() -> None
```

Solo se acepta texto de una palabra o frase válida del contenido del usuario; la coordinación lo resuelve desde su identificador. Una petición arbitraria de texto no se expone como función libre en la pantalla. Los aciertos de caché no generan una llamada TTS. La reproducción efectiva la realiza la vista con el audio recibido.

### 3.7 M6 Prácticas y Find it

Archivo principal: `homelens/practicas.py`. Las vistas se ubican en `homelens/ui/cuestionarios.py` (`renderizar_pantalla_cuestionarios`, `guardar_intentos_cuestionario_finalizado`) y `homelens/ui/find_it.py` (`renderizar_pantalla_find_it`, `guardar_intento_find_it_pendiente`).

```python
obtener_actividad_publica(actividad: Actividad) -> ActividadPublica
```

```python
mezclar_opciones_actividad(actividad: Actividad) -> list[Opcion]
```

```python
validar_y_responder_actividad(usuario: ContextoUsuario, actividad: Actividad, opcion_id: str, intento_id: UUID | None = None) -> Resultado[ResultadoPractica]
```

```python
responder_actividad(usuario: ContextoUsuario, actividad_id: UUID, opcion_id: str, opcion_correcta_id: str, explicacion: str, intento_id: UUID) -> Resultado[ResultadoPractica]
```

```python
obtener_desafios_find_it_disponibles(usuario: ContextoUsuario, exploracion_actual: Exploracion | None = None) -> list[DesafioFindIt]
```

```python
construir_intento_cuestionario(usuario: ContextoUsuario, actividad: Actividad, opcion_elegida_id: str, resultado_practica: ResultadoPractica, fecha: datetime | None = None) -> IntentoPractica
```

```python
construir_intento_find_it(usuario: ContextoUsuario, desafio: DesafioFindIt, verificacion: VerificacionFindIt, intento_id: UUID | None = None, fecha: datetime | None = None) -> IntentoPractica
```

M6 evalúa localmente las preguntas de cuestionarios con la solución canónica de la entidad `Actividad` en el servidor sin consultar a Gemini, y en Find It construye los desafíos disponibles (a partir del vocabulario explorado y del catálogo doméstico base), invoca `verificar_find_it` (M3) y convierte el resultado en `IntentoPractica` para guardarlo de forma idempotente mediante M7 (`RepositorioSupabase.guardar_intento`).

ResultadoPractica incluye intento_id, resultado, explicación y registrado: bool. Si falla el guardado, se mantiene el resultado pendiente de esa operación en `st.session_state` y se ofrece reintentar solo su registro con la misma clave (`guardar_intentos_cuestionario_finalizado` en `homelens/ui/cuestionarios.py` y `guardar_intento_find_it_pendiente` en `homelens/ui/find_it.py`). No se vuelve a llamar a Gemini para persistir una verificación ya obtenida.

### 3.8 M7 Persistencia e historial

Contrato: `homelens/datos/repositorio.py` (`RepositorioHomeLens`). Implementación integrada: `homelens/datos/supabase.py` (`RepositorioSupabase`). Vista de historial: `homelens/ui/historial.py` (`renderizar_pantalla_historial`).

```python
guardar_exploracion(usuario: ContextoUsuario, exploracion: Exploracion) -> Resultado[UUID]
```

```python
obtener_exploracion(usuario: ContextoUsuario, exploracion_id: UUID) -> Resultado[Exploracion]
```

```python
listar_exploraciones(usuario: ContextoUsuario, limite: int = 50) -> Resultado[list[ResumenExploracion]]
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
listar_intentos(usuario: ContextoUsuario, desde: datetime | None = None) -> Resultado[list[IntentoPractica]]
```

```python
registrar_consumo_gemini(usuario: ContextoUsuario, registro: RegistroConsumoIA) -> Resultado[UUID]
```

```python
consultar_consumo_gemini(usuario: ContextoUsuario, filtro: FiltroConsumoIA | None = None) -> Resultado[list[RegistroConsumoIA]]
```

Ninguna consulta omite la comprobación de pertenencia. En Supabase se aplican políticas Row Level Security (RLS) basadas en `auth.uid()` y permisos mínimos (`GRANT SELECT, INSERT`, con `UPDATE` y `DELETE` revocados).

La exploración, sus objetos y sus actividades se guardan de forma atómica en una única fila de `public.exploraciones` (con columnas `JSONB` para `objetos` y `actividades`). El identificador de exploración y el `intento_id` evitan duplicaciones al reintentar mediante `upsert(..., ignore_duplicates=True)` (`ON CONFLICT DO NOTHING`).

### 3.9 M8 Progreso

Archivo principal: `homelens/progreso.py`. Vista: `homelens/ui/progreso.py` (`renderizar_pantalla_progreso`, `formatear_porcentaje_aciertos`).

```python
obtener_progreso(usuario: ContextoUsuario, repositorio: RepositorioHomeLens | None = None, config: Configuracion | None = None) -> Resultado[ResumenProgreso]
```

```python
consultar_progreso_usuario(usuario: ContextoUsuario, repositorio: RepositorioHomeLens | None = None, config: Configuracion | None = None) -> Resultado[ResumenProgreso]
```

```python
calcular_progreso(vocabulario: list[ObjetoEducativo], intentos: list[IntentoPractica]) -> ResumenProgreso
```

`obtener_progreso` (y su alias `consultar_progreso_usuario`) coordina las consultas `listar_vocabulario` y `listar_intentos` con M7; `calcular_progreso` es pura. Cuestionarios y Find it se presentan por separado. Los resultados indeterminables se informan con su propio conteo y se excluyen del denominador de aciertos sobre intentos evaluables. Si no hay intentos evaluables, se devuelve `None` (mostrado en pantalla como «Sin intentos evaluables»); si el porcentaje real es cero, se muestra «0 %».

## 4 Persistencia implementada en Supabase (`sql/`)

En la implementación integrada en `main`, las tablas de PostgreSQL en Supabase consolidan los objetos y actividades como arreglos `JSONB` validados dentro de `public.exploraciones` para garantizar atomicidad en una sola inserción, y separan los intentos y la telemetría en tablas inmutables con RLS:

| Tabla SQL (`sql/`) | Contenido y restricciones |
| --- | --- |
| `public.exploraciones` (`sql/migracion_tarea_7_historial.sql`) | `id` (UUID PK), `user_id` (FK a `auth.users`), `estado`, `creada_en`, `schema_version`, `objetos` (`JSONB` array) y `actividades` (`JSONB` array). RLS por `user_id = auth.uid()`. |
| `public.intentos_practica` (`sql/migracion_tarea_10_intentos_practica.sql`) | `id` (UUID PK, `intento_id`), `user_id` (FK a `auth.users`), `tipo` (`CUESTIONARIO` o `FIND_IT`), `fecha`, `actividad_id`, `desafio_id`, `opcion_elegida_id`, `resultado` (`CORRECTO`, `INCORRECTO`, `INDETERMINABLE`) y `objeto_ids` (`JSONB` array). RLS por `user_id = auth.uid()`. |
| `public.creadores_autorizados` (`sql/migracion_tarea_consumo_ia.sql`) | `user_id` (UUID PK), `nombre_etiqueta`, `creado_en`. Padrón restringido de creadores con política SELECT no recursiva (`user_id = (SELECT auth.uid())`). |
| `public.consumo_gemini` (`sql/migracion_tarea_consumo_ia.sql`) | `id`, `operacion_id` (`UNIQUE`), `user_id`, `fecha`, `modelo`, `estado`, `duracion_ms`, `numero_llamadas`, `numero_reintentos`, `codigo_error`, `prompt_tokens`, `candidates_tokens`, `thoughts_tokens`, `total_tokens`, `cached_tokens`, `tarifa_version`, `costo_estimado` y `metadatos` (`JSONB`). |

No se incluyen fotos, claves, tokens ni audios en estas tablas. En modo demostración local (`usuario.es_demo=True`), `RepositorioSupabase` utiliza diccionarios aislados en `st.session_state` (`_exploraciones_demo` e `_intentos_demo`) bajo el mismo contrato `RepositorioHomeLens`.

## 5 Carpetas y archivos verificados en el repositorio

| Ruta relativa | Responsabilidad |
| --- | --- |
| `app.py` | Entrada de Streamlit, barra lateral de sesión y enrutamiento hacia cada pantalla. |
| `homelens/modelos.py` | Entidades y enumeraciones inmutables del dominio (`Exploracion`, `ObjetoEducativo`, `RecuadroNormalizado`, `Actividad`, `DesafioFindIt`, `VerificacionFindIt`, `IntentoPractica`, `ResumenProgreso`, `EventoTecnico`, `RegistroConsumoIA`). |
| `homelens/errores.py` | `Resultado[T]`, `ErrorOperacion` y códigos de error tipificados. |
| `homelens/config.py`, `homelens/telemetria.py` y `homelens/costos.py` | M0: carga de entorno, autorización de creadores, registro de eventos técnicos y cálculo de costos de Gemini con `Decimal`. |
| `homelens/acceso.py` | M1: flujo OAuth con Google/Supabase, verificación de sesión y modo demo. |
| `homelens/imagenes.py` | M2: validación JPEG/PNG hasta 10 MB, corrección EXIF, redimensionamiento y liberación en memoria. |
| `homelens/analisis.py` | M3: `analizar_exploracion` y `verificar_find_it` con validaciones geométricas y pedagógicas. |
| `homelens/esquemas_ia.py` | Esquemas Pydantic pedidos a Gemini (`RespuestaExploracionIA` y `RespuestaFindItIA`). |
| `homelens/prompts/` | `exploracion.txt` y `find_it.txt`; instrucciones del sistema versionadas. |
| `homelens/exploracion.py` | M4: `calcular_coordenadas_recuadro`, `dibujar_recuadros`, `adaptar_recuadro` y `construir_tarjetas`. |
| `homelens/audio.py` | M5: `obtener_audio`, caché temporal acotada por sesión y deduplicación de síntesis en curso. |
| `homelens/practicas.py` | M6: proyección y corrección local de actividades, catálogo y desafíos Find It, y constructores de `IntentoPractica`. |
| `homelens/progreso.py` | M8: `obtener_progreso`, `consultar_progreso_usuario` y `calcular_progreso`. |
| `homelens/datos/` | M7: `repositorio.py` (`RepositorioHomeLens`) y `supabase.py` (`RepositorioSupabase`). |
| `homelens/integraciones/` | `autenticacion.py` (`AdaptadorAutenticacion`), `gemini.py` (`AdaptadorGemini`) y `tts.py` (`AdaptadorTTS`). |
| `homelens/ui/` | `acceso.py`, `captura.py`, `exploracion.py`, `audio.py`, `cuestionarios.py`, `find_it.py`, `historial.py`, `progreso.py`, `consumo.py` y `estado.py`. |
| `sql/` | Scripts SQL versionados para Supabase (`migracion_tarea_7_historial.sql`, `migracion_tarea_10_intentos_practica.sql`, `migracion_tarea_consumo_ia.sql`, `procedimiento_registro_creadores.sql`, `verificar_seguridad_rls.sql`). |
| `tests/` | Suite de pruebas automatizadas del software en `main` con simulaciones de servicios externos y `AppTest` (257 pruebas aprobadas en la corrida local verificada sobre `origin/main` en el commit `d4aa17a`, PR #13). |
| `docs/` | Documentación técnica (`docs/TAREA8_AUDIO_BAJO_DEMANDA.md` en `main`; `docs/evaluacion/A1..A4` en la rama `origin/HLE_Evaluacion`). |
| `scripts/evaluacion/` y `data/evaluacion/` | Flujo A1–A3 y dataset sintético anotado en CVAT (disponibles en la rama `origin/HLE_Evaluacion`). |
| `Dockerfile`, `compose.yaml`, `.dockerignore`, `.gitignore`, `.env.example`, `pyproject.toml`, `requirements.txt`, `README.md` | Configuración de contenedor, dependencias y guía de instalación y uso. |

## 6 Recorridos y seguimiento en el código

### 6.1 Cómo seguir una fotografía desde la carga hasta los objetos, el vocabulario y el cuestionario

1. **Carga o captura en pantalla (`homelens/ui/captura.py` y `homelens/ui/estado.py`):** en `renderizar_pantalla_captura(config)`, el usuario selecciona archivo (`st.file_uploader`) o cámara (`st.camera_input`). Al recibir bytes nuevos, se llama a `registrar_nueva_imagen(bytes_capturados, nuevo_origen)` en `homelens/ui/estado.py`, que limpia cualquier exploración o preparación anterior (`invalidar_preparacion_anterior()`) y guarda los bytes crudos en `st.session_state.imagen_cargada_bytes` sin llamar a Gemini.
2. **Preparación y saneamiento en memoria (`homelens/imagenes.py`):** cuando el usuario pulsa «⚙️ Preparar Imagen», `renderizar_pantalla_captura` invoca `preparar_imagen(contenido=st.session_state.imagen_cargada_bytes, max_bytes=config.max_image_size_bytes, max_dimension_px=1280)`. Esta función comprueba que el archivo no supere 10 000 000 bytes, valida la cabecera real JPEG/PNG, decodifica la imagen completa, aplica `ImageOps.exif_transpose` para corregir la orientación EXIF, elimina metadatos y devuelve `Resultado[ImagenPreparada]`, almacenado en `st.session_state.imagen_preparada`.
3. **Solicitud a Gemini con esquema JSON estructurado (`homelens/analisis.py`, `homelens/esquemas_ia.py` y `homelens/integraciones/gemini.py`):** cuando el usuario pulsa «✨ Analizar Fotografía con Gemini», `renderizar_pantalla_captura` llama a `analizar_exploracion(usuario, imagen=st.session_state.imagen_preparada, operacion_id=uuid4())` en `homelens/analisis.py`.
   - `analizar_exploracion` verifica la sesión activa, lee `homelens/prompts/exploracion.txt` con `_cargar_prompt_exploracion()` e invoca `AdaptadorGemini.analizar_imagen_exploracion(...)` en `homelens/integraciones/gemini.py`.
   - `AdaptadorGemini._ejecutar_llamada_multimodal` construye `types.GenerateContentConfig(system_instruction=instrucciones, temperature=0.2, response_mime_type="application/json", response_schema=RespuestaExploracionIA)`, donde `RespuestaExploracionIA` está definida en `homelens/esquemas_ia.py`.
4. **Validación de la respuesta en Python (`homelens/integraciones/gemini.py`, `homelens/analisis.py` y `homelens/modelos.py`):**
   - Primero, `AdaptadorGemini._ejecutar_llamada_multimodal` valida el JSON crudo contra Pydantic con `RespuestaExploracionIA.model_validate_json(texto_respuesta)` y registra el evento técnico de consumo mediante `registrar_evento(...)` (`homelens/telemetria.py` y `homelens/costos.py`).
   - Segundo, `analizar_exploracion` (`homelens/analisis.py`) valida las reglas del dominio: convierte `respuesta_ia.estado` a `EstadoAnalisis` (`UTILIZABLE`, `SIN_OBJETOS_CLAROS`, `REPETIR_CAPTURA` o `FUERA_DE_ALCANCE`); verifica que los estados no utilizables no traigan objetos ni actividades; comprueba para `UTILIZABLE` entre 1 y 5 objetos con textos bilingües completos y coordenadas `[ymin, xmin, ymax, xmax]` válidas entre 0 y 1000 (`RecuadroNormalizado.__post_init__` en `homelens/modelos.py`); y valida entre 1 y 2 actividades con 3 opciones distintas, `opcion_correcta_id` perteneciente a las opciones y `objetos_relacionados` existentes. Con ello construye la entidad inmutable `Exploracion` y la guarda en `st.session_state.exploracion_actual`.
5. **Presentación de recuadros, tarjetas de vocabulario, audio y guardado (`homelens/ui/exploracion.py` y `homelens/exploracion.py`):** `renderizar_pantalla_captura` llama a `mostrar_exploracion(exploracion, imagen)` en `homelens/ui/exploracion.py`.
   - Si el estado es `UTILIZABLE`, `dibujar_recuadros(imagen, exploracion.objetos, objeto_seleccionado_id)` en `homelens/exploracion.py` escala cada `RecuadroNormalizado` a píxeles reales con `calcular_coordenadas_recuadro(...)` y dibuja las cajas y etiquetas `#1..#5` sobre una copia en memoria de la imagen preparada.
   - Debajo del visor responsivo se renderizan las tarjetas educativas bilingües (`EN · US` / `ES`) con frase de ejemplo, botones «Enfocar» / «Ver todos» y los controles de pronunciación `mostrar_controles_audio(exploracion, obj)` (`homelens/ui/audio.py` -> `obtener_audio` en `homelens/audio.py`).
   - Si el usuario pulsa «💾 Guardar», se invoca `RepositorioSupabase.guardar_exploracion(usuario_actual, exploracion)` en `homelens/datos/supabase.py`.
6. **Paso al cuestionario interactivo (`homelens/ui/cuestionarios.py` y `homelens/practicas.py`):** al pulsar «🚀 Comenzar Cuestionario Interactivo» al pie de `mostrar_exploracion` (o entrar a «Prácticas y Cuestionarios» en `app.py`), `renderizar_pantalla_cuestionarios(config)` en `homelens/ui/cuestionarios.py` oculta la solución proyectando cada pregunta con `obtener_actividad_publica(actividad)` y mezclando sus opciones con `mezclar_opciones_actividad(actividad)`. Al confirmar una opción, `validar_y_responder_actividad(usuario, actividad, opcion_id, intento_id)` en `homelens/practicas.py` corrige localmente sin llamar a Gemini, muestra la explicación y, al completar el cuestionario, `guardar_intentos_cuestionario_finalizado(...)` persiste cada `IntentoPractica` en `public.intentos_practica` mediante `RepositorioSupabase.guardar_intento(...)`.

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
