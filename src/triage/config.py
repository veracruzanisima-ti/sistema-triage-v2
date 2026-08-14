"""Configuración de la aplicación.

Los secretos se leen exclusivamente desde variables de entorno. Este módulo no
contiene valores reales de producción.
"""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_CLAVE_DESARROLLO = "solo-desarrollo-no-usar-en-produccion-cambiar-antes-de-desplegar"


class Configuracion(BaseSettings):
    """Configuración mínima del servicio web."""

    app_env: str = "development"
    app_secret_key: str = ""
    database_url: str = "sqlite+pysqlite:///./triage_dev.sqlite3"
    openai_api_key: str = ""
    openai_model: str = "gpt-5"
    openai_model_lector: str = ""
    openai_model_web: str = ""
    gemini_api_key: str = ""
    gemini_model_lector: str = "gemini-3.6-flash"
    gemini_model_web: str = "gemini-3.6-flash"
    fesa_automatizacion_habilitada: bool = False
    fesa_usuario: str = ""
    fesa_password: str = ""
    nadro_edi_habilitado: bool = False
    nadro_edi_archivo: str = ""
    max_documento_bytes: int = 15 * 1024 * 1024
    bootstrap_admin_email: str = ""
    bootstrap_admin_name: str = ""
    bootstrap_admin_password: str = ""
    session_max_age_seconds: int = 43_200
    codigo_postal_consulta_default: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def modelo_openai_lector(self) -> str:
        """Resuelve el modelo del lector conservando compatibilidad con OPENAI_MODEL."""

        return self.openai_model_lector.strip() or self.openai_model.strip()

    @property
    def modelo_openai_web(self) -> str:
        """Resuelve el modelo web conservando compatibilidad con OPENAI_MODEL."""

        return self.openai_model_web.strip() or self.openai_model.strip()

    @property
    def es_produccion(self) -> bool:
        """Indica si deben activarse controles estrictos de despliegue."""

        return self.app_env.strip().lower() == "production"

    @property
    def clave_sesion(self) -> str:
        """Devuelve una clave fija sólo para desarrollo cuando no hay secreto real."""

        return self.app_secret_key or _CLAVE_DESARROLLO

    @model_validator(mode="after")
    def validar_configuracion(self):
        """Impide configuraciones inseguras y bootstraps incompletos."""

        if self.session_max_age_seconds <= 0:
            raise ValueError("SESSION_MAX_AGE_SECONDS debe ser mayor que cero")
        if self.max_documento_bytes <= 0:
            raise ValueError("MAX_DOCUMENTO_BYTES debe ser mayor que cero")
        if not self.modelo_openai_lector:
            raise ValueError("OPENAI_MODEL u OPENAI_MODEL_LECTOR debe definir el modelo del lector")
        if not self.modelo_openai_web:
            raise ValueError("OPENAI_MODEL u OPENAI_MODEL_WEB debe definir el modelo web")
        if self.gemini_api_key.strip() and not self.gemini_model_lector.strip():
            raise ValueError(
                "GEMINI_MODEL_LECTOR no puede estar vacío cuando Gemini está configurado"
            )
        if self.gemini_api_key.strip() and not self.gemini_model_web.strip():
            raise ValueError("GEMINI_MODEL_WEB no puede estar vacío cuando Gemini está configurado")

        self.fesa_usuario = self.fesa_usuario.strip()
        if self.fesa_automatizacion_habilitada and not (
            self.fesa_usuario and self.fesa_password
        ):
            raise ValueError(
                "FESA_USUARIO y FESA_PASSWORD son obligatorios cuando FESA está habilitado"
            )

        self.nadro_edi_archivo = self.nadro_edi_archivo.strip()
        if self.nadro_edi_habilitado and not self.nadro_edi_archivo:
            raise ValueError(
                "NADRO_EDI_ARCHIVO es obligatorio cuando la integración EDI está habilitada"
            )

        codigo_postal = self.codigo_postal_consulta_default.strip()
        if codigo_postal and (len(codigo_postal) != 5 or not codigo_postal.isdigit()):
            raise ValueError("CODIGO_POSTAL_CONSULTA_DEFAULT debe contener 5 dígitos")
        self.codigo_postal_consulta_default = codigo_postal

        if self.es_produccion:
            if not self.database_url.strip():
                raise ValueError("DATABASE_URL es obligatoria en producción")
            if self.database_url.lower().startswith("sqlite"):
                raise ValueError("producción requiere una base de datos compartida")
            if len(self.app_secret_key) < 32:
                raise ValueError("APP_SECRET_KEY debe tener al menos 32 caracteres")

        bootstrap = (
            self.bootstrap_admin_email.strip(),
            self.bootstrap_admin_name.strip(),
            self.bootstrap_admin_password,
        )
        if any(bootstrap) and not all(bootstrap):
            raise ValueError("el administrador inicial requiere correo, nombre y contraseña")
        if self.bootstrap_admin_password and len(self.bootstrap_admin_password) < 12:
            raise ValueError("la contraseña del administrador inicial requiere 12 caracteres")

        return self


@lru_cache
def obtener_configuracion() -> Configuracion:
    """Devuelve una única configuración por proceso."""

    return Configuracion()
