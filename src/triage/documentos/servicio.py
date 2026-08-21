"""Operaciones para recibir, interpretar y revisar documentos de una cotización."""

from hashlib import sha256
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from triage.cotizaciones.modelos import ahora_utc
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.lectores.base import ErrorLecturaDocumento, LectorDocumento
from triage.lectores.esquemas import LecturaDocumento, PartidaLeida

MIME_PERMITIDOS = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
}

DecisionInclusion = tuple[bool, str | None]


class ArchivoDocumentoInvalido(ValueError):
    """El archivo no cumple las reglas mínimas de entrada del MVP."""


def limpiar_nombre_archivo(nombre: str | None) -> str:
    """Conserva sólo el nombre final y evita rutas suministradas por el cliente."""

    nombre_limpio = Path(nombre or "documento").name.strip()
    return (nombre_limpio or "documento")[:255]


def limpiar_clave_idempotencia(clave: str | None) -> str | None:
    """Limita la clave interna usada para reintentar un elemento de la cola."""

    valor = (clave or "").strip()
    return valor[:80] or None


def limpiar_motivo_exclusion(motivo: str | None) -> str | None:
    """Oculta prefijos técnicos antiguos y conserva un motivo entendible."""

    valor = " ".join((motivo or "").split())
    if not valor:
        return None
    partes = valor.split(" · ", 2)
    if valor.startswith("POL-") and len(partes) == 3 and partes[1].startswith("R"):
        return partes[2][:300]
    return valor[:300]


def validar_archivo(*, contenido: bytes, mime_type: str, max_bytes: int) -> None:
    """Valida tipo y tamaño antes de enviar contenido a un servicio externo."""

    if mime_type not in MIME_PERMITIDOS:
        raise ArchivoDocumentoInvalido("Sólo se admiten PDF, JPG, PNG o WEBP.")
    if not contenido:
        raise ArchivoDocumentoInvalido("El archivo está vacío.")
    if len(contenido) > max_bytes:
        megabytes = max_bytes / (1024 * 1024)
        raise ArchivoDocumentoInvalido(
            f"El archivo supera el límite de {megabytes:.0f} MB."
        )


def listar_documentos_cotizacion(sesion: Session, cotizacion_id: str) -> list[Documento]:
    """Lista primero los documentos recibidos más recientemente."""

    consulta = (
        select(Documento)
        .where(Documento.cotizacion_id == cotizacion_id)
        .order_by(Documento.recibido_en.desc())
    )
    return list(sesion.scalars(consulta))


def obtener_documento(
    sesion: Session,
    *,
    cotizacion_id: str,
    documento_id: str,
) -> Documento | None:
    """Recupera un documento únicamente dentro de su cotización."""

    consulta = select(Documento).where(
        Documento.id == documento_id,
        Documento.cotizacion_id == cotizacion_id,
    )
    return sesion.scalar(consulta)


def _obtener_documento_por_clave(
    sesion: Session,
    *,
    cotizacion_id: str,
    clave_idempotencia: str,
) -> Documento | None:
    consulta = select(Documento).where(
        Documento.cotizacion_id == cotizacion_id,
        Documento.clave_idempotencia == clave_idempotencia,
    )
    return sesion.scalar(consulta)


def listar_partidas_documento(sesion: Session, documento_id: str) -> list[PartidaDocumento]:
    """Entrega las partidas en el orden visible para la revisión humana."""

    consulta = (
        select(PartidaDocumento)
        .where(PartidaDocumento.documento_id == documento_id)
        .order_by(PartidaDocumento.orden.asc())
    )
    return list(sesion.scalars(consulta))


def lectura_tiene_datos_utiles(lectura: LecturaDocumento) -> bool:
    """Evita tratar una respuesta estructurada completamente vacía como lectura válida."""

    if any(
        (
            lectura.tipo_documento,
            lectura.memorandum,
            lectura.folios,
            lectura.fecha_documento,
            lectura.municipio,
        )
    ):
        return True

    campos_partida = (
        "producto_solicitado",
        "marca_solicitada",
        "concentracion",
        "forma_farmaceutica_dispositivo",
        "presentacion_solicitada",
        "cantidad",
        "unidad_medida",
    )
    for partida in lectura.partidas:
        if any(getattr(partida, campo) not in (None, "") for campo in campos_partida):
            return True

    return False


def _reemplazar_partidas(
    sesion: Session,
    documento: Documento,
    partidas: list[PartidaLeida],
    decisiones_inclusion: list[DecisionInclusion] | None = None,
) -> None:
    """Sustituye partidas conservando la decisión humana de incluirlas o excluirlas."""

    sesion.execute(
        delete(PartidaDocumento).where(PartidaDocumento.documento_id == documento.id)
    )
    for indice, partida in enumerate(partidas, start=1):
        incluida = True
        motivo_exclusion = None
        if decisiones_inclusion and indice - 1 < len(decisiones_inclusion):
            incluida, motivo_exclusion = decisiones_inclusion[indice - 1]
        if incluida:
            motivo_exclusion = None
        else:
            motivo_exclusion = limpiar_motivo_exclusion(motivo_exclusion)

        sesion.add(
            PartidaDocumento(
                documento_id=documento.id,
                orden=indice,
                producto_solicitado=partida.producto_solicitado,
                marca_solicitada=partida.marca_solicitada,
                concentracion=partida.concentracion,
                forma_farmaceutica_dispositivo=partida.forma_farmaceutica_dispositivo,
                presentacion_solicitada=partida.presentacion_solicitada,
                cantidad=partida.cantidad,
                unidad_medida=partida.unidad_medida,
                incluida_cotizacion=incluida,
                motivo_exclusion=motivo_exclusion,
            )
        )


