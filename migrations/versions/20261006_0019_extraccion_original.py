"""Conserva extracción original, nombres y avisos sin alterar la revisión humana."""

import sqlalchemy as sa
from alembic import op

revision = "20261006_0019"
down_revision = "20260821_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documentos", sa.Column("extraccion_original", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("documentos", "extraccion_original")
