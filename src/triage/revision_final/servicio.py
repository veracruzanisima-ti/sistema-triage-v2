"""Consolida productos preparados y evidencia elegida antes del cierre."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from triage.historico.decisiones_servicio import listar_selecciones_actuales
from triage.historico.modelos import ObservacionPrecio
from triage.historico.servicio import ProductoHistorico, listar_productos_historico
from triage.restricciones.servicio import AlertaRestriccion, evaluar_partida


@dataclass(frozen=True)
class ProductoPreCierre:
    producto: ProductoHistorico
    referencia: ObservacionPrecio | None
    oportunidad: ObservacionPrecio | None
    alertas: tuple[AlertaRestriccion, ...]
    pendientes: tuple[str, ...]


def listar_precierre(sesion: Session, cotizacion_id: str) -> list[ProductoPreCierre]:
    """Presenta evidencia; no aprueba ni rechaza partidas automáticamente."""

    productos = listar_productos_historico(sesion, cotizacion_id)
    selecciones = listar_selecciones_actuales(sesion, cotizacion_id)
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
        pendientes = () if referencia else ("Seleccionar referencia estable",)
        resultado.append(
            ProductoPreCierre(
                producto=producto,
                referencia=referencia,
                oportunidad=oportunidad,
                alertas=evaluar_partida(producto.partida),
                pendientes=pendientes,
            )
        )
    return resultado
