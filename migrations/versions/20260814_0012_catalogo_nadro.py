"""Agrega snapshot persistente y bitácora de importaciones EdiNadro."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0012"
down_revision: str | None = "20260813_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "importaciones_nadro",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("cargada_por_usuario_id", sa.String(length=36), nullable=False),
        sa.Column("cargada_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archivo_catalogo", sa.String(length=255), nullable=False),
        sa.Column("sha256_catalogo", sa.String(length=64), nullable=False),
        sa.Column("articulos_cargados", sa.Integer(), nullable=False),
        sa.Column("archivo_ofertas", sa.String(length=255), nullable=False),
        sa.Column("sha256_ofertas", sa.String(length=64), nullable=False),
        sa.Column("ofertas_cargadas", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["cargada_por_usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_importaciones_nadro_cargada_en",
        "importaciones_nadro",
        ["cargada_en"],
        unique=False,
    )

    op.create_table(
        "articulos_nadro",
        sa.Column("codigo_nadro", sa.String(length=8), nullable=False),
        sa.Column("importacion_id", sa.String(length=36), nullable=False),
        sa.Column("descripcion", sa.String(length=200), nullable=False),
        sa.Column("laboratorio", sa.String(length=80), nullable=False),
        sa.Column("codigo_ean", sa.String(length=14), nullable=False),
        sa.Column("familia", sa.String(length=4), nullable=False),
        sa.Column("departamento", sa.String(length=4), nullable=False),
        sa.Column("categoria", sa.String(length=4), nullable=False),
        sa.Column("clave_ssa", sa.String(length=4), nullable=False),
        sa.Column("clasificacion_fiscal", sa.String(length=4), nullable=False),
        sa.Column("requiere_refrigeracion", sa.Boolean(), nullable=True),
        sa.Column("precio_publico_sin_iva", sa.Numeric(14, 2), nullable=False),
        sa.Column("precio_venta_reportado", sa.Numeric(14, 2), nullable=False),
        sa.Column("precio_farmacia_sin_iva", sa.Numeric(14, 2), nullable=False),
        sa.Column("descuento_limitado_pct", sa.Numeric(7, 2), nullable=False),
        sa.Column("fecha_ultimo_movimiento", sa.String(length=6), nullable=False),
        sa.ForeignKeyConstraint(["importacion_id"], ["importaciones_nadro.id"]),
        sa.PrimaryKeyConstraint("codigo_nadro"),
    )
    op.create_index(
        "ix_articulos_nadro_importacion_id",
        "articulos_nadro",
        ["importacion_id"],
        unique=False,
    )
    op.create_index(
        "ix_articulos_nadro_descripcion",
        "articulos_nadro",
        ["descripcion"],
        unique=False,
    )
    op.create_index(
        "ix_articulos_nadro_codigo_ean",
        "articulos_nadro",
        ["codigo_ean"],
        unique=False,
    )
    op.create_index(
        "ix_articulos_nadro_descripcion_codigo",
        "articulos_nadro",
        ["descripcion", "codigo_nadro"],
        unique=False,
    )

    op.create_table(
        "ofertas_nadro",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("importacion_id", sa.String(length=36), nullable=False),
        sa.Column("codigo_nadro", sa.String(length=8), nullable=False),
        sa.Column("descripcion", sa.String(length=200), nullable=False),
        sa.Column("codigo_ean", sa.String(length=14), nullable=False),
        sa.Column("precio_farmacia_sin_iva", sa.Numeric(14, 2), nullable=False),
        sa.Column("cantidad_con_cargo", sa.Integer(), nullable=False),
        sa.Column("descuento_primera_escala_pct", sa.Numeric(7, 2), nullable=False),
        sa.Column("descuento_segunda_escala_pct", sa.Numeric(7, 2), nullable=False),
        sa.Column("cantidad_sin_cargo", sa.Integer(), nullable=False),
        sa.Column("desde_piezas_primera_escala", sa.Integer(), nullable=False),
        sa.Column("desde_piezas_segunda_escala", sa.Integer(), nullable=False),
        sa.Column("descuento_factura_pct", sa.Numeric(7, 2), nullable=False),
        sa.ForeignKeyConstraint(["codigo_nadro"], ["articulos_nadro.codigo_nadro"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["importacion_id"], ["importaciones_nadro.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ofertas_nadro_importacion_id",
        "ofertas_nadro",
        ["importacion_id"],
        unique=False,
    )
    op.create_index(
        "ix_ofertas_nadro_codigo_nadro",
        "ofertas_nadro",
        ["codigo_nadro"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ofertas_nadro_codigo_nadro", table_name="ofertas_nadro")
    op.drop_index("ix_ofertas_nadro_importacion_id", table_name="ofertas_nadro")
    op.drop_table("ofertas_nadro")
    op.drop_index("ix_articulos_nadro_descripcion_codigo", table_name="articulos_nadro")
    op.drop_index("ix_articulos_nadro_codigo_ean", table_name="articulos_nadro")
    op.drop_index("ix_articulos_nadro_descripcion", table_name="articulos_nadro")
    op.drop_index("ix_articulos_nadro_importacion_id", table_name="articulos_nadro")
    op.drop_table("articulos_nadro")
    op.drop_index("ix_importaciones_nadro_cargada_en", table_name="importaciones_nadro")
    op.drop_table("importaciones_nadro")
