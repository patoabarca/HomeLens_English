# Protocolo de evaluación final HomeLens English

**Estado: borrador; no congelado y no autorizado para ejecutar Gemini.**

Este protocolo prepara una prueba técnica de tres imágenes con el ejecutor A2 y el informe A3 existentes. La prueba no se ha ejecutado. No se deben ajustar etiquetas, equivalencias ni umbrales después de observar respuestas del modelo.

## Conjunto y selección reproducible

- Versión: `evaluacion_sintetica_lucas_v1`, 30 imágenes sintéticas aceptadas, 541 anotaciones, 6 ambientes.
- Fuente de evaluación: `annotations/instances_normalized.json` y las anotaciones normalizadas de A1 en `anotaciones.csv`. Se conserva `instances_default.json` como COCO original.
- El importador convirtió una vez los cuadros COCO `[x, y, ancho, alto]` en píxeles a `[ymin, xmin, ymax, xmax]` en `[0,1000]`; A2/A3 compara esos cuadros con las coordenadas predichas en ese mismo formato.
- La selección fija está en `data/evaluacion/cvat/finales/evaluacion_sintetica_lucas_v1/seleccion_prueba_3.csv`: la primera imagen, en orden del manifiesto, de baño, cocina y living. Los IDs y SHA-256 hacen reproducible la selección: `_1` (13 referencias), `_6` (22) y `_26` (21). La selección suma 56 referencias.

Tres imágenes sólo comprueban el circuito en tres ambientes; no son una muestra representativa para estimar desempeño.

## Etiquetas, cajas y correspondencias A3

El código usa `VERSION_CRITERIOS = "a3-v1"`. Normaliza etiquetas por `casefold`, eliminación de diacríticos y espacios repetidos, y aplica únicamente estas equivalencias predefinidas:

- `sofa`, `couch`, `settee` → `sofa`
- `television`, `tv`, `television set` → `television`
- `refrigerator`, `fridge` → `refrigerator`
- `cabinet`, `cupboard` → `cabinet`
- `drapes`, `curtain`, `curtains` → `drapes`
- `rug`, `carpet` → `rug`
- `lamp`, `light fixture` → `lamp`
- plural `chairs` → `chair`
- `picture`, `painting`, `framed picture` → `picture`
- `plant`, `potted plant`, `houseplant` → `plant`
- `cushion`, `throw pillow` → `cushion`

No se propone ninguna equivalencia nueva. `Table`/`Dining Table`, `Cabinet`/`Kitchen Cabinet` y `Cabinet`/`Bathroom Cabinet` permanecen distintos; no se fusionan automáticamente.

`emparejar` exige igualdad de las etiquetas canónicas y hace una asignación uno a uno que maximiza primero el número de pares y después la suma de IoU. El umbral **0.5 no decide si dos cajas se emparejan**: se usa en A3 sólo para contar localizaciones con IoU ≥ 0.5. Para una categoría única en las referencias, el código puede emparejar incluso con IoU 0; con instancias repetidas requiere IoU positivo, y empates o referencias indistinguibles quedan pendientes de revisión. La revisión humana A3 puede confirmar o descartar identificaciones y asignar una referencia una sola vez.

## Omisiones, detecciones adicionales y errores

- La cobertura usa como denominador todas las anotaciones de las imágenes con respuesta válida y como numerador los pares que tienen referencia e IoU calculado. Referencias no emparejadas quedan como omisiones/no cubiertas. Un estado válido sin objetos también aporta sus referencias al denominador, sin pares.
- La preparación del manifiesto deja `exhaustiva=false`. Por ello, una detección adicional sin referencia no se cuenta automáticamente como falsa positiva: queda como identificación pendiente, salvo adjudicación humana. La precisión de identificaciones revisadas excluye pendientes; no debe interpretarse como precisión completa sin revisar esas detecciones.
- `respuesta_invalida`, `fallida_api` y `fallida_local` se informan como fallidas y no aportan detecciones ni referencias a las métricas de reconocimiento/cobertura. Las imágenes no ejecutadas tampoco forman parte de ese denominador. Se informan por separado y no deben ocultarse al interpretar el resumen.
- Una asociación de clase correcta no implica localización correcta: el IoU medio y el conteo IoU ≥ 0.5 informan la localización por separado. Los errores lingüísticos requieren la revisión humana A3; no se califican automáticamente como exactos por el parser.

