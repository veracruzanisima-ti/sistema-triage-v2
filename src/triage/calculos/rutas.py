"""Rutas de calculo comercial con parametros confirmados por una persona."""

from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from triage.calculos.servicio import crear_calculo, listar_productos_calculo
from triage.cotizaciones.servicio import obtener_cotizacion
from triage.usuarios.seguridad import Sesion, UsuarioActual, obtener_token_csrf, validar_token_csrf

router = APIRouter(prefix="/cotizaciones", tags=["calculos"])


@router.get("/{cotizacion_id}/calculos", response_class=HTMLResponse)
def ver_calculos(
    cotizacion_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    guardado: int = 0,
):
    cotizacion = obtener_cotizacion(sesion, cotizacion_id)
    if cotizacion is None:
        raise HTTPException(status_code=404, detail="Cotizacion no encontrada")
    return request.app.state.plantillas.TemplateResponse(
        request=request,
        name="calculos/lista.html",
        context={
            "usuario": usuario,
            "csrf_token": obtener_token_csrf(request),
            "cotizacion": cotizacion,
            "productos": listar_productos_calculo(sesion, cotizacion_id),
            "guardado": bool(guardado),
        },
    )


@router.post("/{cotizacion_id}/calculos/{partida_id}")
def guardar_calculo(
    cotizacion_id: str,
    partida_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    csrf_token: Annotated[str, Form()],
    markup_porcentaje: Annotated[str, Form()],
    iva_venta_porcentaje: Annotated[str, Form()],
):
    validar_token_csrf(request, csrf_token)
    if obtener_cotizacion(sesion, cotizacion_id) is None:
        raise HTTPException(status_code=404, detail="Cotizacion no encontrada")
    try:
        markup = Decimal(markup_porcentaje.strip())
        iva = Decimal(iva_venta_porcentaje.strip())
    except (InvalidOperation, ValueError) as error:
        raise HTTPException(status_code=422, detail="Porcentajes invalidos") from error

    try:
        crear_calculo(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_id=partida_id,
            usuario_id=usuario.id,
            markup_porcentaje=markup,
            iva_venta_porcentaje=iva,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return RedirectResponse(
        url=f"/cotizaciones/{cotizacion_id}/calculos?guardado=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )
