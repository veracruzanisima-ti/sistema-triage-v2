"""Crea cuentas internas para proteger el acceso a Triage."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0002"
down_revision: str | None = "20260810_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crea usuarios con contraseña hasheada y sin registro público."""

    op.create_table(
        "usuarios",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("correo", sa.String(length=254), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("es_admin", sa.Boolean(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("correo"),
    )
    op.create_index("ix_usuarios_correo", "usuarios", ["correo"])


def downgrade() -> None:
    """Retira las cuentas internas creadas por esta versión."""

    op.drop_index("ix_usuarios_correo", table_name="usuarios")
    op.drop_table("usuarios")
