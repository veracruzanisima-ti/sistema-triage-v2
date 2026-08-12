"""Rutas para subir documentos y revisar la lectura antes de cotizar."""

import re
from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.datastructures import FormData

from triage.cotizaciones.servicio import obtener_cotizacion
from triage.documentos.modelos import EstadoDocumento
from triage.documentos.servicio import (
    ArchivoDocumentoInvalido,
    eliminar_documento,
    guardar_revision,
    listar_partidas_documento,
    obtener_documento,
    procesar_documento,
    validar_archivo,
)
from triage.lectores.esquemas import LecturaDocumento, PartidaLeida
from triage.restricciones import evaluar_partida
from triage.usuarios.seguridad import Sesion, UsuarioActual, obtener_token_csrf, validar_token_csrf

router = APIRouter(tags=["documentos"])


def _plantillas(request: Request):
    return request.app.state.plantillas


def _contexto(request: Request, usuario, **valores):
    return {
        "usuario": usuario,
        "csrf_token": obtener_token_csrf(request),
        **valores,
    }


def _cotizacion_o_404(sesion: Sesion, cotizacion_id: str):
    cotizacion = obtener_cotizacion(sesion, cotizacion_id)
    if cotizacion is None:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    return cotizacion


def _documento_o_404(sesion: Sesion, cotizacion_id: str, documento_id: str):
    documento = obtener_documento(
        sesion,
        cotizacion_id=cotizacion_id,
        documento_id=documento_id,
    )
    if documento is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return documento


def _limpiar_texto(valor: object | None) -> str | None:
    texto = " ".join(str(valor or "").split())
    return texto or None


def _separar_folios(valor: object | None) -> list[str]:
    """Acepta folios separados por coma, punto y coma o salto de línea."""

    texto = str(valor or "")
    return [parte.strip() for parte in re.split(r"[,;\n]+", texto) if parte.strip()]


def _cantidad(valor: object | None) -> int | None:
    """Convierte una cantidad humana a entero y rechaza fracciones."""

    texto = str(valor or "").strip().replace(",", ".")
    if not texto:
        return None
    try:
        numero = Decimal(texto)
    except InvalidOperation as error:
        raise ValueError(f"Cantidad inválida: {texto}") from error
    if numero < 0:
        raise ValueError("La cantidad no puede ser negativa")
    if numero != numero.to_integral_value():
        raise ValueError("La cantidad debe ser un número entero")
    return int(numero)


def _cantidad_visible(valor: object | None) -> str:
    """Evita mostrar ceros decimales heredados sin ocultar una fracción existente."""

    if valor is None:
        return ""
    try:
        numero = Decimal(str(valor))
    except InvalidOperation:
        return str(valor)
    if numero == numero.to_integral_value():
        return str(int(numero))
    return format(numero, "f")


def _partida_desde_formulario(formulario: FormData, indice: int) -> PartidaLeida | None:
    prefijo = f"partida_{indice}_"
    valores = {
        "producto_solicitado": _limpiar_texto(formulario.get(prefijo + "producto")),
        "marca_solicitada": _limpiar_texto(formulario.get(prefijo + "marca")),
        "concentracion": _limpiar_texto(formulario.get(prefijo + "concentracion")),
        "forma_farmaceutica_dispositivo": _limpiar_texto(formulario.get(prefijo + "forma")),
        "presentacion_solicitada": _limpiar_texto(formulario.get(prefijo + "presentacion")),
        "cantidad": _cantidad(formulario.get(prefijo + "cantidad")),
        "unidad_medida": _limpiar_texto(formulario.get(prefijo + "unidad")),
    }
    if all(valor is None for valor in valores.values()):
        return None
    return PartidaLeida(**valores)


def _render_subida(
    request: Request,
    usuario,
    cotizacion,
    *,
    error: str | None = None,
    codigo: int = 200,
):
    return _plantillas(request).TemplateResponse(
        request=request,
        name="documentos/subir.html",
        context=_contexto(request, usuario, cotizacion=cotizacion, error=error),
        status_code=codigo,
    )


