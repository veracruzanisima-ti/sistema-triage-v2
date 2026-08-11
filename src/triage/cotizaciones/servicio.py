"""Operaciones de negocio mínimas para cotizaciones persistentes."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from triage.cotizaciones.modelos import Cotizacion, EstadoCotizacion, ahora_utc


def limpiar_referencia(referencia: str | None) -> str | None:
    """Conserva una referencia útil sin obligar a conocer el memorándum al inicio."""

    if referencia is None:
        return None
    valor = " ".join(referencia.split())
    return valor or None


def crear_cotizacion(sesion: Session, referencia: str | None = None) -> Cotizacion:
    """Crea una unidad de trabajo recuperable por futuras sesiones."""

    cotizacion = Cotizacion(referencia=limpiar_referencia(referencia))
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
