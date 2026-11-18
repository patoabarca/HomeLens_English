-- =====================================================================
-- HomeLens English — Suite de Verificación de Políticas RLS y Seguridad en PostgreSQL
-- =====================================================================
-- PROPÓSITO:
-- Ejecutar una batería de pruebas controladas simulando diferentes identidades
-- y roles (anónimo, usuario regular y creador) para validar:
--   1. Creador leyendo consumos propios y globales del equipo.
--   2. Creador insertando su propio consumo legítimo (operación exitosa completa).
--   2b. Creador insertando operación fallida (HTTP 429, estado ERROR, tokens y costo NULL).
--   2c. Creador insertando operación con tokens de caché (cached_tokens preservado).
--   3. Rechazo de inserción atribuida a otro usuario (suplantación de identidad).
--   4. Rechazo de lectura e inserción por usuarios no autorizados (estudiantes regulares).
--   5. Ausencia total de acceso anónimo (lectura e inserción bloqueadas).
--   6. Rechazo de UPDATE y DELETE (inmutabilidad técnica garantizada).
--   7. Ausencia de recursión infinita RLS (error 42P17 prevenido).
--   8. Inserción duplicada legítima (prueba positiva: WITH CHECK aprobado, ON CONFLICT DO NOTHING descarta sin error).
--   9. Inserción duplicada no autorizada (prueba negativa: WITH CHECK evaluado ANTES del conflicto, bloqueado por RLS).
--
-- INSTRUCCIONES DE USO EN SUPABASE SQL EDITOR:
-- 1. Reemplazar los marcadores '<UUID_VERIFICADO_DE_PATRICIA>' y '<UUID_VERIFICADO_DE_LUCAS>'
--    por los UUIDs reales verificados de Patricia y Lucas (disponibles en tu archivo local .env).
-- 2. Este script NO modifica la tabla administrada 'auth.users' (utiliza las identidades reales existentes de Patricia y Lucas).
-- 3. Para el usuario no autorizado se utiliza un UUID dinámico simulado sin crear cuentas artificiales en Auth.
-- 4. El script se ejecuta dentro de un bloque transaccional con ROLLBACK final, garantizando
--    que la base de datos quede exactamente en su estado original sin dejar registros de prueba.
-- =====================================================================

BEGIN;

DO $$
DECLARE
    -- Identidades existentes de los creadores (reemplazar marcadores al ejecutar en Supabase)
    uid_patricia UUID := '<UUID_VERIFICADO_DE_PATRICIA>';
    uid_lucas    UUID := '<UUID_VERIFICADO_DE_LUCAS>';

    -- Identidad simulada para usuario no autorizado (no pertenece a creadores_autorizados)
    uid_ajeno    UUID := gen_random_uuid();

    op_id_1      UUID := gen_random_uuid();
    filas_leidas INT;
    error_atrapado BOOLEAN;
