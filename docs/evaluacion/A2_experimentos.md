# A2 — Experimentos reproducibles con HomeLens

HomeLens integra Gemini, modelo multimodal preentrenado. No se entrena una red propia ni se ajustan pesos. Las fotografías se usan exclusivamente para evaluación. Se desarrolló el procedimiento con las cinco fotografías sintéticas piloto y fixtures; no se han medido resultados reales de Gemini en esta actividad.

## Componentes reutilizados

Se usan `homelens.imagenes.preparar_imagen` (M2), `homelens.analisis.analizar_exploracion` (M3), su cargador de prompt `homelens/prompts/exploracion.txt`, `RespuestaExploracionIA` y `AdaptadorGemini`. M0–M8 y la interfaz permanecen sin cambios.

La preparación coincide con la interfaz: límite `MAX_IMAGE_SIZE_BYTES`, máximo 1280 píxeles, normalización de orientación y eliminación de metadatos en memoria. Se conservan hashes del archivo original y de los bytes preparados. Si EXIF cambia la orientación respecto de CVAT, el experimento exige revisión de datos en vez de alterar las cajas humanas. Las discrepancias de tamaño sólo se admiten con la transformación uniforme y revisión humana de A1; la diferencia de relación de aspecto debe ser ≤0,001.

El adaptador actual retorna el esquema validado, sin texto original ni tokens. `ClienteRegistrado`, dentro de evaluación, envuelve el transporte mediante el punto de inyección existente. Observa todas las llamadas y devuelve la misma respuesta al adaptador; conserva texto original, configuración enviada, uso reportado y versión del modelo cuando existen. No construye una segunda integración con Gemini. `analizar_exploracion` aplica también sus validaciones de geometría, actividades y referencias. Se conserva la coerción de tipos del esquema Pydantic de la aplicación.

La configuración actual del adaptador usa temperatura 0,2, JSON y el esquema de HomeLens. Modelo, timeout, reintentos y límite de archivo proceden de la configuración existente. Los parámetros no fijados (por ejemplo semilla, top-p o máximo de tokens) se documentan como defaults del SDK/proveedor, sin inventar valores. El registro incluye configuración observada, hashes de prompt/esquema/código, versiones del SDK, Pillow y Pydantic. Esas versiones ayudan a repetir el procedimiento, pero un modelo generativo puede variar.

## Entorno y simulación completa

Ejecutar desde la raíz del repositorio con un Python que tenga las dependencias de la aplicación. No hacen falta FiftyOne, servicios externos ni nuevas dependencias para A2/A3. El entorno local comprobado es Python 3.13.17; el objetivo declarado del proyecto es Python 3.11. No se verificó esta entrega sobre 3.11. `.venv-evaluacion` se preparó para A1 y actualmente carece de `google-genai`; el `python` instalado sí tiene las dependencias utilizadas.

```powershell
python -m scripts.evaluacion.ejecutar_experimento preparar --root data/evaluacion/cvat/pilotos/piloto_v1 --fotos-root data/evaluacion/cvat/fotografias_originales/piloto_v1 --conjunto piloto --origen sintetica --manifest data/evaluacion/resultados/manifest_piloto_v1.json
python -m scripts.evaluacion.ejecutar_experimento ejecutar --manifest data/evaluacion/resultados/manifest_piloto_v1.json --run-id simulacion_piloto_v1
python -m scripts.evaluacion.informe_metricas --run data/evaluacion/resultados/simulacion_piloto_v1
```

Si ya existe el manifiesto, reutilizarlo y omitir `preparar`. El modo predeterminado es simulado: usa el adaptador original con un cliente que retorna `fixtures/respuesta_simulada.json`. Esa respuesta fija identifica una silla en todas las imágenes; **no depende de la fotografía ni de CVAT** y no pretende ser correcta para esas escenas. Sólo verifica el procedimiento técnico. Las métricas y los tiempos resultantes no son evidencia de calidad ni latencia de Gemini.

Repetir `ejecutar` con el mismo identificador reanuda el experimento. Las respuestas válidas no se repiten; los fallos e intentos interrumpidos sólo se repiten con `--reintentar-fallidas`. Cada nuevo intento se archiva por separado. Un estado `en_curso` puede significar que la API recibió la consulta antes de un corte; revisar antes de autorizar el reintento. La ejecución es secuencial: no iniciar dos procesos sobre el mismo `run-id`. Un cambio de datos o configuración exige otra ejecución; conservar también las fallidas.

## Una prueba real, sólo después de autorización

No se ejecutó este comando. Primero registrar en el manifiesto lateral `origen` (`real`/`sintetica`) y `permisos: "confirmados"` para las imágenes del lote cuando se haya verificado su uso; no asignar permisos ficticios. La credencial se obtiene de `GEMINI_API_KEY`, mediante la configuración existente y `.env` ignorado por Git. No escribirla en argumentos, documentos ni resultados.

```powershell
python -m scripts.evaluacion.ejecutar_experimento ejecutar --manifest data/evaluacion/resultados/manifest_piloto_v1.json --run-id gemini_piloto_una_v1 --image-id cvat_piloto_v1_1 --limite 1 --real --autorizar-api
```

