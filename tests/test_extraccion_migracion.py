"""Migración de evidencia automática sobre datos ficticios ya existentes."""

from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config


def test_extraccion_original_upgrade_downgrade_preserva_documento(tmp_path, monkeypatch):
    raiz = Path(__file__).resolve().parents[1]
    url = f"sqlite+pysqlite:///{tmp_path / 'migracion.sqlite3'}"
    monkeypatch.setenv("DATABASE_URL", url)
    from triage.config import obtener_configuracion

    obtener_configuracion.cache_clear()
    config = Config(str(raiz / "alembic.ini"))
    config.set_main_option("script_location", str(raiz / "migrations"))
    try:
        command.upgrade(config, "20260821_0018")
        motor = sa.create_engine(url)
        metadata = sa.MetaData()
        cotizaciones = sa.Table("cotizaciones", metadata, autoload_with=motor)
        documentos = sa.Table("documentos", metadata, autoload_with=motor)
        ahora = datetime.now(UTC)
        with motor.begin() as conexion:
            conexion.execute(
                cotizaciones.insert().values(
                    id="cot-ficticia",
                    referencia="FICTICIA",
                    estado="EN_PROCESO",
                    creada_en=ahora,
                    actualizada_en=ahora,
                    referencia_fijada_manual=False,
                )
            )
            conexion.execute(
                documentos.insert().values(
                    id="doc-ficticio",
                    cotizacion_id="cot-ficticia",
                    nombre_original="foto.png",
                    mime_type="image/png",
                    tamano_bytes=8,
                    sha256="0" * 64,
                    contenido_original=b"ficticio",
                    estado="REVISADO",
                    folios=[],
                    parece_fragmento=False,
                    senales_fragmento=[],
                    recibido_en=ahora,
                )
            )
        command.upgrade(config, "head")
        with motor.connect() as conexion:
            assert (
                conexion.execute(
                    sa.text("SELECT extraccion_original FROM documentos WHERE id='doc-ficticio'")
                ).scalar()
                is None
            )
        command.downgrade(config, "20260821_0018")
        assert "extraccion_original" not in {
            columna["name"] for columna in sa.inspect(motor).get_columns("documentos")
        }
        with motor.connect() as conexion:
            assert (
                conexion.execute(
                    sa.text("SELECT contenido_original FROM documentos WHERE id='doc-ficticio'")
                ).scalar()
                == b"ficticio"
            )
        command.upgrade(config, "head")
        assert "extraccion_original" in {
            columna["name"] for columna in sa.inspect(motor).get_columns("documentos")
        }
        motor.dispose()
    finally:
        obtener_configuracion.cache_clear()
