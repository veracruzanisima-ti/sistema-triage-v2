"""Orquestación de consultas actuales sin elegir automáticamente un proveedor ganador."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from triage.cotizaciones.modelos import Cotizacion, ahora_utc
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.historico.decisiones_servicio import referencias_estables_cotizadas_hoy
from triage.historico.modelos import (
    LIMITE_FUENTE_OBSERVACION,
    LIMITE_PRODUCTO_OBSERVADO,
    LIMITE_PROVEEDOR_OBSERVACION,
    OrigenObservacionPrecio,
)
from triage.historico.servicio import clave_producto, crear_observacion_precio
from triage.normalizacion.modelos import NormalizacionPartida
from triage.proveedores.base import ProveedorProducto, ResultadoProveedor, SolicitudProveedor
from triage.proveedores.coincidencia_catalogo import (
    CandidatoCatalogo,
    evaluar_candidato,
    extraer_presentacion_comercial,
    terminos_busqueda_ampliada,
)
from triage.proveedores.descubrimiento_web import (
    CandidatoWeb,
    DescubridorWeb,
    ErrorDescubrimientoWeb,
)
from triage.proveedores.modelos import (
    CandidatoWebDescartado,
    ConsultaProveedor,
    ConsultaWeb,
    EstadoConsultaProveedor,
    EstadoConsultaWeb,
)


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
    productos_reutilizados_hoy: int = 0
    partidas_duplicadas_omitidas: int = 0


@dataclass(frozen=True)
class ResumenDescubrimientoWeb:
    """Distingue candidatos útiles de resultados descartados conservadoramente."""

    candidatos: int
    guardados: int
    descartados: int
    intentos: int


@dataclass(frozen=True)
class PresentacionAlternativaWeb:
    """Presentación convergente que todavía requiere confirmación humana."""

    valor: str
    valor_busqueda: str
    fuentes: tuple[str, ...]
    candidatos_ids: tuple[str, ...]


@dataclass(frozen=True)
class TrazabilidadWebPartida:
    """Última consulta web y sus descartes, sin mezclarlos con precios históricos."""

    consulta: ConsultaWeb
    descartados: tuple[CandidatoWebDescartado, ...]
    presentacion_alternativa: PresentacionAlternativaWeb | None = None
    presentacion_alternativa_ambigua: bool = False


@dataclass(frozen=True)
class _EvaluacionWeb:
    candidato: CandidatoWeb
    intento_busqueda: int
    proveedor: str | None
    producto_observado: str | None
    motivos: tuple[str, ...]


def _limpiar(valor: str | None) -> str | None:
    if valor is None:
        return None
    limpio = " ".join(valor.split())
    return limpio or None


_MOTIVOS_ADMITIDOS_PRESENTACION = {
    "presentación distinta",
    "precio no visible",
}


def _fuente_independiente(candidato: CandidatoWebDescartado) -> tuple[str, str]:
    proveedor = _limpiar(candidato.proveedor)
    if proveedor:
        return f"proveedor:{proveedor.casefold()}", proveedor
    dominio = (urlsplit(candidato.url).hostname or candidato.url).casefold()
    return f"url:{dominio}", dominio


def _presentacion_alternativa_web(
    descartados: Sequence[CandidatoWebDescartado],
) -> tuple[PresentacionAlternativaWeb | None, bool]:
    candidatos = [
        candidato
        for candidato in descartados
        if "presentación distinta" in candidato.motivos
        and set(candidato.motivos).issubset(_MOTIVOS_ADMITIDOS_PRESENTACION)
    ]
    if not candidatos:
        return None, False

    por_presentacion: dict[str, list[CandidatoWebDescartado]] = {}
    for candidato in candidatos:
        presentacion = extraer_presentacion_comercial(candidato.producto_observado)
        if presentacion is None:
            return None, True
        por_presentacion.setdefault(presentacion, []).append(candidato)
    if len(por_presentacion) != 1:
        return None, True

    presentacion, coincidencias = next(iter(por_presentacion.items()))
    fuentes: dict[str, str] = {}
    for candidato in coincidencias:
        clave, etiqueta = _fuente_independiente(candidato)
        fuentes.setdefault(clave, etiqueta)
    return (
        PresentacionAlternativaWeb(
            valor=presentacion,
            valor_busqueda=presentacion.removeprefix("Caja con "),
            fuentes=tuple(fuentes.values()),
            candidatos_ids=tuple(candidato.id for candidato in coincidencias),
        ),
        False,
    )


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


def listar_trazabilidad_web(
    sesion: Session,
    cotizacion_id: str,
) -> dict[str, TrazabilidadWebPartida]:
    """Devuelve sólo la ejecución web más reciente de cada partida para una UI compacta."""

    consultas = list(
        sesion.scalars(
            select(ConsultaWeb)
            .where(ConsultaWeb.cotizacion_id == cotizacion_id)
            .order_by(ConsultaWeb.iniciada_en.desc())
        )
    )
    ultimas: dict[str, ConsultaWeb] = {}
    for consulta in consultas:
        if consulta.partida_documento_id:
            ultimas.setdefault(consulta.partida_documento_id, consulta)
    if not ultimas:
        return {}

    descartados_por_consulta: dict[str, list[CandidatoWebDescartado]] = {
        consulta.id: [] for consulta in ultimas.values()
    }
    descartados = sesion.scalars(
        select(CandidatoWebDescartado)
        .where(CandidatoWebDescartado.consulta_web_id.in_(descartados_por_consulta))
        .order_by(
            CandidatoWebDescartado.intento_busqueda.asc(),
            CandidatoWebDescartado.descartado_en.asc(),
        )
    )
    for candidato in descartados:
        descartados_por_consulta[candidato.consulta_web_id].append(candidato)

    normalizaciones = {
        normalizacion.partida_documento_id: normalizacion
        for normalizacion in sesion.scalars(
            select(NormalizacionPartida).where(
                NormalizacionPartida.partida_documento_id.in_(tuple(ultimas))
            )
        )
    }

    resultado: dict[str, TrazabilidadWebPartida] = {}
    for partida_id, consulta in ultimas.items():
        descartados_consulta = tuple(descartados_por_consulta[consulta.id])
        normalizacion = normalizaciones.get(partida_id)
        presentacion_buscada = consulta.criterios_busqueda.get("presentacion")
        criterio_valido = presentacion_buscada is None or isinstance(
            presentacion_buscada, str
        )
        busqueda_vigente = (
            normalizacion is not None
            and criterio_valido
            and _limpiar(normalizacion.presentacion) == _limpiar(presentacion_buscada)
        )
        alternativa, ambigua = (
            _presentacion_alternativa_web(descartados_consulta)
            if busqueda_vigente
            else (None, False)
        )
        if alternativa and _limpiar(alternativa.valor_busqueda) == _limpiar(
            normalizacion.presentacion if normalizacion else None
        ):
            alternativa, ambigua = None, True
        resultado[partida_id] = TrazabilidadWebPartida(
            consulta=consulta,
            descartados=descartados_consulta,
            presentacion_alternativa=alternativa,
            presentacion_alternativa_ambigua=ambigua,
        )
    return resultado


def confirmar_presentacion_alternativa_web(
    sesion: Session,
    *,
    cotizacion_id: str,
    partida_documento_id: str,
    candidato_descartado_id: str,
    usuario_id: str,
) -> str:
    """Actualiza sólo la copia operativa tras revalidar la sugerencia persistida."""

    fila = _normalizacion_elegible(
        sesion,
        cotizacion_id=cotizacion_id,
        partida_documento_id=partida_documento_id,
    )
    if fila is None:
        raise ValueError("el producto ya no está preparado o dejó de ser elegible")
    normalizacion, _, _ = fila
    trazabilidad = listar_trazabilidad_web(sesion, cotizacion_id).get(
        partida_documento_id
    )
    alternativa = trazabilidad.presentacion_alternativa if trazabilidad else None
    if alternativa is None or candidato_descartado_id not in alternativa.candidatos_ids:
        raise ValueError(
            "La presentación alternativa ya no es inequívoca. Edita la preparación manualmente."
        )
    if _limpiar(normalizacion.presentacion) == _limpiar(alternativa.valor_busqueda):
        raise ValueError("La presentación de búsqueda ya usa esa alternativa.")

    normalizacion.presentacion = alternativa.valor_busqueda
    normalizacion.confirmada_por_usuario_id = usuario_id
    normalizacion.actualizada_en = ahora_utc()
    sesion.add(normalizacion)
    sesion.commit()
    return alternativa.valor_busqueda


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


def ejecutar_consultas_partida(
    sesion: Session,
    *,
    cotizacion_id: str,
    partida_documento_id: str,
    usuario_id: str,
    proveedores: Sequence[ProveedorProducto],
) -> ResumenConsultaUnificada:
    """Reconsulta una partida contra todos los canales sin aplicar reutilización diaria."""

    if not proveedores:
        raise ValueError("No hay proveedores automáticos configurados.")

    intentos = 0
    precios_encontrados = 0
    no_encontrados = 0
    errores = 0
    for proveedor in proveedores:
        intentos += 1
        try:
            intento = ejecutar_consulta(
                sesion,
                cotizacion_id=cotizacion_id,
                partida_documento_id=partida_documento_id,
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


def ejecutar_consultas_configuradas(
    sesion: Session,
    *,
    cotizacion_id: str,
    usuario_id: str,
    proveedores: Sequence[ProveedorProducto],
) -> ResumenConsultaUnificada:
    """Consulta una vez por identidad y reutiliza referencias estables del día cuando existen."""

    cotizacion = sesion.get(Cotizacion, cotizacion_id)
    if cotizacion is None:
        raise ValueError("la cotización ya no existe")
    codigo_postal = _limpiar(cotizacion.codigo_postal_consulta)
    if codigo_postal is None:
        raise ValueError("Configura un código postal antes de consultar proveedores.")

    productos = listar_productos_consultables(sesion, cotizacion_id)
    if not productos:
        raise ValueError("No hay productos confirmados para consultar.")

    productos_unicos: dict[str, ProductoConsultable] = {}
    for producto in productos:
        productos_unicos.setdefault(clave_producto(producto.normalizacion), producto)
    duplicadas = len(productos) - len(productos_unicos)

    referencias_hoy = referencias_estables_cotizadas_hoy(
        sesion,
        claves=set(productos_unicos),
        codigo_postal=codigo_postal,
    )
    if not proveedores and len(referencias_hoy) < len(productos_unicos):
        raise ValueError("No hay proveedores automáticos configurados.")

    intentos = 0
    precios_encontrados = 0
    no_encontrados = 0
    errores = 0
    reutilizados = 0
    for clave, producto in productos_unicos.items():
        if clave in referencias_hoy:
            reutilizados += 1
            continue

        resumen = ejecutar_consultas_partida(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=producto.partida.id,
            usuario_id=usuario_id,
            proveedores=proveedores,
        )
        intentos += resumen.intentos
        precios_encontrados += resumen.precios_encontrados
        no_encontrados += resumen.no_encontrados
        errores += resumen.errores

    return ResumenConsultaUnificada(
        intentos=intentos,
        precios_encontrados=precios_encontrados,
        no_encontrados=no_encontrados,
        errores=errores,
        productos_reutilizados_hoy=reutilizados,
        partidas_duplicadas_omitidas=duplicadas,
    )


def _motivos_descarte_web(
    solicitud: SolicitudProveedor,
    candidato: CandidatoWeb,
) -> tuple[str | None, str | None, tuple[str, ...]]:
    proveedor = _limpiar(candidato.proveedor)
    producto_observado = _limpiar(candidato.producto_exacto)
    url = str(candidato.url)
    motivos: list[str] = []
    if proveedor is None:
        motivos.append("proveedor o fuente no identificada")
    elif len(proveedor) > LIMITE_PROVEEDOR_OBSERVACION:
        motivos.append("proveedor excede el límite del histórico cotizable")
    if producto_observado is None:
        motivos.append("faltan datos suficientes para comprobar coincidencia")
    elif len(producto_observado) > LIMITE_PRODUCTO_OBSERVADO:
        motivos.append("producto observado excede el límite del histórico cotizable")
    if len(url) > LIMITE_FUENTE_OBSERVACION:
        motivos.append("URL excede el límite del histórico cotizable")
    if candidato.precio_total is None:
        motivos.append("precio no visible")

    if producto_observado is not None:
        evaluacion = evaluar_candidato(
            solicitud,
            CandidatoCatalogo(
                descripcion=producto_observado,
                precio_observado=candidato.precio_total or Decimal("1"),
                stock=None,
                fuente=str(candidato.url),
            ),
        )
        motivos.extend(evaluacion.motivos)
    if not candidato.coincidencia_exacta and not any(
        motivo
        in {
            "marca distinta",
            "producto distinto",
            "forma o dispositivo distinto",
            "concentración distinta",
            "presentación distinta",
            "faltan datos suficientes para comprobar coincidencia",
        }
        for motivo in motivos
    ):
        motivos.append("faltan datos suficientes para comprobar coincidencia")
    return proveedor, producto_observado, tuple(dict.fromkeys(motivos))


def _evaluar_candidatos_web(
    solicitud: SolicitudProveedor,
    candidatos: Sequence[CandidatoWeb],
    *,
    intento_busqueda: int,
) -> tuple[_EvaluacionWeb, ...]:
    return tuple(
        _EvaluacionWeb(
            candidato=candidato,
            intento_busqueda=intento_busqueda,
            proveedor=resultado[0],
            producto_observado=resultado[1],
            motivos=resultado[2],
        )
        for candidato in candidatos
        for resultado in (_motivos_descarte_web(solicitud, candidato),)
    )


def _finalizar_consulta_web(
    sesion: Session,
    consulta: ConsultaWeb,
    evaluaciones: Sequence[_EvaluacionWeb],
    *,
    guardados: int,
    intentos: int,
    error: str | None = None,
) -> None:
    descartados = [evaluacion for evaluacion in evaluaciones if evaluacion.motivos]
    for evaluacion in descartados:
        sesion.add(
            CandidatoWebDescartado(
                consulta_web_id=consulta.id,
                proveedor=evaluacion.proveedor,
                producto_observado=evaluacion.producto_observado,
                url=str(evaluacion.candidato.url),
                precio_observado=evaluacion.candidato.precio_total,
                motivos=list(evaluacion.motivos),
                intento_busqueda=evaluacion.intento_busqueda,
            )
        )
    consulta.estado = (
        EstadoConsultaWeb.ERROR.value if error else EstadoConsultaWeb.COMPLETADA.value
    )
    consulta.intentos = intentos
    consulta.candidatos = len(evaluaciones)
    consulta.guardados = guardados
    consulta.descartados = len(descartados)
    consulta.mensaje_error = error
    consulta.finalizada_en = ahora_utc()
    sesion.add(consulta)
    sesion.commit()


def ejecutar_descubrimiento_web(
    sesion: Session,
    *,
    cotizacion_id: str,
    partida_documento_id: str,
    usuario_id: str,
    descubridor: DescubridorWeb,
) -> ResumenDescubrimientoWeb:
    """Hace como máximo dos búsquedas y sólo guarda coincidencias estrictas."""

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
    criterios = {
        "producto": solicitud.producto,
        "marca": solicitud.marca,
        "concentracion": solicitud.concentracion,
        "forma_dispositivo": solicitud.forma_dispositivo,
        "presentacion": solicitud.presentacion,
        "codigo_postal": solicitud.codigo_postal,
    }
    terminos_ampliados = terminos_busqueda_ampliada(solicitud)
    consulta = ConsultaWeb(
        cotizacion_id=cotizacion_id,
        partida_documento_id=partida_documento_id,
        clave_producto=clave_producto(normalizacion),
        modelo=_limpiar(getattr(descubridor, "modelo", None))
        or type(descubridor).__name__,
        criterios_busqueda=criterios,
        terminos_ampliados=list(terminos_ampliados),
        ejecutada_por_usuario_id=usuario_id,
    )
    sesion.add(consulta)
    sesion.commit()
    sesion.refresh(consulta)

    evaluaciones: list[_EvaluacionWeb] = []
    intentos = 1
    try:
        primeros = descubridor.buscar(solicitud)
    except ErrorDescubrimientoWeb as error:
        _finalizar_consulta_web(
            sesion,
            consulta,
            evaluaciones,
            guardados=0,
            intentos=intentos,
            error=str(error),
        )
        raise
    evaluaciones.extend(
        _evaluar_candidatos_web(solicitud, primeros, intento_busqueda=1)
    )

    validos = [evaluacion for evaluacion in evaluaciones if not evaluacion.motivos]
    if not validos and terminos_ampliados:
        intentos = 2
        try:
            segundos = descubridor.buscar(
                solicitud,
                terminos_adicionales=terminos_ampliados,
            )
        except ErrorDescubrimientoWeb as error:
            _finalizar_consulta_web(
                sesion,
                consulta,
                evaluaciones,
                guardados=0,
                intentos=intentos,
                error=str(error),
            )
            raise
        segundas_evaluaciones = _evaluar_candidatos_web(
            solicitud,
            segundos,
            intento_busqueda=2,
        )
        evaluaciones.extend(segundas_evaluaciones)
        validos = [evaluacion for evaluacion in segundas_evaluaciones if not evaluacion.motivos]

    guardados = 0
    fuentes_guardadas: set[str] = set()
    for evaluacion in validos:
        candidato = evaluacion.candidato
        fuente = str(candidato.url)
        if fuente in fuentes_guardadas:
            continue
        fuentes_guardadas.add(fuente)
        crear_observacion_precio(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_documento_id,
            usuario_id=usuario_id,
            proveedor=evaluacion.proveedor or "Fuente web",
            fuente=fuente,
            precio_antes_iva=None,
            iva_porcentaje=None,
            precio_total=candidato.precio_total,
            es_promocion=candidato.es_promocion,
            condiciones_promocion=candidato.condiciones_promocion,
            disponibilidad=candidato.disponibilidad,
            entrega_viable=candidato.entrega_viable,
            codigo_postal=codigo_postal,
            producto_observado=evaluacion.producto_observado,
            origen=OrigenObservacionPrecio.WEB,
            guardar=False,
        )
        guardados += 1

    _finalizar_consulta_web(
        sesion,
        consulta,
        evaluaciones,
        guardados=guardados,
        intentos=intentos,
    )
    descartados = sum(bool(evaluacion.motivos) for evaluacion in evaluaciones)
    return ResumenDescubrimientoWeb(
        candidatos=len(evaluaciones),
        guardados=guardados,
        descartados=descartados,
        intentos=intentos,
    )
