# Tarea 8 — Audio bajo demanda (M5)

## Estado y alcance

Implementación en `HLE_Victoria`, basada en `origin/main` `a4d3fb9` mediante el
fast-forward autorizado. No se hicieron commits, push ni integración hacia main.
Los archivos de evaluación sin seguimiento se conservaron.

El clon tenía un refspec limitado a `HLE_Victoria`: `git fetch origin` no
actualizaba `origin/main`. Se comprobó el SHA mediante `ls-remote` y se ejecutó
`git -c http.sslBackend=schannel fetch origin refs/heads/main:refs/remotes/origin/main`.
Se usó el almacén de certificados de Windows sin desactivar la validación TLS.

Se mantienen los contratos de `SolicitudAudio`, `AudioDisponible`,
`obtener_audio(usuario, solicitud, operacion_id)` y `limpiar_cache_audio(sesion_id)`.
No se modificaron Gemini, su modelo o prompt, M6, M7, Supabase, la autenticación
ni las dependencias. Los cambios de estos módulos recibidos por fast-forward
ya pertenecían a main.

## Generación y reproducción

Cada tarjeta de M4 agrega «Escuchar palabra» y «Escuchar frase». El texto se toma
del nombre o la frase en inglés del objeto perteneciente a la exploración activa
del usuario. No se recibe texto libre desde el navegador.

Solo un botón invoca `obtener_audio()`. Renderizar tarjetas, enfocar objetos,
redibujar la interfaz o cargar una imagen no sintetiza audio. El reproductor
nativo `st.audio` recibe bytes MP3 con MIME `audio/mpeg` y `autoplay=False`.
Después de preparar el audio se pulsa ▶; el reproductor permite repetirlo sin
otra solicitud. Los reruns consultan la caché sin generar contenido nuevo.

El adaptador usa Google Cloud TTS con texto plano (`SynthesisInput.text`, nunca
SSML), idioma `en-US`, voz `en-US-Standard-C`, velocidad `1.0` y formato MP3.
Idioma y voz se leen de la configuración existente. La solicitud al SDK tiene
timeout de 10 segundos y `retry=None`, sin reintentos automáticos. Se admite
inyectar un cliente mediante `AdaptadorTTS(cliente=...)`.

Los textos se limitan a 500 caracteres y 2.000 bytes UTF-8, deben contener letras
y no pueden incluir controles Unicode ni etiquetas delimitadas por `<` o `>`.
Solo se aceptan idiomas ingleses, voces Standard del mismo idioma y velocidades
finitas entre 0.25 y 2.0. Los mensajes de error no incluyen texto del proveedor,
credenciales ni tokens. Un fallo muestra una advertencia junto a la tarjeta y
permite continuar leyendo y usando los otros controles.

## Caché, concurrencia y aislamiento

Se amplió la caché existente de `homelens/audio.py`, sin persistencia de audios
del usuario ni una segunda caché de bytes en la UI.

- Ámbito por usuario y sesión; los identificadores del índice se guardan como
  hashes para no retener tokens de acceso como claves.
- Clave de audio: tupla de texto, idioma, voz y velocidad, sin concatenaciones
  ambiguas.
- TTL: `AUDIO_CACHE_TTL_SECONDS`, por defecto 3.600 segundos. Debe ser positivo.
  Se mide con reloj monotónico desde la generación y no se extiende al escuchar.
- Hasta 32 entradas y 2 MiB por sesión, 64 sesiones y 16 MiB de contenido en total.
  Cada respuesta admite hasta 512 KiB; las expulsiones siguen el uso reciente.
- Los vencidos se purgan al consultar o solicitar audio, también en otras
  sesiones. Una pestaña abandonada no produce tareas en segundo plano: el tope
  global mantiene acotada la memoria hasta la siguiente purga.
- Hasta 16 solicitudes simultáneas en curso. Una misma solicitud pendiente
  comparte un `Future`: los duplicados esperan la misma síntesis, sin llamar al
  proveedor otra vez. El candado no permanece retenido durante la llamada de red.
