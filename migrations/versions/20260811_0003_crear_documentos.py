"""Crea documentos y partidas revisables de una cotización."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0003"
down_revision: str | None = "20260810_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Agrega metadatos documentales y partidas sin almacenar archivos originales."""

    op.create_table(
        "documentos",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("cotizacion_id", sa.String(length=36), nullable=False),
        sa.Column("nombre_original", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("tamano_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("estado", sa.String(length=24), nullable=False),
        sa.Column("tipo_documento", sa.String(length=120), nullable=True),
        sa.Column("memorandum", sa.String(length=180), nullable=True),
        sa.Column("folios", sa.JSON(), nullable=False),
        sa.Column("fecha_documento", sa.String(length=80), nullable=True),
        sa.Column("municipio", sa.String(length=160), nullable=True),
        sa.Column("parece_fragmento", sa.Boolean(), nullable=False),
        sa.Column("senales_fragmento", sa.JSON(), nullable=False),
        sa.Column("modelo_lector", sa.String(length=120), nullable=True),
        sa.Column("error_lector", sa.Text(), nullable=True),
        sa.Column("recibido_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("analizado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revisado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revisado_por_usuario_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["cotizacion_id"], ["cotizaciones.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["revisado_por_usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documentos_cotizacion_id", "documentos", ["cotizacion_id"])
    op.create_index("ix_documentos_estado", "documentos", ["estado"])
    op.create_index("ix_documentos_memorandum", "documentos", ["memorandum"])
    op.create_index("ix_documentos_sha256", "documentos", ["sha256"])

    op.create_table(
        "partidas_documento",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("documento_id", sa.String(length=36), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("producto_solicitado", sa.String(length=500), nullable=True),
        sa.Column("marca_solicitada", sa.String(length=240), nullable=True),
        sa.Column("concentracion", sa.String(length=240), nullable=True),
        sa.Column("forma_farmaceutica_dispositivo", sa.String(length=300), nullable=True),
        sa.Column("presentacion_solicitada", sa.String(length=500), nullable=True),
        sa.Column("cantidad", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("unidad_medida", sa.String(length=160), nullable=True),
        sa.ForeignKeyConstraint(["documento_id"], ["documentos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_partidas_documento_documento_id",
        "partidas_documento",
        ["documento_id"],
    )


def downgrade() -> None:
    """Retira la capa documental sin afectar cotizaciones ni usuarios."""

    op.drop_index("ix_partidas_documento_documento_id", table_name="partidas_documento")
    op.drop_table("partidas_documento")
    op.drop_index("ix_documentos_sha256", table_name="documentos")
    op.drop_index("ix_documentos_memorandum", table_name="documentos")
    op.drop_index("ix_documentos_estado", table_name="documentos")
    op.drop_index("ix_documentos_cotizacion_id", table_name="documentos")
    op.drop_table("documentos")