def _render_revision(
    request: Request,
    usuario,
    cotizacion,
    documento,
    partidas,
    *,
    error: str | None = None,
    codigo: int = 200,
):
    alertas_por_partida = [evaluar_partida(partida) for partida in partidas]
    partidas_con_alerta = sum(bool(alertas) for alertas in alertas_por_partida)
    return _plantillas(request).TemplateResponse(
        request=request,
        name="documentos/revisar.html",
        context=_contexto(
            request,
            usuario,
            cotizacion=cotizacion,
            documento=documento,
            partidas=partidas,
            error=error,
            estado_error=EstadoDocumento.ERROR.value,
            cantidad_visible=_cantidad_visible,
            alertas_por_partida=alertas_por_partida,
            partidas_con_alerta=partidas_con_alerta,
        ),
        status_code=codigo,
    )


@router.get(
    "/cotizaciones/{cotizacion_id}/documentos/nuevo",
    response_class=HTMLResponse,
    name="subir_documento",
)
def formulario_subida(
    cotizacion_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
):
    """Muestra la carga documental con alternativa tradicional sin JavaScript."""

    cotizacion = _cotizacion_o_404(sesion, cotizacion_id)
    return _render_subida(request, usuario, cotizacion)


@router.post("/cotizaciones/{cotizacion_id}/documentos", name="procesar_documento")
async def subir_y_procesar(
    cotizacion_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    csrf_token: Annotated[str, Form()],
    archivo: Annotated[UploadFile, File()],
):
    """Procesa un archivo en memoria y dirige inmediatamente a revisión humana."""

    validar_token_csrf(request, csrf_token)
    cotizacion = _cotizacion_o_404(sesion, cotizacion_id)
    lector = request.app.state.lector_documentos
    if lector is None:
        return _render_subida(
            request,
            usuario,
            cotizacion,
            error="El lector documental todavía no está configurado en este entorno.",
            codigo=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    max_bytes = request.app.state.configuracion.max_documento_bytes
    contenido = await archivo.read(max_bytes + 1)
    await archivo.close()
    mime_type = archivo.content_type or ""

    try:
        validar_archivo(contenido=contenido, mime_type=mime_type, max_bytes=max_bytes)
    except ArchivoDocumentoInvalido as error:
        return _render_subida(
            request,
            usuario,
            cotizacion,
            error=str(error),
            codigo=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    documento = procesar_documento(
        sesion,
        cotizacion_id=cotizacion.id,
        nombre_archivo=archivo.filename or "documento",
        mime_type=mime_type,
        contenido=contenido,
        lector=lector,
    )
    return RedirectResponse(
        url=f"/cotizaciones/{cotizacion.id}/documentos/{documento.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/cotizaciones/{cotizacion_id}/documentos/cola",
    response_class=JSONResponse,
    name="procesar_documento_cola",
)
async def subir_y_procesar_cola(
    cotizacion_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    csrf_token: Annotated[str, Form()],
    archivo: Annotated[UploadFile, File()],
):
    """Procesa un elemento de la cola y devuelve un resultado pequeño para la interfaz."""

    validar_token_csrf(request, csrf_token)
    cotizacion = _cotizacion_o_404(sesion, cotizacion_id)
    lector = request.app.state.lector_documentos
    if lector is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "ok": False,
                "error": "El lector documental todavía no está configurado en este entorno.",
            },
        )

    max_bytes = request.app.state.configuracion.max_documento_bytes
    contenido = await archivo.read(max_bytes + 1)
    nombre_archivo = archivo.filename or "documento"
    mime_type = archivo.content_type or ""
    await archivo.close()

    try:
        validar_archivo(contenido=contenido, mime_type=mime_type, max_bytes=max_bytes)
    except ArchivoDocumentoInvalido as error:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"ok": False, "error": str(error)},
        )

    documento = procesar_documento(
        sesion,
        cotizacion_id=cotizacion.id,
        nombre_archivo=nombre_archivo,
        mime_type=mime_type,
        contenido=contenido,
        lector=lector,
    )
    revision_url = f"/cotizaciones/{cotizacion.id}/documentos/{documento.id}"
    lectura_correcta = documento.estado != EstadoDocumento.ERROR.value
    return JSONResponse(
        content={
            "ok": lectura_correcta,
            "documento_id": documento.id,
            "estado": documento.estado,
            "error": documento.error_lector if not lectura_correcta else None,
            "revision_url": revision_url,
        }
    )


@router.get(
    "/cotizaciones/{cotizacion_id}/documentos/{documento_id}",
    response_class=HTMLResponse,
    name="revisar_documento",
)
def revision(
    cotizacion_id: str,
    documento_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
):
    """Muestra únicamente los campos que una persona necesita confirmar o corregir."""

    cotizacion = _cotizacion_o_404(sesion, cotizacion_id)
    documento = _documento_o_404(sesion, cotizacion_id, documento_id)
    partidas = listar_partidas_documento(sesion, documento.id)
    return _render_revision(request, usuario, cotizacion, documento, partidas)


@router.post(
    "/cotizaciones/{cotizacion_id}/documentos/{documento_id}/revision",
    name="guardar_revision_documento",
)
async def guardar(
    cotizacion_id: str,
    documento_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
):
    """Persiste las correcciones humanas sin ejecutar todavía reglas comerciales."""

    cotizacion = _cotizacion_o_404(sesion, cotizacion_id)
    documento = _documento_o_404(sesion, cotizacion_id, documento_id)
    partidas_actuales = listar_partidas_documento(sesion, documento.id)
    formulario = await request.form()
    validar_token_csrf(request, str(formulario.get("csrf_token") or ""))

    try:
        total = int(str(formulario.get("partidas_total") or "0"))
        if total < 0 or total > 100:
            raise ValueError("Cantidad de renglones fuera del límite permitido")
        partidas = [
            partida
            for indice in range(total)
            if (partida := _partida_desde_formulario(formulario, indice)) is not None
        ]
        lectura = LecturaDocumento(
            tipo_documento=_limpiar_texto(formulario.get("tipo_documento")),
            memorandum=_limpiar_texto(formulario.get("memorandum")),
            folios=_separar_folios(formulario.get("folios")),
            fecha_documento=_limpiar_texto(formulario.get("fecha_documento")),
            municipio=_limpiar_texto(formulario.get("municipio")),
            parece_fragmento=formulario.get("parece_fragmento") == "1",
            senales_fragmento=documento.senales_fragmento,
            partidas=partidas,
        )
    except (ValueError, TypeError) as error:
        return _render_revision(
            request,
            usuario,
            cotizacion,
            documento,
            partidas_actuales,
            error=str(error),
            codigo=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    guardar_revision(
        sesion,
        documento=documento,
        lectura_revisada=lectura,
        usuario_id=usuario.id,
    )
    return RedirectResponse(
        url=f"/cotizaciones/{cotizacion.id}/documentos/{documento.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/cotizaciones/{cotizacion_id}/documentos/{documento_id}/eliminar",
    name="eliminar_documento",
)
def eliminar(
    cotizacion_id: str,
    documento_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    csrf_token: Annotated[str, Form()],
):
    """Elimina por completo el registro de un archivo cargado por error."""

    validar_token_csrf(request, csrf_token)
    cotizacion = _cotizacion_o_404(sesion, cotizacion_id)
    documento = _documento_o_404(sesion, cotizacion_id, documento_id)
    eliminar_documento(sesion, documento=documento)
    return RedirectResponse(
        url=f"/cotizaciones/{cotizacion.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
