"""Operaciones de negocio mínimas para cotizaciones persistentes."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from triage.cotizaciones.modelos import Cotizacion, EstadoCotizacion, ahora_utc
from triage.documentos.modelos import Documento, EstadoDocumento


def limpiar_referencia(referencia: str | None) -> str | None:
    """Conserva una referencia útil sin obligar a conocer el memorándum al inicio."""

    if referencia is None:
        return None
    valor = " ".join(referencia.split())
    return valor or None


def limpiar_codigo_postal(codigo_postal: str | None) -> str | None:
    """Normaliza un CP mexicano sin inventar ubicación cuando no fue proporcionado."""

    if codigo_postal is None:
        return None
    valor = codigo_postal.strip()
    if not valor:
        return None
    if len(valor) != 5 or not valor.isdigit():
        raise ValueError("El código postal debe contener exactamente 5 dígitos.")
    return valor


def crear_cotizacion(
    sesion: Session,
    referencia: str | None = None,
    codigo_postal_consulta: str | None = None,
) -> Cotizacion:
    """Crea una unidad de trabajo recuperable por futuras sesiones."""

    referencia_limpia = limpiar_referencia(referencia)
    cotizacion = Cotizacion(
        referencia=referencia_limpia,
        referencia_fijada_manual=referencia_limpia is not None,
        codigo_postal_consulta=limpiar_codigo_postal(codigo_postal_consulta),
    )
    sesion.add(cotizacion)
    sesion.commit()
    sesion.refresh(cotizacion)
    return cotizacion


def listar_cotizaciones(sesion: Session) -> list[Cotizacion]:
    """Devuelve primero las cotizaciones modificadas más recientemente."""

    consulta = select(Cotizacion).order_by(Cotizacion.actualizada_en.desc())
    return list(sesion.scalars(consulta))


def obtener_cotizacion(sesion: Session, cotizacion_id: str) -> Cotizacion | None:
    """Recupera una cotización por su identificador interno."""

    return sesion.get(Cotizacion, cotizacion_id)


def referencias_documentos_revisados(sesion: Session, cotizacion_id: str) -> list[str]:
    """Lista referencias distintas confirmadas por personas en documentos revisados."""

    consulta = select(Documento.memorandum).where(
        Documento.cotizacion_id == cotizacion_id,
        Documento.estado == EstadoDocumento.REVISADO.value,
        Documento.memorandum.is_not(None),
    )
    referencias = {
        referencia_limpia
        for referencia in sesion.scalars(consulta)
        if (referencia_limpia := limpiar_referencia(referencia)) is not None
    }
    return sorted(referencias)


def sincronizar_referencia_cotizacion(
    sesion: Session,
    cotizacion_id: str,
) -> list[str]:
    """Sincroniza sólo cuando una referencia revisada es inequívoca y no está fijada."""

    cotizacion = obtener_cotizacion(sesion, cotizacion_id)
    if cotizacion is None:
        return []

    referencias = referencias_documentos_revisados(sesion, cotizacion_id)
    if cotizacion.referencia_fijada_manual:
        return referencias

    nueva_referencia = referencias[0] if len(referencias) == 1 else None
    if cotizacion.referencia != nueva_referencia:
        cotizacion.referencia = nueva_referencia
        cotizacion.actualizada_en = ahora_utc()
        sesion.add(cotizacion)
        sesion.commit()
        sesion.refresh(cotizacion)

    return referencias


def actualizar_referencia_manual(
    sesion: Session,
    cotizacion: Cotizacion,
    referencia: str | None,
) -> Cotizacion:
    """Fija una referencia elegida por una persona y evita sobrescrituras automáticas."""

    referencia_limpia = limpiar_referencia(referencia)
    if referencia_limpia is None:
        raise ValueError("Escribe una referencia antes de guardarla.")

    cotizacion.referencia = referencia_limpia
    cotizacion.referencia_fijada_manual = True
    cotizacion.actualizada_en = ahora_utc()
    sesion.add(cotizacion)
    sesion.commit()
    sesion.refresh(cotizacion)
    return cotizacion


def actualizar_codigo_postal_consulta(
    sesion: Session,
    cotizacion: Cotizacion,
    codigo_postal: str | None,
) -> Cotizacion:
    """Cambia el contexto geográfico que usarán las consultas nuevas."""

    valor = limpiar_codigo_postal(codigo_postal)
    if valor is None:
        raise ValueError("Escribe un código postal antes de guardarlo.")
    cotizacion.codigo_postal_consulta = valor
    cotizacion.actualizada_en = ahora_utc()
    sesion.add(cotizacion)
    sesion.commit()
    sesion.refresh(cotizacion)
    return cotizacion


def usar_referencia_automatica(sesion: Session, cotizacion: Cotizacion) -> Cotizacion:
    """Libera una referencia manual para volver a usar documentos revisados."""

    cotizacion.referencia_fijada_manual = False
    cotizacion.referencia = None
    cotizacion.actualizada_en = ahora_utc()
    sesion.add(cotizacion)
    sesion.commit()
    sincronizar_referencia_cotizacion(sesion, cotizacion.id)
    sesion.refresh(cotizacion)
    return cotizacion


def actualizar_estado(
    sesion: Session,
    cotizacion: Cotizacion,
    estado: EstadoCotizacion,
) -> Cotizacion:
    """Actualiza un estado explícitamente elegido por una persona."""

    cotizacion.estado = estado.value
    cotizacion.actualizada_en = ahora_utc()
    sesion.add(cotizacion)
    sesion.commit()
    sesion.refresh(cotizacion)
    return cotizacion
