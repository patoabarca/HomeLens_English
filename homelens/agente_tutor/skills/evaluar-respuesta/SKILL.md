---
name: evaluar-respuesta
description: >-
  Evalúa de forma estructurada la respuesta escrita por el alumno frente a la
  consigna, los objetos involucrados y el criterio interno de corrección,
  admitiendo variantes válidas en contexto e identificando dificultades o confusiones.
entrypoint: ejecutar.py
allowed_agents:
  - agente_tutor
---

# Skill: Evaluar Respuesta (`evaluar-respuesta`)

## 1. Propósito
Analizar la respuesta enviada por el alumno para la actividad vigente, devolviendo una **valoración estructurada** (`CORRECTA`, `PARCIAL` o `INCORRECTA`), una **devolución pedagógica breve** y, cuando corresponda, la **dificultad observada** y el identificador de otro objeto de la foto si el alumno los confundió (por ejemplo, si respondió `chair` cuando se le pedía `cup`).

## 2. Cuándo se invoca
- Cuando el alumno pulsa «Enviar respuesta» y `orquestar-practica` procesa el evento `ENVIAR_RESPUESTA`.

## 3. Entradas
### Obligatorias
- `consigna` (`str`): consigna presentada al alumno.
- `objetos_actividad` (`Sequence[ObjetoEducativo]`): objetos involucrados en la actividad (1 a 3).
- `objeto_objetivo` (`ObjetoEducativo`): objeto de la foto que el alumno debía nombrar o describir.
- `criterio_correccion` (`str`): criterio interno preparado por `preparar-actividad`.
- `respuesta_alumno` (`str`): texto ingresado por el estudiante.

### Opcionales
- `respuestas_aceptadas` (`Sequence[str] | None`): variantes válidas de referencia.
- `todos_objetos_foto` (`Sequence[ObjetoEducativo] | None`): totalidad de objetos detectados en la foto activa para detectar si la respuesta coincide con otro objeto presente en la escena.
- `adaptador` (`AdaptadorGemini | None`): cliente de Gemini con salida estructurada `EsquemaEvaluacionTutorIA`.
- `policy` (`dict | None`): política activa de `policy.json`.

## 4. Salida
Devuelve `Resultado[EvaluacionTutor]` con:
- `valoracion` (`Literal["CORRECTA", "PARCIAL", "INCORRECTA"]`).
- `devolucion` (`str`): comentario breve para el alumno.
- `dificultad_detectada` (`str | None`): etiqueta de dificultad (por ejemplo, `"confusion_entre_objetos_de_la_foto"`, `"aproximacion_ortografica"`, `"traduccion_en_espanol"`, `"vocabulario_no_reconocido"`, o `None` si es `CORRECTA`).
- `objeto_confundido_id` (`str | None`): identificador validado de otro objeto de la foto activa si el alumno lo nombró por confusión.

## 5. Reglas que le aplican (`policy.json`)
1. **Límite y saneamiento de entrada:** la respuesta del alumno no puede estar vacía ni superar `max_longitud_respuesta_chars` (`300`), y se trata como dato no confiable (`treat_student_input_as_untrusted=true`).
2. **Separación de responsabilidades:** `evaluar-respuesta` **no** genera pistas; si hace falta una pista, deja su elaboración a la skill independiente `dar-pista`.
3. **Validación de IDs:** si `objeto_confundido_id` viene informado, se comprueba con `validar_ids_pertenecen_a_foto` que pertenezca a la fotografía activa.

## 6. Ejemplo reproducible
```python
from uuid import uuid4
from homelens.modelos import ObjetoEducativo, RecuadroNormalizado
from homelens.agente_tutor.cargador import cargar_ejecutor_skill

obj_cup = ObjetoEducativo(uuid4(), uuid4(), "Cup", "Taza", RecuadroNormalizado(10, 10, 200, 200), "A cup.", "Una taza.")
obj_chair = ObjetoEducativo(uuid4(), uuid4(), "Chair", "Silla", RecuadroNormalizado(300, 300, 700, 700), "A chair.", "Una silla.")

mod = cargar_ejecutor_skill("evaluar-respuesta")
res_ok = mod.ejecutar_evaluar_respuesta("¿Cómo se dice «Taza»?", [obj_cup, obj_chair], obj_cup, "Aceptar cup", "a cup")
assert res_ok.ok and res_ok.valor.valoracion == "CORRECTA"

res_conf = mod.ejecutar_evaluar_respuesta("¿Cómo se dice «Taza»?", [obj_cup, obj_chair], obj_cup, "Aceptar cup", "chair", todos_objetos_foto=[obj_cup, obj_chair])
assert res_conf.ok and res_conf.valor.valoracion == "INCORRECTA"
assert res_conf.valor.objeto_confundido_id == str(obj_chair.objeto_id)
```
