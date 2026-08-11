"""Crea la tabla inicial de cotizaciones compartidas."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crea la unidad mínima de trabajo persistente."""

    op.create_table(
        "cotizaciones",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("referencia", sa.String(length=160), nullable=True),
        sa.Column("estado", sa.String(length=32), nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizada_en", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cotizaciones_estado", "cotizaciones", ["estado"])


def downgrade() -> None:
    """Revierte por completo la primera migración."""

    op.drop_index("ix_cotizaciones_estado", table_name="cotizaciones")
    op.drop_table("cotizaciones")
