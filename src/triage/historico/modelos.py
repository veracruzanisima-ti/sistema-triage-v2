"""Persistencia append-only de precios observados en fuentes externas."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from triage.base_datos import Base
from triage.cotizaciones.modelos import ahora_utc
from triage.historico.disponibilidad import resolver_disponibilidad_operativa

LIMITE_PROVEEDOR_OBSERVACION = 240
LIMITE_PRODUCTO_OBSERVADO = 700
LIMITE_FUENTE_OBSERVACION = 500


class OrigenObservacionPrecio(StrEnum):
    """Distingue cómo llegó la evidencia sin cambiar su naturaleza append-only."""

    MANUAL = "MANUAL"
    ADAPTADOR = "ADAPTADOR"
    WEB = "WEB"


class ObservacionPrecio(Base):
    """Fotografía inmutable de un precio observado para un producto exacto."""

    __tablename__ = "observaciones_precio"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    clave_producto: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    normalizacion_partida_id: Mapped[str | None] = mapped_column(
        ForeignKey("normalizaciones_partida.partida_documento_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    producto: Mapped[str | None] = mapped_column(String(500), nullable=True)
    marca: Mapped[str | None] = mapped_column(String(240), nullable=True)
    concentracion: Mapped[str | None] = mapped_column(String(240), nullable=True)
    forma_dispositivo: Mapped[str | None] = mapped_column(String(300), nullable=True)
    presentacion: Mapped[str | None] = mapped_column(String(500), nullable=True)
    producto_observado: Mapped[str | None] = mapped_column(
        String(LIMITE_PRODUCTO_OBSERVADO),
        nullable=True,
    )
    origen: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    proveedor: Mapped[str] = mapped_column(
        String(LIMITE_PROVEEDOR_OBSERVACION),
        nullable=False,
        index=True,
    )
    precio_antes_iva: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    iva_porcentaje: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    precio_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    es_promocion: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    condiciones_promocion: Mapped[str | None] = mapped_column(Text, nullable=True)
    disponibilidad: Mapped[str | None] = mapped_column(String(200), nullable=True)
    entrega_viable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    codigo_postal: Mapped[str | None] = mapped_column(String(5), nullable=True)
    fuente: Mapped[str] = mapped_column(String(LIMITE_FUENTE_OBSERVACION), nullable=False)
    evidencia_identidad: Mapped[dict[str, object] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    observado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=ahora_utc,
        index=True,
    )
    capturada_por_usuario_id: Mapped[str] = mapped_column(
        ForeignKey("usuarios.id"),
        nullable=False,
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=ahora_utc,
    )

    @property
    def disponibilidad_operativa(self) -> bool | None:
        """Deriva disponibilidad sólo para evidencia WEB; conserva manual/adaptador explícitos."""

        if self.origen != OrigenObservacionPrecio.WEB.value:
            return self.entrega_viable
        return resolver_disponibilidad_operativa(
            entrega_viable=self.entrega_viable,
            disponibilidad=self.disponibilidad,
        )
