"""Reglas mínimas para preparar partidas revisadas sin alterar la solicitud original."""

from dataclasses import dataclass
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.normalizacion.modelos import NormalizacionPartida


@dataclass(frozen=True)
class ValoresNormalizacion:
    """Campos editables que después alimentarán búsquedas y comparaciones."""

    producto: str | None
    marca: str | None
    concentracion: str | None
    forma_dispositivo: str | None
    presentacion: str | None


@dataclass(frozen=True)
class EntradaNormalizacion:
    """Une evidencia revisada, propuesta conservadora y valor ya confirmado."""

    partida: PartidaDocumento
    documento: Documento
    normalizacion: NormalizacionPartida | None
    propuesta: ValoresNormalizacion


@dataclass(frozen=True)
class ResumenNormalizacion:
    total: int
    preparados: int


def _limpiar_texto(valor: str | None) -> str | None:
    if valor is None:
        return None
    limpio = " ".join(valor.split())
    return limpio or None


def _normalizar_unidades(valor: str | None) -> str | None:
    """Corrige sólo formato inequívoco; no infiere concentración ni presentación."""

    limpio = _limpiar_texto(valor)
    if limpio is None:
        return None
    limpio = re.sub(r"\bmg\s*/\s*ml\b", "mg/mL", limpio, flags=re.IGNORECASE)
    limpio = re.sub(r"\bml\b", "mL", limpio, flags=re.IGNORECASE)
    return limpio


def propuesta_desde_partida(partida: PartidaDocumento) -> ValoresNormalizacion:
    """Copia la revisión humana aplicando únicamente limpieza tipográfica segura."""

    return ValoresNormalizacion(
        producto=_limpiar_texto(partida.producto_solicitado),
        marca=_limpiar_texto(partida.marca_solicitada),
        concentracion=_normalizar_unidades(partida.concentracion),
        forma_dispositivo=_limpiar_texto(partida.forma_farmaceutica_dispositivo),
        presentacion=_normalizar_unidades(partida.presentacion_solicitada),
    )


def listar_partidas_normalizables(
    sesion: Session,
    cotizacion_id: str,
) -> list[EntradaNormalizacion]:
    """Incluye únicamente partidas vigentes de documentos aprobados por una persona."""

    consulta = (
        select(PartidaDocumento, Documento, NormalizacionPartida)
        .join(Documento, Documento.id == PartidaDocumento.documento_id)
        .outerjoin(
            NormalizacionPartida,
            NormalizacionPartida.partida_documento_id == PartidaDocumento.id,
        )
        .where(
            Documento.cotizacion_id == cotizacion_id,
            Documento.estado == EstadoDocumento.REVISADO.value,
            PartidaDocumento.incluida_cotizacion.is_(True),
        )
        .order_by(Documento.recibido_en.asc(), PartidaDocumento.orden.asc())
    )
    return [
        EntradaNormalizacion(
            partida=partida,
            documento=documento,
            normalizacion=normalizacion,
            propuesta=propuesta_desde_partida(partida),
        )
        for partida, documento, normalizacion in sesion.execute(consulta)
    ]


def resumen_normalizacion_cotizacion(
    sesion: Session,
    cotizacion_id: str,
) -> ResumenNormalizacion:
    """Cuenta partidas elegibles y cuántas ya tienen una preparación confirmada."""

    base = (
        select(PartidaDocumento.id)
        .join(Documento, Documento.id == PartidaDocumento.documento_id)
        .where(
            Documento.cotizacion_id == cotizacion_id,
            Documento.estado == EstadoDocumento.REVISADO.value,
            PartidaDocumento.incluida_cotizacion.is_(True),
        )
        .subquery()
    )
    total = sesion.scalar(select(func.count()).select_from(base)) or 0
    preparados = sesion.scalar(
        select(func.count())
        .select_from(NormalizacionPartida)
        .where(NormalizacionPartida.partida_documento_id.in_(select(base.c.id)))
    ) or 0
    return ResumenNormalizacion(total=int(total), preparados=int(preparados))


def guardar_normalizaciones(
    sesion: Session,
    *,
    cotizacion_id: str,
    usuario_id: str,
    valores_por_partida: dict[str, ValoresNormalizacion],
) -> None:
    """Guarda sólo partidas que siguen siendo revisadas e incluidas en esta cotización."""

    elegibles = {
        entrada.partida.id: entrada
        for entrada in listar_partidas_normalizables(sesion, cotizacion_id)
    }
    if set(valores_por_partida) != set(elegibles):
        raise ValueError(
            "La lista de partidas cambió. Recarga la página antes de guardar la preparación."
        )

    for partida_id, valores in valores_por_partida.items():
        normalizacion = sesion.get(NormalizacionPartida, partida_id)
        if normalizacion is None:
            normalizacion = NormalizacionPartida(
                partida_documento_id=partida_id,
                confirmada_por_usuario_id=usuario_id,
            )
        normalizacion.producto = _limpiar_texto(valores.producto)
        normalizacion.marca = _limpiar_texto(valores.marca)
        normalizacion.concentracion = _normalizar_unidades(valores.concentracion)
        normalizacion.forma_dispositivo = _limpiar_texto(valores.forma_dispositivo)
        normalizacion.presentacion = _normalizar_unidades(valores.presentacion)
        normalizacion.confirmada_por_usuario_id = usuario_id
        sesion.add(normalizacion)

    sesion.commit()
