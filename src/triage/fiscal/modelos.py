"""Eventos append-only de validación fiscal por producto exacto."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from triage.base_datos import Base
from triage.cotizaciones.modelos import ahora_utc


class EstadoValidacionFiscal(StrEnum):
    """Una validación se retira agregando un evento pendiente, no reescribiéndola."""

    VALIDADA = "VALIDADA"
    PENDIENTE = "PENDIENTE"


class TratamientoIVA(StrEnum):
    """Distingue tasa cero de exención para no perder semántica fiscal."""

    TASA = "TASA"
    EXENTO = "EXENTO"


class FuenteValidacionFiscal(StrEnum):
    """Explica si la persona confirmó la propuesta o registró una corrección."""

    SUGERENCIA_CONFIRMADA = "SUGERENCIA_CONFIRMADA"
    CORRECCION_HUMANA = "CORRECCION_HUMANA"
    RETIRO_HUMANO = "RETIRO_HUMANO"


class ValidacionFiscalPartida(Base):
    """Evento inmutable asociado a la identidad exacta vigente al decidir."""

    __tablename__ = "validaciones_fiscales_partida"

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
    tratamiento_iva: Mapped[str | None] = mapped_column(String(24), nullable=True)
    iva_porcentaje: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    version_motor: Mapped[str] = mapped_column(String(64), nullable=False)
    sugerencia_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
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
