# Entrega A2 y A3 — 31 de octubre de 2026

## Alcance y estado inicial comprobado

Se trabajó en `HLE_Evaluacion`. La identidad local permanece en Victoria Magliano; no se modificó configuración de Git, no se hicieron commits, push ni merge.

A1 ya tenía importación CVAT COCO 1.0, conversión a HomeLens, validación, importación de decisiones humanas y galería. Se verificaron 5 fotografías piloto aceptadas, 26 anotaciones, asociación de originales por hash y las discrepancias documentadas de Comedor, Dormitorio y Living. Sus 18 tests pasaron antes de implementar A2/A3. Había modificaciones y archivos sin seguimiento de A1; se conservaron.

## 1. Archivos creados o modificados en esta actividad

| Archivo | Responsabilidad |
|---|---|
| `scripts/evaluacion/dataset_experimento.py` (nuevo) | Manifiesto lateral, lectura de A1, rutas y metadatos |
| `scripts/evaluacion/ejecutar_experimento.py` (nuevo) | A2, simulación, transporte registrado, reanudación y protocolo |
| `scripts/evaluacion/metricas.py` (nuevo) | IoU, correspondencias, denominadores y tiempos |
| `scripts/evaluacion/informe_metricas.py` (nuevo) | Revisión humana y exportaciones A3 |
| `scripts/evaluacion/fixtures/respuesta_simulada.json` (nuevo) | Respuesta controlada, ajena a la referencia CVAT |
| `tests/test_evaluacion_a2_a3.py` (nuevo) | 36 casos automatizados de A2/A3 |
| `docs/evaluacion/A2_experimentos.md` (nuevo) | Procedimiento y comandos completos |
| `docs/evaluacion/A3_metricas.md` (nuevo) | Definiciones matemáticas y criterios humanos |
| `docs/evaluacion/A4_resultados.md` (nuevo) | Estructura de resultados aún pendientes |
| `docs/evaluacion/ENTREGA_A2_A3.md` (nuevo) | Este informe |
| `docs/evaluacion/A1_dataset.md` (modificado) | Decisión definitiva 5 piloto + 30 finales, conservando antecedentes |
| `scripts/evaluacion/README.md` (modificado) | Entrada unificada a A1–A4 |
| `.gitignore` (ampliado) | Exclusión de resultados, imágenes y exportaciones privadas |

Ya estaban pendientes al comenzar: cambios en `.gitignore`, `A1_dataset.md`, `scripts/evaluacion/README.md`, `clases_domesticas.txt`, `descargar_openimages.py`, `validar_dataset.py`, `tests/test_evaluacion_a1.py`; y los archivos nuevos `importar_cvat.py`, `importar_revision.py`, `generar_galeria_revision.py` y las dos muestras domésticas de Open Images. No se descartó ese trabajo. En los tres archivos compartidos se añadieron sólo los cambios necesarios para esta entrega. Los directorios de imágenes de esas muestras ahora quedan excluidos de Git.

## 2. Funcionalidades implementadas

- Reutilización de M2/M3, prompt, esquema y adaptador originales, con parámetros de preparación iguales a la interfaz. No se modificaron `homelens/` ni `app.py`.
- Experimentos por imagen con hashes, fechas UTC, modelo, prompt/esquema/configuración/código, respuestas y preguntas completas, tiempos, errores y consumo reportado. JSON por intento y un índice CSV.
- Simulación sin red por defecto, autorización explícita para modo real, continuación tras fallos, historial de reintentos y reanudación sin repetir respuestas válidas.
- Manifiestos separados piloto/final; procedencia, permisos y exhaustividad por fotografía; protocolo congelado, control de separación por ID/hash y reserva del conjunto final.
- Correspondencia uno a uno con equivalencias versionadas, revisión de ambigüedades e inventarios incompletos; precisión provisional con pendientes explícitos, cobertura, IoU y proporción conjunta de detección/ubicación.
- Revisión humana de nombres/traducción y gramática/pertinencia de frases en inglés y español. Cada criterio usa solamente sus casos revisados.
- Informes por imagen, objeto y referencia, resumen general, tiempos de éxitos/fallos y copias auditables de las revisiones aplicadas. Los originales de CVAT permanecen intactos.

## 3. Pruebas y ejecución comprobadas

- **A1: 18/18 aprobadas. A2/A3: 36/36 aprobadas. Evaluación: 54/54.**
- **Suite completa: 123 aprobadas y 1 fallo existente de interfaz**, reproducido también ejecutando sólo ese test, sin los tests nuevos. `tests/test_estado_ui.py::TestEstadoUI::test_regresion_interaccion_botones_tarjeta_y_selector_con_apptest` falla en `btn1.click().run()` porque Streamlit AppTest no encuentra en las opciones el icono serializado del selector (`ValueError: content_icon ... is not in list`). No se modificó la interfaz ni se ocultó/excluyó el test. Esa incidencia requiere una tarea independiente compatible con la restricción de M0–M8.
- Validador del piloto: `valid=true`, 5 candidatas/aceptadas/seleccionadas. Conserva 3 advertencias conocidas: dos nombres PNG con formato JPEG y el tamaño transformado de Living.
- Simulación completa final verificada: `data/evaluacion/resultados/simulacion_piloto_a2a3_verificada`, con **5 respuestas simuladas válidas y 5 registros**. Repetir el comando no añadió intentos. El informe está en `informes/informe_e56e5e4ca137/` dentro de esa ejecución.
- Estos cinco resultados sólo verifican el contrato de software y las exportaciones. **No son respuestas reales ni métricas de calidad/tiempo de Gemini. No se realizaron llamadas reales.**
- Entorno usado: Python 3.13.17, `google-genai` 1.29.0, Pydantic 2.11.7 y Pillow 11.3.0. No se instalaron dependencias ni se activaron servicios. Falta verificar Python 3.11 si se exige esa versión para la entrega.
- Rama e identidad verificadas al terminar; `git diff --check` sin errores y sin cambios en M0–M8/interfaz.

## 4. Ejecutar una simulación de las cinco imágenes

Desde la raíz, el manifiesto local ya preparado se puede reutilizar:

```powershell
python -m scripts.evaluacion.ejecutar_experimento ejecutar --manifest data/evaluacion/resultados/manifest_piloto_v1.json --run-id simulacion_piloto_v1
python -m scripts.evaluacion.informe_metricas --run data/evaluacion/resultados/simulacion_piloto_v1
```

Para preparar el manifiesto en otro entorno con las mismas fotos, consultar [A2](A2_experimentos.md). Los resultados locales están excluidos de Git. El primer informe crea `revision_humana.csv`; editar decisiones y volver a generar el informe aplica la revisión sin reemplazar informes anteriores.

## 5. Prueba real de una imagen, posterior a autorización

El comando siguiente **no se ejecutó**. Requiere credencial en el entorno y permisos de uso verificados (`permisos: "confirmados"`) en el manifiesto. La procedencia piloto está registrada como sintética; los permisos siguen pendientes, sin inventarlos.

```powershell
python -m scripts.evaluacion.ejecutar_experimento ejecutar --manifest data/evaluacion/resultados/manifest_piloto_v1.json --run-id gemini_piloto_una_v1 --image-id cvat_piloto_v1_1 --limite 1 --real --autorizar-api
```

Una imagen puede ocasionar reintento según la configuración existente. Para limitarla a una sola petición, fijar antes `$env:GEMINI_MAX_RETRIES = "0"`. Nunca colocar la clave en el comando.

## 6. Incorporar las 30 fotografías de Lucas

Usar el importador CVAT existente, un nuevo `--lote lucas_final_v1`, `--destino evaluacion_final`, directorio separado de originales y salida `data/evaluacion/cvat/finales/lucas_final_v1`. Revisar en la galería, importar decisiones y validar A1. Preparar el manifiesto final, completar procedencia/permisos/exhaustividad y congelar el protocolo antes de analizar. [A2 contiene todos los comandos](A2_experimentos.md#incorporar-las-30-fotografías-de-lucas).

No se cambia la lógica de importación. Todas las imágenes se anotan con CVAT, no se usan etiquetas simples alternativas. La ejecución final exige las 30 fotografías y rechaza simulaciones o imágenes compartidas con el piloto. Estas imágenes no se usaron ni se necesitan para desarrollar el procedimiento.

## 7. Qué falta para completar A2 y A3

El procedimiento técnico está implementado y probado con fixtures. Para completar la evaluación empírica faltan: documentar permisos/procedencia, autorizar y verificar una llamada real piloto, revisar sus resultados, fijar las decisiones del protocolo, recibir/anotar/revisar las 30 imágenes nuevas, ejecutar el conjunto reservado y completar la revisión humana de ambigüedades, nombres y frases. Después se podrán completar A4 y las conclusiones con datos medidos.

Además queda la incidencia independiente del test de interfaz y, si se requiere, validar en Python 3.11. No se declara que la suite global esté completamente aprobada ni que el desempeño real de Gemini haya sido medido.

## 8. Alcance listo para revisar antes de commit

Los archivos nuevos de A2/A3, documentación A1–A4/entrega y ampliación de privacidad están listos para revisión. Como los importadores CVAT de A1 aún estaban sin seguimiento, deben incorporarse también para que el flujo sea reproducible desde un clon nuevo. Es conveniente revisar primero ese conjunto pendiente de A1 y luego separar el desarrollo A2/A3 en otro commit. No incluir originales, resultados privados, `.env` ni carpetas temporales. **No se creó ningún commit ni se hizo push/merge.**
