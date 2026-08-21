"""Captura humana y trazable del precio unitario final sin IVA."""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from triage.comercial.modelos import EstadoComercial
from triage.comercial.precio_venta_modelos import (
    EstadoPrecioVenta,
    FuentePrecioVenta,
    PrecioVentaPartida,
)
from triage.comercial.servicio import (
    asegurar_partida_cotizable,
    listar_decisiones_comerciales_actuales,
)
from triage.historico.decisiones_servicio import listar_selecciones_actuales
from triage.historico.servicio import ProductoHistorico, listar_productos_historico
from triage.usuarios.modelos import Usuario

_DOS_DECIMALES = Decimal("0.01")


@dataclass(frozen=True)
class PrecioVentaActual:
    """Última confirmación vigente que todavía corresponde a la identidad exacta."""

    id: str
    precio_unitario_sin_iva: Decimal
    referencia_estable_id: str | None
    fuente_decision: str
    observacion: str | None
    validado_por_nombre: str | None
    creada_en: datetime


def _ultimo_evento_por_partida(sesion: Session) -> dict[tuple[str, str], PrecioVentaPartida]:
    ultimos: dict[tuple[str, str], PrecioVentaPartida] = {}
    for evento in sesion.scalars(
        select(PrecioVentaPartida).order_by(
            PrecioVentaPartida.creada_en.desc(),
            PrecioVentaPartida.id.desc(),
        )
    ):
        if evento.partida_documento_id:
            ultimos.setdefault((evento.cotizacion_id, evento.partida_documento_id), evento)
    return ultimos


def listar_precios_venta_actuales(
    sesion: Session,
    *,
    cotizacion_id: str,
    productos: list[ProductoHistorico],
) -> dict[str, PrecioVentaActual]:
    """Mantiene vigencia sólo si no cambiaron identidad, referencia ni decisión comercial."""

    por_partida = {
        partida_id: evento
        for (evento_cotizacion, partida_id), evento in _ultimo_evento_por_partida(sesion).items()
        if evento_cotizacion == cotizacion_id
    }
    selecciones = listar_selecciones_actuales(sesion, cotizacion_id)
    decisiones = listar_decisiones_comerciales_actuales(sesion, cotizacion_id)

    def vigente(producto: ProductoHistorico, evento: PrecioVentaPartida) -> bool:
        seleccion = selecciones.get(producto.partida.id)
        decision = decisiones.get(producto.partida.id)
        if evento.clave_producto != producto.clave_producto:
            return False
        if evento.estado != EstadoPrecioVenta.VALIDADO.value:
            return False
        if evento.precio_unitario_sin_iva is None:
            return False
        if seleccion is None or evento.referencia_estable_id != seleccion.referencia_estable_id:
            return False
        if decision is None:
            return True
        if decision.estado != EstadoComercial.COTIZABLE:
            return False
        return decision.creada_en is None or decision.creada_en <= evento.creada_en

    vigentes = {
        producto.partida.id: por_partida[producto.partida.id]
        for producto in productos
        if producto.partida.id in por_partida
        and vigente(producto, por_partida[producto.partida.id])
    }
    usuarios_ids = {evento.validado_por_usuario_id for evento in vigentes.values()}
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
            id=evento.id,
            precio_unitario_sin_iva=Decimal(evento.precio_unitario_sin_iva),
            referencia_estable_id=evento.referencia_estable_id,
            fuente_decision=evento.fuente_decision,
            observacion=evento.observacion,
            validado_por_nombre=nombres.get(evento.validado_por_usuario_id),
            creada_en=evento.creada_en,
        )
        for partida_id, evento in vigentes.items()
    }


def _producto(
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


def _precio_normalizado(valor: Decimal) -> Decimal:
    precio = Decimal(valor)
    if not precio.is_finite() or precio <= 0:
        raise ValueError("el precio unitario final sin IVA debe ser mayor que cero")
    return precio.quantize(_DOS_DECIMALES, rounding=ROUND_HALF_UP)


def registrar_precio_venta(
    sesion: Session,
    *,
    cotizacion_id: str,
    partida_id: str,
    usuario_id: str,
    precio_unitario_sin_iva: Decimal,
    observacion: str | None,
) -> PrecioVentaPartida:
    """Registra una decisión por partida sin convertirla en regla de margen reusable."""

    producto = _producto(
        sesion,
        cotizacion_id=cotizacion_id,
        partida_id=partida_id,
    )
    asegurar_partida_cotizable(
        sesion,
        cotizacion_id=cotizacion_id,
        partida_id=partida_id,
    )
    seleccion = listar_selecciones_actuales(sesion, cotizacion_id).get(partida_id)
    referencia_id = seleccion.referencia_estable_id if seleccion else None
    if not referencia_id:
        raise ValueError("selecciona una referencia estable antes de confirmar el precio final")

    observacion_limpia = " ".join((observacion or "").split()) or None
    if observacion_limpia and len(observacion_limpia) > 500:
        raise ValueError("la observación no puede exceder 500 caracteres")

    evento = PrecioVentaPartida(
        cotizacion_id=cotizacion_id,
        partida_documento_id=partida_id,
        clave_producto=producto.clave_producto,
        estado=EstadoPrecioVenta.VALIDADO.value,
        precio_unitario_sin_iva=_precio_normalizado(precio_unitario_sin_iva),
        referencia_estable_id=referencia_id,
        observacion=observacion_limpia,
        fuente_decision=FuentePrecioVenta.CAPTURA_HUMANA.value,
        validado_por_usuario_id=usuario_id,
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
) -> PrecioVentaPartida:
    """Retira la vigencia agregando un evento PENDIENTE y conserva el histórico."""

    producto = _producto(
        sesion,
        cotizacion_id=cotizacion_id,
        partida_id=partida_id,
    )
    evento = PrecioVentaPartida(
        cotizacion_id=cotizacion_id,
        partida_documento_id=partida_id,
        clave_producto=producto.clave_producto,
        estado=EstadoPrecioVenta.PENDIENTE.value,
        precio_unitario_sin_iva=None,
        referencia_estable_id=None,
        observacion="Precio final retirado mediante revisión humana",
        fuente_decision=FuentePrecioVenta.RETIRO_HUMANO.value,
        validado_por_usuario_id=usuario_id,
    )
    sesion.add(evento)
    sesion.commit()
    sesion.refresh(evento)
    return evento
