-- =====================================================================
-- HomeLens English — Migración Tarea 10: Registro de Intentos de Práctica
-- Persistencia idempotente de intentos de Cuestionarios y Desafíos Find It
-- =====================================================================
-- NOTA: Este script NO debe ejecutarse automáticamente sin autorización previa.
-- Debe aplicarse de forma controlada en el SQL Editor del panel de Supabase.

BEGIN;

-- 1. Crear tabla principal de intentos de práctica (idempotente)
CREATE TABLE IF NOT EXISTS public.intentos_practica (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL,
    fecha TIMESTAMPTZ NOT NULL DEFAULT now(),
    actividad_id UUID NULL,
    desafio_id UUID NULL,
    opcion_elegida_id TEXT NULL,
    resultado TEXT NOT NULL,
    objeto_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    CONSTRAINT chk_intentos_practica_tipo_valido
        CHECK (tipo IN ('CUESTIONARIO', 'FIND_IT')),
    CONSTRAINT chk_intentos_practica_resultado_valido
        CHECK (resultado IN ('CORRECTO', 'INCORRECTO', 'INDETERMINABLE')),
    CONSTRAINT chk_intentos_practica_objeto_ids_array
        CHECK (jsonb_typeof(objeto_ids) = 'array'),
    CONSTRAINT chk_intentos_practica_referencia_coherente
        CHECK (
            (tipo = 'CUESTIONARIO' AND actividad_id IS NOT NULL AND desafio_id IS NULL)
            OR
            (tipo = 'FIND_IT' AND desafio_id IS NOT NULL AND actividad_id IS NULL)
        )
);

-- Asegurar restricciones de integridad si la tabla ya existía previamente
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_intentos_practica_tipo_valido'
          AND conrelid = 'public.intentos_practica'::regclass
    ) THEN
        ALTER TABLE public.intentos_practica
            ADD CONSTRAINT chk_intentos_practica_tipo_valido
            CHECK (tipo IN ('CUESTIONARIO', 'FIND_IT'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_intentos_practica_resultado_valido'
          AND conrelid = 'public.intentos_practica'::regclass
    ) THEN
        ALTER TABLE public.intentos_practica
            ADD CONSTRAINT chk_intentos_practica_resultado_valido
            CHECK (resultado IN ('CORRECTO', 'INCORRECTO', 'INDETERMINABLE'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_intentos_practica_objeto_ids_array'
          AND conrelid = 'public.intentos_practica'::regclass
    ) THEN
        ALTER TABLE public.intentos_practica
            ADD CONSTRAINT chk_intentos_practica_objeto_ids_array
            CHECK (jsonb_typeof(objeto_ids) = 'array');
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_intentos_practica_referencia_coherente'
          AND conrelid = 'public.intentos_practica'::regclass
    ) THEN
        ALTER TABLE public.intentos_practica
            ADD CONSTRAINT chk_intentos_practica_referencia_coherente
            CHECK (
                (tipo = 'CUESTIONARIO' AND actividad_id IS NOT NULL AND desafio_id IS NULL)
                OR
                (tipo = 'FIND_IT' AND desafio_id IS NOT NULL AND actividad_id IS NULL)
            );
    END IF;
END
$$;

-- 2. Índices para optimizar consultas por usuario ordenadas con los más recientes primero
CREATE INDEX IF NOT EXISTS idx_intentos_practica_user_fecha
    ON public.intentos_practica (user_id, fecha DESC);

CREATE INDEX IF NOT EXISTS idx_intentos_practica_user_tipo_fecha
    ON public.intentos_practica (user_id, tipo, fecha DESC);

-- 3. Privilegios SQL mínimos (defensa en profundidad independiente de RLS)
-- Los intentos de práctica son registros históricos inmutables:
-- Solo se concede SELECT e INSERT a authenticated; UPDATE y DELETE permanecen bloqueados.
REVOKE ALL ON TABLE public.intentos_practica FROM PUBLIC;
REVOKE ALL ON TABLE public.intentos_practica FROM anon;
REVOKE ALL ON TABLE public.intentos_practica FROM authenticated;
GRANT SELECT, INSERT ON TABLE public.intentos_practica TO authenticated;

-- 4. Habilitación estricta de Row Level Security (RLS)
ALTER TABLE public.intentos_practica ENABLE ROW LEVEL SECURITY;

-- 5. Políticas de seguridad basadas exclusivamente en auth.uid()
-- Política de Lectura (SELECT): Cada usuario autenticado solo puede consultar sus propios intentos.
DROP POLICY IF EXISTS "Usuarios ven sus propios intentos de practica" ON public.intentos_practica;
CREATE POLICY "Usuarios ven sus propios intentos de practica"
    ON public.intentos_practica FOR SELECT
    TO authenticated
    USING ((SELECT auth.uid()) = user_id);

-- Política de Inserción (INSERT): Cada usuario autenticado solo puede guardar intentos con su propio user_id.
DROP POLICY IF EXISTS "Usuarios insertan solo sus propios intentos de practica" ON public.intentos_practica;
CREATE POLICY "Usuarios insertan solo sus propios intentos de practica"
    ON public.intentos_practica FOR INSERT
    TO authenticated
    WITH CHECK ((SELECT auth.uid()) = user_id);

COMMIT;
