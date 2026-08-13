"""Trazabilidad persistente de cada intento de consulta a proveedores."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from triage.base_datos import Base
from triage.cotizaciones.modelos import ahora_utc


class EstadoConsultaProveedor(StrEnum):
    """Resultado operativo de un intento de consulta."""

    INICIADA = "INICIADA"
    EXITOSA = "EXITOSA"
    NO_ENCONTRADO = "NO_ENCONTRADO"
    ERROR = "ERROR"


class ConsultaProveedor(Base):
    """Intento inmutable en intención y trazable aunque no produzca precio."""

    __tablename__ = "consultas_proveedor"

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
    proveedor: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    estado: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=EstadoConsultaProveedor.INICIADA.value,
        index=True,
    )
    criterios_busqueda: Mapped[dict] = mapped_column(JSON, nullable=False)
    producto_encontrado: Mapped[str | None] = mapped_column(String(500), nullable=True)
    precio_antes_iva: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    iva_porcentaje: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    precio_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    es_promocion: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    condiciones_promocion: Mapped[str | None] = mapped_column(Text, nullable=True)
    disponibilidad: Mapped[str | None] = mapped_column(String(200), nullable=True)
    entrega_viable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    fuente: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mensaje_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    observacion_precio_id: Mapped[str | None] = mapped_column(
        ForeignKey("observaciones_precio.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ejecutada_por_usuario_id: Mapped[str] = mapped_column(
        ForeignKey("usuarios.id"),
        nullable=False,
    )
    iniciada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=ahora_utc,
        index=True,
    )
    finalizada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
