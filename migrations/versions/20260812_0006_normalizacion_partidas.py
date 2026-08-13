"""Crea una copia operativa de partidas revisadas para búsquedas posteriores."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0006"
down_revision: str | None = "20260812_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Agrega una relación uno a uno separada de la solicitud documental."""

    op.create_table(
        "normalizaciones_partida",
        sa.Column("partida_documento_id", sa.String(length=36), nullable=False),
        sa.Column("producto", sa.String(length=500), nullable=True),
        sa.Column("marca", sa.String(length=240), nullable=True),
        sa.Column("concentracion", sa.String(length=240), nullable=True),
        sa.Column("forma_dispositivo", sa.String(length=300), nullable=True),
        sa.Column("presentacion", sa.String(length=500), nullable=True),
        sa.Column("confirmada_por_usuario_id", sa.String(length=36), nullable=False),
        sa.Column("actualizada_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["partida_documento_id"],
            ["partidas_documento.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["confirmada_por_usuario_id"],
            ["usuarios.id"],
        ),
        sa.PrimaryKeyConstraint("partida_documento_id"),
    )


def downgrade() -> None:
    """Retira únicamente la copia de preparación; la solicitud revisada permanece."""

    op.drop_table("normalizaciones_partida")
