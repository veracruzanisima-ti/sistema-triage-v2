"""Agrega precios finales de venta validados manualmente por partida exacta."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0017"
down_revision: str | None = "20260820_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "precios_finales_venta_partida",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("cotizacion_id", sa.String(length=36), nullable=False),
        sa.Column("partida_documento_id", sa.String(length=36), nullable=True),
        sa.Column("clave_producto", sa.String(length=64), nullable=False),
        sa.Column("estado", sa.String(length=24), nullable=False),
        sa.Column("precio_unitario_sin_iva", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("fuente_comercial", sa.String(length=300), nullable=True),
        sa.Column("observacion", sa.String(length=500), nullable=True),
        sa.Column("fuente_decision", sa.String(length=40), nullable=False),
        sa.Column("validada_por_usuario_id", sa.String(length=36), nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cotizacion_id"], ["cotizaciones.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["partida_documento_id"], ["partidas_documento.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["validada_por_usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for nombre, columnas in (
        ("ix_precios_finales_venta_partida_cotizacion_id", ["cotizacion_id"]),
        ("ix_precios_finales_venta_partida_partida_documento_id", ["partida_documento_id"]),
        ("ix_precios_finales_venta_partida_clave_producto", ["clave_producto"]),
        ("ix_precios_finales_venta_partida_estado", ["estado"]),
        ("ix_precios_finales_venta_partida_creada_en", ["creada_en"]),
    ):
        op.create_index(nombre, "precios_finales_venta_partida", columnas, unique=False)


def downgrade() -> None:
    for nombre in (
        "ix_precios_finales_venta_partida_creada_en",
        "ix_precios_finales_venta_partida_estado",
        "ix_precios_finales_venta_partida_clave_producto",
        "ix_precios_finales_venta_partida_partida_documento_id",
        "ix_precios_finales_venta_partida_cotizacion_id",
    ):
        op.drop_index(nombre, table_name="precios_finales_venta_partida")
    op.drop_table("precios_finales_venta_partida")