BEGIN
    RAISE NOTICE '>>> INICIANDO VERIFICACIÓN CONTROLADA DE RLS (PostgreSQL) <<<';

    -- -----------------------------------------------------------------
    -- A. Registro temporal de creadores autorizados para la prueba
    -- -----------------------------------------------------------------
    -- Garantiza que las identidades estén en creadores_autorizados durante la prueba.
    -- Al finalizar el bloque con ROLLBACK, cualquier cambio temporal queda anulado.
    INSERT INTO public.creadores_autorizados (user_id, nombre_etiqueta) VALUES
        (uid_patricia, 'Patricia'),
        (uid_lucas,    'Lucas')
    ON CONFLICT (user_id) DO NOTHING;

    -- -----------------------------------------------------------------
    -- Test 1: Ausencia de recursión RLS (42P17) al consultar creadores_autorizados
    -- -----------------------------------------------------------------
    PERFORM set_config('role', 'authenticated', true);
    PERFORM set_config('request.jwt.claim.sub', uid_patricia::text, true);

    SELECT count(*) INTO filas_leidas FROM public.creadores_autorizados;
    IF filas_leidas != 1 THEN
        RAISE EXCEPTION 'Fallo Test 1: Patricia debería ver exclusivamente su propio registro de creador (obtenido: %)', filas_leidas;
    END IF;
    RAISE NOTICE '✓ Test 1 APROBADO: Consulta a creadores_autorizados sin recursión RLS (42P17 evitado).';

    -- -----------------------------------------------------------------
    -- Test 2: Creador inserta su propio consumo legítimo (Operación exitosa completa)
    -- -----------------------------------------------------------------
    INSERT INTO public.consumo_gemini (
        id, operacion_id, user_id, modelo, estado, duracion_ms,
        numero_llamadas, numero_reintentos, prompt_tokens, candidates_tokens, costo_estimado
    ) VALUES (
        gen_random_uuid(), op_id_1, uid_patricia, 'gemini-3.6-flash', 'EXITO', 1200,
        1, 0, 1000, 300, 0.001875
    );
    RAISE NOTICE '✓ Test 2 APROBADO: Creadora (Patricia) insertó su propio consumo exitosamente.';

    -- -----------------------------------------------------------------
    -- Test 2b: Creador inserta operación fallida (HTTP 429, tokens y costo NULL)
    -- Valida que las restricciones SQL admitan NULL en tokens y costo ante fallos de API.
    -- -----------------------------------------------------------------
    INSERT INTO public.consumo_gemini (
        id, operacion_id, user_id, modelo, estado, duracion_ms,
        numero_llamadas, numero_reintentos, codigo_error,
        prompt_tokens, candidates_tokens, thoughts_tokens, total_tokens, cached_tokens,
        tarifa_version, costo_estimado, metadatos
    ) VALUES (
        gen_random_uuid(), gen_random_uuid(), uid_patricia, 'gemini-3.6-flash', 'ERROR', 450,
        1, 0, 429,
        NULL, NULL, NULL, NULL, NULL,
        'gemini-3.6-flash-2026-v2', NULL, '{"error": "RESOURCE_EXHAUSTED", "http_code": 429}'::jsonb
    );
    RAISE NOTICE '✓ Test 2b APROBADO: Operación fallida registrada con estado ERROR, código HTTP 429 y costos/tokens NULL.';

    -- -----------------------------------------------------------------
    -- Test 2c: Creador inserta operación con tokens de caché (cached_tokens preservado)
    -- Valida que cached_tokens se admita y preserve sin generar conflicto con las restricciones.
    -- -----------------------------------------------------------------
    INSERT INTO public.consumo_gemini (
        id, operacion_id, user_id, modelo, estado, duracion_ms,
        numero_llamadas, numero_reintentos,
        prompt_tokens, candidates_tokens, thoughts_tokens, total_tokens, cached_tokens,
        tarifa_version, costo_estimado, metadatos
    ) VALUES (
        gen_random_uuid(), gen_random_uuid(), uid_patricia, 'gemini-3.6-flash', 'EXITO', 1350,
        1, 0,
        1200, 250, 50, 1500, 400,
        'gemini-3.6-flash-2026-v2', 0.001755, '{"componente_cache": "lectura"}'::jsonb
    );
    RAISE NOTICE '✓ Test 2c APROBADO: Operación con tokens de caché (cached_tokens) registrada y validada.';

    -- -----------------------------------------------------------------
    -- Test 3: Rechazo de inserción atribuida a otro usuario (suplantación)
    -- -----------------------------------------------------------------
    error_atrapado := false;
    BEGIN
        -- Patricia conectada intenta insertar un registro con user_id de Lucas
        INSERT INTO public.consumo_gemini (
            id, operacion_id, user_id, modelo, estado, duracion_ms,
            numero_llamadas, numero_reintentos, prompt_tokens, candidates_tokens, costo_estimado
        ) VALUES (
            gen_random_uuid(), gen_random_uuid(), uid_lucas, 'gemini-3.6-flash', 'EXITO', 1000,
            1, 0, 800, 200, 0.001350
        );
    EXCEPTION WHEN check_violation OR insufficient_privilege THEN
        error_atrapado := true;
    END;

    IF NOT error_atrapado THEN
        RAISE EXCEPTION 'Fallo Test 3: RLS debió rechazar la inserción con user_id no coincidente con auth.uid()';
    END IF;
    RAISE NOTICE '✓ Test 3 APROBADO: Inserción con user_id ajeno rechazada por política RLS.';

    -- -----------------------------------------------------------------
    -- Test 4: Creador leyendo consumos propios y globales del equipo
    -- -----------------------------------------------------------------
    -- Lucas se conecta y debe poder consultar el registro insertado por Patricia
    PERFORM set_config('request.jwt.claim.sub', uid_lucas::text, true);

    SELECT count(*) INTO filas_leidas FROM public.consumo_gemini;
    IF filas_leidas < 1 THEN
        RAISE EXCEPTION 'Fallo Test 4: Creador Lucas no pudo leer el consumo global del equipo';
    END IF;
    RAISE NOTICE '✓ Test 4 APROBADO: Creadores autorizados tienen visibilidad del consumo del equipo.';

    -- -----------------------------------------------------------------
    -- Test 5: Rechazo de lectura e inserción por usuario no autorizado (estudiante regular)
    -- -----------------------------------------------------------------
    PERFORM set_config('request.jwt.claim.sub', uid_ajeno::text, true);

    -- Intento de lectura por usuario no creador (debe devolver 0 filas bajo RLS)
    SELECT count(*) INTO filas_leidas FROM public.consumo_gemini;
    IF filas_leidas != 0 THEN
        RAISE EXCEPTION 'Fallo Test 5a: Usuario regular pudo leer registros de consumo (obtenido: %)', filas_leidas;
    END IF;

    -- Intento de inserción por usuario no creador (debe ser bloqueado por RLS WITH CHECK)
    error_atrapado := false;
    BEGIN
        INSERT INTO public.consumo_gemini (
            id, operacion_id, user_id, modelo, estado, duracion_ms,
            numero_llamadas, numero_reintentos, prompt_tokens, candidates_tokens, costo_estimado
        ) VALUES (
            gen_random_uuid(), gen_random_uuid(), uid_ajeno, 'gemini-3.6-flash', 'EXITO', 1000,
            1, 0, 500, 200, 0.001000
        );
    EXCEPTION WHEN check_violation OR insufficient_privilege THEN
        error_atrapado := true;
    END;

    IF NOT error_atrapado THEN
        RAISE EXCEPTION 'Fallo Test 5b: Usuario regular pudo insertar registro de consumo';
    END IF;
    RAISE NOTICE '✓ Test 5 APROBADO: Usuario no autorizado bloqueado tanto en lectura como en inserción.';

    -- -----------------------------------------------------------------
    -- Test 6: Ausencia total de acceso anónimo
    -- -----------------------------------------------------------------
    PERFORM set_config('role', 'anon', true);

    error_atrapado := false;
    BEGIN
        SELECT count(*) INTO filas_leidas FROM public.consumo_gemini;
    EXCEPTION WHEN insufficient_privilege THEN
        error_atrapado := true;
    END;

    IF NOT error_atrapado THEN
        RAISE EXCEPTION 'Fallo Test 6a: Rol anónimo pudo consultar tabla consumo_gemini';
    END IF;

    error_atrapado := false;
    BEGIN
        INSERT INTO public.consumo_gemini (
            id, operacion_id, user_id, modelo, estado, duracion_ms,
            numero_llamadas, numero_reintentos, prompt_tokens, candidates_tokens, costo_estimado
        ) VALUES (
            gen_random_uuid(), gen_random_uuid(), uid_ajeno, 'gemini-3.6-flash', 'EXITO', 1000,
            1, 0, 500, 200, 0.001000
        );
    EXCEPTION WHEN insufficient_privilege THEN
        error_atrapado := true;
    END;

    IF NOT error_atrapado THEN
        RAISE EXCEPTION 'Fallo Test 6b: Rol anónimo pudo insertar en consumo_gemini';
    END IF;
    RAISE NOTICE '✓ Test 6 APROBADO: Rol anónimo bloqueado en lectura e inserción por permisos SQL mínimos.';

    -- -----------------------------------------------------------------
    -- Test 7: Rechazo estricto de UPDATE y DELETE (inmutabilidad técnica)
    -- -----------------------------------------------------------------
    PERFORM set_config('role', 'authenticated', true);
    PERFORM set_config('request.jwt.claim.sub', uid_patricia::text, true);

    error_atrapado := false;
    BEGIN
        UPDATE public.consumo_gemini SET estado = 'ERROR' WHERE operacion_id = op_id_1;
    EXCEPTION WHEN insufficient_privilege THEN
        error_atrapado := true;
    END;
    IF NOT error_atrapado THEN
        RAISE EXCEPTION 'Fallo Test 7a: Usuario autenticado pudo ejecutar UPDATE en tabla inmutable';
    END IF;

    error_atrapado := false;
    BEGIN
        DELETE FROM public.consumo_gemini WHERE operacion_id = op_id_1;
    EXCEPTION WHEN insufficient_privilege THEN
        error_atrapado := true;
    END;
    IF NOT error_atrapado THEN
        RAISE EXCEPTION 'Fallo Test 7b: Usuario autenticado pudo ejecutar DELETE en tabla inmutable';
    END IF;
    RAISE NOTICE '✓ Test 7 APROBADO: UPDATE y DELETE bloqueados por privilegios mínimos.';

    -- -----------------------------------------------------------------
    -- Test 8: Inserción duplicada legítima con ON CONFLICT DO NOTHING (Prueba Positiva)
    -- -----------------------------------------------------------------
    -- Patricia conectada reintenta insertar el mismo operacion_id con su propio user_id:
    -- La política WITH CHECK se evalúa positivamente (es Patricia y es creadora),
    -- se detecta el conflicto en operacion_id y DO NOTHING descarta la inserción sin error ni duplicación.
    INSERT INTO public.consumo_gemini (
        id, operacion_id, user_id, modelo, estado, duracion_ms,
        numero_llamadas, numero_reintentos, prompt_tokens, candidates_tokens, costo_estimado
    ) VALUES (
        gen_random_uuid(), op_id_1, uid_patricia, 'gemini-3.6-flash', 'EXITO', 1200,
        1, 0, 1000, 300, 0.001875
    )
    ON CONFLICT (operacion_id) DO NOTHING;

    SELECT count(*) INTO filas_leidas FROM public.consumo_gemini WHERE operacion_id = op_id_1;
    IF filas_leidas != 1 THEN
        RAISE EXCEPTION 'Fallo Test 8: La inserción duplicada legítima debió ser ignorada sin alterar el registro original';
    END IF;
    RAISE NOTICE '✓ Test 8 APROBADO: Inserción duplicada legítima manejada con idempotencia (ON CONFLICT DO NOTHING sin requerir UPDATE).';

    -- -----------------------------------------------------------------
    -- Test 9: Inserción duplicada no autorizada con ON CONFLICT DO NOTHING (Prueba Negativa)
    -- -----------------------------------------------------------------
    -- Un usuario no autorizado (o un intento de suplantación) intenta insertar con el mismo operacion_id_1
    -- usando ON CONFLICT DO NOTHING.
    -- Regla PostgreSQL comprobada: La política INSERT WITH CHECK se evalúa ANTES de la detección de conflicto.
    -- Al no cumplir la política RLS, la sentencia es bloqueada de inmediato, impidiendo eludir la seguridad.
    PERFORM set_config('request.jwt.claim.sub', uid_ajeno::text, true);

    error_atrapado := false;
    BEGIN
        INSERT INTO public.consumo_gemini (
            id, operacion_id, user_id, modelo, estado, duracion_ms,
            numero_llamadas, numero_reintentos, prompt_tokens, candidates_tokens, costo_estimado
        ) VALUES (
            gen_random_uuid(), op_id_1, uid_ajeno, 'gemini-3.6-flash', 'EXITO', 1200,
            1, 0, 1000, 300, 0.001875
        )
        ON CONFLICT (operacion_id) DO NOTHING;
    EXCEPTION WHEN check_violation OR insufficient_privilege THEN
        error_atrapado := true;
    END;

    IF NOT error_atrapado THEN
        RAISE EXCEPTION 'Fallo Test 9: RLS debió evaluar WITH CHECK antes del conflicto y bloquear la inserción no autorizada';
    END IF;
    RAISE NOTICE '✓ Test 9 APROBADO: Inserción duplicada no autorizada bloqueada por RLS WITH CHECK antes de evaluar el conflicto.';

    RAISE NOTICE '>>> TODAS LAS PRUEBAS DE SEGURIDAD RLS FUERON SUPERADAS EXITOSAMENTE <<<';
END
$$;

-- Deshacer todos los cambios de prueba para garantizar base de datos 100% limpia
ROLLBACK;
