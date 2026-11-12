# Incorporación del dataset sintético de evaluación

## Alcance y ubicación

El conjunto está en `data/evaluacion/cvat/finales/evaluacion_sintetica_lucas_v1/`, separado del piloto. Contiene 30 PNG originales, `annotations/instances_default.json` (COCO original), `annotations/instances_normalized.json`, los CSV/JSON de A1, `manifiesto_imagenes.csv`, `transformaciones.json`, `procedencia.json`, `seleccion_revision.csv` y `revision_visual.html`. Se conserva el CSV humano recibido (`seleccion_revision_30.csv`) y la copia validada usada para importar (`seleccion_revision_30_importacion.csv`).

La selección reproducible para una futura prueba de tres imágenes está en `seleccion_prueba_3.csv`; el protocolo A2/A3 y los requisitos de ejecución están documentados en [PROTOCOLO_EVALUACION_FINAL.md](./PROTOCOLO_EVALUACION_FINAL.md).

El RAR de entrada permanece intacto y no se incorpora al commit. En este checkout está en `insumos _locales/HomeLens_English.rar` (el nombre local del directorio tiene un espacio que no aparece en la ruta indicada inicialmente). El RAR y sus archivos temporales se excluyen del cambio.

## Procedencia y uso

Las imágenes son sintéticas. Según la declaración transmitida por Patricia, Lucas Centurión las generó mediante ChatGPT y autorizó su uso dentro del proyecto HomeLens English. No se atribuye licencia, fecha de generación, versión del modelo generador ni autorización para usos externos o redistribución pública.

El conjunto evalúa un modelo preentrenado; no se usa para entrenar una red neuronal propia. Resultados sobre estas imágenes sintéticas no demuestran por sí solos rendimiento sobre fotografías reales.

## Cantidades y validación técnica

- 30 imágenes PNG; 6 ambientes con 5 imágenes cada uno: baño, cocina, comedor, dormitorio, escritorio y living.
- 541 anotaciones; 30 IDs de imagen, 541 IDs de anotación y 80 IDs de categoría originales, únicos.
- Nombres y dimensiones COCO coinciden con todos los PNG. No hay imágenes faltantes/sobrantes ni duplicadas por SHA-256; tampoco hay solapamiento de hash con las 5 fotos del piloto.
- Las 541 cajas tienen coordenadas numéricas finitas, ancho/alto positivos y límites dentro de la imagen. No hay referencias huérfanas.
- El importador A1 devolvió `valid: true` con 30 imágenes, 541 anotaciones y 73 categorías utilizadas. Tras incorporar las decisiones humanas, `validar_dataset.py` devolvió `valid: true`, sin errores ni advertencias; hay 30 candidatas aceptadas y 30 filas seleccionadas. Las 541 anotaciones permanecen intactas.

El COCO original conserva sus 80 categorías. En la copia normalizada, `Coffee table` (ID 22) se unificó con `Coffee Table` (ID 45), dando 79 categorías. El proceso remapea todas las referencias al ID 45; no había anotaciones que usaran el ID 22, así que se actualizaron cero referencias y se conservaron las 541 anotaciones. No se fusionaron las categorías cercanas `Table`/`Dining Table`, `Cabinet`/`Kitchen Cabinet`/`Bathroom Cabinet`, `Chair`/`Office Chair`/`Armchair`, `Bed`/`Bunk Bed`, `Kettle`/`Electric Kettle` y `Curtain`/`Drapes`; el protocolo las mantiene distintas y no propone equivalencias nuevas.

Las imágenes se copiaron byte por byte, sin redimensionar ni recomprimir. La única transformación del COCO es el mapeo de categorías registrado en `transformaciones.json`. El importador existente convierte una vez las cajas COCO `[x, y, ancho, alto]` en píxeles a `[ymin, xmin, ymax, xmax]` normalizado de 0 a 1000, mediante `coco_to_homelens`. La galería presenta esos cuadros; no repite la conversión COCO.

## Simulación y estado de revisión