def _marcar_error_lectura(sesion: Session, documento: Documento, mensaje: str) -> Documento:
    """Persiste un fallo del lector sin crear un borrador engañoso de partidas."""

    documento.estado = EstadoDocumento.ERROR.value
    documento.error_lector = mensaje[:1000]
    _reemplazar_partidas(sesion, documento, [])
    sesion.add(documento)
    sesion.commit()
    sesion.refresh(documento)
    return documento


def procesar_documento(
    sesion: Session,
    *,
    cotizacion_id: str,
    nombre_archivo: str,
    mime_type: str,
    contenido: bytes,
    lector: LectorDocumento,
    clave_idempotencia: str | None = None,
) -> Documento:
    """Registra, conserva y lee un archivo; un reintento reutiliza el mismo registro."""

    huella = sha256(contenido).hexdigest()
    clave = limpiar_clave_idempotencia(clave_idempotencia)
    documento = None

    if clave:
        documento = _obtener_documento_por_clave(
            sesion,
            cotizacion_id=cotizacion_id,
            clave_idempotencia=clave,
        )
        if documento is not None:
            if documento.sha256 != huella:
                raise ArchivoDocumentoInvalido(
                    "El identificador de reintento ya corresponde a otro archivo."
                )
            if documento.contenido_original is None:
                documento.contenido_original = contenido
                sesion.add(documento)
                sesion.commit()
                sesion.refresh(documento)
            if documento.estado != EstadoDocumento.RECIBIDO.value:
                return documento

    if documento is None:
        documento = Documento(
            cotizacion_id=cotizacion_id,
            nombre_original=limpiar_nombre_archivo(nombre_archivo),
            mime_type=mime_type,
            tamano_bytes=len(contenido),
            sha256=huella,
            contenido_original=contenido,
            clave_idempotencia=clave,
            modelo_lector=lector.modelo,
        )
        sesion.add(documento)
        sesion.commit()
        sesion.refresh(documento)

    try:
        lectura = lector.leer(
            contenido=contenido,
            mime_type=mime_type,
            nombre_archivo=documento.nombre_original,
        )
    except ErrorLecturaDocumento as error:
        return _marcar_error_lectura(sesion, documento, str(error))

    if not lectura_tiene_datos_utiles(lectura):
        return _marcar_error_lectura(
            sesion,
            documento,
            "El lector respondió, pero no identificó información útil en el archivo. "
            "Vuelve a intentarlo o revisa que el documento sea legible.",
        )

    documento.tipo_documento = lectura.tipo_documento
    documento.memorandum = lectura.memorandum
    documento.folios = lectura.folios
    documento.fecha_documento = lectura.fecha_documento
    documento.municipio = lectura.municipio
    documento.parece_fragmento = lectura.parece_fragmento
    documento.senales_fragmento = lectura.senales_fragmento
    documento.estado = EstadoDocumento.ANALIZADO.value
    documento.analizado_en = ahora_utc()
    documento.error_lector = None
    _reemplazar_partidas(sesion, documento, lectura.partidas)
    sesion.add(documento)
    sesion.commit()
    sesion.refresh(documento)
    return documento


def guardar_revision(
    sesion: Session,
    *,
    documento: Documento,
    lectura_revisada: LecturaDocumento,
    usuario_id: str,
    decisiones_inclusion: list[DecisionInclusion] | None = None,
) -> Documento:
    """Guarda correcciones y resincroniza la referencia administrativa de la cotización."""

    documento.tipo_documento = lectura_revisada.tipo_documento
    documento.memorandum = lectura_revisada.memorandum
    documento.folios = lectura_revisada.folios
    documento.fecha_documento = lectura_revisada.fecha_documento
    documento.municipio = lectura_revisada.municipio
    documento.parece_fragmento = lectura_revisada.parece_fragmento
    documento.senales_fragmento = lectura_revisada.senales_fragmento
    documento.estado = EstadoDocumento.REVISADO.value
    documento.revisado_en = ahora_utc()
    documento.revisado_por_usuario_id = usuario_id
    _reemplazar_partidas(
        sesion,
        documento,
        lectura_revisada.partidas,
        decisiones_inclusion=decisiones_inclusion,
    )
    sesion.add(documento)
    sesion.commit()
    sesion.refresh(documento)

    from triage.cotizaciones.servicio import sincronizar_referencia_cotizacion

    sincronizar_referencia_cotizacion(sesion, documento.cotizacion_id)
    return documento


def eliminar_documento(sesion: Session, *, documento: Documento) -> None:
    """Elimina un archivo cargado por error y resincroniza la referencia automática."""

    cotizacion_id = documento.cotizacion_id
    sesion.execute(
        delete(PartidaDocumento).where(PartidaDocumento.documento_id == documento.id)
    )
    sesion.delete(documento)
    sesion.commit()

    from triage.cotizaciones.servicio import sincronizar_referencia_cotizacion

    sincronizar_referencia_cotizacion(sesion, cotizacion_id)