"""Agrega idempotencia de cola y decisión de inclusión por partida."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0004"
down_revision: str | None = "20260811_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Permite reintentos seguros y conservar partidas solicitadas pero excluidas."""

    with op.batch_alter_table("documentos") as batch_op:
        batch_op.add_column(sa.Column("clave_idempotencia", sa.String(length=80), nullable=True))
        batch_op.create_unique_constraint(
            "uq_documentos_cotizacion_idempotencia",
            ["cotizacion_id", "clave_idempotencia"],
        )

    with op.batch_alter_table("partidas_documento") as batch_op:
        batch_op.add_column(
            sa.Column(
                "incluida_cotizacion",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch_op.add_column(sa.Column("motivo_exclusion", sa.String(length=300), nullable=True))


def downgrade() -> None:
    """Retira la protección de reintentos y la decisión persistida de inclusión."""

    with op.batch_alter_table("partidas_documento") as batch_op:
        batch_op.drop_column("motivo_exclusion")
        batch_op.drop_column("incluida_cotizacion")

    with op.batch_alter_table("documentos") as batch_op:
        batch_op.drop_constraint("uq_documentos_cotizacion_idempotencia", type_="unique")
        batch_op.drop_column("clave_idempotencia")
