"""Configuración de la aplicación.

Los secretos se leen exclusivamente desde variables de entorno. Este módulo no
contiene valores reales de producción.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    """Configuración mínima del servicio web."""

    app_env: str = "development"
    app_secret_key: str = ""
    database_url: str = ""
    openai_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def obtener_configuracion() -> Configuracion:
    """Devuelve una única configuración por proceso."""

    return Configuracion()
