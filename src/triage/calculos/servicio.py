"""Calcula precios de venta desde decisiones humanas ya confirmadas."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from triage.calculos.modelos import CalculoComercial
from triage.historico.modelos import ObservacionPrecio
from triage.revision_final.servicio import ProductoPreCierre, listar_precierre

_CENTAVO = Decimal("0.01")
_CIEN = Decimal("100")


@dataclass(frozen=True)
class ResultadoCalculo:
    precio_unitario_antes_iva: Decimal
    iva_unitario: Decimal
    precio_unitario_total: Decimal
    subtotal_pedido_antes_iva: Decimal
    iva_pedido: Decimal
    total_pedido: Decimal
    diferencia_bruta_estimada_antes_iva: Decimal | None


@dataclass(frozen=True)
class ProductoCalculable:
    precierre: ProductoPreCierre
    calculo_actual: CalculoComercial | None
    puede_calcular: bool
    motivo_bloqueo: str | None


def _moneda(valor: Decimal) -> Decimal:
    return valor.quantize(_CENTAVO, rounding=ROUND_HALF_UP)


def _decimal(valor: Decimal | int | str) -> Decimal:
    return Decimal(str(valor))


def calcular_importes(
    *,
    costo_referencia_antes_iva: Decimal,
    cantidad: Decimal,
    markup_porcentaje: Decimal,
    iva_venta_porcentaje: Decimal,
    costo_adquisicion_antes_iva: Decimal | None = None,
) -> ResultadoCalculo:
    """Hace solo matematica comercial; no decide IVA, proveedor ni markup."""

    costo = _decimal(costo_referencia_antes_iva)
    cantidad = _decimal(cantidad)
    markup = _decimal(markup_porcentaje)
    iva = _decimal(iva_venta_porcentaje)
    costo_adquisicion = (
        _decimal(costo_adquisicion_antes_iva)
        if costo_adquisicion_antes_iva is not None
        else None
    )

    if costo < 0:
        raise ValueError("el costo de referencia no puede ser negativo")
    if cantidad <= 0:
        raise ValueError("la cantidad debe ser mayor que cero")
    if markup < 0 or markup > Decimal("1000"):
        raise ValueError("el markup debe estar entre 0 y 1000 por ciento")
    if iva < 0 or iva > _CIEN:
        raise ValueError("el IVA de venta debe estar entre 0 y 100 por ciento")
    if costo_adquisicion is not None and costo_adquisicion < 0:
        raise ValueError("el costo de adquisicion no puede ser negativo")

    precio_unitario = _moneda(costo * (Decimal("1") + markup / _CIEN))
    iva_unitario = _moneda(precio_unitario * iva / _CIEN)
    total_unitario = _moneda(precio_unitario + iva_unitario)
    subtotal = _moneda(precio_unitario * cantidad)
    iva_pedido = _moneda(iva_unitario * cantidad)
    total = _moneda(subtotal + iva_pedido)
    diferencia = (
        _moneda((precio_unitario - costo_adquisicion) * cantidad)
        if costo_adquisicion is not None
        else None
    )
    return ResultadoCalculo(
        precio_unitario_antes_iva=precio_unitario,
        iva_unitario=iva_unitario,
        precio_unitario_total=total_unitario,
        subtotal_pedido_antes_iva=subtotal,
        iva_pedido=iva_pedido,
        total_pedido=total,
        diferencia_bruta_estimada_antes_iva=diferencia,
    )


def listar_productos_calculo(
    sesion: Session,
    cotizacion_id: str,
) -> list[ProductoCalculable]:
    productos = listar_precierre(sesion, cotizacion_id)
    calculos = list(
        sesion.scalars(
            select(CalculoComercial)
            .where(CalculoComercial.cotizacion_id == cotizacion_id)
            .order_by(CalculoComercial.creado_en.desc())
        )
    )
    actuales: dict[str, CalculoComercial] = {}
    for calculo in calculos:
        if calculo.partida_documento_id:
            actuales.setdefault(calculo.partida_documento_id, calculo)

    resultado: list[ProductoCalculable] = []
    for item in productos:
        partida = item.producto.partida
        referencia = item.referencia
        motivo = None
        if referencia is None:
            motivo = "Falta seleccionar una referencia estable."
        elif referencia.precio_antes_iva is None:
            motivo = "La referencia estable no tiene precio antes de IVA confirmado."
        elif partida.cantidad is None or partida.cantidad <= 0:
            motivo = "Falta confirmar una cantidad mayor que cero."

        actual = actuales.get(partida.id)
        if actual is not None and actual.clave_producto != item.producto.clave_producto:
            actual = None
        resultado.append(
            ProductoCalculable(
                precierre=item,
                calculo_actual=actual,
                puede_calcular=motivo is None,
                motivo_bloqueo=motivo,
            )
        )
    return resultado


def crear_calculo(
    sesion: Session,
    *,
    cotizacion_id: str,
    partida_id: str,
    usuario_id: str,
    markup_porcentaje: Decimal,
    iva_venta_porcentaje: Decimal,
) -> CalculoComercial:
    """Agrega una revision nueva; nunca modifica un calculo anterior."""

    productos = {
        item.precierre.producto.partida.id: item
        for item in listar_productos_calculo(sesion, cotizacion_id)
    }
    producto = productos.get(partida_id)
    if producto is None:
        raise ValueError("la partida ya no esta preparada o dejo de ser elegible")
    if not producto.puede_calcular:
        raise ValueError(producto.motivo_bloqueo or "la partida no esta lista para calcular")

    item = producto.precierre
    referencia = item.referencia
    if referencia is None or referencia.precio_antes_iva is None:
        raise ValueError("falta una referencia estable con precio antes de IVA")

    oportunidad: ObservacionPrecio | None = item.oportunidad
    costo_adquisicion = (
        _decimal(oportunidad.precio_antes_iva)
        if oportunidad is not None and oportunidad.precio_antes_iva is not None
        else None
    )
    cantidad = _decimal(item.producto.partida.cantidad)
    costo_referencia = _decimal(referencia.precio_antes_iva)
    resultado = calcular_importes(
        costo_referencia_antes_iva=costo_referencia,
        cantidad=cantidad,
        markup_porcentaje=markup_porcentaje,
        iva_venta_porcentaje=iva_venta_porcentaje,
        costo_adquisicion_antes_iva=costo_adquisicion,
    )

    calculo = CalculoComercial(
        cotizacion_id=cotizacion_id,
        partida_documento_id=partida_id,
        clave_producto=item.producto.clave_producto,
        referencia_estable_id=referencia.id,
        oportunidad_adquisicion_id=oportunidad.id if oportunidad else None,
        cantidad=cantidad,
        costo_referencia_antes_iva=_moneda(costo_referencia),
        costo_adquisicion_antes_iva=(
            _moneda(costo_adquisicion) if costo_adquisicion is not None else None
        ),
        markup_porcentaje=_decimal(markup_porcentaje),
        iva_venta_porcentaje=_decimal(iva_venta_porcentaje),
        precio_unitario_antes_iva=resultado.precio_unitario_antes_iva,
        iva_unitario=resultado.iva_unitario,
        precio_unitario_total=resultado.precio_unitario_total,
        subtotal_pedido_antes_iva=resultado.subtotal_pedido_antes_iva,
        iva_pedido=resultado.iva_pedido,
        total_pedido=resultado.total_pedido,
        diferencia_bruta_estimada_antes_iva=(
            resultado.diferencia_bruta_estimada_antes_iva
        ),
        calculado_por_usuario_id=usuario_id,
    )
    sesion.add(calculo)
    sesion.commit()
    sesion.refresh(calculo)
    return calculo