## Límite del producto e interpretación de cobertura

El prompt pide 3–5 objetos claros cuando la escena lo permite, permite 1–2 si son los únicos identificables y prohíbe inventar objetos. `analizar_exploracion` y A3 imponen un máximo de cinco objetos por imagen. El conjunto tiene 541 anotaciones en 30 imágenes (18,0 por imagen en promedio): aun con cinco predicciones emparejables en cada foto, la cobertura de referencias no podría superar 150/541 (27,7%) para las 30 fotos. En las tres imágenes seleccionadas hay 56 referencias y el techo correspondiente es 15/56 (26,8%). Es un techo aritmético, no un resultado esperado. La cobertura no representa exhaustividad de todos los objetos de la escena.

Las imágenes son sintéticas generadas con ChatGPT. Un resultado sólo describe esta muestra y esta versión del circuito; no demuestra desempeño en fotografías reales. El lote tiene seis ambientes y cinco imágenes por ambiente, y la prueba de tres imágenes es aún más limitada. Las etiquetas y su exhaustividad condicionan las métricas.

## Versión de aplicación comparada

Se comparó el código de `HLE_Evaluacion` (revisión `16b7729`) con `origin/main` actualizado a `a4d3fb96cfbcdcd36183bb39ae2e83b13d748a26`; no se cambió de rama ni se hizo merge.

- El modelo predeterminado en ambos códigos es `gemini-2.5-flash`, aunque `GEMINI_MODEL` puede cambiarlo. El prompt versionado `homelens/prompts/exploracion.txt` es idéntico. Para `gemini-2.5-flash`, ambos adaptadores envían `temperature=0.2`, JSON estructurado con `RespuestaExploracionIA` y la imagen más la instrucción textual.
- A2 llama `homelens.analisis.analizar_exploracion`, que carga el texto mediante `_cargar_prompt_exploracion` y usa `homelens.integraciones.gemini.AdaptadorGemini.analizar_imagen_exploracion`; este último llama `client.models.generate_content`. El prompt se envía como `system_instruction`, junto con la imagen, una instrucción textual fija y el esquema Pydantic.
- Esta rama omite en `homelens/analisis.py` la validación de usuario/sesión que sí tiene `origin/main`; también difiere en la configuración y modelos de autenticación. La rama omite `temperature` sólo si se selecciona `gemini-3.6-flash`, mientras `origin/main` envía `0.2` para cualquier modelo.
- Por tanto, A2 ejecutaría la inferencia de **HLE_Evaluacion**, no la aplicación completa actual de `origin/main`. Con el modelo fijado a `gemini-2.5-flash`, prompt y parámetros principales de inferencia coinciden, pero no coincide el código de aplicación/autenticación. El snapshot A2 registra modelo, hash del prompt, esquema y hashes de los módulos usados.

No se propone trasladar ni mezclar cambios de `main`. Si el objetivo es medir el código de producción actual, primero se debe acordar cómo hacerlo sin cambiar esta rama de trabajo.

## Preparación pendiente y comandos previstos

El manifiesto anterior `data/evaluacion/resultados/manifest_evaluacion_sintetica_lucas_v1.json` quedó obsoleto tras incorporar las decisiones humanas y falla la comprobación de hashes A1. Ya se preparó `data/evaluacion/resultados/manifest_evaluacion_sintetica_lucas_v1_revision_humana.json`: `cargar_dataset` valida 30 imágenes y 541 anotaciones; todas figuran con origen sintético y revisión aprobada, pero permisos pendientes y `exhaustiva=false`. Este archivo local está bajo `data/evaluacion/resultados/` y no se incluye en el commit; regenerarlo requiere elegir una ruta nueva inexistente.

Antes de congelarlo:

