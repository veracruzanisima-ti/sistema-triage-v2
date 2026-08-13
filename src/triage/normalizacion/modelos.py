"""Datos separados de la solicitud original usados para búsquedas de producto."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from triage.base_datos import Base
from triage.cotizaciones.modelos import ahora_utc


class NormalizacionPartida(Base):
    """Copia operativa confirmada por una persona para búsquedas posteriores."""

    __tablename__ = "normalizaciones_partida"

    partida_documento_id: Mapped[str] = mapped_column(
        ForeignKey("partidas_documento.id", ondelete="CASCADE"),
        primary_key=True,
    )
    producto: Mapped[str | None] = mapped_column(String(500), nullable=True)
    marca: Mapped[str | None] = mapped_column(String(240), nullable=True)
    concentracion: Mapped[str | None] = mapped_column(String(240), nullable=True)
    forma_dispositivo: Mapped[str | None] = mapped_column(String(300), nullable=True)
    presentacion: Mapped[str | None] = mapped_column(String(500), nullable=True)
    confirmada_por_usuario_id: Mapped[str] = mapped_column(
        ForeignKey("usuarios.id"),
        nullable=False,
    )
    actualizada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=ahora_utc,
        onupdate=ahora_utc,
    )
