"""Crea trazabilidad de intentos de consulta a proveedores."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0008"
down_revision: str | None = "20260813_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Agrega intentos de proveedor sin modificar el histórico append-only."""

    op.create_table(
        "consultas_proveedor",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("cotizacion_id", sa.String(length=36), nullable=False),
        sa.Column("partida_documento_id", sa.String(length=36), nullable=True),
        sa.Column("clave_producto", sa.String(length=64), nullable=False),
        sa.Column("proveedor", sa.String(length=240), nullable=False),
        sa.Column("estado", sa.String(length=24), nullable=False),
        sa.Column("criterios_busqueda", sa.JSON(), nullable=False),
        sa.Column("producto_encontrado", sa.String(length=500), nullable=True),
        sa.Column("precio_antes_iva", sa.Numeric(14, 2), nullable=True),
        sa.Column("iva_porcentaje", sa.Numeric(5, 2), nullable=True),
        sa.Column("precio_total", sa.Numeric(14, 2), nullable=True),
        sa.Column("es_promocion", sa.Boolean(), nullable=False),
        sa.Column("condiciones_promocion", sa.Text(), nullable=True),
        sa.Column("disponibilidad", sa.String(length=200), nullable=True),
        sa.Column("entrega_viable", sa.Boolean(), nullable=True),
        sa.Column("fuente", sa.String(length=500), nullable=True),
        sa.Column("mensaje_error", sa.String(length=300), nullable=True),
        sa.Column("observacion_precio_id", sa.String(length=36), nullable=True),
        sa.Column("ejecutada_por_usuario_id", sa.String(length=36), nullable=False),
        sa.Column("iniciada_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalizada_en", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["cotizacion_id"], ["cotizaciones.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["partida_documento_id"],
            ["partidas_documento.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["observacion_precio_id"],
            ["observaciones_precio.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["ejecutada_por_usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for nombre, columnas in (
        ("ix_consultas_proveedor_cotizacion_id", ["cotizacion_id"]),
        ("ix_consultas_proveedor_partida_documento_id", ["partida_documento_id"]),
        ("ix_consultas_proveedor_clave_producto", ["clave_producto"]),
        ("ix_consultas_proveedor_proveedor", ["proveedor"]),
        ("ix_consultas_proveedor_estado", ["estado"]),
        ("ix_consultas_proveedor_observacion_precio_id", ["observacion_precio_id"]),
        ("ix_consultas_proveedor_iniciada_en", ["iniciada_en"]),
    ):
        op.create_index(nombre, "consultas_proveedor", columnas, unique=False)


def downgrade() -> None:
    """Retira intentos de proveedor conservando observaciones históricas ya creadas."""

    for nombre in (
        "ix_consultas_proveedor_iniciada_en",
        "ix_consultas_proveedor_observacion_precio_id",
        "ix_consultas_proveedor_estado",
        "ix_consultas_proveedor_proveedor",
        "ix_consultas_proveedor_clave_producto",
        "ix_consultas_proveedor_partida_documento_id",
        "ix_consultas_proveedor_cotizacion_id",
    ):
        op.drop_index(nombre, table_name="consultas_proveedor")
    op.drop_table("consultas_proveedor")
