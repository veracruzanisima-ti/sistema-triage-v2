"""Decisiones humanas append-only sobre la evidencia de precios."""

from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from triage.base_datos import Base
from triage.cotizaciones.modelos import ahora_utc


class RolDecisionPrecio(StrEnum):
    """Uso que una persona asigna a una observación de precio."""

    REFERENCIA_ESTABLE = "REFERENCIA_ESTABLE"
    OPORTUNIDAD_ADQUISICION = "OPORTUNIDAD_ADQUISICION"


class DecisionPrecio(Base):
    """Evento inmutable: seleccionar o retirar evidencia para un rol comercial."""

    __tablename__ = "decisiones_precio"

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
    rol: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    observacion_precio_id: Mapped[str | None] = mapped_column(
        ForeignKey("observaciones_precio.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    decidida_por_usuario_id: Mapped[str] = mapped_column(
        ForeignKey("usuarios.id"),
        nullable=False,
    )
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=ahora_utc,
        index=True,
    )
