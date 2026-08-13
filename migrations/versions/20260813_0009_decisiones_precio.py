"""Registra decisiones humanas append-only sobre evidencia de precio."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0009"
down_revision: str | None = "20260813_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decisiones_precio",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("cotizacion_id", sa.String(length=36), nullable=False),
        sa.Column("partida_documento_id", sa.String(length=36), nullable=True),
        sa.Column("clave_producto", sa.String(length=64), nullable=False),
        sa.Column("rol", sa.String(length=40), nullable=False),
        sa.Column("observacion_precio_id", sa.String(length=36), nullable=True),
        sa.Column("decidida_por_usuario_id", sa.String(length=36), nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cotizacion_id"], ["cotizaciones.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["partida_documento_id"], ["partidas_documento.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["observacion_precio_id"], ["observaciones_precio.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["decidida_por_usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for nombre, columnas in (
        ("ix_decisiones_precio_cotizacion_id", ["cotizacion_id"]),
        ("ix_decisiones_precio_partida_documento_id", ["partida_documento_id"]),
        ("ix_decisiones_precio_clave_producto", ["clave_producto"]),
        ("ix_decisiones_precio_rol", ["rol"]),
        ("ix_decisiones_precio_observacion_precio_id", ["observacion_precio_id"]),
        ("ix_decisiones_precio_creada_en", ["creada_en"]),
    ):
        op.create_index(nombre, "decisiones_precio", columnas, unique=False)


def downgrade() -> None:
    for nombre in (
        "ix_decisiones_precio_creada_en",
        "ix_decisiones_precio_observacion_precio_id",
        "ix_decisiones_precio_rol",
        "ix_decisiones_precio_clave_producto",
        "ix_decisiones_precio_partida_documento_id",
        "ix_decisiones_precio_cotizacion_id",
    ):
        op.drop_index(nombre, table_name="decisiones_precio")
    op.drop_table("decisiones_precio")
