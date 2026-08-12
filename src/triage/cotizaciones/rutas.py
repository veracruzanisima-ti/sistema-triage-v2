"""Rutas web sencillas para iniciar, retomar y cerrar cotizaciones."""

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from triage.cotizaciones.modelos import EstadoCotizacion
from triage.cotizaciones.servicio import (
    actualizar_estado,
    actualizar_referencia_manual,
    crear_cotizacion,
    listar_cotizaciones,
    obtener_cotizacion,
    referencias_documentos_revisados,
    usar_referencia_automatica,
)
from triage.documentos.servicio import listar_documentos_cotizacion
from triage.usuarios.seguridad import (
    Sesion,
    UsuarioActual,
    obtener_token_csrf,
    validar_token_csrf,
)

router = APIRouter(prefix="/cotizaciones", tags=["cotizaciones"])


def _plantillas(request: Request):
    return request.app.state.plantillas


def _contexto(request: Request, usuario, **valores):
    """Entrega a las plantillas sólo la identidad y el token necesarios."""

    return {
        "usuario": usuario,
        "csrf_token": obtener_token_csrf(request),
        **valores,
    }


@router.get("", response_class=HTMLResponse, name="listar_cotizaciones")
def lista(request: Request, sesion: Sesion, usuario: UsuarioActual):
    """Muestra las cotizaciones existentes sin información técnica adicional."""

    return _plantillas(request).TemplateResponse(
        request=request,
        name="cotizaciones/lista.html",
        context=_contexto(
            request,
            usuario,
            cotizaciones=listar_cotizaciones(sesion),
        ),
    )


@router.get("/nueva", response_class=HTMLResponse, name="nueva_cotizacion")
def nueva(request: Request, usuario: UsuarioActual):
    """Muestra un formulario mínimo para iniciar trabajo."""

    return _plantillas(request).TemplateResponse(
        request=request,
        name="cotizaciones/nueva.html",
        context=_contexto(request, usuario),
    )


@router.post("", name="crear_cotizacion")
def crear(
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    csrf_token: Annotated[str, Form()],
    referencia: Annotated[str, Form()] = "",
):
    """Guarda inmediatamente una cotización para que no dependa del navegador."""

    validar_token_csrf(request, csrf_token)
    cotizacion = crear_cotizacion(sesion, referencia)
    return RedirectResponse(
        url=f"/cotizaciones/{cotizacion.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/{cotizacion_id}", response_class=HTMLResponse, name="ver_cotizacion")
def detalle(
    cotizacion_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
):
    """Permite retomar una cotización previamente guardada."""

    cotizacion = obtener_cotizacion(sesion, cotizacion_id)
    if cotizacion is None:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    referencias_revisadas = referencias_documentos_revisados(sesion, cotizacion.id)
    return _plantillas(request).TemplateResponse(
        request=request,
        name="cotizaciones/detalle.html",
        context=_contexto(
            request,
            usuario,
            cotizacion=cotizacion,
            estados=tuple(EstadoCotizacion),
            documentos=listar_documentos_cotizacion(sesion, cotizacion.id),
            referencias_revisadas=referencias_revisadas,
            conflicto_referencias=(
                not cotizacion.referencia_fijada_manual
                and len(referencias_revisadas) > 1
            ),
        ),
    )


@router.post("/{cotizacion_id}/referencia", name="cambiar_referencia_cotizacion")
def cambiar_referencia(
    cotizacion_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    csrf_token: Annotated[str, Form()],
    referencia: Annotated[str, Form()] = "",
    accion: Annotated[str, Form()] = "guardar",
):
    """Permite fijar una referencia humana o devolver la cotización al modo automático."""

    validar_token_csrf(request, csrf_token)
    cotizacion = obtener_cotizacion(sesion, cotizacion_id)
    if cotizacion is None:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    if accion == "automatica":
        usar_referencia_automatica(sesion, cotizacion)
    elif accion == "guardar":
        try:
            actualizar_referencia_manual(sesion, cotizacion, referencia)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
    else:
        raise HTTPException(status_code=422, detail="Acción de referencia no permitida")

    return RedirectResponse(
        url=f"/cotizaciones/{cotizacion.id}#referencia-cotizacion",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{cotizacion_id}/estado", name="cambiar_estado_cotizacion")
def cambiar_estado(
    cotizacion_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    estado: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
):
    """Aplica únicamente estados explícitos del flujo, sin inferencias automáticas."""

    validar_token_csrf(request, csrf_token)
    cotizacion = obtener_cotizacion(sesion, cotizacion_id)
    if cotizacion is None:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    try:
        estado_validado = EstadoCotizacion(estado)
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Estado no permitido") from error

    actualizar_estado(sesion, cotizacion, estado_validado)
    return RedirectResponse(
        url=f"/cotizaciones/{cotizacion.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
