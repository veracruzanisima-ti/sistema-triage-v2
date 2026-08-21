"""Rutas para ejecutar consultas actuales sin ocultar la decisión humana posterior."""

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from triage.comercial.modelos import EstadoComercial
from triage.comercial.servicio import listar_decisiones_comerciales_actuales
from triage.cotizaciones.servicio import obtener_cotizacion
from triage.historico.decisiones_servicio import (
    listar_selecciones_actuales,
    referencias_estables_cotizadas_hoy,
)
from triage.historico.servicio import listar_productos_historico
from triage.modelos_ia import obtener_descubridor_web
from triage.proveedores.cofepris_servicio import (
    total_registros_cofepris,
    ultima_importacion_cofepris,
)
from triage.proveedores.descubrimiento_web import ErrorDescubrimientoWeb
from triage.proveedores.nadro_adaptador import adaptadores_nadro_disponibles
from triage.proveedores.servicio import (
    ErrorConsultaProveedor,
    confirmar_presentacion_alternativa_web,
    ejecutar_consulta,
    ejecutar_consultas_configuradas,
    ejecutar_consultas_partida,
    ejecutar_descubrimiento_web,
    listar_productos_consultables,
    listar_trazabilidad_web,
)
from triage.proveedores.vista_precios import preparar_vista_precios
from triage.usuarios.seguridad import (
    Sesion,
    UsuarioActual,
    obtener_token_csrf,
    validar_token_csrf,
)

router = APIRouter(prefix="/cotizaciones", tags=["proveedores"])


def _plantillas(request: Request):
    return request.app.state.plantillas


