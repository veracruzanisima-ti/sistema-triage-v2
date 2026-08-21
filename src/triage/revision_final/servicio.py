"""Consolida productos preparados y evidencia elegida antes del cierre."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from triage.comercial.modelos import EstadoComercial
from triage.comercial.precios_venta_servicio import (
    PrecioVentaActual,
    listar_precios_venta_actuales,
)
from triage.comercial.servicio import (
    DecisionComercialActual,
    decision_cotizable_por_defecto,
    listar_decisiones_comerciales_actuales,
)
from triage.fiscal.calculos import calcular_importes_desde_precio_final
from triage.fiscal.servicio import (
    BorradorCalculoFiscal,
    SugerenciaFiscal,
    ValidacionFiscalActual,
    calcular_borrador_fiscal,
    construir_sugerencia_fiscal,
    listar_validaciones_fiscales_actuales,
)
from triage.historico.decisiones_servicio import listar_selecciones_actuales
from triage.historico.modelos import ObservacionPrecio
from triage.historico.servicio import ProductoHistorico, listar_productos_historico
from triage.restricciones.servicio import AlertaRestriccion, evaluar_partida


@dataclass(frozen=True)
class ProductoPreCierre:
    producto: ProductoHistorico
    referencia: ObservacionPrecio | None
    oportunidad: ObservacionPrecio | None
    decision_comercial: DecisionComercialActual
    sugerencia_fiscal: SugerenciaFiscal
    validacion_fiscal: ValidacionFiscalActual | None
    precio_venta: PrecioVentaActual | None
    calculo_fiscal: BorradorCalculoFiscal | None
    calculo_final: BorradorCalculoFiscal | None
    alertas: tuple[AlertaRestriccion, ...]
    pendientes: tuple[str, ...]


def listar_precierre(sesion: Session, cotizacion_id: str) -> list[ProductoPreCierre]:
    """Presenta evidencia y decisiones humanas sin inventar precio final ni tasa."""

    productos = listar_productos_historico(sesion, cotizacion_id)
    selecciones = listar_selecciones_actuales(sesion, cotizacion_id)
    decisiones_comerciales = listar_decisiones_comerciales_actuales(sesion, cotizacion_id)
    validaciones_fiscales = listar_validaciones_fiscales_actuales(
        sesion,
        cotizacion_id=cotizacion_id,
        productos=productos,
    )
    precios_venta = listar_precios_venta_actuales(
        sesion,
        cotizacion_id=cotizacion_id,
        productos=productos,
    )
    ids = {
        observacion_id
        for seleccion in selecciones.values()
        for observacion_id in (
            seleccion.referencia_estable_id,
            seleccion.oportunidad_adquisicion_id,
        )
        if observacion_id
    }
    observaciones = (
        {
            observacion.id: observacion
            for observacion in sesion.scalars(
                select(ObservacionPrecio).where(ObservacionPrecio.id.in_(ids))
            )
        }
        if ids
        else {}
    )
    resultado: list[ProductoPreCierre] = []
    for producto in productos:
        decision_comercial = decisiones_comerciales.get(
            producto.partida.id,
            decision_cotizable_por_defecto(),
        )
        seleccion = selecciones.get(producto.partida.id)
        referencia = (
            observaciones.get(seleccion.referencia_estable_id)
            if seleccion and seleccion.referencia_estable_id
            else None
        )
        oportunidad = (
            observaciones.get(seleccion.oportunidad_adquisicion_id)
            if seleccion and seleccion.oportunidad_adquisicion_id
            else None
        )
        sugerencia_fiscal = construir_sugerencia_fiscal(
            sesion,
            cotizacion_id=cotizacion_id,
            producto=producto,
            referencia=referencia,
        )
        validacion_fiscal = validaciones_fiscales.get(producto.partida.id)
        precio_venta = precios_venta.get(producto.partida.id)
        calculo_fiscal = calcular_borrador_fiscal(
            producto=producto,
            referencia=referencia,
            sugerencia=sugerencia_fiscal,
            validacion=validacion_fiscal,
        )
        calculo_final = (
            calcular_importes_desde_precio_final(
                producto=producto,
                precio_unitario_sin_iva=precio_venta.precio_unitario_sin_iva,
                validacion=validacion_fiscal,
                origen_precio=f"Precio final manual validado: {precio_venta.fuente_comercial}",
            )
            if precio_venta is not None
            else None
        )
        pendientes_lista: list[str] = []
        if decision_comercial.estado == EstadoComercial.COTIZABLE:
            if referencia is None:
                pendientes_lista.append("Seleccionar referencia estable")
            if validacion_fiscal is None:
                pendientes_lista.append("Validar tratamiento fiscal")
            if precio_venta is None:
                pendientes_lista.append("Definir precio final unitario sin IVA")
        resultado.append(
            ProductoPreCierre(
                producto=producto,
                referencia=referencia,
                oportunidad=oportunidad,
                decision_comercial=decision_comercial,
                sugerencia_fiscal=sugerencia_fiscal,
                validacion_fiscal=validacion_fiscal,
                precio_venta=precio_venta,
                calculo_fiscal=calculo_fiscal,
                calculo_final=calculo_final,
                alertas=evaluar_partida(producto.partida),
                pendientes=tuple(pendientes_lista),
            )
        )
    return resultado
