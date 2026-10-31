# A4 — Resultados del piloto y preparación de la evaluación definitiva

**Cierre del piloto de Cocina: 31 de octubre de 2026.** Se completó una ejecución real y su revisión humana, con dos campos de pertinencia aún pendientes y declarados. Estos resultados corresponden a **una única fotografía sintética piloto**; no representan el desempeño general de Gemini ni resultados de las 30 fotografías finales. Los fixtures y las simulaciones sólo prueban software.

## Configuración, alcance y trazabilidad

Se evaluó Cocina (`cvat_piloto_v1_2`), generada por el equipo con ChatGPT (OpenAI), sin fotografías de terceros como referencia y con autorización registrada para evaluación académica, envío a Gemini y conservación de resultados. Las otras cuatro fotografías del piloto no se ejecutaron y mantienen sus permisos pendientes.

La ejecución real `gemini36_piloto_cocina_una_v2` utilizó `gemini-3.6-flash`, una imagen, una solicitud y cero reintentos. A2 reutilizó la integración, el prompt y el esquema estructurado de la aplicación. No se envió temperatura ni configuración explícita de razonamiento; el valor `medium` registrado corresponde al predeterminado documentado del proveedor. El JSON y sus coordenadas superaron las validaciones de la aplicación; ello no demuestra por sí solo que los objetos sean correctos.

La fuente de esta síntesis es el informe A3 posterior a la revisión humana: `data/evaluacion/resultados/gemini36_piloto_cocina_una_v2/informes/informe_6bc7f76a3ce9/`, generado el `2026-10-31T22:25:28.441563+00:00`. Conserva el resumen, detalles y `revision_aplicada.csv`. Los registros privados de A2 conservan configuración, versiones, hashes y respuesta original. Esta documentación publica sólo la síntesis académica; fotografías, respuestas completas, revisiones privadas, credenciales y certificados permanecen fuera de Git.

## Resultados de una fotografía piloto

| Indicador | Numerador / denominador | Resultado y alcance |
|---|---|---|
| Respuestas válidas | 1 / 1 fotografía ejecutada | Cuatro fotografías del piloto no ejecutadas |
| Precisión de identificación | 4 correctas / 4 detecciones resueltas | 100 %; ninguna identificación pendiente |
| Fracción confirmada del total | 4 / 4 detecciones devueltas | 100 % |
| Cobertura CVAT | 2 referencias emparejadas / 5 referencias de Cocina | 40 % del inventario anotado |
| IoU promedio | Suma 1,4918909407 / 2 pares confirmados | 0,7459 |
| Pares con IoU ≥ 0,50 | 2 / 2 pares confirmados | Ambos superan el umbral |
| Detección y ubicación, criterio conjunto de A3 | 2 pares con IoU ≥ 0,50 / 4 detecciones resueltas | 50 %; no es mAP |
| Nombres y traducciones | 4 correctas / 4 revisadas | 100 % |
| Gramática inglesa | 4 correctas / 4 revisadas | 100 % |
| Gramática española | 4 correctas / 4 revisadas | 100 % |
| Pertinencia inglesa | 3 correctas / 3 revisadas | 100 % entre revisadas; 1 caso pendiente |
| Pertinencia española | 3 correctas / 3 revisadas | 100 % entre revisadas; 1 caso pendiente |
| Tiempo de análisis M3 | Una respuesta exitosa | 10,40 s (valor conservado: 10,3963274 s) |

Con una sola respuesta exitosa, promedio, mediana, mínimo y máximo de tiempo coinciden; no permiten caracterizar la variabilidad de latencia. El recálculo local de A3 no añadió llamadas ni mediciones de Gemini.

## Decisiones humanas y limitaciones de las anotaciones

| Detección | Decisión visual confirmada | Efecto en las métricas |
|---|---|---|
| G1 `bar stool` | Correcta; misma instancia que R8 `Chair` | Par aprobado; IoU 0,8436924979 |
| G2 `kitchen island` | Correcta; la isla no estaba anotada en CVAT. No corresponde a R9 `Cabinet` | Sin referencia: cuenta en identificación, sin aportar cobertura ni IoU |
| G3 `pendant light` | Correcta; Gemini delimitó una lámpara y R6 `Lamp` agrupaba varias | Sin correspondencia individual aprobada: cuenta en identificación, sin aportar cobertura ni IoU |
| G4 `refrigerator` | Correcta; corresponde a R10 `Refrigerator` | Par aprobado; IoU 0,6481984429 |

