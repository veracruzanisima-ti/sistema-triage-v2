"""Agrega snapshot COFEPRIS y evidencia opcional de identidad en precios."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0014"
down_revision: str | None = "20260819_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "observaciones_precio",
        sa.Column("evidencia_identidad", sa.JSON(), nullable=True),
    )
    op.create_table(
        "importaciones_cofepris",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("cargada_por_usuario_id", sa.String(length=36), nullable=False),
        sa.Column("cargada_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archivo", sa.String(length=255), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("registros_cargados", sa.Integer(), nullable=False),
        sa.Column("registros_vigentes", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["cargada_por_usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_importaciones_cofepris_cargada_en",
        "importaciones_cofepris",
        ["cargada_en"],
        unique=False,
    )
    op.create_table(
        "registros_cofepris",
        sa.Column("numero_registro", sa.String(length=255), nullable=False),
        sa.Column("importacion_id", sa.String(length=36), nullable=False),
        sa.Column("denominacion_distintiva", sa.Text(), nullable=False),
        sa.Column(
            "denominacion_distintiva_normalizada",
            sa.String(length=500),
            nullable=False,
        ),
        sa.Column("denominacion_generica", sa.Text(), nullable=False),
        sa.Column("componentes_genericos_normalizados", sa.JSON(), nullable=False),
        sa.Column("estado", sa.String(length=80), nullable=False),
        sa.Column("forma_farmaceutica", sa.Text(), nullable=True),
        sa.Column("via_administracion", sa.Text(), nullable=True),
        sa.Column("tipo_medicamento", sa.Text(), nullable=True),
        sa.Column("presentacion", sa.Text(), nullable=True),
        sa.Column("cantidad", sa.Text(), nullable=True),
        sa.Column("fraccion_sanitaria", sa.Text(), nullable=True),
        sa.Column("sustancia_quimica", sa.Text(), nullable=True),
        sa.Column("titular", sa.Text(), nullable=True),
        sa.Column("fecha_emision", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["importacion_id"], ["importaciones_cofepris.id"]),
        sa.PrimaryKeyConstraint("numero_registro"),
    )
    op.create_index(
        "ix_registros_cofepris_importacion_id",
        "registros_cofepris",
        ["importacion_id"],
        unique=False,
    )
    op.create_index(
        "ix_registros_cofepris_estado",
        "registros_cofepris",
        ["estado"],
        unique=False,
    )
    op.create_index(
        "ix_registros_cofepris_distintiva_estado",
        "registros_cofepris",
        ["denominacion_distintiva_normalizada", "estado"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_registros_cofepris_distintiva_estado",
        table_name="registros_cofepris",
    )
    op.drop_index("ix_registros_cofepris_estado", table_name="registros_cofepris")
    op.drop_index(
        "ix_registros_cofepris_importacion_id",
        table_name="registros_cofepris",
    )
    op.drop_table("registros_cofepris")
    op.drop_index(
        "ix_importaciones_cofepris_cargada_en",
        table_name="importaciones_cofepris",
    )
    op.drop_table("importaciones_cofepris")
    op.drop_column("observaciones_precio", "evidencia_identidad")
