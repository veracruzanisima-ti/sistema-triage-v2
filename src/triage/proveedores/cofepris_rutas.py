"""Pantalla operativa para reemplazar el snapshot público de COFEPRIS."""

from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse

from triage.proveedores.cofepris_servicio import (
    ErrorImportacionCofepris,
    importar_snapshot_cofepris,
    total_registros_cofepris,
    ultima_importacion_cofepris,
)
from triage.usuarios.seguridad import (
    Sesion,
    UsuarioActual,
    obtener_token_csrf,
    validar_token_csrf,
)

router = APIRouter(prefix="/proveedores/cofepris", tags=["proveedores"])
_MAX_LECTURA_XLSX = 50 * 1024 * 1024 + 1


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
        name="proveedores/cofepris_actualizar.html",
        context={
            "usuario": usuario,
            "csrf_token": obtener_token_csrf(request),
            "ultima_importacion": ultima_importacion_cofepris(sesion),
            "total_registros": total_registros_cofepris(sesion),
            "cotizacion_id": cotizacion_id,
            "error": error,
            "mensaje": mensaje,
        },
        status_code=codigo,
    )


@router.get("/actualizar", response_class=HTMLResponse)
def ver_actualizacion_cofepris(
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    cotizacion_id: str = "",
    resultado: str = "",
):
    mensaje = "Catálogo COFEPRIS actualizado correctamente." if resultado == "ok" else ""
    return _render(
        request,
        sesion,
        usuario,
        cotizacion_id=cotizacion_id,
        mensaje=mensaje,
    )


@router.post("/actualizar")
def actualizar_cofepris(
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    csrf_token: Annotated[str, Form()],
    catalogo: Annotated[UploadFile, File()],
    cotizacion_id: Annotated[str, Form()] = "",
):
    validar_token_csrf(request, csrf_token)
    datos = catalogo.file.read(_MAX_LECTURA_XLSX)
    try:
        importar_snapshot_cofepris(
            sesion,
            usuario_id=usuario.id,
            nombre_archivo=catalogo.filename or "",
            datos=datos,
        )
    except ErrorImportacionCofepris as error:
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
        url=f"/proveedores/cofepris/actualizar?resultado=ok{sufijo}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
