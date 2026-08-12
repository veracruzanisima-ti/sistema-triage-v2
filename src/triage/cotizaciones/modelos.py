"""Modelos persistentes del flujo básico de cotización."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from triage.base_datos import Base


class EstadoCotizacion(StrEnum):
    """Estados simples visibles para el equipo durante el MVP."""

    EN_PROCESO = "EN_PROCESO"
    PENDIENTE_REVISION = "PENDIENTE_REVISION"
    FINALIZADA = "FINALIZADA"


def ahora_utc() -> datetime:
    """Genera marcas de tiempo comparables independientemente del despliegue."""

    return datetime.now(UTC)


class Cotizacion(Base):
    """Unidad de trabajo que puede ser retomada por otra sesión."""

    __tablename__ = "cotizaciones"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    referencia: Mapped[str | None] = mapped_column(String(160), nullable=True)
    referencia_fijada_manual: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    estado: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=EstadoCotizacion.EN_PROCESO.value,
        index=True,
    )
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=ahora_utc,
    )
    actualizada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=ahora_utc,
        onupdate=ahora_utc,
    )
