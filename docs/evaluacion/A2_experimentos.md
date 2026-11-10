# A2 — Experimentos reproducibles con HomeLens

HomeLens integra Gemini, modelo multimodal preentrenado. No se entrena una red propia ni se ajustan pesos. Las fotografías se usan exclusivamente para evaluación. Se desarrolló el procedimiento con las cinco fotografías sintéticas piloto y fixtures. Posteriormente se completó una prueba real autorizada de Cocina con Gemini 3.6 y revisión humana, conservando un intento TLS fallido anterior; sus resultados y limitaciones están en [A4](A4_resultados.md). Las otras cuatro imágenes no se ejecutaron y la evaluación definitiva de 30 fotografías sigue pendiente.

## Componentes reutilizados

Se usan `homelens.imagenes.preparar_imagen` (M2), `homelens.analisis.analizar_exploracion` (M3), su cargador de prompt `homelens/prompts/exploracion.txt`, `RespuestaExploracionIA` y `AdaptadorGemini`. La adaptación autorizada de M3 para Gemini 3.6 afecta únicamente la configuración de generación: omite `temperature` cuando el identificador es exactamente `gemini-3.6-flash`. Los demás módulos, la interfaz, el prompt y el esquema permanecen sin cambios.

La preparación coincide con la interfaz: límite `MAX_IMAGE_SIZE_BYTES`, máximo 1280 píxeles, normalización de orientación y eliminación de metadatos en memoria. Se conservan hashes del archivo original y de los bytes preparados. Si EXIF cambia la orientación respecto de CVAT, el experimento exige revisión de datos en vez de alterar las cajas humanas. Las discrepancias de tamaño sólo se admiten con la transformación uniforme y revisión humana de A1; la diferencia de relación de aspecto debe ser ≤0,001.

El adaptador actual retorna el esquema validado, sin texto original ni tokens. `ClienteRegistrado`, dentro de evaluación, envuelve el transporte mediante el punto de inyección existente. Observa todas las llamadas y devuelve la misma respuesta al adaptador; conserva texto original, configuración enviada, uso reportado y versión del modelo cuando existen. No construye una segunda integración con Gemini. `analizar_exploracion` aplica también sus validaciones de geometría, actividades y referencias. Se conserva la coerción de tipos del esquema Pydantic de la aplicación.

El modelo seleccionado para esta evaluación es **`gemini-3.6-flash`**, configurado con `GEMINI_MODEL` en el `.env` local, fuera de Git. Modelo, timeout, reintentos y límite de archivo proceden del mismo cargador de configuración que usa la aplicación. Se mantienen JSON y el esquema de HomeLens.

