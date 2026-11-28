---
name: preparar-actividad
description: >-
  Prepara una práctica breve o un refuerzo focalizado de vocabulario en inglés
  utilizando entre uno y tres objetos detectados en la fotografía activa,
  separando la consigna visible para el alumno del criterio interno de corrección.
entrypoint: ejecutar.py
allowed_agents:
  - agente_tutor
---

# Skill: Preparar Actividad (`preparar-actividad`)

## 1. Propósito
Construir una actividad breve de práctica de vocabulario (o un ejercicio de refuerzo contrastivo) sobre entre **1 y 3 objetos detectados en la fotografía activa** de HomeLens English. Funciona incluso cuando la exploración cuenta con un único objeto identificado.

## 2. Cuándo se invoca
- Al iniciar la práctica opcional con el tutor (`INICIAR_PRACTICA`).
- Al avanzar a la siguiente actividad de la sesión (`AVANZAR_ACTIVIDAD` / acción pedagógica `AVANZAR`).
- Cuando `orquestar-practica` decide la acción pedagógica `PREPARAR_REFUERZO` tras detectar una confusión o dificultad del alumno (por ejemplo, si confundió `cup` con `chair` y ambos objetos están en la fotografía activa).

## 3. Entradas
### Obligatorias
- `objetos_foto` (`Sequence[ObjetoEducativo]`): lista de objetos detectados en la fotografía activa (con `objeto_id`, `nombre_en`, `nombre_es`, `recuadro`, `frase_en` y `frase_es`).

### Opcionales
- `objetos_ya_practicados_ids` (`Sequence[str] | None`): identificadores de objetos ya cubiertos en turnos previos para priorizar vocabulario pendiente.
- `modo_refuerzo` (`bool`, por defecto `False`): indica si debe construir una consigna de refuerzo para resolver una confusión reciente.
- `dificultad_previa` (`str | None`): descripción de la dificultad observada en la evaluación anterior.
- `objeto_objetivo_forzado_id` (`str | None`): identificador del objeto de la foto que se desea reforzar.
- `objeto_confundido_id` (`str | None`): identificador del segundo objeto de la foto con el que el alumno se confundió, para contrastarlos en la nueva consigna.
- `adaptador` (`AdaptadorGemini | None`): cliente de Gemini con salida estructurada `EsquemaActividadTutorIA`.
- `policy` (`dict | None`): política activa de `policy.json`.

## 4. Salida
Devuelve `Resultado[ActividadTutor]` donde `ActividadTutor` contiene:
- `actividad_tutor_id` (`str`): identificador único de la actividad.
- `consigna` (`str`): instrucción breve para el alumno (sin revelar la solución en inglés).
- `objeto_ids` (`list[str]`): entre 1 y 3 identificadores de objetos pertenecientes a la foto activa.
- `objeto_objetivo_id` (`str`): identificador del objeto cuya denominación o uso se evalúa.
- `criterio_correccion` (`str`): pauta interna de corrección para `evaluar-respuesta` (**oculta en `vista_alumno()`**).
- `respuestas_aceptadas` (`list[str]`): variantes válidas en inglés (**ocultas en `vista_alumno()`**).
- `es_refuerzo` (`bool`): `True` si la actividad fue generada como refuerzo focalizado.

## 5. Reglas que le aplican (`policy.json`)
1. **Cantidad de objetos:** entre `min_objetos_actividad` (`1`) y `max_objetos_actividad` (`3`). Si la foto tiene un solo objeto, opera con ese único objeto.
2. **Pertenencia estricta a la foto activa:** todo ID en `objeto_ids` y `objeto_objetivo_id` se valida con `validar_ids_pertenecen_a_foto`. Si Gemini devuelve un ID ajeno a la foto activa, la operación se bloquea con `CODIGO_ACCESO_DENEGADO`.
3. **Separación de vista del alumno:** `ActividadTutor.vista_alumno()` expone únicamente `consigna`, `objeto_ids` y `es_refuerzo`, ocultando `criterio_correccion` y `respuestas_aceptadas`.

## 6. Ejemplo reproducible
```python
from uuid import uuid4
from homelens.modelos import ObjetoEducativo, RecuadroNormalizado
from homelens.agente_tutor.cargador import cargar_ejecutor_skill

obj_cup = ObjetoEducativo(
    objeto_id=uuid4(),
    exploracion_id=uuid4(),
    nombre_en="Coffee Mug",
    nombre_es="Taza de café",
    recuadro=RecuadroNormalizado(100, 100, 400, 400),
    frase_en="The coffee mug is on the table.",
    frase_es="La taza de café está sobre la mesa.",
)

mod = cargar_ejecutor_skill("preparar-actividad")
res = mod.ejecutar_preparar_actividad(objetos_foto=[obj_cup])
assert res.ok and res.valor is not None
assert res.valor.objeto_ids == [str(obj_cup.objeto_id)]
assert "criterio_correccion" not in res.valor.vista_alumno()
```
