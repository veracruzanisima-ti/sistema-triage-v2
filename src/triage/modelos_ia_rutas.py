"""Selector temporal de modelos de IA para comparar el piloto sin tocar secretos."""

from typing import Annotated

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from triage.modelos_ia import opciones_modelo, seleccionar_modelos
from triage.usuarios.seguridad import UsuarioActual, obtener_token_csrf, validar_token_csrf

router = APIRouter(tags=["modelos-ia"])


def _render(
    request: Request,
    usuario,
    *,
    error: str = "",
    guardado: bool = False,
    codigo: int = status.HTTP_200_OK,
):
    return request.app.state.plantillas.TemplateResponse(
        request=request,
        name="modelos_ia/seleccionar.html",
        context={
            "usuario": usuario,
            "csrf_token": obtener_token_csrf(request),
            "lectores": opciones_modelo(request, "lector"),
            "buscadores": opciones_modelo(request, "web"),
            "error": error,
            "guardado": guardado,
        },
        status_code=codigo,
    )


@router.get("/modelos-ia", response_class=HTMLResponse)
def ver_modelos_ia(
    request: Request,
    usuario: UsuarioActual,
    guardado: int = 0,
):
    """Muestra únicamente opciones conocidas y si su proveedor está configurado."""

    return _render(request, usuario, guardado=bool(guardado))


@router.post("/modelos-ia")
def guardar_modelos_ia(
    request: Request,
    usuario: UsuarioActual,
    csrf_token: Annotated[str, Form()],
    modelo_lector: Annotated[str, Form()],
    modelo_web: Annotated[str, Form()],
):
    """Guarda la selección en la sesión del navegador sin exponer ni modificar API keys."""

    validar_token_csrf(request, csrf_token)
    try:
        seleccionar_modelos(
            request,
            lector=modelo_lector,
            web=modelo_web,
        )
    except ValueError as error:
        return _render(
            request,
            usuario,
            error=str(error),
            codigo=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    return RedirectResponse(
        url="/modelos-ia?guardado=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )
