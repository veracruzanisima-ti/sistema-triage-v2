"""Conserva consultas web y candidatos descartados fuera del histórico cotizable."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_0013"
down_revision: str | None = "20260814_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "consultas_web",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("cotizacion_id", sa.String(length=36), nullable=False),
        sa.Column("partida_documento_id", sa.String(length=36), nullable=True),
        sa.Column("clave_producto", sa.String(length=64), nullable=False),
        sa.Column("modelo", sa.String(length=120), nullable=False),
        sa.Column("estado", sa.String(length=24), nullable=False),
        sa.Column("criterios_busqueda", sa.JSON(), nullable=False),
        sa.Column("terminos_ampliados", sa.JSON(), nullable=False),
        sa.Column("intentos", sa.Integer(), nullable=False),
        sa.Column("candidatos", sa.Integer(), nullable=False),
        sa.Column("guardados", sa.Integer(), nullable=False),
        sa.Column("descartados", sa.Integer(), nullable=False),
        sa.Column("mensaje_error", sa.String(length=300), nullable=True),
        sa.Column("ejecutada_por_usuario_id", sa.String(length=36), nullable=False),
        sa.Column("iniciada_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalizada_en", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["cotizacion_id"], ["cotizaciones.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["partida_documento_id"],
            ["partidas_documento.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["ejecutada_por_usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for nombre, columnas in (
        ("ix_consultas_web_cotizacion_id", ["cotizacion_id"]),
        ("ix_consultas_web_partida_documento_id", ["partida_documento_id"]),
        ("ix_consultas_web_clave_producto", ["clave_producto"]),
        ("ix_consultas_web_estado", ["estado"]),
        ("ix_consultas_web_iniciada_en", ["iniciada_en"]),
    ):
        op.create_index(nombre, "consultas_web", columnas, unique=False)

    op.create_table(
        "candidatos_web_descartados",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("consulta_web_id", sa.String(length=36), nullable=False),
        sa.Column("proveedor", sa.String(length=240), nullable=True),
        sa.Column("producto_observado", sa.String(length=700), nullable=True),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("precio_observado", sa.Numeric(14, 2), nullable=True),
        sa.Column("motivos", sa.JSON(), nullable=False),
        sa.Column("intento_busqueda", sa.Integer(), nullable=False),
        sa.Column("descartado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["consulta_web_id"],
            ["consultas_web.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_candidatos_web_descartados_consulta_web_id",
        "candidatos_web_descartados",
        ["consulta_web_id"],
        unique=False,
    )
    op.create_index(
        "ix_candidatos_web_descartados_descartado_en",
        "candidatos_web_descartados",
        ["descartado_en"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_candidatos_web_descartados_descartado_en",
        table_name="candidatos_web_descartados",
    )
    op.drop_index(
        "ix_candidatos_web_descartados_consulta_web_id",
        table_name="candidatos_web_descartados",
    )
    op.drop_table("candidatos_web_descartados")
    for nombre in (
        "ix_consultas_web_iniciada_en",
        "ix_consultas_web_estado",
        "ix_consultas_web_clave_producto",
        "ix_consultas_web_partida_documento_id",
        "ix_consultas_web_cotizacion_id",
    ):
        op.drop_index(nombre, table_name="consultas_web")
    op.drop_table("consultas_web")
