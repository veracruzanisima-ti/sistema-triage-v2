"""crear revisiones append-only de calculo comercial

Revision ID: 20260813_0010
Revises: 20260813_0009
"""

from alembic import op
import sqlalchemy as sa

revision = "20260813_0010"
down_revision = "20260813_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "calculos_comerciales",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("cotizacion_id", sa.String(length=36), nullable=False),
        sa.Column("partida_documento_id", sa.String(length=36), nullable=True),
        sa.Column("clave_producto", sa.String(length=64), nullable=False),
        sa.Column("referencia_estable_id", sa.String(length=36), nullable=True),
        sa.Column("oportunidad_adquisicion_id", sa.String(length=36), nullable=True),
        sa.Column("cantidad", sa.Numeric(12, 3), nullable=False),
        sa.Column("costo_referencia_antes_iva", sa.Numeric(14, 2), nullable=False),
        sa.Column("costo_adquisicion_antes_iva", sa.Numeric(14, 2), nullable=True),
        sa.Column("markup_porcentaje", sa.Numeric(7, 2), nullable=False),
        sa.Column("iva_venta_porcentaje", sa.Numeric(5, 2), nullable=False),
        sa.Column("precio_unitario_antes_iva", sa.Numeric(14, 2), nullable=False),
        sa.Column("iva_unitario", sa.Numeric(14, 2), nullable=False),
        sa.Column("precio_unitario_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("subtotal_pedido_antes_iva", sa.Numeric(16, 2), nullable=False),
        sa.Column("iva_pedido", sa.Numeric(16, 2), nullable=False),
        sa.Column("total_pedido", sa.Numeric(16, 2), nullable=False),
        sa.Column("diferencia_bruta_estimada_antes_iva", sa.Numeric(16, 2), nullable=True),
        sa.Column("calculado_por_usuario_id", sa.String(length=36), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cotizacion_id"], ["cotizaciones.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["partida_documento_id"], ["partidas_documento.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["referencia_estable_id"], ["observaciones_precio.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["oportunidad_adquisicion_id"], ["observaciones_precio.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["calculado_por_usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_calculos_comerciales_cotizacion_id", "calculos_comerciales", ["cotizacion_id"])
    op.create_index("ix_calculos_comerciales_partida_documento_id", "calculos_comerciales", ["partida_documento_id"])
    op.create_index("ix_calculos_comerciales_clave_producto", "calculos_comerciales", ["clave_producto"])
    op.create_index("ix_calculos_comerciales_creado_en", "calculos_comerciales", ["creado_en"])


def downgrade() -> None:
    op.drop_index("ix_calculos_comerciales_creado_en", table_name="calculos_comerciales")
    op.drop_index("ix_calculos_comerciales_clave_producto", table_name="calculos_comerciales")
    op.drop_index("ix_calculos_comerciales_partida_documento_id", table_name="calculos_comerciales")
    op.drop_index("ix_calculos_comerciales_cotizacion_id", table_name="calculos_comerciales")
    op.drop_table("calculos_comerciales")
