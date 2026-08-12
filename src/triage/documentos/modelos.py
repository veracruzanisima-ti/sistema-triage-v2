"""Modelos persistentes para documentos y su revisión humana."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from triage.base_datos import Base
from triage.cotizaciones.modelos import ahora_utc


class EstadoDocumento(StrEnum):
    """Estados mínimos del procesamiento documental."""

    RECIBIDO = "RECIBIDO"
    ANALIZADO = "ANALIZADO"
    ERROR = "ERROR"
    REVISADO = "REVISADO"


class Documento(Base):
    """Metadatos y extracción de una fuente; el archivo original aún no se conserva."""

    __tablename__ = "documentos"
    __table_args__ = (
        UniqueConstraint(
            "cotizacion_id",
            "clave_idempotencia",
            name="uq_documentos_cotizacion_idempotencia",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    cotizacion_id: Mapped[str] = mapped_column(
        ForeignKey("cotizaciones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nombre_original: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    tamano_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    clave_idempotencia: Mapped[str | None] = mapped_column(String(80), nullable=True)
    estado: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=EstadoDocumento.RECIBIDO.value,
        index=True,
    )
    tipo_documento: Mapped[str | None] = mapped_column(String(120), nullable=True)
    memorandum: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    folios: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    fecha_documento: Mapped[str | None] = mapped_column(String(80), nullable=True)
    municipio: Mapped[str | None] = mapped_column(String(160), nullable=True)
    parece_fragmento: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    senales_fragmento: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    modelo_lector: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_lector: Mapped[str | None] = mapped_column(Text, nullable=True)
    recibido_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=ahora_utc,
    )
    analizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revisado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revisado_por_usuario_id: Mapped[str | None] = mapped_column(
        ForeignKey("usuarios.id"),
        nullable=True,
    )


class PartidaDocumento(Base):
    """Partida editable obtenida del documento antes de normalizar el producto."""

    __tablename__ = "partidas_documento"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    documento_id: Mapped[str] = mapped_column(
        ForeignKey("documentos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    producto_solicitado: Mapped[str | None] = mapped_column(String(500), nullable=True)
    marca_solicitada: Mapped[str | None] = mapped_column(String(240), nullable=True)
    concentracion: Mapped[str | None] = mapped_column(String(240), nullable=True)
    forma_farmaceutica_dispositivo: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
    )
    presentacion_solicitada: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cantidad: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    unidad_medida: Mapped[str | None] = mapped_column(String(160), nullable=True)
    incluida_cotizacion: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    motivo_exclusion: Mapped[str | None] = mapped_column(String(300), nullable=True)
