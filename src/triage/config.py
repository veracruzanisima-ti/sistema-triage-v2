"""Configuración de la aplicación.

Los secretos se leen exclusivamente desde variables de entorno. Este módulo no
contiene valores reales de producción.
"""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    """Configuración mínima del servicio web."""

    app_env: str = "development"
    app_secret_key: str = ""
    database_url: str = "sqlite+pysqlite:///./triage_dev.sqlite3"
    openai_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validar_persistencia_produccion(self):
        """Impide desplegar producción usando una base SQLite local."""

        if self.app_env.strip().lower() == "production":
            if not self.database_url.strip():
                raise ValueError("DATABASE_URL es obligatoria en producción")
            if self.database_url.lower().startswith("sqlite"):
                raise ValueError("producción requiere una base de datos compartida")
        return self


@lru_cache
def obtener_configuracion() -> Configuracion:
    """Devuelve una única configuración por proceso."""

    return Configuracion()
