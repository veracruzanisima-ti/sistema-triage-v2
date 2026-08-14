"""Conserva el código postal usado para consultar y observar precios."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0010"
down_revision: str | None = "20260813_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cotizaciones",
        sa.Column("codigo_postal_consulta", sa.String(length=5), nullable=True),
    )
    op.add_column(
        "observaciones_precio",
        sa.Column("codigo_postal", sa.String(length=5), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("observaciones_precio", "codigo_postal")
    op.drop_column("cotizaciones", "codigo_postal_consulta")
