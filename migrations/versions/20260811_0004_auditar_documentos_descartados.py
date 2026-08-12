"""Registra quién y cuándo descartó un documento cargado por error."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0004"
down_revision: str | None = "20260811_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Agrega trazabilidad mínima para quitar documentos sin borrarlos físicamente."""

    op.add_column(
        "documentos",
        sa.Column("descartado_en", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "documentos",
        sa.Column("descartado_por_usuario_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_documentos_descartado_por_usuario_id_usuarios",
        "documentos",
        "usuarios",
        ["descartado_por_usuario_id"],
        ["id"],
    )


def downgrade() -> None:
    """Retira los metadatos de descarte sin tocar el resto del documento."""

    op.drop_constraint(
        "fk_documentos_descartado_por_usuario_id_usuarios",
        "documentos",
        type_="foreignkey",
    )
    op.drop_column("documentos", "descartado_por_usuario_id")
    op.drop_column("documentos", "descartado_en")
