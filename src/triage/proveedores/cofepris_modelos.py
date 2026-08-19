"""Snapshot local y bitácora de importaciones del registro público COFEPRIS."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from triage.base_datos import Base
from triage.cotizaciones.modelos import ahora_utc


class ImportacionCofepris(Base):
    """Bitácora append-only de una actualización completa del snapshot."""

    __tablename__ = "importaciones_cofepris"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    cargada_por_usuario_id: Mapped[str] = mapped_column(
        ForeignKey("usuarios.id"),
        nullable=False,
    )
    cargada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=ahora_utc,
        index=True,
    )
    archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    registros_cargados: Mapped[int] = mapped_column(Integer, nullable=False)
    registros_vigentes: Mapped[int] = mapped_column(Integer, nullable=False)


class RegistroCofepris(Base):
    """Registro sanitario del snapshot actualmente disponible para identidad."""

    __tablename__ = "registros_cofepris"

    numero_registro: Mapped[str] = mapped_column(String(255), primary_key=True)
    importacion_id: Mapped[str] = mapped_column(
        ForeignKey("importaciones_cofepris.id"),
        nullable=False,
        index=True,
    )
    denominacion_distintiva: Mapped[str] = mapped_column(Text, nullable=False)
    denominacion_distintiva_normalizada: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    denominacion_generica: Mapped[str] = mapped_column(Text, nullable=False)
    componentes_genericos_normalizados: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
    )
    estado: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    forma_farmaceutica: Mapped[str | None] = mapped_column(Text, nullable=True)
    via_administracion: Mapped[str | None] = mapped_column(Text, nullable=True)
    tipo_medicamento: Mapped[str | None] = mapped_column(Text, nullable=True)
    presentacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    cantidad: Mapped[str | None] = mapped_column(Text, nullable=True)
    fraccion_sanitaria: Mapped[str | None] = mapped_column(Text, nullable=True)
    sustancia_quimica: Mapped[str | None] = mapped_column(Text, nullable=True)
    titular: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_emision: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_registros_cofepris_distintiva_estado",
            "denominacion_distintiva_normalizada",
            "estado",
        ),
    )
