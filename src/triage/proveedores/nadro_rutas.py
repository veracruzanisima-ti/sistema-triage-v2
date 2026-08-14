"""Pantalla simple para actualizar el snapshot EdiNadro sin tocar servidor ni GitHub."""

from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse

from triage.proveedores.nadro_servicio import (
    ErrorImportacionNadro,
    importar_snapshot_nadro,
    ultima_importacion_nadro,
)
from triage.usuarios.seguridad import (
    Sesion,
    UsuarioActual,
    obtener_token_csrf,
    validar_token_csrf,
)

router = APIRouter(prefix="/proveedores/nadro", tags=["proveedores"])
_MAX_LECTURA_CATALOGO = 10 * 1024 * 1024 + 1
_MAX_LECTURA_OFERTAS = 5 * 1024 * 1024 + 1


def _render(
    request: Request,
    sesion: Sesion,
    usuario,
    *,
    cotizacion_id: str = "",
    error: str = "",
    mensaje: str = "",
    codigo: int = status.HTTP_200_OK,
):
    return request.app.state.plantillas.TemplateResponse(
        request=request,
        name="proveedores/nadro_actualizar.html",
        context={
            "usuario": usuario,
            "csrf_token": obtener_token_csrf(request),
            "ultima_importacion": ultima_importacion_nadro(sesion),
            "cotizacion_id": cotizacion_id,
            "error": error,
            "mensaje": mensaje,
        },
        status_code=codigo,
    )


@router.get("/actualizar", response_class=HTMLResponse)
def ver_actualizacion_nadro(
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    cotizacion_id: str = "",
    resultado: str = "",
):
    mensaje = "Catálogo NADRO actualizado correctamente." if resultado == "ok" else ""
    return _render(
        request,
        sesion,
        usuario,
        cotizacion_id=cotizacion_id,
        mensaje=mensaje,
    )


@router.post("/actualizar")
def actualizar_nadro(
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    csrf_token: Annotated[str, Form()],
    catalogo: Annotated[UploadFile, File()],
    ofertas: Annotated[UploadFile, File()],
    cotizacion_id: Annotated[str, Form()] = "",
):
    validar_token_csrf(request, csrf_token)
    datos_catalogo = catalogo.file.read(_MAX_LECTURA_CATALOGO)
    datos_ofertas = ofertas.file.read(_MAX_LECTURA_OFERTAS)
    try:
        importar_snapshot_nadro(
            sesion,
            usuario_id=usuario.id,
            nombre_catalogo=catalogo.filename or "",
            datos_catalogo=datos_catalogo,
            nombre_ofertas=ofertas.filename or "",
            datos_ofertas=datos_ofertas,
        )
    except ErrorImportacionNadro as error:
        return _render(
            request,
            sesion,
            usuario,
            cotizacion_id=cotizacion_id,
            error=str(error),
            codigo=status.HTTP_409_CONFLICT,
        )

    sufijo = f"&cotizacion_id={cotizacion_id}" if cotizacion_id else ""
    return RedirectResponse(
        url=f"/proveedores/nadro/actualizar?resultado=ok{sufijo}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
