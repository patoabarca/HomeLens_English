# Herramientas A1

Ejecutar siempre con un entorno separado:

```powershell
python -m venv .venv-evaluacion
.venv-evaluacion\Scripts\Activate.ps1
pip install -r requirements-evaluacion.txt
python scripts/evaluacion/descargar_openimages.py --max-samples 10 --seed 42 --classes-file scripts/evaluacion/clases_domesticas.txt --destino data/evaluacion
python scripts/evaluacion/validar_dataset.py --root data/evaluacion
```

Antes de una descarga mayor, comprobar espacio disponible y revisar los resultados de la muestra. El script limita el split a `validation` y permite reutilizar imágenes y metadatos mediante un dataset FiftyOne nombrado.