1. Las equivalencias quedan fijadas en la sección A3: no se agregan equivalencias y las categorías cercanas enumeradas permanecen distintas.
2. Revisar y declarar el alcance de exhaustividad de las anotaciones. El manifiesto preparado pone `exhaustiva=false`; no cambiarlo sin esa revisión.
3. Confirmar que la autorización de uso cubre enviar las imágenes a Gemini y obtener autorización expresa para las llamadas, que pueden tener costo. Para las tres imágenes autorizadas, registrar `permisos="confirmados"` en sus entradas del manifiesto. El ejecutor ya exige origen no pendiente, permiso confirmado y revisión humana aprobada.
4. Fijar modelo y política de reintentos antes de congelar. Los siguientes comandos fijan `gemini-2.5-flash`, timeout de 60 segundos y cero reintentos de la capa HomeLens; se deben usar los mismos valores al congelar y ejecutar:

```powershell
$env:GEMINI_MODEL = "gemini-2.5-flash"
$env:GEMINI_TIMEOUT_SECONDS = "60"
$env:GEMINI_MAX_RETRIES = "0"
python -m scripts.evaluacion.ejecutar_experimento congelar --manifest data/evaluacion/resultados/manifest_evaluacion_sintetica_lucas_v1_revision_humana.json --piloto-manifest data/evaluacion/resultados/manifest_piloto_v1.json --protocolo data/evaluacion/resultados/protocolo_evaluacion_sintetica_lucas_v1_prueba3.json
```

Congelar sólo registra configuración y huellas; no llama a Gemini. La prueba posterior consta de tres invocaciones, una por imagen, con un límite de una imagen por comando y sin `--reintentar-fallidas`:

```powershell
$env:GEMINI_MODEL = "gemini-2.5-flash"
$env:GEMINI_TIMEOUT_SECONDS = "60"
$env:GEMINI_MAX_RETRIES = "0"
python -m scripts.evaluacion.ejecutar_experimento ejecutar --manifest data/evaluacion/resultados/manifest_evaluacion_sintetica_lucas_v1_revision_humana.json --run-id prueba3_sintetica_lucas_v1 --real --autorizar-api --limite 1 --image-id cvat_evaluacion_sintetica_lucas_v1_1 --protocolo data/evaluacion/resultados/protocolo_evaluacion_sintetica_lucas_v1_prueba3.json
python -m scripts.evaluacion.ejecutar_experimento ejecutar --manifest data/evaluacion/resultados/manifest_evaluacion_sintetica_lucas_v1_revision_humana.json --run-id prueba3_sintetica_lucas_v1 --real --autorizar-api --limite 1 --image-id cvat_evaluacion_sintetica_lucas_v1_6 --protocolo data/evaluacion/resultados/protocolo_evaluacion_sintetica_lucas_v1_prueba3.json
python -m scripts.evaluacion.ejecutar_experimento ejecutar --manifest data/evaluacion/resultados/manifest_evaluacion_sintetica_lucas_v1_revision_humana.json --run-id prueba3_sintetica_lucas_v1 --real --autorizar-api --limite 1 --image-id cvat_evaluacion_sintetica_lucas_v1_26 --protocolo data/evaluacion/resultados/protocolo_evaluacion_sintetica_lucas_v1_prueba3.json
python -m scripts.evaluacion.informe_metricas --run data/evaluacion/resultados/prueba3_sintetica_lucas_v1
```

El adaptador limita sus reintentos propios a cero: como máximo una invocación `generate_content` por imagen en la capa HomeLens (tres en total). El repositorio no fija una política de reintentos internos del SDK del proveedor, por lo que no se afirma un límite absoluto de solicitudes HTTP. No reejecutar automáticamente fallas; si hubiera que reintentar, crear otro run-id y registrar la autorización. A2 guarda `ejecucion.json`, el índice `respuestas.csv` y un `intento_0001.json` por imagen bajo `data/evaluacion/resultados/prueba3_sintetica_lucas_v1/`; A3 guarda el informe en `informes/informe_<id>/`. Estos resultados no existen aún y no son parte de este commit.
