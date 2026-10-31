# Herramientas de evaluación A1–A4

El protocolo definitivo usa 5 fotografías sintéticas piloto y 30 nuevas fotografías finales, todas anotadas en CVAT. Los comandos de Open Images de este documento se conservan como antecedente de A1.

- [A1: preparación CVAT y antecedentes](../../docs/evaluacion/A1_dataset.md).
- [A2: simulación completa, prueba real de una imagen e incorporación de Lucas](../../docs/evaluacion/A2_experimentos.md).
- [A3: métricas, denominadores y revisión humana](../../docs/evaluacion/A3_metricas.md).
- [A4: estructura de resultados pendientes](../../docs/evaluacion/A4_resultados.md).
- [Informe de entrega y verificación](../../docs/evaluacion/ENTREGA_A2_A3.md).

Las herramientas nuevas se ejecutan desde la raíz como módulos: `python -m scripts.evaluacion.ejecutar_experimento --help` y `python -m scripts.evaluacion.informe_metricas --help`. No realizan llamadas reales por defecto. M0–M8 permanecen sin cambios.

Ejecutar siempre con un entorno separado:

```

## Importación CVAT

Las exportaciones CVAT COCO 1.0 se importan sin mezclar su lógica con FiftyOne/Open Images:

```powershell
python scripts/evaluacion/importar_cvat.py `
  --export-zip data/evaluacion/cvat/HLE_5_Imagenes_Prueba.zip `
  --output data/evaluacion/cvat/pilotos/piloto_v1 `
  --lote piloto_v1 `
  --destino piloto
python scripts/evaluacion/validar_dataset.py --root data/evaluacion/cvat/pilotos/piloto_v1
```

El ZIP exportado contiene anotaciones y metadatos, pero normalmente no contiene las fotografías originales. Copiar primero esas fotografías privadas en `data/evaluacion/cvat/fotografias_originales/<lote>/` y actualizar `ruta_relativa` en el CSV generado antes de completar la revisión. No hay aceptación visual automática.powershell
python -m venv .venv-evaluacion
.venv-evaluacion\Scripts\Activate.ps1
pip install -r requirements-evaluacion.txt
python scripts/evaluacion/descargar_openimages.py --max-samples 10 --seed 42 --classes-file scripts/evaluacion/clases_domesticas.txt --destino data/evaluacion
python scripts/evaluacion/validar_dataset.py --root data/evaluacion
```

Antes de una descarga mayor, comprobar espacio disponible y revisar los resultados de la muestra. El script limita el split a `validation` y permite reutilizar imágenes y metadatos mediante un dataset FiftyOne nombrado.

## Corrección controlada de A1

La muestra de depuración usa un destino y un nombre FiftyOne nuevos. No reutilizar silenciosamente un dataset anterior:

```powershell
python scripts/evaluacion/descargar_openimages.py `
  --max-samples 20 --seed 42 `
  --classes-file scripts/evaluacion/clases_domesticas.txt `
  --only-matching `
  --dataset-name homelens_a1_domestic_v1_2026_10_30 `
  --destino data/evaluacion_muestra_domestica_v1

python scripts/evaluacion/generar_galeria_revision.py --root data/evaluacion_muestra_domestica_v1
python scripts/evaluacion/validar_dataset.py --root data/evaluacion_muestra_domestica_v1
```

El filtro `classes` solicita las categorías de Open Images; `only_matching=True` limita las fotos a coincidencias. `Plant` y las categorías naturales fueron retiradas. El campo `cantidad_objetos` cuenta cada detección original y se valida contra `anotaciones.csv`.

## Uso con MongoDB manual aislado

En Windows, si el descubrimiento automático del puerto de FiftyOne falla, iniciar manualmente el MongoDB incluido sin tocar la base existente:

```powershell
$mongod = ".venv-evaluacion\Lib\site-packages\fiftyone\db\bin\mongod.exe"
$db = "$env:USERPROFILE\.copilot\session-state\HLE_A1\fiftyone_manual_db"
New-Item -ItemType Directory -Force -Path $db | Out-Null
& $mongod --dbpath $db --logpath "$db\mongod_manual.log" --port 27018 --bind_ip 127.0.0.1
```

En otra terminal, conectar FiftyOne a ese servidor:

```powershell
$env:FIFTYONE_DATABASE_URI = "mongodb://127.0.0.1:27018/fiftyone"
python scripts/evaluacion/descargar_openimages.py --max-samples 20 --seed 20261030 --classes-file scripts/evaluacion/clases_domesticas.txt --only-matching --dataset-name homelens_a1_domestic_sample_v3_2026_10_30 --destino data/evaluacion_domestica_muestra_v3
python scripts/evaluacion/generar_galeria_revision.py --root data/evaluacion_domestica_muestra_v3
python scripts/evaluacion/validar_dataset.py --root data/evaluacion_domestica_muestra_v3
```
