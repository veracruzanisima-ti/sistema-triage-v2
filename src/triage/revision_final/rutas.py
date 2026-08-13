"""Rutas de revisión consolidada previa al cierre."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from triage.cotizaciones.servicio import obtener_cotizacion
from triage.normalizacion.servicio import resumen_normalizacion_cotizacion
from triage.revision_final.servicio import listar_precierre
from triage.usuarios.seguridad import Sesion, UsuarioActual, obtener_token_csrf

router = APIRouter(prefix="/cotizaciones", tags=["revision-final"])


@router.get("/{cotizacion_id}/revision-final", response_class=HTMLResponse)
def ver_revision_final(
    cotizacion_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
):
    """Muestra una vista integrada sin ejecutar decisiones automáticas."""

    cotizacion = obtener_cotizacion(sesion, cotizacion_id)
    if cotizacion is None:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    productos = listar_precierre(sesion, cotizacion_id)
    resumen = resumen_normalizacion_cotizacion(sesion, cotizacion_id)
    return request.app.state.plantillas.TemplateResponse(
        request=request,
        name="revision_final/lista.html",
        context={
            "usuario": usuario,
            "csrf_token": obtener_token_csrf(request),
            "cotizacion": cotizacion,
            "productos": productos,
            "total_incluidas": resumen.total,
            "sin_preparar": max(resumen.total - resumen.preparados, 0),
            "con_referencia": sum(not item.pendientes for item in productos),
            "con_alertas": sum(bool(item.alertas) for item in productos),
        },
    )
