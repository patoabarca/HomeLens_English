-- =====================================================================
-- HomeLens English — Migración: Panel de Consumo de Inteligencia Artificial (Gemini)
-- =====================================================================
-- NOTA IMPORTANTE:
-- Este script NO debe ejecutarse automáticamente sin autorización previa.
-- Debe aplicarse de forma controlada en el SQL Editor del panel de Supabase
-- una vez aprobado por el equipo creador (Patricia, Lucas, Victoria).
--
-- Objetivos de la migración:
-- 1. Crear tabla de autorización explícita para el equipo creador (public.creadores_autorizados).
-- 2. Crear tabla técnica inmutable para métricas de consumo de Gemini (public.consumo_gemini).
-- 3. Habilitar Row Level Security (RLS) estricto y no recursivo (previene error 42P17).
-- 4. Garantizar inserciones idempotentes sobre operacion_id manteniendo UPDATE y DELETE bloqueados.
-- 5. Restringir la lectura global del panel exclusivamente a los creadores autorizados.
-- 6. Impedir que un cliente autenticado inserte registros atribuidos a otro user_id.
-- 7. Validar integridad de datos (costos no negativos, consistencia de reintentos y metadatos limpios).
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 1. Tabla de Creadores Autorizados (Control de acceso explícito para el MVP)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.creadores_autorizados (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    nombre_etiqueta TEXT NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_creador_nombre_valido CHECK (char_length(trim(nombre_etiqueta)) > 0)
);

-- Habilitar RLS en creadores_autorizados
ALTER TABLE public.creadores_autorizados ENABLE ROW LEVEL SECURITY;

-- Privilegios SQL mínimos: solo SELECT a authenticated (sin UPDATE, INSERT ni DELETE para clientes)
REVOKE ALL ON TABLE public.creadores_autorizados FROM PUBLIC;
REVOKE ALL ON TABLE public.creadores_autorizados FROM anon;
REVOKE ALL ON TABLE public.creadores_autorizados FROM authenticated;
GRANT SELECT ON TABLE public.creadores_autorizados TO authenticated;

-- Cada usuario autenticado solo puede leer su propio registro si existe (sin subconsultas recursivas).
-- Esto evita estrictamente el error PostgreSQL 42P17 (infinite recursion detected in policy).
DROP POLICY IF EXISTS "Lectura de creadores para usuarios autenticados" ON public.creadores_autorizados;
DROP POLICY IF EXISTS "Solo creadores leen tabla de creadores autorizados" ON public.creadores_autorizados;
DROP POLICY IF EXISTS "Usuarios consultan su propio registro de creador" ON public.creadores_autorizados;
CREATE POLICY "Usuarios consultan su propio registro de creador"
    ON public.creadores_autorizados FOR SELECT
    TO authenticated
    USING (user_id = (SELECT auth.uid()));

-- ---------------------------------------------------------------------
-- 2. Tabla Principal de Métricas de Consumo (public.consumo_gemini)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.consumo_gemini (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operacion_id UUID NOT NULL UNIQUE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    fecha TIMESTAMPTZ NOT NULL DEFAULT now(),
    modelo TEXT NOT NULL,
    estado TEXT NOT NULL,
    duracion_ms INT NOT NULL DEFAULT 0,
    numero_llamadas INT NOT NULL DEFAULT 1,
    numero_reintentos INT NOT NULL DEFAULT 0,
    codigo_error INT,
    prompt_tokens INT,
    candidates_tokens INT,
    thoughts_tokens INT,
    total_tokens INT,
    cached_tokens INT,
    tarifa_version TEXT,
    costo_estimado NUMERIC(10, 6),
    metadatos JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_consumo_gemini_estado
        CHECK (estado IN ('EXITO', 'ERROR', 'BLOQUEADO')),
    CONSTRAINT chk_consumo_costo_no_negativo
        CHECK (costo_estimado IS NULL OR costo_estimado >= 0),
    CONSTRAINT chk_consumo_tokens_no_negativos
        CHECK (
            (prompt_tokens IS NULL OR prompt_tokens >= 0) AND
            (candidates_tokens IS NULL OR candidates_tokens >= 0) AND
            (thoughts_tokens IS NULL OR thoughts_tokens >= 0) AND
            (total_tokens IS NULL OR total_tokens >= 0) AND
            (cached_tokens IS NULL OR cached_tokens >= 0)
        ),
    CONSTRAINT chk_consumo_duracion_no_negativa
        CHECK (duracion_ms >= 0),
    CONSTRAINT chk_consumo_llamadas_pos
        CHECK (numero_llamadas >= 1),
    CONSTRAINT chk_consumo_reintentos_no_negativo
        CHECK (numero_reintentos >= 0),
    CONSTRAINT chk_consumo_consistencia_llamadas_reintentos
        CHECK (numero_llamadas >= (numero_reintentos + 1)),
    CONSTRAINT chk_consumo_metadatos_sin_secretos
        CHECK (
            NOT (metadatos ?| ARRAY['api_key', 'token', 'authorization', 'bearer', 'password', 'secret', 'imagen', 'base64'])
        )
);