Para Gemini 3.6 no se envían `temperature`, `top_p`, `top_k`, `candidate_count`, penalizaciones de presencia/frecuencia ni `thinking_config`. El razonamiento **`medium` es el valor predeterminado documentado del proveedor**, no un parámetro enviado ni una observación medida de sus procesos internos. A2 registra `temperatura_enviada=false`, omite la clave `temperature` y distingue el origen del razonamiento mediante `razonamiento.origen=predeterminado_proveedor` y `razonamiento.configuracion_enviada=false`. El transporte conserva aparte la configuración realmente enviada. Para `gemini-2.5-flash` se conserva la temperatura 0,2; no se aplica retroactivamente la configuración de 3.6 a sus registros. Véase la [guía oficial de migración](https://ai.google.dev/gemini-api/docs/generate-content/whats-new-gemini-3.6).

La versión instalada `google-genai 1.29.0` permite la solicitud básica con imágenes y el esquema Pydantic. No se actualiza el SDK: no necesitamos configurar explícitamente `thinking_level`, que esta versión aún no admite. Los parámetros no fijados, como máximo de tokens o semilla, siguen dependiendo del SDK/proveedor. No se atribuye determinismo a una temperatura omitida ni al razonamiento predeterminado. El registro incluye hashes de prompt/esquema/código y versiones del SDK, Pillow y Pydantic; un modelo generativo puede variar entre ejecuciones.

## Entorno y simulación completa

Ejecutar desde la raíz del repositorio con un Python que tenga las dependencias de la aplicación. No hacen falta FiftyOne, servicios externos ni nuevas dependencias para A2/A3. El entorno local comprobado es Python 3.13.17; el objetivo declarado del proyecto es Python 3.11. No se verificó esta entrega sobre 3.11. `.venv-evaluacion` se preparó para A1 y actualmente carece de `google-genai`; el `python` instalado sí tiene las dependencias utilizadas.

```powershell
python -m scripts.evaluacion.ejecutar_experimento preparar --root data/evaluacion/cvat/pilotos/piloto_v1 --fotos-root data/evaluacion/cvat/fotografias_originales/piloto_v1 --conjunto piloto --origen sintetica --manifest data/evaluacion/resultados/manifest_piloto_v1.json
python -m scripts.evaluacion.ejecutar_experimento ejecutar --manifest data/evaluacion/resultados/manifest_piloto_v1.json --run-id simulacion_piloto_gemini36_v1
python -m scripts.evaluacion.informe_metricas --run data/evaluacion/resultados/simulacion_piloto_gemini36_v1
```

Si ya existe el manifiesto, reutilizarlo y omitir `preparar`. El modo predeterminado es simulado: usa el adaptador original con un cliente que retorna `fixtures/respuesta_simulada.json`. Esa respuesta fija identifica una silla en todas las imágenes; **no depende de la fotografía ni de CVAT** y no pretende ser correcta para esas escenas. Sólo verifica el procedimiento técnico. Las métricas y los tiempos resultantes no son evidencia de calidad ni latencia de Gemini.

Repetir `ejecutar` con el mismo identificador reanuda el experimento. Las respuestas válidas no se repiten; los fallos e intentos interrumpidos sólo se repiten con `--reintentar-fallidas`. Cada nuevo intento se archiva por separado. Un estado `en_curso` puede significar que la API recibió la consulta antes de un corte; revisar antes de autorizar el reintento. La ejecución es secuencial: no iniciar dos procesos sobre el mismo `run-id`. Un cambio de datos o configuración exige otra ejecución; conservar también las fallidas.

La migración de 2.5 a 3.6 requiere un **run-id nuevo**, como los ejemplos anteriores. Las simulaciones anteriores conservan su configuración y no se sobrescriben. Si hubiera un protocolo final ya congelado, preparar una nueva versión antes de ejecutar el conjunto reservado.

## Una prueba real, sólo después de autorización

El ejemplo siguiente describe una futura ejecución y no debe repetirse sin nueva autorización; el historial de Cocina ya ejecutado se detalla en A4. Primero registrar en el manifiesto lateral `origen` (`real`/`sintetica`) y `permisos: "confirmados"` para las imágenes seleccionadas cuando se haya verificado su uso; no asignar permisos ficticios. A2 aplica primero `--image-id` y después `--limite`, y comprueba los permisos de esa selección antes de crear la ejecución o consultar al cliente. Las imágenes no seleccionadas pueden permanecer pendientes. Sin filtros se comprueba todo el lote; para la evaluación final se conservan además el protocolo congelado, la separación piloto/final y la exigencia de 30 fotografías. La credencial se obtiene de `GEMINI_API_KEY`, mediante la configuración existente y `.env` ignorado por Git. No escribirla en argumentos, documentos ni resultados.

```powershell
python -m scripts.evaluacion.ejecutar_experimento ejecutar --manifest data/evaluacion/resultados/manifest_piloto_v1.json --run-id gemini36_piloto_cocina_nueva_autorizacion --image-id cvat_piloto_v1_2 --limite 1 --real --autorizar-api
```

Selecciona **una imagen**. El adaptador puede hacer un segundo intento si `GEMINI_MAX_RETRIES=1`, como la aplicación. Para autorizar exactamente una petición y sin reintentos, fijar previamente `$env:GEMINI_MAX_RETRIES = "0"`; queda registrado como cambio de configuración. No se estiman costos ni tokens ausentes.

## Incorporar las 30 fotografías sintéticas de Lucas

Las 30 imágenes de evaluación están incorporadas en `data/evaluacion/cvat/finales/evaluacion_sintetica_lucas_v1`. El archivo RAR original se conserva localmente, fuera de Git. Se preservan el COCO original y una copia normalizada que unifica únicamente `Coffee table`/`Coffee Table`; `transformaciones.json` y el informe de entrega registran hashes y cambios. El importador admite COCO JSON extraído además de los ZIP CVAT habituales. La procedencia y el alcance de uso están documentados sin atribuir licencias ni permisos adicionales.

La validación técnica no reemplaza la revisión visual: inicialmente las 30 filas están pendientes. Generar o volver a abrir la galería y guardar las decisiones antes de cualquier evaluación real:

```powershell
python -m scripts.evaluacion.generar_galeria_revision --root data/evaluacion/cvat/finales/evaluacion_sintetica_lucas_v1
# Abrir revision_visual.html, revisar las 30 imágenes y descargar el CSV de decisiones.
# Guardarlo como seleccion_revision.csv en la carpeta del conjunto.
python -m scripts.evaluacion.importar_revision --root data/evaluacion/cvat/finales/evaluacion_sintetica_lucas_v1 --revision-csv data/evaluacion/cvat/finales/evaluacion_sintetica_lucas_v1/seleccion_revision.csv
python -m scripts.evaluacion.validar_dataset --root data/evaluacion/cvat/finales/evaluacion_sintetica_lucas_v1
```

Al completar la revisión, volver a preparar una versión nueva del manifiesto final; marcar `permisos` como `confirmados` según el alcance documentado y dejar `exhaustiva=false` salvo confirmación humana específica. No sobrescribir el manifiesto anterior. Sólo entonces congelar el protocolo basado en el piloto, comprobar separación por ID/hash y ejecutar una prueba real pequeña tras autorización expresa.

La simulación con el fixture local sí puede ejecutarse sobre el conjunto final para validar el circuito, sin protocolo ni acceso a Gemini:

```powershell
python -m scripts.evaluacion.ejecutar_experimento ejecutar --manifest data/evaluacion/resultados/manifest_evaluacion_sintetica_lucas_v1.json --run-id simulacion_validacion_evaluacion_sintetica_lucas_v1
python -m scripts.evaluacion.informe_metricas --run data/evaluacion/resultados/simulacion_validacion_evaluacion_sintetica_lucas_v1
```

La respuesta fija no depende de las imágenes ni de CVAT; no es una métrica de rendimiento. La simulación omite la carga de `.env` y la lectura de claves. Las ejecuciones reales siguen requiriendo el protocolo congelado, las 30 imágenes, procedencia/permisos confirmados y aprobación humana para cada imagen seleccionada.

El protocolo fija prompt, modelo, esquema, dependencias, código, sinónimos, umbral y manifiesto. La preparación del manifiesto y la congelación leen metadatos, sin analizar las fotografías. La reserva también depende de la disciplina del equipo: no existe un bloqueo contra inspecciones manuales o ediciones deliberadas de archivos.

## Archivos de salida y privacidad

`data/evaluacion/resultados/<run-id>/ejecucion.json` conserva configuración y una copia de los metadatos/anotaciones; no se envían al modelo. Cada imagen tiene `intento_0001.json`, etc., con timestamps UTC, hash, duración, estado, respuesta y llamadas/tokens disponibles. `respuestas.csv` enlaza cada registro e incluye estado y datos de trazabilidad. La duración principal mide M3 y sus reintentos; la duración por llamada mide el transporte. Los errores de preparación no se presentan como latencia de API.

La carpeta de resultados, originales, imágenes descargadas y exportaciones se excluyen de Git. Los errores guardan códigos controlados, sin mensajes de excepción del proveedor. No se registran bytes de imagen ni claves de autenticación. Las respuestas pueden contener información privada de la escena: conservarlas localmente y revisar cualquier exportación para la presentación. Las rutas se validan dentro del proyecto y del directorio de fotografías autorizado; no se ejecuta contenido de respuestas. Los originales y anotaciones de CVAT no se sobrescriben.

## Validación

```powershell
New-Item -ItemType Directory -Force tmp | Out-Null
python -m pytest tests/test_evaluacion_a1.py tests/test_evaluacion_a2_a3.py -q -p no:cacheprovider --basetemp tmp/pytest-evaluacion-nueva
```

Usar una carpeta temporal nueva en cada ejecución evita que pytest deba limpiar carpetas de pruebas anteriores. Todos los tests nuevos impiden crear un cliente real; los tokens y errores de proveedor se prueban con clientes falsos. Ver [informe de entrega](ENTREGA_A2_A3.md) para el resultado verificado.