def _proveedores(request: Request, sesion: Sesion) -> dict[str, object]:
    """Combina fuentes externas con el snapshot NADRO vigente de esta petición."""

    proveedores = dict(request.app.state.proveedores_productos)
    for adaptador in adaptadores_nadro_disponibles(
        sesion,
        request.app.state.fabrica_sesiones,
    ):
        proveedores[adaptador.nombre.casefold()] = adaptador
    return proveedores


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
    proveedores = _proveedores(request, sesion)
    importacion_cofepris = ultima_importacion_cofepris(sesion)
    total_cofepris = total_registros_cofepris(sesion)
    productos = listar_productos_historico(sesion, cotizacion.id)
    consultables = listar_productos_consultables(sesion, cotizacion.id)
    consultas_por_partida = {
        producto.partida.id: producto.consultas for producto in consultables
    }
    trazabilidad_web_por_partida = listar_trazabilidad_web(sesion, cotizacion.id)
    selecciones = listar_selecciones_actuales(sesion, cotizacion.id)
    decisiones_comerciales = listar_decisiones_comerciales_actuales(sesion, cotizacion.id)
    ids_cotizables = {
        producto.partida.id
        for producto in productos
        if decisiones_comerciales.get(producto.partida.id, None) is None
        or decisiones_comerciales[producto.partida.id].estado == EstadoComercial.COTIZABLE
    }
    vistas_precios = {}
    for producto in productos:
        seleccion = selecciones.get(producto.partida.id)
        referencia_id = seleccion.referencia_estable_id if seleccion else None
        vistas_precios[producto.partida.id] = preparar_vista_precios(
            producto.observaciones,
            referencia_id=referencia_id,
            codigo_postal=cotizacion.codigo_postal_consulta,
        )

    referencias_hoy = referencias_estables_cotizadas_hoy(
        sesion,
        claves={
            producto.clave_producto
            for producto in productos
            if producto.partida.id in ids_cotizables
        },
        codigo_postal=cotizacion.codigo_postal_consulta,
    )
    con_referencia = sum(
        bool(seleccion.referencia_estable_id)
        for partida_id, seleccion in selecciones.items()
        if partida_id in ids_cotizables
    )
    return _plantillas(request).TemplateResponse(
        request=request,
        name="proveedores/consulta.html",
        context={
            "usuario": usuario,
            "csrf_token": obtener_token_csrf(request),
            "cotizacion": cotizacion,
            "productos": productos,
            "decisiones_comerciales": decisiones_comerciales,
            "estados_comerciales": EstadoComercial,
            "cotizables": len(ids_cotizables),
            "no_se_cotiza": len(productos) - len(ids_cotizables),
            "consultas_por_partida": consultas_por_partida,
            "trazabilidad_web_por_partida": trazabilidad_web_por_partida,
            "selecciones": selecciones,
            "vistas_precios": vistas_precios,
            "referencias_cotizadas_hoy": referencias_hoy,
            "con_referencia": con_referencia,
            "todas_con_referencia": bool(ids_cotizables)
            and con_referencia == len(ids_cotizables),
            "proveedores": tuple(proveedor.nombre for proveedor in proveedores.values()),
            "cofepris_importacion": importacion_cofepris,
            "cofepris_total_registros": total_cofepris,
            "cofepris_activo": importacion_cofepris is not None and total_cofepris > 0,
            "descubrimiento_web_disponible": obtener_descubridor_web(request) is not None,
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
    precios: int = 0,
    errores: int = 0,
    reutilizados: int = 0,
    duplicadas: int = 0,
    web_guardados: int = 0,
    web_descartados: int = 0,
    web_intentos: int = 0,
):
    """Muestra productos preparados, precios observados e intentos recientes."""

    cotizacion = obtener_cotizacion(sesion, cotizacion_id)
    if cotizacion is None:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    resumen_unificado = f"Búsqueda completada: {precios} precio(s) encontrado(s)"
    if reutilizados:
        resumen_unificado += f", {reutilizados} producto(s) reutilizado(s) de hoy"
    if duplicadas:
        resumen_unificado += f", {duplicadas} partida(s) repetida(s) sin consulta duplicada"
    if errores:
        resumen_unificado += f" y {errores} fuente(s) con error"
    resumen_unificado += "."

    mensajes = {
        "exitosa": "Consulta guardada como una nueva observación de precio.",
        "no_encontrado": "El proveedor no reportó una coincidencia utilizable.",
        "unificada": resumen_unificado,
        "revalidada": (
            f"Revalidación completada: {precios} precio(s) nuevo(s) observado(s)"
            + (f" y {errores} fuente(s) con error." if errores else ".")
        ),
        "web": (
            (
                f"Búsqueda web completada: {web_guardados} opción(es) exacta(s) guardada(s)"
                if web_guardados
                else "Búsqueda web completada sin coincidencias exactas"
            )
            + (f" después de {web_intentos} búsqueda(s)" if web_intentos else "")
            + (
                f" y {web_descartados} resultado(s) descartado(s)."
                if web_descartados
                else "."
            )
        ),
        "presentacion_actualizada": (
            "Presentación de búsqueda actualizada. La solicitud original no cambió. "
            "Busca precios nuevamente para comprobar la coincidencia."
        ),
    }
    return _render(
        request,
        sesion,
        usuario,
        cotizacion,
        mensaje=mensajes.get(resultado, ""),
    )


@router.post("/{cotizacion_id}/proveedores/consultar")
def consultar_proveedores_configurados(
    cotizacion_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    csrf_token: Annotated[str, Form()],
):
    """Consulta identidades nuevas y reutiliza referencias estables observadas hoy."""

    validar_token_csrf(request, csrf_token)
    cotizacion = obtener_cotizacion(sesion, cotizacion_id)
    if cotizacion is None:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    try:
        resumen = ejecutar_consultas_configuradas(
            sesion,
            cotizacion_id=cotizacion_id,
            usuario_id=usuario.id,
            proveedores=tuple(_proveedores(request, sesion).values()),
        )
    except ValueError as error:
        return _render(
            request,
            sesion,
            usuario,
            cotizacion,
            error=str(error),
            status_code=status.HTTP_409_CONFLICT,
        )

    return RedirectResponse(
        url=(
            f"/cotizaciones/{cotizacion_id}/proveedores"
            f"?resultado=unificada&precios={resumen.precios_encontrados}"
            f"&errores={resumen.errores}"
            f"&reutilizados={resumen.productos_reutilizados_hoy}"
            f"&duplicadas={resumen.partidas_duplicadas_omitidas}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{cotizacion_id}/proveedores/{partida_documento_id}/revalidar")
def revalidar_precio_partida(
    cotizacion_id: str,
    partida_documento_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    csrf_token: Annotated[str, Form()],
):
    """Fuerza un recheck corto del producto contra todos los adaptadores configurados."""

    validar_token_csrf(request, csrf_token)
    cotizacion = obtener_cotizacion(sesion, cotizacion_id)
    if cotizacion is None:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    try:
        resumen = ejecutar_consultas_partida(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_documento_id,
            usuario_id=usuario.id,
            proveedores=tuple(_proveedores(request, sesion).values()),
        )
    except ValueError as error:
        return _render(
            request,
            sesion,
            usuario,
            cotizacion,
            error=str(error),
            status_code=status.HTTP_409_CONFLICT,
        )

    return RedirectResponse(
        url=(
            f"/cotizaciones/{cotizacion_id}/proveedores"
            f"?resultado=revalidada&precios={resumen.precios_encontrados}"
            f"&errores={resumen.errores}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{cotizacion_id}/proveedores/{partida_documento_id}/buscar-web")
def buscar_mas_opciones_web(
    cotizacion_id: str,
    partida_documento_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    csrf_token: Annotated[str, Form()],
):
    """Busca candidatos públicos sólo cuando la persona necesita ampliar opciones."""

    validar_token_csrf(request, csrf_token)
    cotizacion = obtener_cotizacion(sesion, cotizacion_id)
    if cotizacion is None:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    descubridor = obtener_descubridor_web(request)
    if descubridor is None:
        return _render(
            request,
            sesion,
            usuario,
            cotizacion,
            error="La búsqueda web no está configurada en este entorno.",
            status_code=status.HTTP_409_CONFLICT,
        )

    try:
        resumen = ejecutar_descubrimiento_web(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_documento_id,
            usuario_id=usuario.id,
            descubridor=descubridor,
        )
    except ValueError as error:
        return _render(
            request,
            sesion,
            usuario,
            cotizacion,
            error=str(error),
            status_code=status.HTTP_409_CONFLICT,
        )
    except ErrorDescubrimientoWeb as error:
        return _render(
            request,
            sesion,
            usuario,
            cotizacion,
            error=str(error),
            status_code=status.HTTP_502_BAD_GATEWAY,
        )

    return RedirectResponse(
        url=(
            f"/cotizaciones/{cotizacion_id}/proveedores?resultado=web"
            f"&web_guardados={resumen.guardados}&web_descartados={resumen.descartados}"
            f"&web_intentos={resumen.intentos}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
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

    adaptador = _proveedores(request, sesion).get(proveedor.casefold())
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


@router.post(
    "/{cotizacion_id}/proveedores/{partida_documento_id}"
    "/presentacion-alternativa/{candidato_descartado_id}"
)
def usar_presentacion_alternativa_web(
    cotizacion_id: str,
    partida_documento_id: str,
    candidato_descartado_id: str,
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    csrf_token: Annotated[str, Form()],
):
    """Confirma una presentación web sin tocar la evidencia documental."""

    validar_token_csrf(request, csrf_token)
    cotizacion = obtener_cotizacion(sesion, cotizacion_id)
    if cotizacion is None:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    try:
        confirmar_presentacion_alternativa_web(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_documento_id,
            candidato_descartado_id=candidato_descartado_id,
            usuario_id=usuario.id,
        )
    except ValueError as error:
        return _render(
            request,
            sesion,
            usuario,
            cotizacion,
            error=str(error),
            status_code=status.HTTP_409_CONFLICT,
        )

    return RedirectResponse(
        url=(
            f"/cotizaciones/{cotizacion_id}/proveedores"
            "?resultado=presentacion_actualizada"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )
