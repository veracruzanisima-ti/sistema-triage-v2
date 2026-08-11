"""Rutas web sencillas para iniciar, retomar y cerrar cotizaciones."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from triage.base_datos import obtener_sesion
from triage.cotizaciones.modelos import EstadoCotizacion
from triage.cotizaciones.servicio import (
    actualizar_estado,
    crear_cotizacion,
    listar_cotizaciones,
    obtener_cotizacion,
)

router = APIRouter(prefix="/cotizaciones", tags=["cotizaciones"])
Sesion = Annotated[Session, Depends(obtener_sesion)]


def _plantillas(request: Request):
    return request.app.state.plantillas


@router.get("", response_class=HTMLResponse, name="listar_cotizaciones")
def lista(request: Request, sesion: Sesion):
    """Muestra las cotizaciones existentes sin información técnica adicional."""

    return _plantillas(request).TemplateResponse(
        request=request,
        name="cotizaciones/lista.html",
        context={"cotizaciones": listar_cotizaciones(sesion)},
    )


@router.get("/nueva", response_class=HTMLResponse, name="nueva_cotizacion")
def nueva(request: Request):
    """Muestra un formulario mínimo para iniciar trabajo."""

    return _plantillas(request).TemplateResponse(
        request=request,
        name="cotizaciones/nueva.html",
        context={},
    )


@router.post("", name="crear_cotizacion")
def crear(
    referencia: Annotated[str, Form()] = "",
    *,
    sesion: Sesion,
):
    """Guarda inmediatamente una cotización para que no dependa del navegador."""

    cotizacion = crear_cotizacion(sesion, referencia)
    return RedirectResponse(
        url=f"/cotizaciones/{cotizacion.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/{cotizacion_id}", response_class=HTMLResponse, name="ver_cotizacion")
def detalle(cotizacion_id: str, request: Request, sesion: Sesion):
    """Permite retomar una cotización previamente guardada."""

    cotizacion = obtener_cotizacion(sesion, cotizacion_id)
    if cotizacion is None:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    return _plantillas(request).TemplateResponse(
        request=request,
        name="cotizaciones/detalle.html",
        context={
            "cotizacion": cotizacion,
            "estados": tuple(EstadoCotizacion),
        },
    )


@router.post("/{cotizacion_id}/estado", name="cambiar_estado_cotizacion")
def cambiar_estado(
    cotizacion_id: str,
    estado: Annotated[str, Form()],
    sesion: Sesion,
):
    """Aplica únicamente estados explícitos del flujo, sin inferencias automáticas."""

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