- Si se limpia una sesión durante una síntesis, el resultado pendiente se
  invalida y no vuelve a poblar la caché. Los fallos no se cachean.

`homelens/ui/audio.py` crea un UUID privado por sesión de Streamlit y lo combina
con la identidad comprobada por M1. Esto separa dos navegadores demo aunque ambos
usen `local_demo_session`. Se crea una copia local de `ContextoUsuario` solo para
M5, sin alterar el contexto de autenticación original ni su contrato. Esa copia
no retiene el token OAuth, el email ni el nombre.

La identidad de origen se compara mediante hash. Al cambiar de usuario o sesión
se libera el ámbito anterior. La UI guarda únicamente la selección del
reproductor para los objetos de la exploración actual; los bytes siguen en M5.

`limpiar_datos_exploracion()` y `cerrar_sesion_usuario()` llaman a la limpieza del
ámbito de audio. En el cierre se hace antes de la revocación remota, para descartar
audio incluso si esta falla. No se cambió el manejo de errores de autenticación.
El reproductor desaparece en el siguiente rerun si el audio expiró o fue expulsado.

## Bloqueo de servicios reales y configuración futura

**No se hicieron llamadas reales a Google Cloud TTS, se crearon credenciales ni
se habilitó facturación.** No se modificó `.env`.

El servicio real está deshabilitado por defecto. La nueva variable optativa
`GOOGLE_TTS_ENABLED` se comprueba en M5 y no amplía el contrato `Configuracion`.
Mientras no exista una autorización posterior, dejarla ausente o en `false`.
El adaptador real también se bloquea en `APP_ENV=test/testing` y para usuarios
demo, incluso si esa variable se establece en `true`.

Para una prueba real futura, con autorización, harán falta:

1. Un proyecto Google Cloud con API `texttospeech.googleapis.com` y facturación
   habilitadas, permisos apropiados y cuota disponible.
2. Credenciales ADC válidas, mediante el mecanismo autorizado para ese entorno.
   `GOOGLE_APPLICATION_CREDENTIALS` puede señalar el archivo correspondiente;
   nunca debe incorporarse al repositorio. La API key de Gemini no sustituye ADC.
3. Una sesión autenticada real de HomeLens y `GOOGLE_TTS_ENABLED=true`, además de
   los parámetros existentes de idioma, voz y TTL.
4. Un clic en un botón y luego ▶ para verificar pronunciación audible, latencia,
   facturación y reproducción en los navegadores de destino.

En la revisión local no se encontraron credenciales TTS ni ADC de gcloud. No se
pudo comprobar la habilitación de la API o la facturación del proyecto.

Referencias oficiales consultadas: [autenticación](https://docs.cloud.google.com/text-to-speech/docs/authentication),
[síntesis](https://docs.cloud.google.com/text-to-speech/docs/samples/tts-quickstart),
[voces](https://docs.cloud.google.com/text-to-speech/docs/list-voices-and-types),
[límites](https://docs.cloud.google.com/text-to-speech/quotas) y
[precios](https://cloud.google.com/text-to-speech/pricing).
Google publica 5.000 bytes por solicitud y una cuota general de 1.000 solicitudes
por minuto por proyecto. Para Standard publica 4 millones de caracteres gratuitos
por mes y USD 4 por millón adicional; verificar nuevamente antes de habilitar el
servicio. La facturación es obligatoria aunque el uso esté dentro de la franquicia.

## Pruebas automáticas y prueba manual sin cuota

Comando ejecutado desde la raíz, con Python que ya tiene las dependencias del
proyecto (no el entorno de evaluación):

```powershell
python -m pytest tests -q -p no:cacheprovider
```

Resultado: **137 pruebas aprobadas** (54 nuevas de M5 y 83 existentes).
`git diff --check` también terminó sin errores.
Verificación final repetida el **4 de noviembre de 2026**: 137 pruebas aprobadas,
sin llamadas reales a TTS y sin cambios posteriores en el código de la aplicación.

Las suites nuevas `tests/test_audio.py` y `tests/test_ui_audio.py` usan únicamente
clientes simulados. Cubren palabra y frase, clic frente a render, caché, TTL,
aislamiento, limpieza, doble solicitud concurrente, cierre durante síntesis,
límites de memoria, textos inválidos, credenciales ausentes, timeout, errores
sanitizados, tarjetas utilizables tras un fallo y ausencia de llamadas a Gemini.

Los tests UI usan `AppTest` sobre las tarjetas reales de M4. El selector superior
se sustituye por un `st.radio` equivalente dentro de los tests: la versión local
de AppTest no serializa correctamente las opciones con iconos de
`segmented_control`. No se cambia el selector de la aplicación.

La vista aislada se ejecuta con:

```powershell
python -m streamlit run scripts/prueba_audio_simulado.py --server.address 127.0.0.1 --server.port 8518 --browser.gatherUsageStats false
```

Abrir `http://127.0.0.1:8518`. Esta vista carga objetos fijos, simula una sesión y
parchea el constructor del adaptador solo durante el render de prueba. No invoca
Gemini, Supabase ni TTS real. El fixture `tests/fixtures/audio_simulado.mp3` contiene
frames MPEG de **silencio sintético**, no una voz ni datos de un usuario.

Comprobar manualmente:

1. Al entrar hay dos tarjetas y cero solicitudes al cliente simulado.
2. Pulsar «Escuchar palabra»: aparece un reproductor sin iniciarse solo y el
   contador aumenta a uno. Pulsar ▶ y verificar que el navegador admite el MP3.
   Este fixture es silencioso: no sirve para evaluar pronunciación.
3. Repetir palabra: el contador no aumenta. Pulsar frase: aumenta a dos.
4. Enfocar otro objeto o cambiar tema: no aumenta el contador.
5. Elegir «Error» o «Tiempo agotado» en la barra lateral, limpiar el audio y
   solicitarlo: aparece una advertencia y las tarjetas siguen disponibles.
6. Abrir otra pestaña: tiene estado y contador propios. Cerrar la sesión simulada
   en la primera no borra el audio de la segunda.
7. Revisar botones y reproductor a ancho de notebook y móvil (por ejemplo, 390 px),
   con los temas claro y oscuro. Los controles nuevos son nativos, sin CSS añadido.

**Prueba manual de interfaz aprobada por el equipo el 4 de noviembre de 2026.**
El equipo confirmó que los botones «Escuchar palabra» y «Escuchar frase» aparecen
y funcionan, que no hay reproducción automática, que el reproductor se abre y
permite reproducir el archivo, y que las tarjetas educativas siguen funcionando.
Esta aprobación corresponde a la simulación con el MP3 silencioso; no evalúa la
pronunciación de Google Cloud TTS.

La revisión automática de navegador del agente había quedado bloqueada por la
herramienta de control de Chrome. La prueba manual posterior informada por el
equipo confirma la reproducción funcional. No hace falta otra simulación audible
para cerrar esta validación de interfaz.

**Pendiente exclusivo del servicio real:** configurar credenciales, comprobar la
API y obtener autorización antes de probar pronunciación con Google Cloud TTS.
El servicio real permanece deshabilitado por defecto.

## Integración con Tareas 7 y 9

Revisión final contra `origin/HLE_Pato` **`4271f19`**, obtenida mediante fetch
explícito el 4 de noviembre de 2026. El ancestro común con esta entrega es
`a4d3fb9`. No se cambió de rama ni se hizo un merge.

Además de comparar los diffs, se ejecutó `git apply --check` con el diff de M5
contra copias temporales de los dos archivos de Patricia. Solo se comprobó la
aplicación de los parches: no se aplicaron ni se modificaron archivos de su rama.

| Archivo | Resultado | Criterio para la futura integración |
| --- | --- | --- |
| `homelens/ui/exploracion.py` | El parche no aplica directamente por el contexto al final del archivo. Ambas tareas agregan contenido después de la frase de la última tarjeta. | Mantener el import de audio y `mostrar_controles_audio(exploracion, obj)` dentro del contenedor de **cada tarjeta** (12 espacios de indentación). Conservar el bloque `if exploracion.actividades:` de Patricia **fuera del bucle** de tarjetas (4 espacios), con su botón de acceso al cuestionario y su navegación. |
| `homelens/ui/estado.py` | El parche de M5 aplica sobre la copia de Patricia sin conflicto de contexto. Esto no sustituye las pruebas de integración posteriores. | Conservar la inicialización y `limpiar_datos_cuestionario()` de Patricia, sus llamadas al limpiar/invalidar exploración y las llamadas de M5 a `limpiar_audio_sesion_ui()`. Conservar también su import de `Any`. |

Los estados del audio usan el prefijo `_audio_`; no coinciden con
`cuestionario_*` ni `radio_actividad_*`. El cambio de navegación al cuestionario
no solicita audio y M5 no modifica M6. Al integrar las dos tareas habrá que
ejecutar ambas suites, especialmente el cierre de sesión y el descarte de imagen,
para comprobar que se limpian tanto audio como cuestionario.

Con Lucas, conservar las llamadas de limpieza de M5 al incorporar historial. No
se agregan audios a Supabase ni se modifican sus esquemas.

## Archivos de esta entrega

Modificados: `homelens/audio.py`, `homelens/integraciones/tts.py`,
`homelens/ui/estado.py`, `homelens/ui/exploracion.py`.

Nuevos: `homelens/ui/audio.py`, `tests/test_audio.py`, `tests/test_ui_audio.py`,
`tests/fixtures/audio_simulado.mp3`, `scripts/prueba_audio_simulado.py` y este documento.

## Preparación del commit y exclusiones

El área de preparación se limita a los siguientes **10 archivos**:

1. `homelens/audio.py`
2. `homelens/integraciones/tts.py`
3. `homelens/ui/audio.py`
4. `homelens/ui/estado.py`
5. `homelens/ui/exploracion.py`
6. `tests/test_audio.py`
7. `tests/test_ui_audio.py`
8. `tests/fixtures/audio_simulado.mp3`
9. `scripts/prueba_audio_simulado.py`
10. `docs/TAREA8_AUDIO_BAJO_DEMANDA.md`

**Se incluyen los dos archivos de simulación.** El MP3 es un fixture sintético
silencioso, sin datos privados, usado por las pruebas del servicio y de la UI.
El script es la vista reproducible que usa `tests/test_ui_audio.py`. Excluir uno
de ellos dejaría incompletas las pruebas en un clon nuevo. No son audios generados
por Google ni resultados de evaluaciones; no consumen cuota. La aplicación normal
no importa ni ejecuta ese script.

**Se excluyen** `.env`, credenciales, claves, configuración privada, fotos y datos
de evaluación (`data/evaluacion/`, `data/evaluacion_domestica_*/`), resultados o
exportaciones locales, entornos virtuales, cachés, logs y temporales. No se usan
`git add .` ni inclusiones amplias de directorios.

Se verificó que `.env`, los nombres habituales de credenciales y
`.streamlit/secrets.toml` están ignorados y no están versionados. Los archivos de
evaluación no están versionados en esta rama. Se agregaron exclusiones **locales**
en `.git/info/exclude` para `/data/evaluacion/`, `/data/evaluacion_domestica_*/`,
`/.aws/` y `/.codex/`, sin incluir ese archivo de metadatos en el commit ni alterar
los datos. Estas reglas locales no se distribuyen a otros clones.

Los cambios quedan preparados para un commit posterior. **No se realizó commit,
push ni merge de ramas.** La prueba de pronunciación real continúa pendiente.
