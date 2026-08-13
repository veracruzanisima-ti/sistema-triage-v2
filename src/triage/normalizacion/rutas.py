"""Pantalla para confirmar datos de búsqueda sin alterar la solicitud revisada."""

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from triage.cotizaciones.servicio import obtener_cotizacion
from triage.normalizacion.servicio import (
    ValoresNormalizacion,
    guardar_normalizaciones,
    listar_partidas_normalizables,
)
from triage.usuarios.seguridad import Sesion, UsuarioActual, obtener_token_csrf, validar_token_csrf

router = APIRouter(prefix="/cotizaciones", tags=["normalizacion"])


def _plantillas(request: Request):
    return request.app.state.plantillas


def _limpiar_formulario(valor) -> str | None:
    texto = str(valor or "").strip()
    return texto or None


@router.get(
    "/{cotizacion_id}/normalizacion",
    response_class=HTMLResponse,
    name="normalizar_productos_cotizacion",
)
def ver_normalizacion(
    cotizacion_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    guardado: int = 0,
):
    """Muestra sólo partidas revisadas e incluidas que podrán buscarse después."""

    cotizacion = obtener_cotizacion(sesion, cotizacion_id)
    if cotizacion is None:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    return _plantillas(request).TemplateResponse(
        request=request,
        name="normalizacion/revisar.html",
        context={
            "usuario": usuario,
            "csrf_token": obtener_token_csrf(request),
            "cotizacion": cotizacion,
            "entradas": listar_partidas_normalizables(sesion, cotizacion.id),
            "guardado": bool(guardado),
        },
    )


@router.post(
    "/{cotizacion_id}/normalizacion",
    name="guardar_normalizacion_cotizacion",
)
async def guardar_normalizacion(
    cotizacion_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
):
    """Confirma en bloque la copia operativa que luego usarán los proveedores."""

    cotizacion = obtener_cotizacion(sesion, cotizacion_id)
    if cotizacion is None:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    formulario = await request.form()
    validar_token_csrf(request, str(formulario.get("csrf_token") or ""))

    try:
        total = int(str(formulario.get("partidas_total") or "0"))
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Número de partidas inválido") from error
    if total < 0 or total > 200:
        raise HTTPException(status_code=422, detail="Número de partidas fuera de rango")

    valores_por_partida: dict[str, ValoresNormalizacion] = {}
    for indice in range(total):
        partida_id = _limpiar_formulario(formulario.get(f"partida_{indice}_id"))
        if partida_id is None or partida_id in valores_por_partida:
            raise HTTPException(status_code=422, detail="Partida inválida o repetida")
        valores_por_partida[partida_id] = ValoresNormalizacion(
            producto=_limpiar_formulario(formulario.get(f"partida_{indice}_producto")),
            marca=_limpiar_formulario(formulario.get(f"partida_{indice}_marca")),
            concentracion=_limpiar_formulario(
                formulario.get(f"partida_{indice}_concentracion")
            ),
            forma_dispositivo=_limpiar_formulario(
                formulario.get(f"partida_{indice}_forma")
            ),
            presentacion=_limpiar_formulario(
                formulario.get(f"partida_{indice}_presentacion")
            ),
        )

    try:
        guardar_normalizaciones(
            sesion,
            cotizacion_id=cotizacion.id,
            usuario_id=usuario.id,
            valores_por_partida=valores_por_partida,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    return RedirectResponse(
        url=f"/cotizaciones/{cotizacion.id}/normalizacion?guardado=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )
