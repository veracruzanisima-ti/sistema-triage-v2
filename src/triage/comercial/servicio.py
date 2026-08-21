"""Registro y consulta de decisiones comerciales sin inferencias sanitarias."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from triage.comercial.modelos import (
    DecisionComercialPartida,
    EstadoComercial,
    FuenteDecisionComercial,
)
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.usuarios.modelos import Usuario


@dataclass(frozen=True)
class DecisionComercialActual:
    """Último evento aplicable a una partida; la ausencia equivale a cotizable."""

    estado: EstadoComercial
    motivo: str | None = None
    fuente_validacion: str | None = None
    regla_referencia: str | None = None
    decidida_por_usuario_id: str | None = None
    decidida_por_nombre: str | None = None
    creada_en: datetime | None = None


def decision_cotizable_por_defecto() -> DecisionComercialActual:
    """Mantiene compatibilidad: ninguna decisión previa significa cotizable."""

    return DecisionComercialActual(estado=EstadoComercial.COTIZABLE)


def _limpiar(valor: str | None) -> str | None:
    if valor is None:
        return None
    limpio = " ".join(valor.split())
    return limpio or None


def _partida_elegible(
    sesion: Session,
    *,
    cotizacion_id: str,
    partida_id: str,
) -> PartidaDocumento | None:
    return sesion.scalar(
        select(PartidaDocumento)
        .join(Documento)
        .where(
            PartidaDocumento.id == partida_id,
            Documento.cotizacion_id == cotizacion_id,
            Documento.estado == EstadoDocumento.REVISADO.value,
            PartidaDocumento.incluida_cotizacion.is_(True),
        )
    )


def registrar_decision_comercial(
    sesion: Session,
    *,
    cotizacion_id: str,
    partida_id: str,
    usuario_id: str,
    estado: EstadoComercial,
    motivo: str | None,
) -> DecisionComercialPartida:
    """Agrega un evento manual; nunca reescribe una decisión anterior."""

    if _partida_elegible(
        sesion,
        cotizacion_id=cotizacion_id,
        partida_id=partida_id,
    ) is None:
        raise ValueError("la partida ya no pertenece al flujo cotizable")

    motivo_limpio = _limpiar(motivo)
    if estado == EstadoComercial.NO_SE_COTIZA and not motivo_limpio:
        raise ValueError("indica el motivo para marcar NO SE COTIZA")
    if motivo_limpio and len(motivo_limpio) > 500:
        raise ValueError("el motivo no puede exceder 500 caracteres")

    decision = DecisionComercialPartida(
        cotizacion_id=cotizacion_id,
        partida_documento_id=partida_id,
        estado=estado.value,
        motivo=motivo_limpio,
        fuente_validacion=FuenteDecisionComercial.REVISION_HUMANA.value,
        regla_referencia=None,
        decidida_por_usuario_id=usuario_id,
    )
    sesion.add(decision)
    sesion.commit()
    sesion.refresh(decision)
    return decision


def listar_decisiones_comerciales_actuales(
    sesion: Session,
    cotizacion_id: str,
) -> dict[str, DecisionComercialActual]:
    """Devuelve el evento más reciente por partida dentro de la cotización."""

    ultimas: dict[str, DecisionComercialPartida] = {}
    for decision in sesion.scalars(
        select(DecisionComercialPartida)
        .where(DecisionComercialPartida.cotizacion_id == cotizacion_id)
        .order_by(
            DecisionComercialPartida.creada_en.desc(),
            DecisionComercialPartida.id.desc(),
        )
    ):
        if decision.partida_documento_id:
            ultimas.setdefault(decision.partida_documento_id, decision)

    usuarios_ids = {decision.decidida_por_usuario_id for decision in ultimas.values()}
    nombres = (
        {
            usuario.id: usuario.nombre
            for usuario in sesion.scalars(select(Usuario).where(Usuario.id.in_(usuarios_ids)))
        }
        if usuarios_ids
        else {}
    )
    return {
        partida_id: DecisionComercialActual(
            estado=EstadoComercial(decision.estado),
            motivo=decision.motivo,
            fuente_validacion=decision.fuente_validacion,
            regla_referencia=decision.regla_referencia,
            decidida_por_usuario_id=decision.decidida_por_usuario_id,
            decidida_por_nombre=nombres.get(decision.decidida_por_usuario_id),
            creada_en=decision.creada_en,
        )
        for partida_id, decision in ultimas.items()
    }


def partida_no_se_cotiza(
    sesion: Session,
    *,
    cotizacion_id: str,
    partida_id: str,
) -> bool:
    """Consulta el último evento sin convertir alertas sanitarias en decisiones."""

    decision = sesion.scalar(
        select(DecisionComercialPartida)
        .where(
            DecisionComercialPartida.cotizacion_id == cotizacion_id,
            DecisionComercialPartida.partida_documento_id == partida_id,
        )
        .order_by(
            DecisionComercialPartida.creada_en.desc(),
            DecisionComercialPartida.id.desc(),
        )
        .limit(1)
    )
    return bool(decision and decision.estado == EstadoComercial.NO_SE_COTIZA.value)


def asegurar_partida_cotizable(
    sesion: Session,
    *,
    cotizacion_id: str,
    partida_id: str,
) -> None:
    """Impide generar evidencia de precio para un resultado no cotizable."""

    if partida_no_se_cotiza(
        sesion,
        cotizacion_id=cotizacion_id,
        partida_id=partida_id,
    ):
        raise ValueError("La partida está marcada como NO SE COTIZA.")
