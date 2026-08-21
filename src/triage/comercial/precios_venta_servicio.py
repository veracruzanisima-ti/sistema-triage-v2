"""Registro y consulta del precio final de venta validado por una persona."""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from triage.comercial.precios_venta_modelos import (
    EstadoPrecioVenta,
    FuenteDecisionPrecioVenta,
    PrecioFinalVentaPartida,
)
from triage.comercial.servicio import asegurar_partida_cotizable
from triage.historico.servicio import ProductoHistorico, listar_productos_historico
from triage.usuarios.modelos import Usuario

_DOS_DECIMALES = Decimal("0.01")


@dataclass(frozen=True)
class PrecioVentaActual:
    precio_unitario_sin_iva: Decimal
    fuente_comercial: str
    observacion: str | None
    fuente_decision: str
    validada_por_nombre: str | None
    creada_en: datetime


def _limpiar(valor: str | None) -> str | None:
    if valor is None:
        return None
    limpio = " ".join(valor.split())
    return limpio or None


def _producto_actual(
    sesion: Session,
    *,
    cotizacion_id: str,
    partida_id: str,
) -> ProductoHistorico:
    producto = next(
        (
            candidato
            for candidato in listar_productos_historico(sesion, cotizacion_id)
            if candidato.partida.id == partida_id
        ),
        None,
    )
    if producto is None:
        raise ValueError("la partida ya no está preparada o dejó de ser elegible")
    return producto


def _ultimos_eventos_por_partida(
    sesion: Session,
) -> dict[tuple[str, str], PrecioFinalVentaPartida]:
    ultimos: dict[tuple[str, str], PrecioFinalVentaPartida] = {}
    for evento in sesion.scalars(
        select(PrecioFinalVentaPartida).order_by(
            PrecioFinalVentaPartida.creada_en.desc(),
            PrecioFinalVentaPartida.id.desc(),
        )
    ):
        if evento.partida_documento_id:
            ultimos.setdefault(
                (evento.cotizacion_id, evento.partida_documento_id),
                evento,
            )
    return ultimos


def listar_precios_venta_actuales(
    sesion: Session,
    *,
    cotizacion_id: str,
    productos: list[ProductoHistorico],
) -> dict[str, PrecioVentaActual]:
    """Sólo conserva el precio si pertenece a la identidad exacta vigente."""

    por_partida = {
        partida_id: evento
        for (evento_cotizacion, partida_id), evento in _ultimos_eventos_por_partida(
            sesion
        ).items()
        if evento_cotizacion == cotizacion_id
    }
    vigentes = {
        producto.partida.id: por_partida[producto.partida.id]
        for producto in productos
        if producto.partida.id in por_partida
        and por_partida[producto.partida.id].clave_producto == producto.clave_producto
        and por_partida[producto.partida.id].estado == EstadoPrecioVenta.VALIDADO.value
        and por_partida[producto.partida.id].precio_unitario_sin_iva is not None
        and por_partida[producto.partida.id].fuente_comercial
    }
    usuarios_ids = {evento.validada_por_usuario_id for evento in vigentes.values()}
    nombres = (
        {
            usuario.id: usuario.nombre
            for usuario in sesion.scalars(select(Usuario).where(Usuario.id.in_(usuarios_ids)))
        }
        if usuarios_ids
        else {}
    )
    return {
        partida_id: PrecioVentaActual(
            precio_unitario_sin_iva=Decimal(evento.precio_unitario_sin_iva),
            fuente_comercial=evento.fuente_comercial or "",
            observacion=evento.observacion,
            fuente_decision=evento.fuente_decision,
            validada_por_nombre=nombres.get(evento.validada_por_usuario_id),
            creada_en=evento.creada_en,
        )
        for partida_id, evento in vigentes.items()
    }


def registrar_precio_venta(
    sesion: Session,
    *,
    cotizacion_id: str,
    partida_id: str,
    usuario_id: str,
    precio_unitario_sin_iva: Decimal,
    fuente_comercial: str,
    observacion: str | None,
) -> PrecioFinalVentaPartida:
    """Registra una captura manual explícita; no calcula margen ni utilidad."""

    producto = _producto_actual(
        sesion,
        cotizacion_id=cotizacion_id,
        partida_id=partida_id,
    )
    asegurar_partida_cotizable(
        sesion,
        cotizacion_id=cotizacion_id,
        partida_id=partida_id,
    )
    precio = Decimal(precio_unitario_sin_iva).quantize(
        _DOS_DECIMALES,
        rounding=ROUND_HALF_UP,
    )
    if precio <= 0:
        raise ValueError("el precio final unitario sin IVA debe ser mayor que cero")

    fuente = _limpiar(fuente_comercial)
    if not fuente:
        raise ValueError("indica la fuente o criterio comercial del precio final")
    if len(fuente) > 300:
        raise ValueError("la fuente comercial no puede exceder 300 caracteres")

    observacion_limpia = _limpiar(observacion)
    if observacion_limpia and len(observacion_limpia) > 500:
        raise ValueError("la observación no puede exceder 500 caracteres")

    evento = PrecioFinalVentaPartida(
        cotizacion_id=cotizacion_id,
        partida_documento_id=partida_id,
        clave_producto=producto.clave_producto,
        estado=EstadoPrecioVenta.VALIDADO.value,
        precio_unitario_sin_iva=precio,
        fuente_comercial=fuente,
        observacion=observacion_limpia,
        fuente_decision=FuenteDecisionPrecioVenta.CAPTURA_MANUAL.value,
        validada_por_usuario_id=usuario_id,
    )
    sesion.add(evento)
    sesion.commit()
    sesion.refresh(evento)
    return evento


def retirar_precio_venta(
    sesion: Session,
    *,
    cotizacion_id: str,
    partida_id: str,
    usuario_id: str,
) -> PrecioFinalVentaPartida:
    """Revierte el precio vigente agregando un evento pendiente auditable."""

    producto = _producto_actual(
        sesion,
        cotizacion_id=cotizacion_id,
        partida_id=partida_id,
    )
    evento = PrecioFinalVentaPartida(
        cotizacion_id=cotizacion_id,
        partida_documento_id=partida_id,
        clave_producto=producto.clave_producto,
        estado=EstadoPrecioVenta.PENDIENTE.value,
        precio_unitario_sin_iva=None,
        fuente_comercial=None,
        observacion="Precio final retirado mediante revisión humana",
        fuente_decision=FuenteDecisionPrecioVenta.RETIRO_HUMANO.value,
        validada_por_usuario_id=usuario_id,
    )
    sesion.add(evento)
    sesion.commit()
    sesion.refresh(evento)
    return evento
