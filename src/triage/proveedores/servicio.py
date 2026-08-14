"""Orquestación de consultas actuales sin elegir automáticamente un proveedor ganador."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from triage.cotizaciones.modelos import Cotizacion, ahora_utc
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.historico.modelos import OrigenObservacionPrecio
from triage.historico.servicio import clave_producto, crear_observacion_precio
from triage.normalizacion.modelos import NormalizacionPartida
from triage.proveedores.base import ProveedorProducto, ResultadoProveedor, SolicitudProveedor
from triage.proveedores.coincidencia_catalogo import CandidatoCatalogo, evaluar_candidato
from triage.proveedores.descubrimiento_web import DescubridorWeb
from triage.proveedores.modelos import ConsultaProveedor, EstadoConsultaProveedor


class ErrorConsultaProveedor(Exception):
    """Error operativo ya registrado que puede mostrarse sin filtrar detalles internos."""


@dataclass(frozen=True)
class ProductoConsultable:
    """Producto preparado y sus intentos recientes de consulta."""

    normalizacion: NormalizacionPartida
    partida: PartidaDocumento
    documento: Documento
    consultas: tuple[ConsultaProveedor, ...]


@dataclass(frozen=True)
class ResumenConsultaUnificada:
    """Conteo simple de una búsqueda sin ocultar fallos parciales."""

    intentos: int
    precios_encontrados: int
    no_encontrados: int
    errores: int


@dataclass(frozen=True)
class ResumenDescubrimientoWeb:
    """Distingue candidatos útiles de resultados descartados conservadoramente."""

    candidatos: int
    guardados: int
    descartados: int


def _limpiar(valor: str | None) -> str | None:
    if valor is None:
        return None
    limpio = " ".join(valor.split())
    return limpio or None


def _normalizacion_elegible(
    sesion: Session,
    *,
    cotizacion_id: str,
    partida_documento_id: str,
) -> tuple[NormalizacionPartida, PartidaDocumento, Documento] | None:
    consulta = (
        select(NormalizacionPartida, PartidaDocumento, Documento)
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
    return sesion.execute(consulta).one_or_none()


def listar_productos_consultables(
    sesion: Session,
    cotizacion_id: str,
) -> list[ProductoConsultable]:
    """Lista productos preparados y conserva visible el historial de intentos de proveedor."""

    consulta_productos = (
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
    filas = list(sesion.execute(consulta_productos))
    if not filas:
        return []

    ids_partida = [partida.id for _, partida, _ in filas]
    consultas = list(
        sesion.scalars(
            select(ConsultaProveedor)
            .where(ConsultaProveedor.partida_documento_id.in_(ids_partida))
            .order_by(ConsultaProveedor.iniciada_en.desc())
        )
    )
    por_partida: dict[str, list[ConsultaProveedor]] = {
        identificador: [] for identificador in ids_partida
    }
    for intento in consultas:
        if intento.partida_documento_id:
            por_partida.setdefault(intento.partida_documento_id, []).append(intento)

    return [
        ProductoConsultable(
            normalizacion=normalizacion,
            partida=partida,
            documento=documento,
            consultas=tuple(por_partida.get(partida.id, [])[:8]),
        )
        for normalizacion, partida, documento in filas
    ]


def _validar_resultado(resultado: ResultadoProveedor) -> None:
    if not resultado.encontrado:
        return
    if not _limpiar(resultado.fuente):
        raise ValueError("el proveedor no indicó la fuente de la observación")
    precios = [resultado.precio_antes_iva, resultado.precio_total]
    if all(precio is None for precio in precios):
        raise ValueError("el proveedor indicó coincidencia sin precio observable")
    for precio in precios:
        if precio is not None and precio <= Decimal("0"):
            raise ValueError("el proveedor devolvió un precio no válido")
    if resultado.iva_porcentaje is not None and not (
        Decimal("0") <= resultado.iva_porcentaje <= Decimal("100")
    ):
        raise ValueError("el proveedor devolvió un porcentaje de IVA no válido")


def _solicitud_desde_normalizacion(
    *,
    partida_documento_id: str,
    normalizacion: NormalizacionPartida,
    codigo_postal: str,
) -> SolicitudProveedor:
    return SolicitudProveedor(
        partida_documento_id=partida_documento_id,
        producto=_limpiar(normalizacion.producto),
        marca=_limpiar(normalizacion.marca),
        concentracion=_limpiar(normalizacion.concentracion),
        forma_dispositivo=_limpiar(normalizacion.forma_dispositivo),
        presentacion=_limpiar(normalizacion.presentacion),
        codigo_postal=codigo_postal,
    )


def ejecutar_consulta(
    sesion: Session,
    *,
    cotizacion_id: str,
    partida_documento_id: str,
    usuario_id: str,
    proveedor: ProveedorProducto,
) -> ConsultaProveedor:
    """Registra el intento y sólo convierte hechos exitosos en una observación histórica."""

    fila = _normalizacion_elegible(
        sesion,
        cotizacion_id=cotizacion_id,
        partida_documento_id=partida_documento_id,
    )
    if fila is None:
        raise ValueError("el producto ya no está preparado o dejó de ser elegible")
    normalizacion, _, _ = fila

    cotizacion = sesion.get(Cotizacion, cotizacion_id)
    if cotizacion is None:
        raise ValueError("la cotización ya no existe")
    codigo_postal = _limpiar(cotizacion.codigo_postal_consulta)
    if codigo_postal is None:
        raise ValueError("Configura un código postal antes de consultar proveedores.")

    nombre_proveedor = _limpiar(proveedor.nombre)
    if not nombre_proveedor:
        raise ValueError("el adaptador de proveedor no tiene nombre")

    solicitud = _solicitud_desde_normalizacion(
        partida_documento_id=partida_documento_id,
        normalizacion=normalizacion,
        codigo_postal=codigo_postal,
    )
    criterios = {
        "producto": solicitud.producto,
        "marca": solicitud.marca,
        "concentracion": solicitud.concentracion,
        "forma_dispositivo": solicitud.forma_dispositivo,
        "presentacion": solicitud.presentacion,
        "codigo_postal": solicitud.codigo_postal,
    }
    intento = ConsultaProveedor(
        cotizacion_id=cotizacion_id,
        partida_documento_id=partida_documento_id,
        clave_producto=clave_producto(normalizacion),
        proveedor=nombre_proveedor,
        criterios_busqueda=criterios,
        ejecutada_por_usuario_id=usuario_id,
    )
    sesion.add(intento)
    sesion.commit()
    sesion.refresh(intento)

    try:
        resultado = proveedor.consultar(solicitud)
        _validar_resultado(resultado)
    except Exception as error:
        intento.estado = EstadoConsultaProveedor.ERROR.value
        intento.mensaje_error = "El proveedor no pudo completar la consulta."
        intento.finalizada_en = ahora_utc()
        sesion.add(intento)
        sesion.commit()
        raise ErrorConsultaProveedor(intento.mensaje_error) from error

    intento.producto_encontrado = _limpiar(resultado.producto_exacto)
    intento.precio_antes_iva = resultado.precio_antes_iva
    intento.iva_porcentaje = resultado.iva_porcentaje
    intento.precio_total = resultado.precio_total
    intento.es_promocion = resultado.es_promocion
    intento.condiciones_promocion = _limpiar(resultado.condiciones_promocion)
    intento.disponibilidad = _limpiar(resultado.disponibilidad)
    intento.entrega_viable = resultado.entrega_viable
    intento.fuente = _limpiar(resultado.fuente)
    intento.finalizada_en = ahora_utc()

    if not resultado.encontrado:
        intento.estado = EstadoConsultaProveedor.NO_ENCONTRADO.value
        sesion.add(intento)
        sesion.commit()
        sesion.refresh(intento)
        return intento

    observacion = crear_observacion_precio(
        sesion,
        cotizacion_id=cotizacion_id,
        partida_documento_id=partida_documento_id,
        usuario_id=usuario_id,
        proveedor=nombre_proveedor,
        fuente=intento.fuente or nombre_proveedor,
        precio_antes_iva=resultado.precio_antes_iva,
        iva_porcentaje=resultado.iva_porcentaje,
        precio_total=resultado.precio_total,
        es_promocion=resultado.es_promocion,
        condiciones_promocion=resultado.condiciones_promocion,
        disponibilidad=resultado.disponibilidad,
        entrega_viable=resultado.entrega_viable,
        codigo_postal=codigo_postal,
        producto_observado=resultado.producto_exacto,
        origen=OrigenObservacionPrecio.ADAPTADOR,
        guardar=False,
    )
    intento.estado = EstadoConsultaProveedor.EXITOSA.value
    intento.observacion_precio_id = observacion.id
    sesion.add(intento)
    sesion.commit()
    sesion.refresh(intento)
    return intento


def ejecutar_consultas_configuradas(
    sesion: Session,
    *,
    cotizacion_id: str,
    usuario_id: str,
    proveedores: Sequence[ProveedorProducto],
) -> ResumenConsultaUnificada:
    """Consulta todos los productos y canales secuencialmente sin caer por un fallo aislado."""

    cotizacion = sesion.get(Cotizacion, cotizacion_id)
    if cotizacion is None:
        raise ValueError("la cotización ya no existe")
    if not _limpiar(cotizacion.codigo_postal_consulta):
        raise ValueError("Configura un código postal antes de consultar proveedores.")
    if not proveedores:
        raise ValueError("No hay proveedores automáticos configurados.")

    productos = listar_productos_consultables(sesion, cotizacion_id)
    if not productos:
        raise ValueError("No hay productos confirmados para consultar.")

    intentos = 0
    precios_encontrados = 0
    no_encontrados = 0
    errores = 0
    for producto in productos:
        for proveedor in proveedores:
            intentos += 1
            try:
                intento = ejecutar_consulta(
                    sesion,
                    cotizacion_id=cotizacion_id,
                    partida_documento_id=producto.partida.id,
                    usuario_id=usuario_id,
                    proveedor=proveedor,
                )
            except ErrorConsultaProveedor:
                errores += 1
                continue

            if intento.estado == EstadoConsultaProveedor.EXITOSA.value:
                precios_encontrados += 1
            elif intento.estado == EstadoConsultaProveedor.NO_ENCONTRADO.value:
                no_encontrados += 1

    return ResumenConsultaUnificada(
        intentos=intentos,
        precios_encontrados=precios_encontrados,
        no_encontrados=no_encontrados,
        errores=errores,
    )


def ejecutar_descubrimiento_web(
    sesion: Session,
    *,
    cotizacion_id: str,
    partida_documento_id: str,
    usuario_id: str,
    descubridor: DescubridorWeb,
) -> ResumenDescubrimientoWeb:
    """Busca opciones públicas y guarda sólo coincidencias exactas con precio visible."""

    fila = _normalizacion_elegible(
        sesion,
        cotizacion_id=cotizacion_id,
        partida_documento_id=partida_documento_id,
    )
    if fila is None:
        raise ValueError("el producto ya no está preparado o dejó de ser elegible")
    normalizacion, _, _ = fila

    cotizacion = sesion.get(Cotizacion, cotizacion_id)
    if cotizacion is None:
        raise ValueError("la cotización ya no existe")
    codigo_postal = _limpiar(cotizacion.codigo_postal_consulta)
    if codigo_postal is None:
        raise ValueError("Configura un código postal antes de buscar en la web.")

    solicitud = _solicitud_desde_normalizacion(
        partida_documento_id=partida_documento_id,
        normalizacion=normalizacion,
        codigo_postal=codigo_postal,
    )
    candidatos = descubridor.buscar(solicitud)
    guardados = 0
    descartados = 0
    for candidato in candidatos:
        proveedor = _limpiar(candidato.proveedor)
        producto_observado = _limpiar(candidato.producto_exacto)
        if (
            not candidato.coincidencia_exacta
            or candidato.precio_total is None
            or not proveedor
            or not producto_observado
        ):
            descartados += 1
            continue

        evaluacion = evaluar_candidato(
            solicitud,
            CandidatoCatalogo(
                descripcion=producto_observado,
                precio_observado=candidato.precio_total,
                stock=None,
                fuente=str(candidato.url),
            ),
        )
        if not evaluacion.coincide:
            descartados += 1
            continue

        crear_observacion_precio(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_documento_id,
            usuario_id=usuario_id,
            proveedor=proveedor,
            fuente=str(candidato.url),
            precio_antes_iva=None,
            iva_porcentaje=None,
            precio_total=candidato.precio_total,
            es_promocion=candidato.es_promocion,
            condiciones_promocion=candidato.condiciones_promocion,
            disponibilidad=candidato.disponibilidad,
            entrega_viable=candidato.entrega_viable,
            codigo_postal=codigo_postal,
            producto_observado=producto_observado,
            origen=OrigenObservacionPrecio.WEB,
        )
        guardados += 1

    return ResumenDescubrimientoWeb(
        candidatos=len(candidatos),
        guardados=guardados,
        descartados=descartados,
    )
