"""Agrega decisiones comerciales append-only por partida."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0015"
down_revision: str | None = "20260820_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decisiones_comerciales_partida",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("cotizacion_id", sa.String(length=36), nullable=False),
        sa.Column("partida_documento_id", sa.String(length=36), nullable=True),
        sa.Column("estado", sa.String(length=24), nullable=False),
        sa.Column("motivo", sa.String(length=500), nullable=True),
        sa.Column("fuente_validacion", sa.String(length=40), nullable=False),
        sa.Column("regla_referencia", sa.String(length=160), nullable=True),
        sa.Column("decidida_por_usuario_id", sa.String(length=36), nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cotizacion_id"], ["cotizaciones.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["partida_documento_id"], ["partidas_documento.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["decidida_por_usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for nombre, columnas in (
        ("ix_decisiones_comerciales_cotizacion_id", ["cotizacion_id"]),
        ("ix_decisiones_comerciales_partida_id", ["partida_documento_id"]),
        ("ix_decisiones_comerciales_estado", ["estado"]),
        ("ix_decisiones_comerciales_creada_en", ["creada_en"]),
    ):
        op.create_index(nombre, "decisiones_comerciales_partida", columnas, unique=False)


def downgrade() -> None:
    for nombre in (
        "ix_decisiones_comerciales_creada_en",
        "ix_decisiones_comerciales_estado",
        "ix_decisiones_comerciales_partida_id",
        "ix_decisiones_comerciales_cotizacion_id",
    ):
        op.drop_index(nombre, table_name="decisiones_comerciales_partida")
    op.drop_table("decisiones_comerciales_partida")
