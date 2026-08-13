"""Crea observaciones históricas append-only para productos preparados."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0007"
down_revision: str | None = "20260812_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Agrega observaciones que sobreviven a cambios posteriores de la solicitud."""

    op.create_table(
        "observaciones_precio",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("clave_producto", sa.String(length=64), nullable=False),
        sa.Column("normalizacion_partida_id", sa.String(length=36), nullable=True),
        sa.Column("producto", sa.String(length=500), nullable=True),
        sa.Column("marca", sa.String(length=240), nullable=True),
        sa.Column("concentracion", sa.String(length=240), nullable=True),
        sa.Column("forma_dispositivo", sa.String(length=300), nullable=True),
        sa.Column("presentacion", sa.String(length=500), nullable=True),
        sa.Column("proveedor", sa.String(length=240), nullable=False),
        sa.Column("precio_antes_iva", sa.Numeric(14, 2), nullable=True),
        sa.Column("iva_porcentaje", sa.Numeric(5, 2), nullable=True),
        sa.Column("precio_total", sa.Numeric(14, 2), nullable=True),
        sa.Column("es_promocion", sa.Boolean(), nullable=False),
        sa.Column("condiciones_promocion", sa.Text(), nullable=True),
        sa.Column("disponibilidad", sa.String(length=200), nullable=True),
        sa.Column("entrega_viable", sa.Boolean(), nullable=True),
        sa.Column("fuente", sa.String(length=500), nullable=False),
        sa.Column("observado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capturada_por_usuario_id", sa.String(length=36), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["normalizacion_partida_id"],
            ["normalizaciones_partida.partida_documento_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["capturada_por_usuario_id"],
            ["usuarios.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_observaciones_precio_clave_producto",
        "observaciones_precio",
        ["clave_producto"],
        unique=False,
    )
    op.create_index(
        "ix_observaciones_precio_normalizacion_partida_id",
        "observaciones_precio",
        ["normalizacion_partida_id"],
        unique=False,
    )
    op.create_index(
        "ix_observaciones_precio_proveedor",
        "observaciones_precio",
        ["proveedor"],
        unique=False,
    )
    op.create_index(
        "ix_observaciones_precio_observado_en",
        "observaciones_precio",
        ["observado_en"],
        unique=False,
    )


def downgrade() -> None:
    """Retira sólo el histórico; productos preparados y solicitud permanecen."""

    op.drop_index("ix_observaciones_precio_observado_en", table_name="observaciones_precio")
    op.drop_index("ix_observaciones_precio_proveedor", table_name="observaciones_precio")
    op.drop_index(
        "ix_observaciones_precio_normalizacion_partida_id",
        table_name="observaciones_precio",
    )
    op.drop_index("ix_observaciones_precio_clave_producto", table_name="observaciones_precio")
    op.drop_table("observaciones_precio")
