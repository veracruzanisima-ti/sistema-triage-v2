"""Eventos append-only para el precio unitario final confirmado por una persona."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from triage.base_datos import Base
from triage.cotizaciones.modelos import ahora_utc


class EstadoPrecioVenta(StrEnum):
    """El precio vigente se retira agregando un evento, nunca borrando el anterior."""

    VALIDADO = "VALIDADO"
    PENDIENTE = "PENDIENTE"


class FuentePrecioVenta(StrEnum):
    """Origen explícito de la decisión comercial por partida."""

    CAPTURA_HUMANA = "CAPTURA_HUMANA"
    RETIRO_HUMANO = "RETIRO_HUMANO"


class PrecioVentaPartida(Base):
    """Precio final sin IVA confirmado para una identidad exacta de producto."""

    __tablename__ = "precios_venta_partida"

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
        Numeric(precision=14, scale=2),
        nullable=True,
    )
    referencia_estable_id: Mapped[str | None] = mapped_column(
        ForeignKey("observaciones_precio.id", ondelete="SET NULL"),
        nullable=True,
    )
    observacion: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fuente_decision: Mapped[str] = mapped_column(String(40), nullable=False)
    validado_por_usuario_id: Mapped[str] = mapped_column(
        ForeignKey("usuarios.id"),
        nullable=False,
    )
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=ahora_utc,
        index=True,
    )
