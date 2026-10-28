# A1 — Preparación y curación del dataset

## Decisión de fuente
HomeLens English utiliza exclusivamente **Open Images V7**. El dataset ofrece fotografías públicas con categorías y bounding boxes preparados para detección visual. No se combinan fotografías de COCO, ADE20K, SUN RGB-D u otros conjuntos.

HomeLens English utiliza Gemini como modelo multimodal preentrenado. Las fotografías de Open Images V7 se emplean exclusivamente para evaluación y análisis experimental. No se utilizan para entrenar ni ajustar los pesos del modelo.

## Objetivo y alcance
La selección busca hasta 120 fotografías verificadas: 20 para piloto y 100 reservadas para evaluación final. Antes de la selección definitiva pueden descargarse hasta 200 candidatas mediante una muestra aleatoria reproducible con semilla configurable. El objetivo de cantidad es orientativo, y una limitación real debe quedar documentada en lugar de completarse artificialmente.

## Preparación reproducible
La descarga usa el entorno separado descrito en `requirements-evaluacion.txt`:

```powershell
python -m venv .venv-evaluacion
.venv-evaluacion\Scripts\Activate.ps1
pip install -r requirements-evaluacion.txt
python scripts/evaluacion/descargar_openimages.py --max-samples 10 --seed 42
python scripts/evaluacion/descargar_openimages.py --max-samples 200 --seed 42 --classes-file scripts/evaluacion/clases_domesticas.txt --destino data/evaluacion
python scripts/evaluacion/validar_dataset.py --root data/evaluacion
```

La implementación fija el split `validation` y usa `label_types=["detections"]`. `--classes-file` permite seleccionar categorías reales de Open Images; puede combinarse con `--only-matching` para limitar las imágenes, aunque por defecto conserva las etiquetas disponibles de las candidatas.

## Organización
- `data/evaluacion/imagenes/`: fotografías reproducibles obtenidas desde Open Images.
- `candidatos.csv`: metadatos por imagen y estado de revisión.
- `seleccion.csv`: decisión manual y asignación a piloto o evaluación.
- `anotaciones.csv`: una fila por objeto anotado, separada de los metadatos de imagen.
- `descarga_fallida.json`: identificadores y errores de descarga.

Las imágenes no se incluyen en Git por defecto. Los CSV sí permiten auditar la selección sin redistribuir fotografías no verificadas.

## Anotaciones
Las imágenes conservan identificadores de Open Images, su split y sus metadatos disponibles. Los cuadros originales se registran primero en el formato normalizado relativo `[x, y, ancho, alto]` de FiftyOne/Open Images. Cuando se convierte al formato HomeLens `[ymin, xmin, ymax, xmax]` se usan las dimensiones reales, se produce una escala de 0 a 1000 y se conserva una columna separada. El script rechaza recuadros fuera de rango o con área no positiva.

La presencia de una anotación original no se interpreta como exhaustividad ni como validación visual automática.

## Revisión y calidad
La revisión manual registra ambiente, iluminación, dificultad, aceptación, descarte, destino y procedencia. La validación comprueba existencia, formato, legibilidad, IDs únicos, hashes exactos, metadatos coherentes y separación entre piloto y final. También debe advertir sobre revisiones pendientes, licencias pendientes y posibles duplicados visuales.

## Privacidad y licencias
Open Images V7 informa licencias generales, pero una condición global no garantiza la situación jurídica individual de cada fotografía. La atribución y licencia de cada imagen se mantiene pendiente hasta obtener y verificar datos disponibles. Deben evitarse imágenes innecesariamente sensibles. Las fotos descargadas deben conservarse fuera de Git y no redistribuirse sin comprobar cada obligación aplicable.

## Estado actual
A1 permanece **parcial** hasta completar la revisión visual y alcanzar la selección de 120 imágenes o documentar una limitación fundada. Se realizó una muestra controlada de validación:

- 10 imágenes obtenidas desde el split `validation` de Open Images V7.
- 101 anotaciones individuales exportadas.
- Dimensiones leídas y registradas para las 10 imágenes.
- Ninguna imagen fue aceptada ni distribuida aún entre piloto/evaluación: la selección manual sigue pendiente.
- No se declaran licencias individuales verificadas ni datos reales de autoría; esos campos quedan pendientes.

## Herramientas
La muestra fue ejecutada con Python 3.13.17, FiftyOne 1.22.1 y Pillow 13.0.0 en el entorno local `.venv-evaluacion`. No se realizaron llamadas a Gemini ni se modificaron M0-M8 en esta actividad.
