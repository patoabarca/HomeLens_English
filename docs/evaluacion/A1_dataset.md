# A1 — Preparación y curación del dataset

## Decisión de fuente
HomeLens English conserva **Open Images V7** como antecedente y fuente complementaria, e incorpora fotografías domésticas etiquetadas manualmente mediante CVAT. Las fuentes tienen metadatos separados y no se mezclan sin trazabilidad.

HomeLens English utiliza Gemini como modelo multimodal preentrenado. Las fotografías de Open Images V7 se emplean exclusivamente para evaluación y análisis experimental. No se utilizan para entrenar ni ajustar los pesos del modelo.

## Objetivo y alcance
La decisión definitiva del equipo es usar **5 fotografías sintéticas piloto** y **30 fotografías nuevas para evaluación final**, todas con etiquetas y bounding boxes manuales en CVAT. Lucas preparará las 30 nuevas fotografías; se registrará por imagen si es real o sintética y se confirmarán sus permisos de uso. El conjunto final permanece reservado hasta fijar prompt, modelo y criterios. No hace falta disponer ahora de esas imágenes para desarrollar A2 y A3.

El objetivo anterior de 120 fotografías (20 piloto y 100 finales) y las descargas de Open Images se conservan aquí como antecedentes, sin formar parte del protocolo definitivo. No se requiere un sistema alternativo de etiquetas simples ni entrenamiento propio.

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

### Problema detectado y corrección
La primera ejecución utilizó el nombre de dataset FiftyOne `homelens_a1_validation` sin clases de filtro ni un parámetro explícito de reutilización. Como resultado, el dataset preexistente se reutilizó y varias imágenes correspondían a naturaleza, animales o plantas; por ejemplo, `d02c404790d920a0` contiene 49 anotaciones `Plant` y `c137232242da09ee` contiene un oso. Las categorías originales se conservaron en el CSV.

FiftyOne recibe `classes` para solicitar etiquetas de Open Images y `only_matching=True` para limitar las muestras a imágenes que contienen al menos una de esas etiquetas. Un nombre de dataset existente ya no se reutiliza silenciosamente: el script exige `--reuse-dataset` o un `--dataset-name` diferente. Los CSV existentes tampoco se sobrescriben por accidente; se requiere `--allow-overwrite`. Para una selección nueva se debe usar un destino y nombre de dataset nuevos.

La implementación fija el split `validation` y usa `label_types=["detections"]`. `--classes-file` permite seleccionar categorías reales de Open Images; el modo corregido usa `--only-matching` por defecto.

### Categorías domésticas verificadas
La lista actual no incluye `Plant`, `Tree`, `Flower`, animales ni categorías generales como criterio principal. Las categorías prioritarias propuestas fueron verificadas contra el archivo local de clases de Open Images V7 y existen todas:

- Cocina: `Refrigerator`, `Microwave oven`, `Kitchen appliance`, `Countertop`, `Cupboard`, `Mug`.
- Living: `Couch`, `Television`, `Lamp`, `Furniture`.
- Dormitorio: `Bed`, `Lamp`, `Furniture`.
- Baño: `Toilet`, `Sink`, `Mirror`, `Towel`.
- Escritorio: `Laptop`, `Computer keyboard`, `Computer monitor`, `Book`, `Desk`.
- Mobiliario adicional: `Chair`, `Table`, `Washing machine`, `Clock`, `Bottle`.

El filtro preselecciona escenas, pero la aceptación no es automática. Se conserva el conjunto completo de detecciones originales y se calcula `cantidad_objetos` como la cantidad de cuadros reales, no como la cantidad de etiquetas distintas.

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

### Galería visual
Después de una descarga, generar la galería:

```powershell
python scripts/evaluacion/generar_galeria_revision.py --root data/evaluacion_muestra_domestica_v1
```

La página `revision_visual.html` muestra cada imagen, sus cuadros y etiquetas originales, el identificador de Open Images, las categorías anotadas y controles de aceptación, ambiente, iluminación, dificultad, motivo de descarte y destino. El botón descarga `seleccion_revision.csv`; ninguna decisión se asigna automáticamente a piloto o evaluación final.

Se aceptan imágenes con varios objetos domésticos plausibles o contexto interior claramente identificable. Se descartan bosques, jardines, exteriores sin contexto de vivienda, animales, imágenes fuera de foco, recortes engañosos, etiquetas visualmente incorrectas dominantes y escenas donde el objeto coincidente aparece de forma incidental. Cada descarte debe conservar su motivo y el identificador original.

## Importación de fotografías CVAT

CVAT permite una anotación manual más específica que la preselección de Open Images. El formato original es COCO 1.0 y la exportación conserva categorías, fotografías declaradas y una fila por objeto en `annotations/instances_default.json`. Las fotografías originales no están incluidas en la exportación y deben incorporarse por separado.

La organización preparatoria es:

