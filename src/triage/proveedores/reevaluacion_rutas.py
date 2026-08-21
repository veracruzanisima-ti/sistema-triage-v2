"""Reevaluación de sólo lectura para descartes web históricos."""

from dataclasses import dataclass
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from triage.documentos.modelos import Documento, PartidaDocumento
from triage.historico.modelos import (
    LIMITE_FUENTE_OBSERVACION,
    LIMITE_PRODUCTO_OBSERVADO,
    LIMITE_PROVEEDOR_OBSERVACION,
)
from triage.normalizacion.modelos import NormalizacionPartida
from triage.proveedores.base import SolicitudProveedor
from triage.proveedores.cofepris_servicio import resolver_identidad_cofepris
from triage.proveedores.coincidencia_catalogo import CandidatoCatalogo, evaluar_candidato
from triage.proveedores.modelos import CandidatoWebDescartado, ConsultaWeb
from triage.usuarios.seguridad import Sesion, UsuarioActual

router = APIRouter(tags=["proveedores"])


@dataclass(frozen=True)
class EvaluacionActualDescarte:
    """Resultado recalculado sin modificar la evidencia histórica."""

    motivos: tuple[str, ...]
    evidencia_identidad: dict[str, object] | None = None

    @property
    def compatible(self) -> bool:
        return not self.motivos


def _limpiar(valor: str | None) -> str | None:
    if valor is None:
        return None
    limpio = " ".join(valor.split())
    return limpio or None


def evaluar_descarte_con_reglas_actuales(
    sesion: Sesion,
    *,
    normalizacion: NormalizacionPartida,
    descartado: CandidatoWebDescartado,
    codigo_postal: str | None,
) -> EvaluacionActualDescarte:
    """Repite sólo validaciones locales reproducibles con los datos persistidos."""

    proveedor = _limpiar(descartado.proveedor)
    producto_observado = _limpiar(descartado.producto_observado)
    motivos: list[str] = []
    evidencia_identidad: dict[str, object] | None = None

    if proveedor is None:
        motivos.append("proveedor o fuente no identificada")
    elif len(proveedor) > LIMITE_PROVEEDOR_OBSERVACION:
        motivos.append("proveedor excede el límite del histórico cotizable")
    if producto_observado is None:
        motivos.append("faltan datos suficientes para comprobar coincidencia")
    elif len(producto_observado) > LIMITE_PRODUCTO_OBSERVADO:
        motivos.append("producto observado excede el límite del histórico cotizable")
    if len(descartado.url) > LIMITE_FUENTE_OBSERVACION:
        motivos.append("URL excede el límite del histórico cotizable")
    if descartado.precio_observado is None:
        motivos.append("precio no visible")

    solicitud = SolicitudProveedor(
        partida_documento_id=normalizacion.partida_documento_id,
        producto=_limpiar(normalizacion.producto),
        marca=_limpiar(normalizacion.marca),
        concentracion=_limpiar(normalizacion.concentracion),
        forma_dispositivo=_limpiar(normalizacion.forma_dispositivo),
        presentacion=_limpiar(normalizacion.presentacion),
        codigo_postal=_limpiar(codigo_postal),
    )
    if producto_observado is not None:
        evaluacion = evaluar_candidato(
            solicitud,
            CandidatoCatalogo(
                descripcion=producto_observado,
                precio_observado=descartado.precio_observado or Decimal("1"),
                stock=None,
                fuente=descartado.url,
            ),
        )
        motivos.extend(evaluacion.motivos)
        if not _limpiar(solicitud.marca) and "producto distinto" in motivos:
            evidencia = resolver_identidad_cofepris(
                sesion,
                producto_solicitado=solicitud.producto,
                producto_observado=producto_observado,
            )
            if evidencia is not None:
                motivos = [motivo for motivo in motivos if motivo != "producto distinto"]
                evidencia_identidad = evidencia.como_json()

    return EvaluacionActualDescarte(
        motivos=tuple(dict.fromkeys(motivos)),
        evidencia_identidad=evidencia_identidad,
    )


@router.get(
    "/cotizaciones/{cotizacion_id}/proveedores/{partida_id}/descartados/{descartado_id}/evaluacion-actual",
    response_class=HTMLResponse,
)
def ver_evaluacion_actual_descarte(
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    cotizacion_id: str,
    partida_id: str,
    descartado_id: str,
):
    """Contrasta un descarte histórico con las reglas vigentes sin mutarlo."""

    fila = sesion.execute(
        select(CandidatoWebDescartado, ConsultaWeb, NormalizacionPartida, PartidaDocumento)
        .join(ConsultaWeb, ConsultaWeb.id == CandidatoWebDescartado.consulta_web_id)
        .join(
            NormalizacionPartida,
            NormalizacionPartida.partida_documento_id == ConsultaWeb.partida_documento_id,
        )
        .join(
            PartidaDocumento,
            PartidaDocumento.id == NormalizacionPartida.partida_documento_id,
        )
        .join(Documento, Documento.id == PartidaDocumento.documento_id)
        .where(
            CandidatoWebDescartado.id == descartado_id,
            ConsultaWeb.partida_documento_id == partida_id,
            Documento.cotizacion_id == cotizacion_id,
        )
    ).one_or_none()
    if fila is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    descartado, consulta, normalizacion, partida = fila
    codigo_postal = consulta.criterios_busqueda.get("codigo_postal")
    if codigo_postal is not None and not isinstance(codigo_postal, str):
        codigo_postal = None
    evaluacion_actual = evaluar_descarte_con_reglas_actuales(
        sesion,
        normalizacion=normalizacion,
        descartado=descartado,
        codigo_postal=codigo_postal,
    )

    return request.app.state.plantillas.TemplateResponse(
        request=request,
        name="proveedores/evaluacion_descarte.html",
        context={
            "usuario": usuario,
            "cotizacion_id": cotizacion_id,
            "partida": partida,
            "normalizacion": normalizacion,
            "consulta": consulta,
            "descartado": descartado,
            "evaluacion_actual": evaluacion_actual,
        },
    )
