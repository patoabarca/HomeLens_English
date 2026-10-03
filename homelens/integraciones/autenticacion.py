"""Adaptador de autenticación externa (Supabase Auth / Google)."""

from __future__ import annotations
from typing import Optional
from homelens.errores import Resultado
from homelens.modelos import ContextoUsuario


class AdaptadorAutenticacion:
    """Cliente para la integración con el proveedor de autenticación."""

    def __init__(self, supabase_url: Optional[str] = None, anon_key: Optional[str] = None):
        self.supabase_url = supabase_url
        self.anon_key = anon_key
