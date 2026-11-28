---
name: orquestar-practica
description: >-
  Punto de entrada del Agente Tutor. Aplica la política compartida policy.json,
  coordina preparar-actividad, evaluar-respuesta y dar-pista, decide la siguiente
  acción pedagógica tras cada evaluación y registra eventos observables en sesión.
entrypoint: ejecutar.py
allowed_agents:
  - agente_tutor
---

# Skill: Orquestar Práctica (`orquestar-practica`)

## 1. Propósito
Actuar como **punto de entrada único del Agente Tutor** y primera de sus cuatro skills ejecutables. Recibe el evento de la interfaz y el `EstadoPracticaTutor`, consulta `policy.json`, despacha de forma directa las acciones explícitas del alumno (`PEDIR_PISTA` → `dar-pista`, `ENVIAR_RESPUESTA` → `evaluar-respuesta`), decide la acción pedagógica posterior a cada evaluación (`AVANZAR`, `PERMITIR_OTRO_INTENTO`, `OFRECER_PISTA`, `PREPARAR_REFUERZO` o `CERRAR`), valida todo identificador contra la foto activa y registra la traza observable para la defensa.

## 2. Cuándo se invoca
- Cuando el usuario toca **«Practicar con el tutor»** desde la exploración de una fotografía (`evento="INICIAR_PRACTICA"`).
- Cuando el alumno toca **«Dame una pista»** (`evento="PEDIR_PISTA"`).
- Cuando el alumno toca **«Enviar respuesta»** (`evento="ENVIAR_RESPUESTA"`).
- Cuando el alumno avanza a otra actividad (`evento="AVANZAR_ACTIVIDAD"`) o cierra el tutor para volver a la foto (`evento="CERRAR_PRACTICA"`).

## 3. Entradas
### Obligatorias
- `evento` (`Literal["INICIAR_PRACTICA", "PEDIR_PISTA", "ENVIAR_RESPUESTA", "AVANZAR_ACTIVIDAD", "CERRAR_PRACTICA"]`).
- `estado_practica` (`EstadoPracticaTutor`): estado vigente en la sesión.
- `exploracion` (`Exploracion`): exploración activa cuyos `objetos` definen el universo válido de la fotografía.

### Opcionales
- `respuesta_alumno` (`str | None`): texto enviado por el estudiante en `ENVIAR_RESPUESTA`.
- `evento_id` (`str | None`): identificador de idempotencia del clic de UI para que un redibujado de Streamlit nunca duplique llamadas a Gemini ni consuma turnos.
- `adaptador` (`AdaptadorGemini | None`): cliente de Gemini reutilizado para interpretación y skills.
- `policy_override` (`dict | None`): política personalizada para pruebas de límites y bloqueos.

## 4. Salida
Devuelve `Resultado[EstadoPracticaTutor]` con el estado actualizado, la actividad vigente (`actividad_actual`), los contadores (`turnos_consumidos`, `pistas_totales`, `refuerzos_realizados`), el objeto resaltado (`objeto_resaltado_id`) y la lista `traza_observable` de `RegistroEventoTutor`.

## 5. Reglas que le aplican (`policy.json`)
1. **Dos tipos de decisión diferenciados:**
   - *Acción explícita del usuario (recorrido directo):* `PEDIR_PISTA` invoca directamente `dar-pista` (sin contar como respuesta ni incrementar `turnos_consumidos`); `ENVIAR_RESPUESTA` invoca directamente `evaluar-respuesta`.
   - *Decisión pedagógica posterior a `evaluar-respuesta`:* usa la valoración, la dificultad detectada y el historial (consultando a Gemini con `EsquemaDecisionOrquestadorIA` cuando requiere interpretación) para elegir entre `AVANZAR`, `PERMITIR_OTRO_INTENTO`, `OFRECER_PISTA`, `PREPARAR_REFUERZO` o `CERRAR`, validando que la acción esté autorizada en `allowed_pedagogical_actions_by_state["EVALUADA"]` y dentro de los límites de `policy.json` antes de ejecutarla.
2. **Validación de pertenencia a la foto activa:** todo `objeto_id` devuelto por cualquier skill se valida contra `exploracion.objetos` antes de actualizar la sesión.
3. **Protección ante redibujados (idempotencia):** si `evento_id` coincide con `ultimo_evento_id_procesado`, retorna el estado existente sin ejecutar skills ni consumir turnos.

## 6. Ejemplo reproducible
```python
from datetime import datetime, timezone
from uuid import uuid4
from homelens.modelos import Exploracion, EstadoAnalisis, ObjetoEducativo, RecuadroNormalizado
from homelens.agente_tutor.contratos import EstadoPracticaTutor
from homelens.agente_tutor.cargador import cargar_ejecutor_skill

exp_id = uuid4()
obj = ObjetoEducativo(uuid4(), exp_id, "Book", "Libro", RecuadroNormalizado(50, 50, 400, 400), "A book.", "Un libro.")
exp = Exploracion(exp_id, uuid4(), datetime.now(timezone.utc), EstadoAnalisis.UTILIZABLE, [obj])
estado = EstadoPracticaTutor(exploracion_id=str(exp_id))

orq = cargar_ejecutor_skill("orquestar-practica")
r1 = orq.ejecutar_orquestar_practica("INICIAR_PRACTICA", estado, exp, evento_id="ev-1")
r2 = orq.ejecutar_orquestar_practica("PEDIR_PISTA", r1.valor, exp, evento_id="ev-2")
assert r2.ok and r2.valor.turnos_consumidos == 0 and r2.valor.pistas_totales == 1
```
