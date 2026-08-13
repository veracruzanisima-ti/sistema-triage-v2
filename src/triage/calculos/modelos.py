from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from triage.base_datos import Base
from triage.cotizaciones.modelos import ahora_utc


class CalculoComercial(Base):
    __tablename__ = "calculos_comerciales"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    cotizacion_id: Mapped[str] = mapped_column(ForeignKey("cotizaciones.id", ondelete="CASCADE"), nullable=False, index=True)
    partida_documento_id: Mapped[str | None] = mapped_column(ForeignKey("partidas_documento.id", ondelete="SET NULL"), nullable=True, index=True)
    clave_producto: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    referencia_estable_id: Mapped[str | None] = mapped_column(ForeignKey("observaciones_precio.id", ondelete="SET NULL"), nullable=True)
    oportunidad_adquisicion_id: Mapped[str | None] = mapped_column(ForeignKey("observaciones_precio.id", ondelete="SET NULL"), nullable=True)
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    costo_referencia_antes_iva: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    costo_adquisicion_antes_iva: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    markup_porcentaje: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    iva_venta_porcentaje: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    precio_unitario_antes_iva: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    iva_unitario: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    precio_unitario_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    subtotal_pedido_antes_iva: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    iva_pedido: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    total_pedido: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    diferencia_bruta_estimada_antes_iva: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    calculado_por_usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=ahora_utc, index=True)
