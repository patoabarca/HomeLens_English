-- =====================================================================
-- HomeLens English — Registro Inicial de Creadores Autorizados
-- =====================================================================
-- NOTA IMPORTANTE DE SEGURIDAD Y CONTROL:
-- Este script NO debe contener identificadores reales codificados en el repositorio.
-- Debe ejecutarse en el SQL Editor de Supabase ÚNICAMENTE DESPUÉS de haber
-- aplicado y verificado 'sql/migracion_tarea_consumo_ia.sql'.
--
-- INSTRUCCIONES PARA EL OPERADOR AUTORIZADO:
-- Reemplazar los marcadores '<UUID_VERIFICADO_DE_...>' por los valores reales
-- disponibles en el archivo local '.env' o en Supabase Dashboard (Authentication -> Users).
--
-- Estado de las identidades:
-- 1. Patricia Abarca: Identidad verificada en Supabase Auth.
-- 2. Lucas Centurión: Identidad verificada en Supabase Auth.
-- 3. Victoria Magliano: PENDIENTE hasta su primer inicio de sesión con Google.
-- =====================================================================

BEGIN;

-- 1. Registro de Patricia Abarca
-- Reemplazar '<UUID_VERIFICADO_DE_PATRICIA>' por el valor de CREADOR_ID_PATRICIA de tu archivo .env local
INSERT INTO public.creadores_autorizados (user_id, nombre_etiqueta)
VALUES ('<UUID_VERIFICADO_DE_PATRICIA>', 'Patricia')
ON CONFLICT (user_id) DO UPDATE
SET nombre_etiqueta = EXCLUDED.nombre_etiqueta;

-- 2. Registro de Lucas Centurión
-- Reemplazar '<UUID_VERIFICADO_DE_LUCAS>' por el valor de CREADOR_ID_LUCAS de tu archivo .env local
INSERT INTO public.creadores_autorizados (user_id, nombre_etiqueta)
VALUES ('<UUID_VERIFICADO_DE_LUCAS>', 'Lucas')
ON CONFLICT (user_id) DO UPDATE
SET nombre_etiqueta = EXCLUDED.nombre_etiqueta;

-- 3. Victoria Magliano — PENDIENTE DE PRIMER INICIO DE SESIÓN
-- Una vez que Victoria inicie sesión con Google por primera vez en la aplicación,
-- obtener su user_id en Supabase Dashboard -> Authentication -> Users y ejecutar:
--
-- INSERT INTO public.creadores_autorizados (user_id, nombre_etiqueta)
-- VALUES ('<UUID_VERIFICADO_DE_VICTORIA>', 'Victoria')
-- ON CONFLICT (user_id) DO UPDATE
-- SET nombre_etiqueta = EXCLUDED.nombre_etiqueta;

COMMIT;

-- Comprobación de verificación posterior (ejecutar para confirmar el alta):
-- SELECT user_id, nombre_etiqueta, creado_en FROM public.creadores_autorizados ORDER BY creado_en;
