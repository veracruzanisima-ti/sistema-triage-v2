"""Cálculos fiscales sobre un precio comercial explícitamente validado."""

from decimal import ROUND_HALF_UP, Decimal

from triage.fiscal.modelos import TratamientoIVA
from triage.fiscal.servicio import BorradorCalculoFiscal, ValidacionFiscalActual
from triage.historico.servicio import ProductoHistorico

_DOS_DECIMALES = Decimal("0.01")


def calcular_importes_desde_precio_final(
    *,
    producto: ProductoHistorico,
    precio_unitario_sin_iva: Decimal,
    validacion: ValidacionFiscalActual | None,
    origen_precio: str,
) -> BorradorCalculoFiscal | None:
    """Aplica sólo el tratamiento fiscal ya validado al precio comercial recibido."""

    cantidad = producto.partida.cantidad
    if validacion is None or cantidad is None or cantidad <= 0:
        return None

    unitario = Decimal(precio_unitario_sin_iva).quantize(
        _DOS_DECIMALES,
        rounding=ROUND_HALF_UP,
    )
    if unitario <= 0:
        return None

    tratamiento = validacion.tratamiento_iva
    tasa = (
        validacion.iva_porcentaje
        if tratamiento == TratamientoIVA.TASA
        else Decimal("0")
    )
    if tasa is None:
        return None

    subtotal = (unitario * Decimal(cantidad)).quantize(
        _DOS_DECIMALES,
        rounding=ROUND_HALF_UP,
    )
    iva = (subtotal * Decimal(tasa) / Decimal("100")).quantize(
        _DOS_DECIMALES,
        rounding=ROUND_HALF_UP,
    )
    return BorradorCalculoFiscal(
        precio_unitario_sin_iva=unitario,
        subtotal=subtotal,
        iva=iva,
        total=(subtotal + iva).quantize(_DOS_DECIMALES, rounding=ROUND_HALF_UP),
        tratamiento_iva=tratamiento,
        iva_porcentaje=validacion.iva_porcentaje,
        validado=True,
        origen_precio=origen_precio,
    )
