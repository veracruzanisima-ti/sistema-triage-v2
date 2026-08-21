"""Agrega validaciones fiscales append-only por producto exacto."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0016"
down_revision: str | None = "20260820_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "validaciones_fiscales_partida",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("cotizacion_id", sa.String(length=36), nullable=False),
        sa.Column("partida_documento_id", sa.String(length=36), nullable=True),
        sa.Column("clave_producto", sa.String(length=64), nullable=False),
        sa.Column("estado", sa.String(length=24), nullable=False),
        sa.Column("tratamiento_iva", sa.String(length=24), nullable=True),
        sa.Column("iva_porcentaje", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("version_motor", sa.String(length=64), nullable=False),
        sa.Column("sugerencia_snapshot", sa.JSON(), nullable=True),
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
        ("ix_validaciones_fiscales_partida_cotizacion_id", ["cotizacion_id"]),
        ("ix_validaciones_fiscales_partida_partida_documento_id", ["partida_documento_id"]),
        ("ix_validaciones_fiscales_partida_clave_producto", ["clave_producto"]),
        ("ix_validaciones_fiscales_partida_estado", ["estado"]),
        ("ix_validaciones_fiscales_partida_creada_en", ["creada_en"]),
    ):
        op.create_index(nombre, "validaciones_fiscales_partida", columnas, unique=False)


def downgrade() -> None:
    for nombre in (
        "ix_validaciones_fiscales_partida_creada_en",
        "ix_validaciones_fiscales_partida_estado",
        "ix_validaciones_fiscales_partida_clave_producto",
        "ix_validaciones_fiscales_partida_partida_documento_id",
        "ix_validaciones_fiscales_partida_cotizacion_id",
    ):
        op.drop_index(nombre, table_name="validaciones_fiscales_partida")
    op.drop_table("validaciones_fiscales_partida")