Quedan dos detecciones correctas sin pareja y tres referencias CVAT sin pareja: R6 `Lamp`, R7 `Window` y R9 `Cabinet`. No se asigna IoU cero a las detecciones sin referencia. La cobertura describe las cinco referencias anotadas de Cocina, no todos los objetos presentes en la escena. Las diferencias de granularidad entre una instancia y un grupo impiden comparar directamente sus recuadros y afectan qué pares pueden aportar a cobertura e IoU. No se cambiaron cajas, equivalencias ni denominadores para mejorar los valores.

La frase de G2 afirma que la encimera es de mármol. Su apariencia en la fotografía no permite confirmar el material real. Traducción y gramática fueron aprobadas; la pertinencia sigue pendiente en inglés y español. Es un mismo caso con dos campos pendientes, excluidos de los respectivos denominadores de pertinencia revisada; no se calificaron automáticamente como incorrectos.

El inventario CVAT no exhaustivo, la muestra de una sola escena sintética, el máximo de cinco detecciones por fotografía, la revisión humana y la variabilidad generativa limitan la interpretación. El piloto permitió comprobar el flujo técnico y detectar necesidades de etiquetado; no permite estimar desempeño general, comparar procedencias ni atribuir mejoras al modelo. HomeLens utiliza un modelo preentrenado: estas imágenes no entrenan ni ajustan sus pesos.

## Conservación de los intentos

El primer intento `gemini36_piloto_cocina_una_v1` falló por validación de la cadena TLS antes de obtener una respuesta válida. Sus resultados e informe permanecen separados. Tras la configuración TLS local verificada, se autorizó la nueva ejecución `gemini36_piloto_cocina_una_v2`; no se reemplazó el fallo ni se mezcló su duración con la respuesta exitosa.

Dentro de v2 se conservaron el informe automático inicial `informe_b05b75b32db4`, el CSV anterior a las decisiones humanas y el nuevo informe `informe_6bc7f76a3ce9`. El cierre conserva expresamente los dos campos lingüísticos pendientes. No se ejecutan las otras imágenes para completar este cierre.

## Preparación de las 30 fotografías finales

Lucas dispone de la [guía de etiquetado y entrega](GUIA_LUCAS_ETIQUETADO_FINAL.md). El conjunto debe contener 30 fotografías nuevas, separadas del piloto por ID y hash. Antes de ejecutar la evaluación definitiva corresponde:

1. Acordar y aplicar categorías y alcance de anotación consistentes, revisar instancias y recuadros, conservar originales y exportar COCO 1.0. Registrar procedencia y permisos por imagen sin confirmarlos por defecto.
2. Importar en un lote nuevo mediante A1, revisar la galería y validar imágenes, metadatos, cajas, duplicados y separación. Declarar exhaustividad sólo después de revisarla específicamente.
3. Preparar un manifiesto final versionado y congelar prompt, modelo, esquema, configuración y criterios mediante el protocolo de [A2](A2_experimentos.md). Resolver los acuerdos metodológicos con el piloto antes de usar el conjunto reservado; no ajustar el prompt repetidamente con las imágenes finales.
4. Obtener autorización expresa antes de nuevas llamadas. La evaluación final completa exige 30 imágenes, procedencia y permisos confirmados de todo el lote ejecutado, y protocolo válido. Los resultados finales todavía están pendientes.
5. Aplicar la revisión humana de [A3](A3_metricas.md) y publicar numeradores, denominadores, pendientes, fallos, casos sin pareja y tiempos, conservando cada ejecución. Segmentar por procedencia cuando los datos lo permitan, sin mezclar piloto y final.

El informe definitivo deberá identificar ejecución, protocolo, fecha UTC, versión reportada del modelo, hashes de prompt/esquema/código/datos, dependencias, timeout, reintentos, parámetros enviados y no fijados. Mantendrá resultados por fotografía y objeto y declarará cualquier cambio o repetición, sin seleccionar silenciosamente la mejor respuesta.
