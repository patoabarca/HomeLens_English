# A3 — Definiciones y criterios de evaluación

La referencia procede de anotaciones manuales de CVAT importadas por A1. Todas las cajas usan `[ymin, xmin, ymax, xmax]` en escala 0–1000. La conversión COCO existente se reutiliza durante la importación; A3 lee esa columna y no vuelve a convertir ni altera las anotaciones humanas.

## Configuración del experimento

El modelo seleccionado es `gemini-3.6-flash`. A2 usa el mismo adaptador, prompt y esquema estructurado de la aplicación: no envía temperatura ni configuración explícita de razonamiento. El nivel `medium` registrado es el predeterminado documentado del proveedor, sin implicar determinismo ni un valor medido internamente. El registro diferencia ese dato de la configuración enviada; véase [A2](A2_experimentos.md).

Este cambio de modelo/configuración **no modifica las métricas, los sinónimos, el umbral IoU ni los criterios de correspondencia y revisión humana definidos abajo**. Los resultados de 3.6 se registran bajo un run-id nuevo y se conservan separados de los anteriores; no se mezclan promedios o precisiones entre modelos. Los tiempos de razonamiento y servicio quedan incluidos en la duración observada, sin estimaciones adicionales. Una simulación identifica el modelo previsto en sus metadatos, pero no es una respuesta auténtica de ese modelo.

## Identificación y correspondencia

Se normalizan mayúsculas, espacios y acentos, y se usa un diccionario versionado y explícito de equivalencias inglesas (`metricas.SINONIMOS`). Ejemplos: couch/sofa, TV/television, fridge/refrigerator. No se presupone que table y coffee table, ni que cushion y pillow, sean siempre intercambiables. Las etiquetas desconocidas o diferencias de granularidad pasan a revisión. El nombre en español se evalúa por separado, para no confirmar una identificación sólo a partir de una traducción potencialmente incorrecta.

La asignación es uno a uno: cada predicción y cada instancia CVAT intervienen a lo sumo una vez. Tras aplicar decisiones humanas, el algoritmo maximiza primero la cantidad de correspondencias equivalentes y luego la suma de IoU mediante programación dinámica (máximo 5 predicciones). Para categorías repetidas exige superposición positiva; empates geométricos o detecciones indistinguibles que compiten por la misma referencia quedan pendientes. Una categoría con una sola referencia puede confirmar identificación aun con IoU=0: se evalúa por separado su mala ubicación. Estos son criterios operativos auditables; una revisión humana puede corregirlos.

Una detección sin correspondencia no es automáticamente falsa cuando CVAT no es exhaustivo. `exhaustiva=false` es el valor inicial por imagen. Sólo con exhaustividad confirmada, una categoría sin correspondencia puede contar como incorrecta. Los casos ambiguos permanecen pendientes incluso con exhaustividad confirmada. Se admiten decisiones humanas `correcta`, `incorrecta`, `pendiente`, con `referencia_id` opcional. Una presencia confirmada sin anotación CVAT aumenta identificación, pero no inventa una caja ni aporta IoU/cobertura. Las referencias manuales no pueden reutilizarse.

Sean C las detecciones confirmadas correctas, I las incorrectas, P las pendientes, D=C+I+P y R las referencias de fotografías con respuesta válida:

- **Precisión sobre casos resueltos:** C/(C+I). Si P=0 coincide con la precisión sobre todas las detecciones; si P>0 se considera provisional y siempre se muestra P.
- **Fracción confirmada sobre el total:** C/D. Se informa como complemento conservador; no implica que P sea incorrecta.
- **Cobertura de referencias:** M/R, donde M son pares con referencia CVAT. Es cobertura del inventario anotado, no recall de todos los objetos de la escena si CVAT es incompleto.

Gemini devuelve hasta 5 objetos por fotografía. Si CVAT tiene más, la cobertura puede ser inferior a 100% aun identificando correctamente las cinco detecciones. No se altera el denominador ni se oculta este límite. Las fotografías fallidas/no ejecutadas se cuentan aparte y no aportan referencias al denominador de cobertura de respuestas válidas. Una respuesta válida `SIN_OBJETOS_CLAROS` o `REPETIR_CAPTURA` sin detecciones sí aporta sus referencias al denominador, pues el análisis se completó y no recuperó objetos. Sin denominador, el valor es null, nunca un cero o acierto inventado.

## Ubicación

Para dos cajas A y B, **IoU = área(A ∩ B) / [área(A) + área(B) − área(A ∩ B)]**. Área = (ymax−ymin)(xmax−xmin). Se exige área positiva, cuatro valores finitos y límites 0–1000; se rechazan booleanos y coordenadas invertidas. No se corrigen recuadros humanos para mejorar resultados.

