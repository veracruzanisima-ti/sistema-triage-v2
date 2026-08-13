"""Operaciones de histórico sin convertir observaciones en decisiones comerciales."""

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.historico.modelos import ObservacionPrecio
from triage.normalizacion.modelos import NormalizacionPartida


@dataclass(frozen=True)
class ProductoHistorico:
    """Producto preparado y sus observaciones exactas más recientes."""

    normalizacion: NormalizacionPartida
    partida: PartidaDocumento
    documento: Documento
    clave_producto: str
    observaciones: tuple[ObservacionPrecio, ...]


def _limpiar(valor: str | None) -> str | None:
    if valor is None:
        return None
    limpio = " ".join(valor.split())
    return limpio or None


def clave_producto(normalizacion: NormalizacionPartida) -> str:
    """Genera una identidad exacta; no intenta resolver equivalencias semánticas."""

    componentes = [
        _limpiar(normalizacion.producto),
        _limpiar(normalizacion.marca),
        _limpiar(normalizacion.concentracion),
        _limpiar(normalizacion.forma_dispositivo),
        _limpiar(normalizacion.presentacion),
    ]
    canonico = [componente.casefold() if componente else "" for componente in componentes]
    serializado = json.dumps(canonico, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def listar_productos_historico(
    sesion: Session,
    cotizacion_id: str,
) -> list[ProductoHistorico]:
    """Devuelve únicamente productos ya preparados de partidas vigentes y revisadas."""

    consulta = (
        select(NormalizacionPartida, PartidaDocumento, Documento)
        .join(
            PartidaDocumento,
            PartidaDocumento.id == NormalizacionPartida.partida_documento_id,
        )
        .join(Documento, Documento.id == PartidaDocumento.documento_id)
        .where(
            Documento.cotizacion_id == cotizacion_id,
            Documento.estado == EstadoDocumento.REVISADO.value,
            PartidaDocumento.incluida_cotizacion.is_(True),
        )
        .order_by(Documento.recibido_en.asc(), PartidaDocumento.orden.asc())
    )
    filas = list(sesion.execute(consulta))
    if not filas:
        return []

    claves = {clave_producto(normalizacion) for normalizacion, _, _ in filas}
    observaciones = list(
        sesion.scalars(
            select(ObservacionPrecio)
            .where(ObservacionPrecio.clave_producto.in_(claves))
            .order_by(ObservacionPrecio.observado_en.desc())
        )
    )
    por_clave: dict[str, list[ObservacionPrecio]] = {clave: [] for clave in claves}
    for observacion in observaciones:
        por_clave.setdefault(observacion.clave_producto, []).append(observacion)

    return [
        ProductoHistorico(
            normalizacion=normalizacion,
            partida=partida,
            documento=documento,
            clave_producto=clave_producto(normalizacion),
            observaciones=tuple(por_clave.get(clave_producto(normalizacion), [])),
        )
        for normalizacion, partida, documento in filas
    ]


def _obtener_normalizacion_elegible(
    sesion: Session,
    *,
    cotizacion_id: str,
    partida_documento_id: str,
) -> NormalizacionPartida | None:
    consulta = (
        select(NormalizacionPartida)
        .join(
            PartidaDocumento,
            PartidaDocumento.id == NormalizacionPartida.partida_documento_id,
        )
        .join(Documento, Documento.id == PartidaDocumento.documento_id)
        .where(
            NormalizacionPartida.partida_documento_id == partida_documento_id,
            Documento.cotizacion_id == cotizacion_id,
            Documento.estado == EstadoDocumento.REVISADO.value,
            PartidaDocumento.incluida_cotizacion.is_(True),
        )
    )
    return sesion.scalar(consulta)


def crear_observacion_precio(
    sesion: Session,
    *,
    cotizacion_id: str,
    partida_documento_id: str,
    usuario_id: str,
    proveedor: str,
    fuente: str,
    precio_antes_iva: Decimal | None,
    iva_porcentaje: Decimal | None,
    precio_total: Decimal | None,
    es_promocion: bool,
    condiciones_promocion: str | None,
    disponibilidad: str | None,
    entrega_viable: bool | None,
) -> ObservacionPrecio:
    """Agrega una observación nueva; nunca modifica una observación anterior."""

    normalizacion = _obtener_normalizacion_elegible(
        sesion,
        cotizacion_id=cotizacion_id,
        partida_documento_id=partida_documento_id,
    )
    if normalizacion is None:
        raise ValueError("el producto ya no está preparado o dejó de ser elegible")

    proveedor_limpio = _limpiar(proveedor)
    fuente_limpia = _limpiar(fuente)
    if not proveedor_limpio:
        raise ValueError("proveedor o establecimiento obligatorio")
    if not fuente_limpia:
        raise ValueError("fuente o evidencia obligatoria")
    if precio_antes_iva is None and precio_total is None:
        raise ValueError("captura al menos un precio observado")

    for nombre, valor in (
        ("precio antes de IVA", precio_antes_iva),
        ("precio total", precio_total),
    ):
        if valor is not None and valor < 0:
            raise ValueError(f"{nombre} no puede ser negativo")
    if iva_porcentaje is not None and not Decimal("0") <= iva_porcentaje <= Decimal("100"):
        raise ValueError("el porcentaje de IVA debe estar entre 0 y 100")

    observacion = ObservacionPrecio(
        clave_producto=clave_producto(normalizacion),
        normalizacion_partida_id=normalizacion.partida_documento_id,
        producto=_limpiar(normalizacion.producto),
        marca=_limpiar(normalizacion.marca),
        concentracion=_limpiar(normalizacion.concentracion),
        forma_dispositivo=_limpiar(normalizacion.forma_dispositivo),
        presentacion=_limpiar(normalizacion.presentacion),
        proveedor=proveedor_limpio,
        precio_antes_iva=precio_antes_iva,
        iva_porcentaje=iva_porcentaje,
        precio_total=precio_total,
        es_promocion=es_promocion,
        condiciones_promocion=_limpiar(condiciones_promocion),
        disponibilidad=_limpiar(disponibilidad),
        entrega_viable=entrega_viable,
        fuente=fuente_limpia,
        capturada_por_usuario_id=usuario_id,
    )
    sesion.add(observacion)
    sesion.commit()
    sesion.refresh(observacion)
    return observacion
