"""Amplía texto externo de descartes web sin truncar su evidencia."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_0014"
down_revision: str | None = "20260819_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("candidatos_web_descartados") as lote:
        lote.alter_column(
            "proveedor",
            existing_type=sa.String(length=240),
            type_=sa.Text(),
            existing_nullable=True,
        )
        lote.alter_column(
            "producto_observado",
            existing_type=sa.String(length=700),
            type_=sa.Text(),
            existing_nullable=True,
        )
        lote.alter_column(
            "url",
            existing_type=sa.String(length=1000),
            type_=sa.Text(),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("candidatos_web_descartados") as lote:
        lote.alter_column(
            "url",
            existing_type=sa.Text(),
            type_=sa.String(length=1000),
            existing_nullable=False,
        )
        lote.alter_column(
            "producto_observado",
            existing_type=sa.Text(),
            type_=sa.String(length=700),
            existing_nullable=True,
        )
        lote.alter_column(
            "proveedor",
            existing_type=sa.Text(),
            type_=sa.String(length=240),
            existing_nullable=True,
        )