Se exportan IoU por par confirmado, promedio `ΣIoU/M`, M, cantidad de pares con IoU≥0,50, detecciones sin pareja y referencias sin pareja. No se calcula el promedio sobre detecciones no emparejadas; se explicita su número para evitar ocultarlas.

La métrica conjunta opcional `deteccion_localizacion_revisadas` es L/(C+I), con L = pares confirmados con IoU≥0,50. Una identificación humana correcta sin caja CVAT no suma a L. Es una proporción conjunta sobre casos resueltos, provisional si hay pendientes; **no es mAP ni una medida COCO estándar**. No se utiliza IoU≥0,50 como filtro para decidir identificación y después inflar su promedio.

## Traducciones y frases

El primer informe crea `revision_humana.csv`, una fila por objeto y respuesta. Revisar los nombres inglés/español conjuntamente en `traduccion`: correcta implica que la denominación inglesa y su traducción son aceptables para el objeto. Se permiten sinónimos, variantes regionales y nombres razonables; no es una comparación exacta de cadenas ni una evaluación hecha por Gemini. Criterios de frase: `gramatica_en`, `pertinencia_en`, `gramatica_es`, `pertinencia_es`, para revisar cada frase y su contexto en ambos idiomas.

En el CSV se usan `correcta` (Sí), `incorrecta` (No), `pendiente`. Para cada criterio k se calcula **correctas_k / (correctas_k + incorrectas_k)** y se informa el número pendiente. Cada criterio tiene su propio denominador: revisar gramática no presupone haber revisado pertinencia. Las preguntas y respuestas educativas se conservan en los JSON de A2; no se añade una métrica lingüística automática ni una calificación pedagógica de preguntas que no se haya solicitado.

Modificar sólo las columnas de decisión, `referencia_id` y observaciones; conservar `run_id`, `image_id`, `intento` e `id_local`. `referencias.csv` permite localizar los IDs humanos. Una identificación manual `pendiente` deja actuar el procedimiento automático; `correcta`/`incorrecta` lo reemplaza. Una referencia manual requiere `correcta`. Los informes posteriores conservan una copia del CSV aplicado para su auditoría y se generan en directorios nuevos. La plantilla original no se sobrescribe. Si se añaden respuestas después de crearla, las filas ausentes cuentan como pendientes; se pueden añadir siguiendo los IDs del detalle por objeto o crear otra plantilla con una ejecución completa nueva.

```powershell
python -m scripts.evaluacion.informe_metricas --run data/evaluacion/resultados/simulacion_piloto_gemini36_v1
# Editar revision_humana.csv y regenerar:
python -m scripts.evaluacion.informe_metricas --run data/evaluacion/resultados/simulacion_piloto_gemini36_v1
```

## Tiempos y agregación

Promedio = Σt/n, mediana = valor central (promedio de los dos centrales si n es par), mínimo y máximo. Se separan respuestas válidas y fallidas; los errores locales sin inicio de análisis tienen duración null y no simulan una llamada. Se muestran tanto últimos intentos por fotografía como todos los intentos conservados. Las duraciones incluyen orquestación M3, validación y reintentos; las duraciones individuales del transporte están en el registro. Los tiempos simulados sólo prueban el instrumento.

El resumen general suma numeradores y denominadores entre fotografías (microagregación), y obtiene IoU promedio de todos los pares, no de promedios por imagen sin ponderar. Los CSV permiten segmentar por procedencia real/sintética y por imagen. Se exportan `resumen.json/csv`, `por_fotografia.json/csv`, `por_objeto.csv`, `referencias.csv` y `revision_aplicada.csv`.

El generador comprueba que el código de métricas e informes coincida con los hashes registrados al ejecutar A2. Si cambia, restaurar esa versión para reproducir el informe original; no recalcular silenciosamente una evaluación final con otros criterios.

## Limitaciones

Muestra pequeña, posible sesgo de escenas sintéticas, inventario CVAT no exhaustivo, criterios de equivalencia discretos, subjetividad humana y variabilidad generativa. Los recuentos de respuestas válidas describen el contrato de software; no equivalen a detecciones correctas. Se deben resolver o declarar los pendientes antes de presentar una precisión definitiva. Las cinco fotografías piloto sirven para depurar el instrumento; las 30 finales quedan reservadas. La prueba real de Cocina y su revisión humana se resumen en [A4](A4_resultados.md): corresponden a una sola fotografía piloto, con pertinencia pendiente para una frase por idioma, y no permiten concluir el desempeño general del modelo. Sus métricas se calcularon con estos mismos criterios, sin alterarlos.
