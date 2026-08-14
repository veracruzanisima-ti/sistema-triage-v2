"""Snapshot normalizado del catálogo EdiNadro y trazabilidad de sus cargas."""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from triage.base_datos import Base
from triage.cotizaciones.modelos import ahora_utc


class ImportacionNadro(Base):
    """Bitácora append-only de una actualización del catálogo NADRO."""

    __tablename__ = "importaciones_nadro"

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
    archivo_catalogo: Mapped[str] = mapped_column(String(255), nullable=False)
    sha256_catalogo: Mapped[str] = mapped_column(String(64), nullable=False)
    articulos_cargados: Mapped[int] = mapped_column(Integer, nullable=False)
    archivo_ofertas: Mapped[str] = mapped_column(String(255), nullable=False)
    sha256_ofertas: Mapped[str] = mapped_column(String(64), nullable=False)
    ofertas_cargadas: Mapped[int] = mapped_column(Integer, nullable=False)


class ArticuloNadro(Base):
    """Artículo del snapshot NADRO actualmente consultable por Triage."""

    __tablename__ = "articulos_nadro"

    codigo_nadro: Mapped[str] = mapped_column(String(8), primary_key=True)
    importacion_id: Mapped[str] = mapped_column(
        ForeignKey("importaciones_nadro.id"),
        nullable=False,
        index=True,
    )
    descripcion: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    laboratorio: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    codigo_ean: Mapped[str] = mapped_column(String(14), nullable=False, default="", index=True)
    familia: Mapped[str] = mapped_column(String(4), nullable=False, default="")
    departamento: Mapped[str] = mapped_column(String(4), nullable=False, default="")
    categoria: Mapped[str] = mapped_column(String(4), nullable=False, default="")
    clave_ssa: Mapped[str] = mapped_column(String(4), nullable=False, default="")
    clasificacion_fiscal: Mapped[str] = mapped_column(String(4), nullable=False, default="")
    requiere_refrigeracion: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    precio_publico_sin_iva: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    precio_venta_reportado: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    precio_farmacia_sin_iva: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    descuento_limitado_pct: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    fecha_ultimo_movimiento: Mapped[str] = mapped_column(String(6), nullable=False, default="")

    __table_args__ = (
        Index("ix_articulos_nadro_descripcion_codigo", "descripcion", "codigo_nadro"),
    )


class OfertaNadro(Base):
    """Oferta vigente del snapshot, separada del precio estable del artículo."""

    __tablename__ = "ofertas_nadro"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    importacion_id: Mapped[str] = mapped_column(
        ForeignKey("importaciones_nadro.id"),
        nullable=False,
        index=True,
    )
    codigo_nadro: Mapped[str] = mapped_column(
        ForeignKey("articulos_nadro.codigo_nadro", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    descripcion: Mapped[str] = mapped_column(String(200), nullable=False)
    codigo_ean: Mapped[str] = mapped_column(String(14), nullable=False, default="")
    precio_farmacia_sin_iva: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    cantidad_con_cargo: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    descuento_primera_escala_pct: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    descuento_segunda_escala_pct: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    cantidad_sin_cargo: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    desde_piezas_primera_escala: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    desde_piezas_segunda_escala: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    descuento_factura_pct: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
