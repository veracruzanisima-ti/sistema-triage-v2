"""Pantalla separada para elegir evidencia de referencia y adquisición."""

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from triage.cotizaciones.servicio import obtener_cotizacion
from triage.historico.decisiones_modelos import RolDecisionPrecio
from triage.historico.decisiones_servicio import (
    listar_selecciones_actuales,
    registrar_decision_precio,
)
from triage.historico.servicio import listar_productos_historico
from triage.usuarios.seguridad import Sesion, UsuarioActual, obtener_token_csrf, validar_token_csrf

router = APIRouter(prefix="/cotizaciones", tags=["decisiones-precio"])


def _plantillas(request: Request):
    return request.app.state.plantillas


def _render(request: Request, sesion: Sesion, usuario, cotizacion, *, error: str = ""):
    return _plantillas(request).TemplateResponse(
        request=request,
        name="historico/decisiones.html",
        context={
            "usuario": usuario,
            "csrf_token": obtener_token_csrf(request),
            "cotizacion": cotizacion,
            "productos": listar_productos_historico(sesion, cotizacion.id),
            "selecciones": listar_selecciones_actuales(sesion, cotizacion.id),
            "roles": RolDecisionPrecio,
            "error": error,
        },
    )


@router.get("/{cotizacion_id}/decisiones-precio", response_class=HTMLResponse)
def ver_decisiones(
    cotizacion_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
):
    cotizacion = obtener_cotizacion(sesion, cotizacion_id)
    if cotizacion is None:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    return _render(request, sesion, usuario, cotizacion)


@router.post("/{cotizacion_id}/decisiones-precio/{partida_id}")
def guardar_decision(
    cotizacion_id: str,
    partida_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    csrf_token: Annotated[str, Form()],
    rol: Annotated[str, Form()],
    observacion_id: Annotated[str, Form()] = "",
):
    validar_token_csrf(request, csrf_token)
    cotizacion = obtener_cotizacion(sesion, cotizacion_id)
    if cotizacion is None:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    try:
        rol_validado = RolDecisionPrecio(rol)
        registrar_decision_precio(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_id=partida_id,
            usuario_id=usuario.id,
            rol=rol_validado,
            observacion_id=observacion_id.strip() or None,
        )
    except ValueError as error:
        return _render(request, sesion, usuario, cotizacion, error=str(error))
    return RedirectResponse(
        url=f"/cotizaciones/{cotizacion_id}/decisiones-precio",
        status_code=status.HTTP_303_SEE_OTHER,
    )
