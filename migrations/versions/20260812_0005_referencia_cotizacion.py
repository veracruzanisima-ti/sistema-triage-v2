"""Distingue referencias manuales y sincroniza referencias revisadas inequívocas."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0005"
down_revision: str | None = "20260812_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Conserva referencias humanas y completa casos inequívocos ya revisados."""

    with op.batch_alter_table("cotizaciones") as batch_op:
        batch_op.add_column(
            sa.Column(
                "referencia_fijada_manual",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    conexion = op.get_bind()
    conexion.execute(
        sa.text(
            """
            UPDATE cotizaciones
            SET referencia_fijada_manual = true
            WHERE referencia IS NOT NULL AND TRIM(referencia) <> ''
            """
        )
    )

    referencias_unicas = conexion.execute(
        sa.text(
            """
            SELECT
                c.id AS cotizacion_id,
                MIN(TRIM(d.memorandum)) AS referencia
            FROM cotizaciones c
            JOIN documentos d ON d.cotizacion_id = c.id
            WHERE c.referencia IS NULL
              AND d.estado = 'REVISADO'
              AND d.memorandum IS NOT NULL
              AND TRIM(d.memorandum) <> ''
            GROUP BY c.id
            HAVING COUNT(DISTINCT TRIM(d.memorandum)) = 1
            """
        )
    ).mappings()

    for fila in referencias_unicas:
        conexion.execute(
            sa.text(
                """
                UPDATE cotizaciones
                SET referencia = :referencia
                WHERE id = :cotizacion_id
                """
            ),
            {
                "referencia": fila["referencia"],
                "cotizacion_id": fila["cotizacion_id"],
            },
        )


def downgrade() -> None:
    """Retira la distinción manual; conserva el texto actual de referencia."""

    with op.batch_alter_table("cotizaciones") as batch_op:
        batch_op.drop_column("referencia_fijada_manual")
