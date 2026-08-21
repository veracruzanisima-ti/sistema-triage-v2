"""Eventos append-only para validar el precio final unitario de venta."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from triage.base_datos import Base
from triage.cotizaciones.modelos import ahora_utc


class EstadoPrecioVenta(StrEnum):
    VALIDADO = "VALIDADO"
    PENDIENTE = "PENDIENTE"


class FuenteDecisionPrecioVenta(StrEnum):
    CAPTURA_MANUAL = "CAPTURA_MANUAL"
    RETIRO_HUMANO = "RETIRO_HUMANO"


class PrecioFinalVentaPartida(Base):
    """Decisión comercial inmutable ligada a la identidad exacta vigente."""

    __tablename__ = "precios_finales_venta_partida"

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
    partida_documento_id: Mapped[str | None] = mapped_column(
        ForeignKey("partidas_documento.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    clave_producto: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    estado: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    precio_unitario_sin_iva: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2),
        nullable=True,
    )
    fuente_comercial: Mapped[str | None] = mapped_column(String(300), nullable=True)
    observacion: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fuente_decision: Mapped[str] = mapped_column(String(40), nullable=False)
    validada_por_usuario_id: Mapped[str] = mapped_column(
        ForeignKey("usuarios.id"),
        nullable=False,
    )
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=ahora_utc,
        index=True,
    )
