"""Conserva el archivo original para revisión humana posterior."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0018"
down_revision: str | None = "20260821_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documentos",
        sa.Column("contenido_original", sa.LargeBinary(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documentos", "contenido_original")
