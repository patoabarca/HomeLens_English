# Incorporación del dataset sintético de evaluación

## Alcance y ubicación

El conjunto está en `data/evaluacion/cvat/finales/evaluacion_sintetica_lucas_v1/`, separado del piloto. Contiene 30 PNG originales, `annotations/instances_default.json` (COCO original), `annotations/instances_normalized.json`, los CSV/JSON de A1, `manifiesto_imagenes.csv`, `transformaciones.json`, `procedencia.json`, `seleccion_revision.csv` y `revision_visual.html`.

El RAR de entrada permanece intacto y no se incorpora al commit. En este checkout está en `insumos _locales/HomeLens_English.rar` (el nombre local del directorio tiene un espacio que no aparece en la ruta indicada inicialmente). El RAR y sus archivos temporales se excluyen del cambio.

## Procedencia y uso

Las imágenes son sintéticas. Según la declaración transmitida por Patricia, Lucas Centurión las generó mediante ChatGPT y autorizó su uso dentro del proyecto HomeLens English. No se atribuye licencia, fecha de generación, versión del modelo generador ni autorización para usos externos o redistribución pública.

El conjunto evalúa un modelo preentrenado; no se usa para entrenar una red neuronal propia. Resultados sobre estas imágenes sintéticas no demuestran por sí solos rendimiento sobre fotografías reales.

## Cantidades y validación técnica

- 30 imágenes PNG; 6 ambientes con 5 imágenes cada uno: baño, cocina, comedor, dormitorio, escritorio y living.
- 541 anotaciones; 30 IDs de imagen, 541 IDs de anotación y 80 IDs de categoría originales, únicos.
- Nombres y dimensiones COCO coinciden con todos los PNG. No hay imágenes faltantes/sobrantes ni duplicadas por SHA-256; tampoco hay solapamiento de hash con las 5 fotos del piloto.
- Las 541 cajas tienen coordenadas numéricas finitas, ancho/alto positivos y límites dentro de la imagen. No hay referencias huérfanas.
- El importador A1 devolvió `valid: true` con 30 imágenes, 541 anotaciones y 73 categorías utilizadas. `validar_dataset.py` devolvió `valid: true`, sin errores; la advertencia de ausencia de `seleccion.csv` es esperada mientras la revisión humana está pendiente.

El COCO original conserva sus 80 categorías. En la copia normalizada, `Coffee table` (ID 22) se unificó con `Coffee Table` (ID 45), dando 79 categorías. El proceso remapea todas las referencias al ID 45; no había anotaciones que usaran el ID 22, así que se actualizaron cero referencias y se conservaron las 541 anotaciones. No se fusionaron categorías similares: `Table`/`Dining Table`, `Cabinet`/`Kitchen Cabinet`/`Bathroom Cabinet`, `Chair`/`Office Chair`/`Armchair`, `Bed`/`Bunk Bed`, `Kettle`/`Electric Kettle` y `Curtain`/`Drapes` quedan para decisión humana.

Las imágenes se copiaron byte por byte, sin redimensionar ni recomprimir. La única transformación del COCO es el mapeo de categorías registrado en `transformaciones.json`. El importador existente convierte una vez las cajas COCO `[x, y, ancho, alto]` en píxeles a `[ymin, xmin, ymax, xmax]` normalizado de 0 a 1000, mediante `coco_to_homelens`. La galería presenta esos cuadros; no repite la conversión COCO.

## Simulación y estado de revisión

La simulación del ejecutor A2 procesó 30 de 30 imágenes: 30 respuestas del fixture local fueron válidas, sin errores, y se generó el informe A3 local. Es una comprobación del circuito; el fixture es una respuesta fija, no depende de imágenes/anotaciones y no constituye resultados ni métricas de rendimiento de Gemini. No se llamó a Gemini, no se consumió ningún servicio pago y la simulación no carga `.env` ni lee claves.

La revisión visual humana sigue **pendiente para las 30 imágenes**. Ninguna está marcada como aprobada; `seleccion_revision.csv` comienza con 30 decisiones `pendiente`. La calidad visual y la exhaustividad de las etiquetas no se consideran validadas automáticamente. El dataset no está declarado definitivo ni congelado.

## Abrir y completar la revisión visual

Desde la raíz del repositorio:

```powershell
python -m scripts.evaluacion.generar_galeria_revision --root data/evaluacion/cvat/finales/evaluacion_sintetica_lucas_v1
Start-Process .\data\evaluacion\cvat\finales\evaluacion_sintetica_lucas_v1\revision_visual.html
```

La galería presenta cada imagen, sus recuadros, categoría e ID de anotación, y permite elegir `Pendiente de revisión`, `Aprobada` o `Requiere corrección`, además de ingresar observaciones. Descargar el CSV desde el botón de la página y guardarlo como `data/evaluacion/cvat/finales/evaluacion_sintetica_lucas_v1/seleccion_revision.csv`; luego importar las decisiones y validar:

```powershell
python -m scripts.evaluacion.importar_revision --root data/evaluacion/cvat/finales/evaluacion_sintetica_lucas_v1 --revision-csv data/evaluacion/cvat/finales/evaluacion_sintetica_lucas_v1/seleccion_revision.csv
python -m scripts.evaluacion.validar_dataset --root data/evaluacion/cvat/finales/evaluacion_sintetica_lucas_v1
python -m scripts.evaluacion.generar_galeria_revision --root data/evaluacion/cvat/finales/evaluacion_sintetica_lucas_v1
```

## Pendientes y siguiente paso

1. Victoria debe revisar las 30 escenas, etiquetas, cajas y posibles omisiones; resolver también las categorías similares enumeradas arriba. No aprobar exhaustividad sin revisar ese aspecto.
2. Tras la revisión, importar las decisiones, validar, preparar un manifiesto nuevo y registrar permisos/procedencia y estado de exhaustividad. No reutilizar el manifiesto de simulación para la evaluación real.
3. Sólo después de revisión y autorización expresa, congelar el protocolo comparándolo con el manifiesto piloto y ejecutar una prueba real de una imagen seleccionada, usando `--image-id <ID> --limite 1 --real --autorizar-api`. No se ejecutó esa prueba en este trabajo.

## Huellas

`transformaciones.json` registra los SHA-256 del RAR fuente, el COCO original y el COCO normalizado, además del mapeo y el procedimiento. La identidad Git local del repositorio se configuró como Victoria Magliano (`vickymagliano@gmail.com`). Antes de cualquier publicación se debe verificar por separado la cuenta GitHub autenticada.
