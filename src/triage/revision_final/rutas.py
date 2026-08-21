"""Rutas de revisión consolidada previa al cierre."""

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from triage.comercial.modelos import EstadoComercial
from triage.comercial.servicio import registrar_decision_comercial
from triage.cotizaciones.servicio import obtener_cotizacion
from triage.normalizacion.servicio import resumen_normalizacion_cotizacion
from triage.revision_final.servicio import listar_precierre
from triage.usuarios.seguridad import (
    Sesion,
    UsuarioActual,
    obtener_token_csrf,
    validar_token_csrf,
)

router = APIRouter(prefix="/cotizaciones", tags=["revision-final"])


def _render(
    cotizacion_id: str,
    request: Request,
    sesion: Sesion,
    usuario,
    *,
    error: str = "",
    status_code: int = status.HTTP_200_OK,
):
    cotizacion = obtener_cotizacion(sesion, cotizacion_id)
    if cotizacion is None:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    productos = listar_precierre(sesion, cotizacion_id)
    resumen = resumen_normalizacion_cotizacion(sesion, cotizacion_id)
    return request.app.state.plantillas.TemplateResponse(
        request=request,
        name="revision_final/lista.html",
        context={
            "usuario": usuario,
            "csrf_token": obtener_token_csrf(request),
            "cotizacion": cotizacion,
            "productos": productos,
            "estados_comerciales": EstadoComercial,
            "total_incluidas": resumen.total,
            "sin_preparar": max(resumen.total - resumen.preparados, 0),
            "con_referencia": sum(
                item.referencia is not None
                and item.decision_comercial.estado == EstadoComercial.COTIZABLE
                for item in productos
            ),
            "no_se_cotiza": sum(
                item.decision_comercial.estado == EstadoComercial.NO_SE_COTIZA
                for item in productos
            ),
            "con_alertas": sum(bool(item.alertas) for item in productos),
            "error": error,
        },
        status_code=status_code,
    )


@router.get("/{cotizacion_id}/revision-final", response_class=HTMLResponse)
def ver_revision_final(
    cotizacion_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
):
    """Muestra una vista integrada sin ejecutar decisiones automáticas."""

    return _render(cotizacion_id, request, sesion, usuario)


@router.post("/{cotizacion_id}/revision-final/{partida_id}/estado-comercial")
def guardar_estado_comercial(
    cotizacion_id: str,
    partida_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    csrf_token: Annotated[str, Form()],
    estado: Annotated[str, Form()],
    motivo: Annotated[str, Form()] = "",
):
    """Registra una decisión humana sin convertir alertas en bloqueos automáticos."""

    validar_token_csrf(request, csrf_token)
    if obtener_cotizacion(sesion, cotizacion_id) is None:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    try:
        estado_validado = EstadoComercial(estado)
    except ValueError:
        return _render(
            cotizacion_id,
            request,
            sesion,
            usuario,
            error="Estado comercial no válido.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    try:
        registrar_decision_comercial(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_id=partida_id,
            usuario_id=usuario.id,
            estado=estado_validado,
            motivo=motivo,
        )
    except ValueError as error:
        return _render(
            cotizacion_id,
            request,
            sesion,
            usuario,
            error=str(error),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    return RedirectResponse(
        url=f"/cotizaciones/{cotizacion_id}/revision-final",
        status_code=status.HTTP_303_SEE_OTHER,
    )
