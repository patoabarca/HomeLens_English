---
name: dar-pista
description: >-
  Genera una ayuda pedagógica breve y progresiva sin revelar la respuesta completa
  y devuelve opcionalmente el identificador del objeto de la fotografía activa
  para resaltarlo visualmente en HomeLens.
entrypoint: ejecutar.py
allowed_agents:
  - agente_tutor
---

# Skill: Dar Pista (`dar-pista`)

## 1. Propósito
Proporcionar una ayuda breve al estudiante para que pueda intentar (o volver a intentar) responder la actividad actual. Es una **skill independiente** que no cuenta como respuesta incorrecta ni consume un intento de evaluación.

## 2. Cuándo se invoca
- **Por pedido directo del alumno (`PEDIR_PISTA`):** incluso **antes de enviar su primera respuesta** (`origen="SOLICITUD_ALUMNO"`).
- **Por decisión pedagógica del tutor (`OFRECER_PISTA`):** después de que `evaluar-respuesta` detecta una respuesta parcial o incorrecta y `orquestar-practica` decide asistir al alumno (`origen="DECISION_TUTOR"`).

## 3. Entradas
### Obligatorias
- `consigna` (`str`): consigna activa de la actividad.
- `objeto_objetivo` (`ObjetoEducativo`): objeto de la fotografía sobre el que se consulta.
- `pistas_anteriores` (`Sequence[str]`): lista de textos de pistas ya otorgadas en la actividad actual, usada para no repetir la misma ayuda.

### Opcionales
- `respuesta_previa` (`str | None`): última respuesta ingresada por el alumno, si existe.
- `dificultad_detectada` (`str | None`): dificultad identificada por `evaluar-respuesta`, si existe.
- `objetos_foto` (`Sequence[ObjetoEducativo] | None`): objetos de la foto activa para validar el identificador resaltado.
- `origen` (`Literal["SOLICITUD_ALUMNO", "DECISION_TUTOR"]`): origen de la pista.
- `adaptador` (`AdaptadorGemini | None`): cliente de Gemini con salida estructurada `EsquemaPistaTutorIA`.

## 4. Salida
Devuelve `Resultado[PistaTutor]` donde `PistaTutor` incluye:
- `numero_pista` (`int`): índice secuencial de la pista en la actividad (`len(pistas_anteriores) + 1`).
- `texto_pista` (`str`): pista breve que orienta al alumno sin entregar la solución literal.
- `objeto_resaltado_id` (`str | None`): identificador validado del objeto en la foto activa para reutilizar el resaltado de recuadros de HomeLens.
- `origen` (`str`): `"SOLICITUD_ALUMNO"` o `"DECISION_TUTOR"`.

## 5. Reglas que le aplican (`policy.json`)
1. **Límites de pistas:** su invocación está sujeta a `max_pistas_por_actividad` y `max_pistas_totales` controlados por `orquestar-practica`.
2. **Progresividad:** si `pistas_anteriores` no está vacía, ofrece una pista diferente (por ejemplo, pasa de contextualizar la ubicación/frase a indicar la inicial y cantidad de letras).
3. **Validación del objeto resaltado:** `objeto_resaltado_id` se comprueba con `validar_ids_pertenecen_a_foto` antes de usarse en la interfaz.
4. **Sin penalización:** pedir una pista se registra como ayuda y mantiene intacto el contador de respuestas enviadas.

## 6. Ejemplo reproducible
```python
from uuid import uuid4
from homelens.modelos import ObjetoEducativo, RecuadroNormalizado
from homelens.agente_tutor.cargador import cargar_ejecutor_skill

obj = ObjetoEducativo(
    objeto_id=uuid4(),
    exploracion_id=uuid4(),
    nombre_en="Lamp",
    nombre_es="Lámpara",
    recuadro=RecuadroNormalizado(50, 50, 300, 300),
    frase_en="The lamp gives warm light.",
    frase_es="La lámpara da luz cálida.",
)

mod = cargar_ejecutor_skill("dar-pista")
p1 = mod.ejecutar_dar_pista("¿Cómo se dice «Lámpara» en inglés?", obj, pistas_anteriores=[])
p2 = mod.ejecutar_dar_pista("¿Cómo se dice «Lámpara» en inglés?", obj, pistas_anteriores=[p1.valor.texto_pista])
assert p1.ok and p2.ok
assert p1.valor.texto_pista != p2.valor.texto_pista
assert p1.valor.objeto_resaltado_id == str(obj.objeto_id)
```