- `data/evaluacion/cvat/*.zip`: exportaciones originales, excluidas de Git por defecto.
- `data/evaluacion/cvat/exportaciones/`: copia interna de exportaciones por lote.
- `data/evaluacion/cvat/fotografias_originales/`: fotografías originales privadas y excluidas de Git.
- `data/evaluacion/cvat/pilotos/<lote>/`: metadatos JSON/CSV normalizados del lote.
- `data/evaluacion/cvat/resultados/`: resultados de validación y revisión.

Importar un lote nuevo:

```powershell
python scripts/evaluacion/importar_cvat.py `
  --export-zip data/evaluacion/cvat/HLE_5_Imagenes_Prueba.zip `
  --output data/evaluacion/cvat/pilotos/piloto_v1 `
  --lote piloto_v1 `
  --destino piloto
python scripts/evaluacion/validar_dataset.py `
  --root data/evaluacion/cvat/pilotos/piloto_v1
```

Cada cuadro COCO `[x, y, ancho, alto]` se convierte usando las dimensiones exportadas al formato HomeLens `[ymin, xmin, ymax, xmax]`, normalizado de 0 a 1000. También se conserva una representación original relativa `[x, y, ancho, alto]` para mostrar recuadros y se conservan las categorías completas y metadatos originales. Cada identificación propia tiene la forma `cvat_<lote>_<id_coCO>`.

Las validaciones comprueban IDs únicos, referencias entre imágenes y anotaciones, categorías definidas, bounding boxes, coordenadas y cantidad de objetos por fotografía. Cuando existen fotografías originales, verifican nombres, dimensiones reales y hashes SHA-256; detectan duplicados exactos. Si las fotografías originales faltan, el validador informa advertencias y no declara completada la revisión visual.

El piloto actual contiene 5 imágenes declaradas, 26 anotaciones, 26 recuadros y 20 categorías utilizadas en 25 categorías definidas. Las cinco fotografías originales están disponibles en su directorio privado CVAT, asociadas por ruta y hash. Este conjunto piloto se separa de las 30 fotografías nuevas de evaluación final; no deben asignarse automáticamente ni mezclar lotes.

La procedencia, los permisos, la autoría, la calidad y el estado de revisión deben registrarse por lote. Ningún dato CVAT se usa para entrenar Gemini ni se afirma una evaluación de Gemini hasta completar la comparación en la etapa posterior.

## Privacidad y licencias
Open Images V7 informa licencias generales, pero una condición global no garantiza la situación jurídica individual de cada fotografía. La atribución y licencia de cada imagen se mantiene pendiente hasta obtener y verificar datos disponibles. Deben evitarse imágenes innecesariamente sensibles. Las fotos descargadas deben conservarse fuera de Git y no redistribuirse sin comprobar cada obligación aplicable.

## Estado actual
El piloto CVAT tiene sus cinco fotografías aceptadas y revisadas; siguen pendientes los permisos y la documentación de procedencia indicados al final. La preparación del conjunto final de 30 imágenes aún no está completa. Como antecedente, se realizó una muestra controlada de Open Images:

- 10 imágenes obtenidas desde el split `validation` de Open Images V7.
- 101 anotaciones individuales exportadas.
- Dimensiones leídas y registradas para las 10 imágenes.
- Ninguna imagen fue aceptada ni distribuida aún entre piloto/evaluación: la selección manual sigue pendiente.
- No se declaran licencias individuales verificadas ni datos reales de autoría; esos campos quedan pendientes.

### Intento de muestra doméstica controlada
Se preparó una muestra nueva separada con 20 candidatas como objetivo máximo, destino `data/evaluacion_muestra_domestica_v1` y dataset FiftyOne `homelens_a1_domestic_v1_2026_10_30`. La ejecución no pudo iniciar porque el servicio de base de datos integrado de FiftyOne no pudo enlazar su puerto en Windows (`DatabaseService failed to bind to port`). No se descargaron imágenes en esa muestra, no se sobrescribieron los CSV anteriores y la revisión visual manual todavía no puede declararse aprobada.

### Solución de la base local FiftyOne
La versión de Python del entorno es 3.13.17. FiftyOne es 1.22.1, PyMongo 4.9.2, MongoEngine 0.29.3 y `fiftyone-db` 1.4.1; el binario incluido ejecuta MongoDB 7.0.28.

El traceback no indicaba corrupción ni falta de permisos. Los registros de MongoDB mostraban recuperación WiredTiger e inicio correcto, pero la sincronización interna de `DatabaseService` no pudo descubrir el puerto del proceso hijo en Windows. La salida utilizaba un puerto dinámico y mostraba `mongod startup complete`; por eso reiniciar, terminar procesos ajenos o borrar datos hubiera sido innecesario y riesgoso.

La solución utilizada no modifica ni elimina la base anterior: se inició el `mongod.exe` incluido de FiftyOne manualmente en el puerto local 27018 con una base aislada en la carpeta de sesión, y FiftyOne se conectó mediante `FIFTYONE_DATABASE_URI=mongodb://127.0.0.1:27018/fiftyone`. MongoDB inició en limpio, mostró `Waiting for connections` y `startup complete`, y `fo.list_datasets()` devolvió una lista válida.

