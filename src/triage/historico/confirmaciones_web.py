"""Confirmaciones humanas de evidencia web sin reescribir la observación automática."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from triage.cotizaciones.modelos import Cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.historico.decisiones_modelos import RolDecisionPrecio
from triage.historico.decisiones_servicio import (
    listar_selecciones_actuales,
    registrar_decision_precio,
)
from triage.historico.modelos import ObservacionPrecio, OrigenObservacionPrecio
from triage.historico.servicio import clave_producto, crear_observacion_precio
from triage.normalizacion.modelos import NormalizacionPartida

_CLAVE_CONFIRMACION = "confirmacion_manual_fuente_web"


def _normalizacion_actual(
    sesion: Session,
    *,
    cotizacion_id: str,
    partida_id: str,
) -> NormalizacionPartida | None:
    return sesion.scalar(
        select(NormalizacionPartida)
        .join(PartidaDocumento)
        .join(Documento)
        .where(
            NormalizacionPartida.partida_documento_id == partida_id,
            Documento.cotizacion_id == cotizacion_id,
            Documento.estado == EstadoDocumento.REVISADO.value,
            PartidaDocumento.incluida_cotizacion.is_(True),
        )
    )


def _confirmacion_existente(
    sesion: Session,
    *,
    clave: str,
    observacion_web_id: str,
    codigo_postal: str | None,
) -> ObservacionPrecio | None:
    """Reutiliza una confirmación previa del mismo clic lógico para evitar duplicados."""

    observaciones = sesion.scalars(
        select(ObservacionPrecio)
        .where(
            ObservacionPrecio.clave_producto == clave,
            ObservacionPrecio.origen == OrigenObservacionPrecio.MANUAL.value,
        )
        .order_by(ObservacionPrecio.creado_en.desc())
    )
    for observacion in observaciones:
        evidencia = observacion.evidencia_identidad or {}
        confirmacion = evidencia.get(_CLAVE_CONFIRMACION)
        if not isinstance(confirmacion, dict):
            continue
        if confirmacion.get("observacion_web_id") != observacion_web_id:
            continue
        if observacion.codigo_postal != codigo_postal:
            continue
        if observacion.disponibilidad_operativa is not True:
            continue
        return observacion
    return None


def confirmar_fuente_web_y_usar_como_referencia(
    sesion: Session,
    *,
    cotizacion_id: str,
    partida_id: str,
    usuario_id: str,
    observacion_web_id: str,
) -> ObservacionPrecio:
    """Registra una reobservación manual y la usa como referencia estable."""

    normalizacion = _normalizacion_actual(
        sesion,
        cotizacion_id=cotizacion_id,
        partida_id=partida_id,
    )
    if normalizacion is None:
        raise ValueError("la partida ya no está preparada o dejó de ser elegible")
    clave = clave_producto(normalizacion)

    original = sesion.get(ObservacionPrecio, observacion_web_id)
    if original is None:
        raise ValueError("la observación web ya no existe")
    if original.clave_producto != clave:
        raise ValueError("la observación web pertenece a otra identidad de producto")
    if original.origen != OrigenObservacionPrecio.WEB.value:
        raise ValueError("sólo puede confirmarse por esta vía una observación web")
    if original.es_promocion:
        raise ValueError("una promoción no puede usarse como referencia estable")
    if original.disponibilidad_operativa is True:
        raise ValueError("la fuente ya está marcada como disponible; usa la selección normal")
    if original.disponibilidad_operativa is False:
        raise ValueError(
            "la fuente reporta falta de disponibilidad; confirma con el proveedor por la vía manual"
        )
    if original.precio_antes_iva is None and original.precio_total is None:
        raise ValueError("la observación web no tiene un precio que pueda confirmarse")
    if not (
        original.fuente.startswith("http://") or original.fuente.startswith("https://")
    ):
        raise ValueError("la observación web no tiene una fuente navegable para verificar")

    cotizacion = sesion.get(Cotizacion, cotizacion_id)
    if cotizacion is None:
        raise ValueError("la cotización ya no existe")
    codigo_postal = cotizacion.codigo_postal_consulta

    confirmada = _confirmacion_existente(
        sesion,
        clave=clave,
        observacion_web_id=original.id,
        codigo_postal=codigo_postal,
    )
    if confirmada is None:
        evidencia = dict(original.evidencia_identidad or {})
        evidencia[_CLAVE_CONFIRMACION] = {
            "observacion_web_id": original.id,
            "tipo": "precio_y_disponibilidad_verificados_en_fuente",
        }
        confirmada = crear_observacion_precio(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_id,
            usuario_id=usuario_id,
            proveedor=original.proveedor,
            fuente=original.fuente,
            precio_antes_iva=original.precio_antes_iva,
            iva_porcentaje=original.iva_porcentaje,
            precio_total=original.precio_total,
            es_promocion=False,
            condiciones_promocion=None,
            disponibilidad="Precio y disponibilidad verificados manualmente en la fuente web",
            entrega_viable=True,
            codigo_postal=codigo_postal,
            producto_observado=original.producto_observado,
            origen=OrigenObservacionPrecio.MANUAL,
            evidencia_identidad=evidencia,
            guardar=False,
        )

    seleccion = listar_selecciones_actuales(sesion, cotizacion_id).get(partida_id)
    if seleccion and seleccion.referencia_estable_id == confirmada.id:
        return confirmada

    registrar_decision_precio(
        sesion,
        cotizacion_id=cotizacion_id,
        partida_id=partida_id,
        usuario_id=usuario_id,
        rol=RolDecisionPrecio.REFERENCIA_ESTABLE,
        observacion_id=confirmada.id,
    )
    return confirmada
