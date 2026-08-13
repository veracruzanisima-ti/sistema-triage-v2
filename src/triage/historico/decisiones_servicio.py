"""Registro y lectura de decisiones humanas sobre observaciones de precio."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.historico.decisiones_modelos import DecisionPrecio, RolDecisionPrecio
from triage.historico.modelos import ObservacionPrecio
from triage.historico.servicio import clave_producto
from triage.normalizacion.modelos import NormalizacionPartida


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
    clave = clave_producto(normalizacion)

    if observacion_id:
        observacion = sesion.get(ObservacionPrecio, observacion_id)
        if observacion is None:
            raise ValueError("la observación seleccionada ya no existe")
        if observacion.clave_producto != clave:
            raise ValueError("la observación pertenece a otra identidad de producto")

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
        return decision.observacion_precio_id

    return {
        partida_id: SeleccionActual(
            referencia_estable_id=vigente(partida_id, RolDecisionPrecio.REFERENCIA_ESTABLE),
            oportunidad_adquisicion_id=vigente(
                partida_id, RolDecisionPrecio.OPORTUNIDAD_ADQUISICION
            ),
        )
        for partida_id in claves
    }
