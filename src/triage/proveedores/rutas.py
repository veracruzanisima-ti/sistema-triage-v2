"""Rutas para ejecutar consultas actuales sin ocultar la decisión humana posterior."""

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from triage.cotizaciones.servicio import obtener_cotizacion
from triage.proveedores.servicio import (
    ErrorConsultaProveedor,
    ejecutar_consulta,
    listar_productos_consultables,
)
from triage.usuarios.seguridad import Sesion, UsuarioActual, obtener_token_csrf, validar_token_csrf

router = APIRouter(prefix="/cotizaciones", tags=["proveedores"])


def _plantillas(request: Request):
    return request.app.state.plantillas


def _proveedores(request: Request) -> dict[str, object]:
    return request.app.state.proveedores_productos


def _render(
    request: Request,
    sesion: Sesion,
    usuario,
    cotizacion,
    *,
    error: str = "",
    mensaje: str = "",
    status_code: int = status.HTTP_200_OK,
):
    proveedores = _proveedores(request)
    return _plantillas(request).TemplateResponse(
        request=request,
        name="proveedores/consulta.html",
        context={
            "usuario": usuario,
            "csrf_token": obtener_token_csrf(request),
            "cotizacion": cotizacion,
            "productos": listar_productos_consultables(sesion, cotizacion.id),
            "proveedores": tuple(proveedor.nombre for proveedor in proveedores.values()),
            "error": error,
            "mensaje": mensaje,
        },
        status_code=status_code,
    )


@router.get("/{cotizacion_id}/proveedores", response_class=HTMLResponse)
def ver_proveedores(
    cotizacion_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    resultado: str = "",
):
    """Muestra productos preparados, adaptadores disponibles e intentos recientes."""

    cotizacion = obtener_cotizacion(sesion, cotizacion_id)
    if cotizacion is None:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    mensajes = {
        "exitosa": "Consulta guardada como una nueva observación histórica.",
        "no_encontrado": "El proveedor no reportó una coincidencia utilizable.",
    }
    return _render(
        request,
        sesion,
        usuario,
        cotizacion,
        mensaje=mensajes.get(resultado, ""),
    )


@router.post("/{cotizacion_id}/proveedores/{partida_documento_id}/consultar")
def consultar_proveedor(
    cotizacion_id: str,
    partida_documento_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    csrf_token: Annotated[str, Form()],
    proveedor: Annotated[str, Form()],
):
    """Ejecuta un adaptador explícito; no compara ni selecciona ganador."""

    validar_token_csrf(request, csrf_token)
    cotizacion = obtener_cotizacion(sesion, cotizacion_id)
    if cotizacion is None:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    adaptador = _proveedores(request).get(proveedor.casefold())
    if adaptador is None:
        raise HTTPException(status_code=422, detail="Proveedor no configurado")

    try:
        intento = ejecutar_consulta(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_documento_id,
            usuario_id=usuario.id,
            proveedor=adaptador,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ErrorConsultaProveedor as error:
        return _render(
            request,
            sesion,
            usuario,
            cotizacion,
            error=str(error),
            status_code=status.HTTP_502_BAD_GATEWAY,
        )

    resultado = "exitosa" if intento.observacion_precio_id else "no_encontrado"
    return RedirectResponse(
        url=f"/cotizaciones/{cotizacion_id}/proveedores?resultado={resultado}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
