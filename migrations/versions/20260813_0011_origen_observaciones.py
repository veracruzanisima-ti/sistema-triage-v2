"""Agrega trazabilidad del origen y del producto mostrado por la fuente."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0011"
down_revision: str | None = "20260813_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "observaciones_precio",
        sa.Column("producto_observado", sa.String(length=700), nullable=True),
    )
    op.add_column(
        "observaciones_precio",
        sa.Column("origen", sa.String(length=24), nullable=True),
    )
    op.create_index(
        "ix_observaciones_precio_origen",
        "observaciones_precio",
        ["origen"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_observaciones_precio_origen", table_name="observaciones_precio")
    op.drop_column("observaciones_precio", "origen")
    op.drop_column("observaciones_precio", "producto_observado")
