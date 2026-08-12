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


class ArchivoDocumentoInvalido(ValueError):
    """El archivo no cumple las reglas mínimas de entrada del MVP."""


def limpiar_nombre_archivo(nombre: str | None) -> str:
    """Conserva sólo el nombre final y evita rutas suministradas por el cliente."""

    nombre_limpio = Path(nombre or "documento").name.strip()
    return (nombre_limpio or "documento")[:255]


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
    """Lista primero los documentos activos recibidos más recientemente."""

    consulta = (
        select(Documento)
        .where(
            Documento.cotizacion_id == cotizacion_id,
            Documento.estado != EstadoDocumento.DESCARTADO.value,
        )
        .order_by(Documento.recibido_en.desc())
    )
    return list(sesion.scalars(consulta))


def obtener_documento(
    sesion: Session,
    *,
    cotizacion_id: str,
    documento_id: str,
) -> Documento | None:
    """Recupera un documento activo únicamente dentro de su cotización."""

    consulta = select(Documento).where(
        Documento.id == documento_id,
        Documento.cotizacion_id == cotizacion_id,
        Documento.estado != EstadoDocumento.DESCARTADO.value,
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


def _reemplazar_partidas(
    sesion: Session,
    documento: Documento,
    partidas: list[PartidaLeida],
) -> None:
    """Sustituye el borrador de partidas por la versión que se está guardando."""

    sesion.execute(
        delete(PartidaDocumento).where(PartidaDocumento.documento_id == documento.id)
    )
    for indice, partida in enumerate(partidas, start=1):
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
            )
        )


def procesar_documento(
    sesion: Session,
    *,
    cotizacion_id: str,
    nombre_archivo: str,
    mime_type: str,
    contenido: bytes,
    lector: LectorDocumento,
) -> Documento:
    """Registra metadatos, ejecuta el lector y persiste un borrador revisable."""

    documento = Documento(
        cotizacion_id=cotizacion_id,
        nombre_original=limpiar_nombre_archivo(nombre_archivo),
        mime_type=mime_type,
        tamano_bytes=len(contenido),
        sha256=sha256(contenido).hexdigest(),
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
        documento.estado = EstadoDocumento.ERROR.value
        documento.error_lector = str(error)[:1000]
        sesion.add(documento)
        sesion.commit()
        sesion.refresh(documento)
        return documento

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
) -> Documento:
    """Guarda la versión corregida por una persona y la marca como revisada."""

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
    _reemplazar_partidas(sesion, documento, lectura_revisada.partidas)
    sesion.add(documento)
    sesion.commit()
    sesion.refresh(documento)
    return documento


def descartar_documento(
    sesion: Session,
    *,
    documento: Documento,
    usuario_id: str,
) -> Documento:
    """Quita un documento del flujo activo sin borrar su rastro de auditoría."""

    documento.estado = EstadoDocumento.DESCARTADO.value
    documento.descartado_en = ahora_utc()
    documento.descartado_por_usuario_id = usuario_id
    sesion.add(documento)
    sesion.commit()
    sesion.refresh(documento)
    return documento