La simulación del ejecutor A2 procesó 30 de 30 imágenes: 30 respuestas del fixture local fueron válidas, sin errores, y se generó el informe A3 local. Es una comprobación del circuito; el fixture es una respuesta fija, no depende de imágenes/anotaciones y no constituye resultados ni métricas de rendimiento de Gemini. No se llamó a Gemini, no se consumió ningún servicio pago y la simulación no carga `.env` ni lee claves.

## Revisión humana incorporada

Se importaron las 30 decisiones entregadas en `seleccion_revision_30.csv`: todas tienen `aceptada=si`, `estado_revision=revisada` y observaciones vacías. La importación se registró el 2026-11-12; esa fecha corresponde únicamente a la importación y no identifica a quien realizó la revisión ni la fecha en que la hizo. El CSV recibido permanece intacto y sus hashes, junto con el de la copia importada, están en `procedencia.json`.

El export recibido tenía `ambiente=pendiente`. Para la copia de importación se recuperó cada ambiente de `manifiesto_imagenes.csv`, vinculando por coincidencia exacta del nombre de archivo. `iluminacion` y `dificultad` quedaron vacíos porque no fueron proporcionados. `seleccion.csv` contiene las 30 decisiones incorporadas. La galería regenerada muestra 30 imágenes aceptadas y ninguna pendiente.

Esta decisión humana no equivale a una validación automática ni a una medición de rendimiento. El dataset no está declarado definitivo ni congelado y no se ejecutó evaluación real con Gemini.

## Abrir o regenerar la galería de revisión visual

Desde la raíz del repositorio:

```powershell
python -m scripts.evaluacion.generar_galeria_revision --root data/evaluacion/cvat/finales/evaluacion_sintetica_lucas_v1
Start-Process .\data\evaluacion\cvat\finales\evaluacion_sintetica_lucas_v1\revision_visual.html
```

La galería presenta cada imagen, sus recuadros, categoría e ID de anotación, y permite actualizar decisiones futuras. Para reimportar el conjunto de decisiones ya incorporado, usar la copia corregida y validar:

```powershell
python -m scripts.evaluacion.importar_revision --root data/evaluacion/cvat/finales/evaluacion_sintetica_lucas_v1 --revision-csv data/evaluacion/cvat/finales/evaluacion_sintetica_lucas_v1/seleccion_revision_30_importacion.csv
python -m scripts.evaluacion.validar_dataset --root data/evaluacion/cvat/finales/evaluacion_sintetica_lucas_v1
python -m scripts.evaluacion.generar_galeria_revision --root data/evaluacion/cvat/finales/evaluacion_sintetica_lucas_v1
```

## Pendientes y siguiente paso

1. Revisar y declarar el alcance de exhaustividad de las anotaciones; el manifiesto preparado deja `exhaustiva=false`.
2. Confirmar que la autorización de uso cubre el envío de las imágenes a Gemini, y autorizar expresamente las llamadas que pueden tener costo. Actualizar los permisos de las tres imágenes en el manifiesto preparado.
3. Congelar el protocolo comparándolo con el manifiesto piloto y ejecutar la prueba de tres imágenes de [PROTOCOLO_EVALUACION_FINAL.md](./PROTOCOLO_EVALUACION_FINAL.md). No se ejecutó esa prueba en este trabajo.

El detalle técnico de los criterios A3, comparación de aplicación con `origin/main`, selección de tres imágenes y comandos está en [PROTOCOLO_EVALUACION_FINAL.md](./PROTOCOLO_EVALUACION_FINAL.md). La prueba descrita allí permanece pendiente y no se llamó a Gemini.

## Huellas

`transformaciones.json` registra los SHA-256 del RAR fuente, el COCO original y el COCO normalizado, además del mapeo y el procedimiento. La identidad Git local del repositorio se configuró como Victoria Magliano (`vickymagliano@gmail.com`). Antes de cualquier publicación se debe verificar por separado la cuenta GitHub autenticada.
