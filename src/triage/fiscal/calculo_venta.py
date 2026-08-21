"""Cálculo final de importes desde un precio de venta confirmado y una validación fiscal."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from triage.fiscal.modelos import TratamientoIVA
from triage.fiscal.servicio import ValidacionFiscalActual
from triage.historico.servicio import ProductoHistorico

_DOS_DECIMALES = Decimal("0.01")


@dataclass(frozen=True)
class CalculoFiscalVenta:
    """Importes listos para emitir porque precio y tratamiento fueron confirmados."""

    precio_unitario_sin_iva: Decimal
    subtotal: Decimal
    iva: Decimal
    total: Decimal
    tratamiento_iva: TratamientoIVA
    iva_porcentaje: Decimal | None
    validado: bool = True
    origen_precio: str = "Precio unitario final confirmado manualmente"


def calcular_importes_venta(
    *,
    producto: ProductoHistorico,
    precio_unitario_sin_iva: Decimal | None,
    validacion: ValidacionFiscalActual | None,
) -> CalculoFiscalVenta | None:
    """Aplica sólo una validación fiscal vigente; nunca infiere una tasa."""

    cantidad = producto.partida.cantidad
    if (
        precio_unitario_sin_iva is None
        or validacion is None
        or cantidad is None
        or cantidad <= 0
    ):
        return None

    unitario = Decimal(precio_unitario_sin_iva)
    if not unitario.is_finite() or unitario <= 0:
        return None
    unitario = unitario.quantize(_DOS_DECIMALES, rounding=ROUND_HALF_UP)

    if validacion.tratamiento_iva == TratamientoIVA.EXENTO:
        tasa = Decimal("0")
    else:
        if validacion.iva_porcentaje is None:
            return None
        tasa = Decimal(validacion.iva_porcentaje)
        if not tasa.is_finite() or not Decimal("0") <= tasa <= Decimal("100"):
            return None

    subtotal = (unitario * Decimal(cantidad)).quantize(
        _DOS_DECIMALES,
        rounding=ROUND_HALF_UP,
    )
    iva = (subtotal * tasa / Decimal("100")).quantize(
        _DOS_DECIMALES,
        rounding=ROUND_HALF_UP,
    )
    return CalculoFiscalVenta(
        precio_unitario_sin_iva=unitario,
        subtotal=subtotal,
        iva=iva,
        total=(subtotal + iva).quantize(_DOS_DECIMALES, rounding=ROUND_HALF_UP),
        tratamiento_iva=validacion.tratamiento_iva,
        iva_porcentaje=validacion.iva_porcentaje,
    )
