-- =====================================================================
-- HomeLens English — Migración Tarea 7: Guardado e Historial
-- Esquema relacional con almacenamiento JSONB de objetos y actividades
-- =====================================================================
-- NOTA: Este script NO debe ejecutarse automáticamente sin autorización previa.
-- Debe aplicarse de forma controlada en el SQL Editor del panel de Supabase.

BEGIN;

-- 1. Crear tabla principal de exploraciones (idempotente)
CREATE TABLE IF NOT EXISTS public.exploraciones (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    estado TEXT NOT NULL,
    creada_en TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    schema_version INT NOT NULL DEFAULT 1,
    objetos JSONB NOT NULL DEFAULT '[]'::jsonb,
    actividades JSONB NOT NULL DEFAULT '[]'::jsonb,
    CONSTRAINT chk_exploraciones_estado_valido
        CHECK (estado IN ('UTILIZABLE', 'SIN_OBJETOS_CLAROS', 'REPETIR_CAPTURA')),
    CONSTRAINT chk_exploraciones_schema_version_pos
        CHECK (schema_version >= 1),
    CONSTRAINT chk_exploraciones_objetos_array
        CHECK (jsonb_typeof(objetos) = 'array'),
    CONSTRAINT chk_exploraciones_actividades_array
        CHECK (jsonb_typeof(actividades) = 'array')
);

-- Asegurar restricciones de integridad también si la tabla ya existía previamente
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_exploraciones_estado_valido'
          AND conrelid = 'public.exploraciones'::regclass
    ) THEN
        ALTER TABLE public.exploraciones
            ADD CONSTRAINT chk_exploraciones_estado_valido
            CHECK (estado IN ('UTILIZABLE', 'SIN_OBJETOS_CLAROS', 'REPETIR_CAPTURA'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_exploraciones_schema_version_pos'
          AND conrelid = 'public.exploraciones'::regclass
    ) THEN
        ALTER TABLE public.exploraciones
            ADD CONSTRAINT chk_exploraciones_schema_version_pos
            CHECK (schema_version >= 1);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_exploraciones_objetos_array'
          AND conrelid = 'public.exploraciones'::regclass
    ) THEN
        ALTER TABLE public.exploraciones
            ADD CONSTRAINT chk_exploraciones_objetos_array
            CHECK (jsonb_typeof(objetos) = 'array');
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_exploraciones_actividades_array'
          AND conrelid = 'public.exploraciones'::regclass
    ) THEN
        ALTER TABLE public.exploraciones
            ADD CONSTRAINT chk_exploraciones_actividades_array
            CHECK (jsonb_typeof(actividades) = 'array');
    END IF;
END
$$;

-- 2. Índices para optimizar consultas por usuario ordenadas cronológicamente
CREATE INDEX IF NOT EXISTS idx_exploraciones_user_fecha
    ON public.exploraciones (user_id, creada_en DESC);

-- 3. Privilegios SQL mínimos (defensa en profundidad independiente de RLS)
-- Bloquear acceso a PUBLIC y anon; otorgar únicamente SELECT e INSERT a authenticated.
-- Se excluyen explícitamente UPDATE, DELETE y TRUNCATE.
REVOKE ALL ON TABLE public.exploraciones FROM PUBLIC;
REVOKE ALL ON TABLE public.exploraciones FROM anon;
REVOKE ALL ON TABLE public.exploraciones FROM authenticated;
GRANT SELECT, INSERT ON TABLE public.exploraciones TO authenticated;

-- 4. Habilitación estricta de Row Level Security (RLS)
ALTER TABLE public.exploraciones ENABLE ROW LEVEL SECURITY;

-- 5. Políticas de seguridad basadas exclusivamente en auth.uid()
-- Política de Lectura (SELECT): Un usuario autenticado solo puede leer sus propias exploraciones.
DROP POLICY IF EXISTS "Usuarios ven sus propias exploraciones" ON public.exploraciones;
CREATE POLICY "Usuarios ven sus propias exploraciones"
    ON public.exploraciones FOR SELECT
    TO authenticated
    USING ((SELECT auth.uid()) = user_id);

-- Política de Inserción (INSERT): Un usuario autenticado solo puede insertar exploraciones con su propio user_id.
DROP POLICY IF EXISTS "Usuarios insertan solo sus propias exploraciones" ON public.exploraciones;
CREATE POLICY "Usuarios insertan solo sus propias exploraciones"
    ON public.exploraciones FOR INSERT
    TO authenticated
    WITH CHECK ((SELECT auth.uid()) = user_id);

COMMIT;

