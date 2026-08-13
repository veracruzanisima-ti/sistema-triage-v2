"""Entorno de migraciones del esquema de Triage V2."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from triage.base_datos import Base, normalizar_database_url
from triage.config import obtener_configuracion
from triage.cotizaciones.modelos import Cotizacion
from triage.documentos.modelos import Documento, PartidaDocumento
from triage.historico.modelos import ObservacionPrecio
from triage.normalizacion.modelos import NormalizacionPartida
from triage.usuarios.modelos import Usuario

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

url_base_datos = normalizar_database_url(obtener_configuracion().database_url)
config.set_main_option("sqlalchemy.url", url_base_datos.replace("%", "%%"))
_MODELOS_REGISTRADOS = (
    Cotizacion,
    Usuario,
    Documento,
    PartidaDocumento,
    NormalizacionPartida,
    ObservacionPrecio,
)
target_metadata = Base.metadata


def ejecutar_migraciones_offline() -> None:
    """Genera SQL sin abrir conexión cuando se solicita modo offline."""

    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def ejecutar_migraciones_online() -> None:
    """Aplica migraciones usando una conexión real de la base configurada."""

    seccion = config.get_section(config.config_ini_section, {})
    motor = engine_from_config(
        seccion,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with motor.connect() as conexion:
        context.configure(
            connection=conexion,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    ejecutar_migraciones_offline()
else:
    ejecutar_migraciones_online()
