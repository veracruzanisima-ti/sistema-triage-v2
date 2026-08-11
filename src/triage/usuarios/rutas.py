"""Rutas de acceso para integrantes autorizados de la empresa."""

from typing import Annotated

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from triage.usuarios.seguridad import (
    Sesion,
    cerrar_sesion,
    iniciar_sesion,
    obtener_token_csrf,
    obtener_usuario_opcional,
    validar_token_csrf,
)
from triage.usuarios.servicio import autenticar_usuario

router = APIRouter(tags=["acceso"])


def _plantillas(request: Request):
    return request.app.state.plantillas


@router.get("/acceso", response_class=HTMLResponse, name="acceso")
def acceso(request: Request, sesion: Sesion):
    """Muestra un único formulario de acceso para cuentas internas."""

    if obtener_usuario_opcional(request, sesion) is not None:
        return RedirectResponse(
            url="/cotizaciones",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return _plantillas(request).TemplateResponse(
        request=request,
        name="usuarios/acceso.html",
        context={
            "csrf_token": obtener_token_csrf(request),
            "error": "",
        },
    )


@router.post("/acceso", response_class=HTMLResponse, name="iniciar_acceso")
def iniciar_acceso(
    request: Request,
    sesion: Sesion,
    correo: Annotated[str, Form()],
    contrasena: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
):
    """Autentica sin revelar si el correo o la contraseña fueron incorrectos."""

    validar_token_csrf(request, csrf_token)
    usuario = autenticar_usuario(sesion, correo, contrasena)
    if usuario is None:
        return _plantillas(request).TemplateResponse(
            request=request,
            name="usuarios/acceso.html",
            context={
                "csrf_token": obtener_token_csrf(request),
                "error": "Correo o contraseña incorrectos.",
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    iniciar_sesion(request, usuario)
    return RedirectResponse(
        url="/cotizaciones",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/salir", name="salir")
def salir(
    request: Request,
    csrf_token: Annotated[str, Form()],
):
    """Cierra explícitamente la sesión del navegador."""

    validar_token_csrf(request, csrf_token)
    cerrar_sesion(request)
    return RedirectResponse(
        url="/acceso",
        status_code=status.HTTP_303_SEE_OTHER,
    )