Selecciona **una imagen**. El adaptador puede hacer un segundo intento si `GEMINI_MAX_RETRIES=1`, como la aplicación. Para autorizar exactamente una petición y sin reintentos, fijar previamente `$env:GEMINI_MAX_RETRIES = "0"`; queda registrado como cambio de configuración. No se estiman costos ni tokens ausentes.

## Incorporar las 30 fotografías de Lucas

1. Anotar todas las fotografías nuevas en CVAT y exportar COCO 1.0. Mantener ZIP y originales en los directorios privados. No usar imágenes finales para ajustar repetidamente prompt o criterios.
2. Usar el importador existente con un lote/destino nuevo. Los comandos siguientes son futuros; no se ejecutaron sin los archivos.

```powershell
python -m scripts.evaluacion.importar_cvat --export-zip data/evaluacion/cvat/lucas_final_v1.zip --output data/evaluacion/cvat/finales/lucas_final_v1 --lote lucas_final_v1 --destino evaluacion_final --fotografias-originales data/evaluacion/cvat/fotografias_originales/lucas_final_v1
python -m scripts.evaluacion.generar_galeria_revision --root data/evaluacion/cvat/finales/lucas_final_v1
# Revisar la galería y exportar decisiones humanas antes del comando siguiente.
python -m scripts.evaluacion.importar_revision --root data/evaluacion/cvat/finales/lucas_final_v1 --revision-csv data/evaluacion/cvat/finales/lucas_final_v1/seleccion_revision.csv
python -m scripts.evaluacion.validar_dataset --root data/evaluacion/cvat/finales/lucas_final_v1
python -m scripts.evaluacion.ejecutar_experimento preparar --root data/evaluacion/cvat/finales/lucas_final_v1 --fotos-root data/evaluacion/cvat/fotografias_originales/lucas_final_v1 --conjunto evaluacion_final --manifest data/evaluacion/resultados/manifest_final_v1.json
```

3. Completar por imagen, en el manifiesto, `origen`, `permisos` y `exhaustiva` (booleano, false por defecto). Confirmar exhaustividad exige revisión específica; haber etiquetado con CVAT no basta. Se conservan las fuentes reales/sintéticas separadas para el análisis. Los manifiestos nuevos tienen hash de los CSV/JSON de A1; si A1 cambia, preparar otra versión del manifiesto, nunca modificar el hash para saltar controles.
4. Fijar las decisiones metodológicas usando sólo el piloto y congelar antes de ejecutar el conjunto final:

```powershell
python -m scripts.evaluacion.ejecutar_experimento congelar --manifest data/evaluacion/resultados/manifest_final_v1.json --piloto-manifest data/evaluacion/resultados/manifest_piloto_v1.json --protocolo data/evaluacion/resultados/protocolo_final_v1.json
# Sólo tras autorización de las llamadas reales:
python -m scripts.evaluacion.ejecutar_experimento ejecutar --manifest data/evaluacion/resultados/manifest_final_v1.json --run-id gemini_final_v1 --protocolo data/evaluacion/resultados/protocolo_final_v1.json --real --autorizar-api
python -m scripts.evaluacion.informe_metricas --run data/evaluacion/resultados/gemini_final_v1
```

El protocolo fija prompt, modelo, esquema, dependencias, código, sinónimos, umbral y manifiesto. Se comprueba separación por ID y hash contra el piloto, y se exigen 30 fotografías para la ejecución final. La preparación del manifiesto y congelación leen metadatos, sin analizar las fotografías. No se permite simular sobre el conjunto final. La reserva también depende de la disciplina del equipo: no existe un bloqueo contra inspecciones manuales o ediciones deliberadas de archivos.

## Archivos de salida y privacidad

`data/evaluacion/resultados/<run-id>/ejecucion.json` conserva configuración y una copia de los metadatos/anotaciones; no se envían al modelo. Cada imagen tiene `intento_0001.json`, etc., con timestamps UTC, hash, duración, estado, respuesta y llamadas/tokens disponibles. `respuestas.csv` enlaza cada registro e incluye estado y datos de trazabilidad. La duración principal mide M3 y sus reintentos; la duración por llamada mide el transporte. Los errores de preparación no se presentan como latencia de API.

La carpeta de resultados, originales, imágenes descargadas y exportaciones se excluyen de Git. Los errores guardan códigos controlados, sin mensajes de excepción del proveedor. No se registran bytes de imagen ni claves de autenticación. Las respuestas pueden contener información privada de la escena: conservarlas localmente y revisar cualquier exportación para la presentación. Las rutas se validan dentro del proyecto y del directorio de fotografías autorizado; no se ejecuta contenido de respuestas. Los originales y anotaciones de CVAT no se sobrescriben.

## Validación

```powershell
New-Item -ItemType Directory -Force tmp | Out-Null
python -m pytest tests/test_evaluacion_a1.py tests/test_evaluacion_a2_a3.py -q -p no:cacheprovider --basetemp tmp/pytest-evaluacion-nueva
```

Usar una carpeta temporal nueva en cada ejecución evita que pytest deba limpiar carpetas de pruebas anteriores. Todos los tests nuevos impiden crear un cliente real; los tokens y errores de proveedor se prueban con clientes falsos. Ver [informe de entrega](ENTREGA_A2_A3.md) para el resultado verificado.