### Muestras nuevas controladas
Se completó una primera prueba separada de 5 imágenes. Las cinco fueron descargadas, validadas y conservadas en `data/evaluacion_domestica_test_v2`; sus 23 cuadros originales y categorías disponibles quedaron en `anotaciones.csv`. La revisión visual mostró escenas claras como una cocina y una lámpara, mientras que otras coincidencias de mesa/silla eran exteriores, públicas o no claramente domésticas.

Después se completó una muestra ampliada de 20 candidatas en `data/evaluacion_domestica_muestra_v3`, validada como `valid: true`. El recuento contiene 20 imágenes y sus 62 objetos anotados. Se generó `revision_visual.html`; ninguna fue aceptada ni asignada automáticamente a piloto o evaluación final.

La revisión visual de la hoja de contacto permite separar ambientes domésticos de simples coincidencias. Las candidatas con mayor contexto doméstico incluyen la cocina en `0b6227bb06345402`, la cocina en `b7beabfc7d3356dd`, la cama en `03646bb2f288eaae`, el escritorio/pantalla en `ff9d6b864d154460`, así como objetos individuales que requieren aceptación visual específica. La aceptación definitiva permanece pendiente en la galería.

## Piloto humano CVAT

El primer piloto CVAT contiene cinco fotografías y 26 anotaciones manuales en 20 categorías. Las cinco imágenes originales se encuentran asociadas por ruta y SHA-256. Las dimensiones reales coinciden con COCO para Baño, Cocina, Comedor y Dormitorio.

Para `Living.jpg`, COCO declara `1200 × 2133` y el archivo real mide `900 × 1600`. Las relaciones de aspecto son `0.5625879044` y `0.5625`, respectivamente; la diferencia es `0.0000879044`. Los datos conservan por separado ambas dimensiones, y la transformación registrada exige redimensionamiento uniforme, coincidencia exacta de tamaño real, revisión humana y diferencia máxima de relación de aspecto de `0.001`. La selección humana aceptó Living y se confirmó visualmente la imagen; la comparación con una fuente original separada para descartar recortes no está disponible.

`Comedor01.png` y `Dormitorio04.png` conservan sus nombres exportados por CVAT, pero sus archivos reales son JPEG bajo nombres `.png.jpeg`. El validador registra estos nombres/formato como advertencias informativas, no como errores ni como aprobación automática de datos. Las coordenadas HomeLens siguen normalizadas y pueden aplicarse a Living sin modificar las anotaciones originales; por ejemplo, un recuadro normalizado se escala proporcionalmente a la versión `900 × 1600`.

Las cinco fotografías fueron marcadas como aceptadas y revisadas por una persona mediante `seleccion_revision.csv`. La decisión quedó incorporada en `candidatos.csv` y `seleccion.csv` sin modificar las anotaciones originales ni los cuadros. La reimportación desde CVAT conserva los campos humanos por `image_id` y no reasigna ni elimina anotaciones.

Incorporar una decisión exportada:

```powershell
python scripts/evaluacion/importar_revision.py `
  --root data/evaluacion/cvat/pilotos/piloto_v1 `
  --revision-csv data/evaluacion/cvat/pilotos/piloto_v1/seleccion_revision.csv
python scripts/evaluacion/validar_dataset.py `
  --root data/evaluacion/cvat/pilotos/piloto_v1
python scripts/evaluacion/generar_galeria_revision.py `
  --root data/evaluacion/cvat/pilotos/piloto_v1
```

Esta revisión humana confirma cinco fotografías aceptadas; no constituye una evaluación ni una métrica de Gemini. La solicitud actual del equipo habilita desarrollar y probar A2/A3 con simulaciones; las llamadas reales requieren autorización expresa. La validación técnica pasa con tres advertencias: dos correspondencias de nombre/formato JPEG bajo nombres PNG y Living como transformación de tamaño documentada. Falta finalizar procedencia, autoría, licencias y permisos.

La conexión con los experimentos se documenta en [A2](A2_experimentos.md), las métricas en [A3](A3_metricas.md) y la estructura de resultados pendientes en [A4](A4_resultados.md). Los metadatos experimentales se guardan en un manifiesto lateral, sin reescribir candidatos, anotaciones ni revisiones originales de A1.

## Herramientas
La muestra fue ejecutada con Python 3.13.17, FiftyOne 1.22.1 y Pillow 13.0.0 en el entorno local `.venv-evaluacion`. No se realizaron llamadas a Gemini ni se modificaron M0-M8 en esta actividad.
