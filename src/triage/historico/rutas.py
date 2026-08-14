"""Rutas para consultar y agregar observaciones históricas de precio."""

from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from triage.cotizaciones.servicio import obtener_cotizacion
from triage.historico.servicio import crear_observacion_precio, listar_productos_historico
from triage.usuarios.seguridad import Sesion, UsuarioActual, obtener_token_csrf, validar_token_csrf

router = APIRouter(prefix="/cotizaciones", tags=["historico"])


def _plantillas(request: Request):
    return request.app.state.plantillas


def _decimal_opcional(valor: str) -> Decimal | None:
    limpio = valor.strip()
    if not limpio:
        return None
    try:
        return Decimal(limpio)
    except InvalidOperation as error:
        raise ValueError("precio o porcentaje inválido") from error


def _entrega_viable(valor: str) -> bool | None:
    if valor == "si":
        return True
    if valor == "no":
        return False
    if valor == "":
        return None
    raise ValueError("estado de entrega no permitido")


def _render_historico(
    request: Request,
    sesion: Sesion,
    usuario,
    cotizacion,
    *,
    error: str = "",
    guardado: bool = False,
    status_code: int = status.HTTP_200_OK,
):
    return _plantillas(request).TemplateResponse(
        request=request,
        name="historico/lista.html",
        context={
            "usuario": usuario,
            "csrf_token": obtener_token_csrf(request),
            "cotizacion": cotizacion,
            "productos": listar_productos_historico(sesion, cotizacion.id),
            "error": error,
            "guardado": guardado,
        },
        status_code=status_code,
    )


@router.get("/{cotizacion_id}/historico", response_class=HTMLResponse)
def ver_historico(
    cotizacion_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    guardado: int = 0,
):
    """Muestra observaciones exactas para productos previamente preparados."""

    cotizacion = obtener_cotizacion(sesion, cotizacion_id)
    if cotizacion is None:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    return _render_historico(
        request,
        sesion,
        usuario,
        cotizacion,
        guardado=bool(guardado),
    )


@router.post("/{cotizacion_id}/historico/{partida_documento_id}")
def agregar_observacion(
    cotizacion_id: str,
    partida_documento_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    csrf_token: Annotated[str, Form()],
    proveedor: Annotated[str, Form()],
    fuente: Annotated[str, Form()],
    precio_antes_iva: Annotated[str, Form()] = "",
    iva_porcentaje: Annotated[str, Form()] = "",
    precio_total: Annotated[str, Form()] = "",
    es_promocion: Annotated[str | None, Form()] = None,
    condiciones_promocion: Annotated[str, Form()] = "",
    disponibilidad: Annotated[str, Form()] = "",
    entrega_viable: Annotated[str, Form()] = "",
):
    """Agrega una fotografía de precio sin editar observaciones históricas previas."""

    validar_token_csrf(request, csrf_token)
    cotizacion = obtener_cotizacion(sesion, cotizacion_id)
    if cotizacion is None:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    try:
        crear_observacion_precio(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_documento_id=partida_documento_id,
            usuario_id=usuario.id,
            proveedor=proveedor,
            fuente=fuente,
            precio_antes_iva=_decimal_opcional(precio_antes_iva),
            iva_porcentaje=_decimal_opcional(iva_porcentaje),
            precio_total=_decimal_opcional(precio_total),
            es_promocion=es_promocion == "1",
            condiciones_promocion=condiciones_promocion,
            disponibilidad=disponibilidad,
            entrega_viable=_entrega_viable(entrega_viable),
            codigo_postal=cotizacion.codigo_postal_consulta,
        )
    except ValueError as error:
        return _render_historico(
            request,
            sesion,
            usuario,
            cotizacion,
            error=str(error),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    return RedirectResponse(
        url=f"/cotizaciones/{cotizacion.id}/historico?guardado=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )
