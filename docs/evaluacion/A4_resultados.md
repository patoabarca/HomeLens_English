# A4 — Estructura para resultados y conclusiones

**Estado: pendiente de experimentos reales autorizados y revisión humana.** Los fixtures y simulaciones prueban software; no aportan evidencia del desempeño de Gemini.

## Configuración y datos

Registrar identificador de ejecución y protocolo congelado, fecha UTC, modelo/versión reportada, hashes del prompt y esquema, versiones de código/dependencias, temperatura, timeout, reintentos y parámetros no fijados. Identificar el lote CVAT, hashes de imágenes, procedencia real/sintética, permisos y exhaustividad. Explicar separación entre 5 imágenes piloto y 30 finales. No incluir originales privados ni credenciales en la entrega académica.

## Tabla de resultados pendientes

| Indicador | Numerador / denominador | Valor medido | Pendientes / alcance |
|---|---|---|---|
| Fotos evaluadas, válidas y fallidas | Por lote e intento | Pendiente | Separar piloto/final |
| Precisión de identificación | C / (C+I) | Pendiente | Informar P y C/D |
| Cobertura de referencias | M / R | Pendiente | Máximo 5 detecciones/foto |
| IoU promedio | ΣIoU / M | Pendiente | Informar sin pareja |
| Ubicación IoU ≥0,50 | L / M | Pendiente | Incluir L absoluto |
| Detección y ubicación | L / (C+I) | Pendiente | Provisional con P>0 |
| Traducciones | Correctas / revisadas | Pendiente | Inglés/español conjuntamente |
| Gramática y pertinencia | Correctas / revisadas, por criterio e idioma | Pendiente | Pendientes por criterio |
| Tiempo | Promedio, mediana, mínimo, máximo; n | Pendiente | Éxitos y fallos separados |

Los valores se obtendrán de los informes A3, acompañados de sus denominadores. Conservar resultados por fotografía y objeto para investigar diferencias, errores y casos humanos. Informar las fotografías no ejecutadas y cualquier intento fallido o repetido; no elegir silenciosamente la mejor respuesta de varias ejecuciones.

## Análisis, conclusiones y limitaciones

Completar después de medir: patrones de reconocimiento/localización, ejemplos representativos anonimizados, errores de traducción o frases, diferencias por procedencia y límites por tamaño de muestra/anotación. Distinguir resultados exploratorios del piloto y estimación del conjunto reservado. Declarar los cambios de protocolo y justificar cualquier repetición posterior sin reemplazar el resultado original. Evitar conclusiones causales o generalizaciones que esta muestra no respalde.

El proyecto usa Gemini preentrenado: no presenta aprendizaje propio, entrenamiento con este dataset ni mejora de pesos.
