"""Registro y lectura de decisiones humanas sobre observaciones de precio."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from triage.comercial.servicio import asegurar_partida_cotizable
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.historico.decisiones_modelos import DecisionPrecio, RolDecisionPrecio
from triage.historico.modelos import ObservacionPrecio
from triage.historico.servicio import clave_producto
from triage.normalizacion.modelos import NormalizacionPartida

_ZONA_OPERATIVA = ZoneInfo("America/Mexico_City")


@dataclass(frozen=True)
class SeleccionActual:
    referencia_estable_id: str | None = None
    oportunidad_adquisicion_id: str | None = None


def _normalizacion_actual(
    sesion: Session,
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


def _momento_utc(valor: datetime) -> datetime:
    """Normaliza timestamps para comparar SQLite y PostgreSQL de forma consistente."""

    if valor.tzinfo is None:
        return valor.replace(tzinfo=UTC)
    return valor.astimezone(UTC)


def _fecha_operativa(valor: datetime) -> date:
    """Convierte timestamps al día operativo de México."""

    return _momento_utc(valor).astimezone(_ZONA_OPERATIVA).date()


def observacion_apta_como_referencia(observacion: ObservacionPrecio | None) -> bool:
    """Una referencia requiere precio no promocional y disponibilidad operativa confirmada."""

    return bool(
        observacion is not None
        and not observacion.es_promocion
        and observacion.disponibilidad_operativa is True
    )


def registrar_decision_precio(
    sesion: Session,
    *,
    cotizacion_id: str,
    partida_id: str,
    usuario_id: str,
    rol: RolDecisionPrecio,
    observacion_id: str | None,
) -> DecisionPrecio:
    """Agrega un evento nuevo; observación nula significa retirar la selección."""

    normalizacion = _normalizacion_actual(sesion, cotizacion_id, partida_id)
    if normalizacion is None:
        raise ValueError("la partida ya no está preparada o dejó de ser elegible")
    asegurar_partida_cotizable(
        sesion,
        cotizacion_id=cotizacion_id,
        partida_id=partida_id,
    )
    clave = clave_producto(normalizacion)

    if observacion_id:
        observacion = sesion.get(ObservacionPrecio, observacion_id)
        if observacion is None:
            raise ValueError("la observación seleccionada ya no existe")
        if observacion.clave_producto != clave:
            raise ValueError("la observación pertenece a otra identidad de producto")
        if rol == RolDecisionPrecio.REFERENCIA_ESTABLE:
            if observacion.es_promocion:
                raise ValueError("una promoción no puede usarse como referencia estable")
            if observacion.disponibilidad_operativa is not True:
                raise ValueError(
                    "la disponibilidad y entrega deben estar confirmadas antes de cotizar"
                )

    decision = DecisionPrecio(
        cotizacion_id=cotizacion_id,
        partida_documento_id=partida_id,
        clave_producto=clave,
        rol=rol.value,
        observacion_precio_id=observacion_id or None,
        decidida_por_usuario_id=usuario_id,
    )
    sesion.add(decision)
    sesion.commit()
    sesion.refresh(decision)
    return decision


def referencias_estables_cotizadas_hoy(
    sesion: Session,
    *,
    claves: set[str],
    codigo_postal: str | None,
    ahora: datetime | None = None,
) -> dict[str, ObservacionPrecio]:
    """Devuelve por identidad la referencia realmente usada hoy con el mismo CP."""

    if not claves or not codigo_postal:
        return {}

    ahora = ahora or datetime.now(UTC)
    fecha_hoy = _fecha_operativa(ahora)

    ultimas_por_partida: dict[tuple[str, str], DecisionPrecio] = {}
    for decision in sesion.scalars(
        select(DecisionPrecio)
        .where(DecisionPrecio.rol == RolDecisionPrecio.REFERENCIA_ESTABLE.value)
        .order_by(DecisionPrecio.creada_en.desc())
    ):
        if decision.partida_documento_id is None:
            continue
        llave = (decision.cotizacion_id, decision.partida_documento_id)
        ultimas_por_partida.setdefault(llave, decision)

    resultado: dict[str, ObservacionPrecio] = {}
    for decision in ultimas_por_partida.values():
        if decision.clave_producto not in claves:
            continue
        if decision.observacion_precio_id is None:
            continue
        if _fecha_operativa(decision.creada_en) != fecha_hoy:
            continue

        observacion = sesion.get(ObservacionPrecio, decision.observacion_precio_id)
        if observacion is None:
            continue
        if observacion.clave_producto != decision.clave_producto:
            continue
        if not observacion_apta_como_referencia(observacion):
            continue
        if observacion.codigo_postal != codigo_postal:
            continue
        if _fecha_operativa(observacion.observado_en) != fecha_hoy:
            continue

        actual = resultado.get(decision.clave_producto)
        if actual is None or _momento_utc(observacion.observado_en) > _momento_utc(
            actual.observado_en
        ):
            resultado[decision.clave_producto] = observacion

    return resultado


def listar_selecciones_actuales(
    sesion: Session,
    cotizacion_id: str,
) -> dict[str, SeleccionActual]:
    """Usa el último evento de cada rol sólo si corresponde a la identidad actual."""

    filas = list(
        sesion.execute(
            select(NormalizacionPartida, PartidaDocumento)
            .join(PartidaDocumento)
            .join(Documento)
            .where(
                Documento.cotizacion_id == cotizacion_id,
                Documento.estado == EstadoDocumento.REVISADO.value,
                PartidaDocumento.incluida_cotizacion.is_(True),
            )
        )
    )
    claves = {partida.id: clave_producto(normalizacion) for normalizacion, partida in filas}
    if not claves:
        return {}

    ultimas: dict[tuple[str, str], DecisionPrecio] = {}
    for decision in sesion.scalars(
        select(DecisionPrecio)
        .where(DecisionPrecio.cotizacion_id == cotizacion_id)
        .order_by(DecisionPrecio.creada_en.desc())
    ):
        if decision.partida_documento_id not in claves:
            continue
        llave = (decision.partida_documento_id, decision.rol)
        ultimas.setdefault(llave, decision)

    def vigente(partida_id: str, rol: RolDecisionPrecio) -> str | None:
        decision = ultimas.get((partida_id, rol.value))
        if decision is None or decision.clave_producto != claves[partida_id]:
            return None
        observacion_id = decision.observacion_precio_id
        if observacion_id and rol == RolDecisionPrecio.REFERENCIA_ESTABLE:
            observacion = sesion.get(ObservacionPrecio, observacion_id)
            if not observacion_apta_como_referencia(observacion):
                return None
        return observacion_id

    return {
        partida_id: SeleccionActual(
            referencia_estable_id=vigente(partida_id, RolDecisionPrecio.REFERENCIA_ESTABLE),
            oportunidad_adquisicion_id=vigente(
                partida_id, RolDecisionPrecio.OPORTUNIDAD_ADQUISICION
            ),
        )
        for partida_id in claves
    }