-- Asegurar restricciones de integridad si la tabla ya existía de ejecuciones previas
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_consumo_costo_no_negativo'
          AND conrelid = 'public.consumo_gemini'::regclass
    ) THEN
        ALTER TABLE public.consumo_gemini
            ADD CONSTRAINT chk_consumo_costo_no_negativo
            CHECK (costo_estimado IS NULL OR costo_estimado >= 0);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_consumo_consistencia_llamadas_reintentos'
          AND conrelid = 'public.consumo_gemini'::regclass
    ) THEN
        ALTER TABLE public.consumo_gemini
            ADD CONSTRAINT chk_consumo_consistencia_llamadas_reintentos
            CHECK (numero_llamadas >= (numero_reintentos + 1));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_consumo_metadatos_sin_secretos'
          AND conrelid = 'public.consumo_gemini'::regclass
    ) THEN
        ALTER TABLE public.consumo_gemini
            ADD CONSTRAINT chk_consumo_metadatos_sin_secretos
            CHECK (NOT (metadatos ?| ARRAY['api_key', 'token', 'authorization', 'bearer', 'password', 'secret', 'imagen', 'base64']));
    END IF;
END
$$;

-- ---------------------------------------------------------------------
-- 3. Índices para optimizar filtros y orden cronológico
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_consumo_gemini_fecha
    ON public.consumo_gemini (fecha DESC);

CREATE INDEX IF NOT EXISTS idx_consumo_gemini_user_fecha
    ON public.consumo_gemini (user_id, fecha DESC);

CREATE INDEX IF NOT EXISTS idx_consumo_gemini_modelo
    ON public.consumo_gemini (modelo, fecha DESC);

-- ---------------------------------------------------------------------
-- 4. Privilegios SQL mínimos (Defensa en profundidad)
-- ---------------------------------------------------------------------
-- Los registros de consumo son estrictamente inmutables:
-- Solo se concede SELECT e INSERT. UPDATE y DELETE permanecen bloqueados.
REVOKE ALL ON TABLE public.consumo_gemini FROM PUBLIC;
REVOKE ALL ON TABLE public.consumo_gemini FROM anon;
REVOKE ALL ON TABLE public.consumo_gemini FROM authenticated;
GRANT SELECT, INSERT ON TABLE public.consumo_gemini TO authenticated;

-- ---------------------------------------------------------------------
-- 5. Row Level Security (RLS)
-- ---------------------------------------------------------------------
ALTER TABLE public.consumo_gemini ENABLE ROW LEVEL SECURITY;

-- Política de Inserción: Restringida exclusivamente a los creadores autorizados
-- para evitar que usuarios regulares inserten registros de consumo a su nombre.
-- Requiere coincidencia exacta con auth.uid() para evitar atribuciones indebidas.
DROP POLICY IF EXISTS "Usuarios insertan solo su propio consumo" ON public.consumo_gemini;
DROP POLICY IF EXISTS "Solo creadores autorizados insertan su propio consumo" ON public.consumo_gemini;
CREATE POLICY "Solo creadores autorizados insertan su propio consumo"
    ON public.consumo_gemini FOR INSERT
    TO authenticated
    WITH CHECK (
        (SELECT auth.uid()) = user_id
        AND EXISTS (
            SELECT 1 FROM public.creadores_autorizados
            WHERE user_id = (SELECT auth.uid())
        )
    );

-- Política de Lectura: Exclusiva para integrantes registrados en creadores_autorizados.
-- Permite a cualquier creador consultar las métricas agregadas del equipo sin recursión.
DROP POLICY IF EXISTS "Solo creadores autorizados consultan consumo" ON public.consumo_gemini;
CREATE POLICY "Solo creadores autorizados consultan consumo"
    ON public.consumo_gemini FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.creadores_autorizados
            WHERE user_id = (SELECT auth.uid())
        )
    );

COMMIT;

-- =====================================================================
-- INSTRUCCIONES DE ROLLBACK (EN CASO DE REQUERIR REVERSIÓN):
-- BEGIN;
-- DROP TABLE IF EXISTS public.consumo_gemini CASCADE;
-- DROP TABLE IF EXISTS public.creadores_autorizados CASCADE;
-- COMMIT;
-- =====================================================================
