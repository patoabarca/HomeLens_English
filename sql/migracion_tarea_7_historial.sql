-- =====================================================================
-- HomeLens English — Migración Tarea 7: Guardado e Historial
-- Esquema relacional con almacenamiento JSONB de objetos y actividades
-- =====================================================================
-- NOTA: Este script NO debe ejecutarse automáticamente sin autorización previa.
-- Debe aplicarse en el SQL Editor del panel de Supabase.

-- 1. Crear tabla principal de exploraciones
CREATE TABLE IF NOT EXISTS public.exploraciones (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    estado TEXT NOT NULL,
    creada_en TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    schema_version INT NOT NULL DEFAULT 1,
    objetos JSONB NOT NULL DEFAULT '[]'::jsonb,
    actividades JSONB NOT NULL DEFAULT '[]'::jsonb
);

-- 2. Índices para optimizar consultas por usuario ordenadas cronológicamente
CREATE INDEX IF NOT EXISTS idx_exploraciones_user_fecha 
    ON public.exploraciones (user_id, creada_en DESC);

-- 3. Habilitación estricta de Row Level Security (RLS)
ALTER TABLE public.exploraciones ENABLE ROW LEVEL SECURITY;

-- 4. Políticas de seguridad basadas exclusivamente en auth.uid()
-- Política de Lectura (SELECT): Un usuario autenticado solo puede leer sus propias exploraciones.
DROP POLICY IF EXISTS "Usuarios ven sus propias exploraciones" ON public.exploraciones;
CREATE POLICY "Usuarios ven sus propias exploraciones"
    ON public.exploraciones FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

-- Política de Inserción (INSERT): Un usuario autenticado solo puede insertar exploraciones con su propio user_id.
DROP POLICY IF EXISTS "Usuarios insertan solo sus propias exploraciones" ON public.exploraciones;
CREATE POLICY "Usuarios insertan solo sus propias exploraciones"
    ON public.exploraciones FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = user_id);

