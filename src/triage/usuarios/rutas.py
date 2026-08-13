"""Rutas de acceso y administración mínima para integrantes autorizados."""

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from triage.usuarios.modelos import Usuario
from triage.usuarios.seguridad import (
    Sesion,
    UsuarioActual,
    UsuarioAdmin,
    cerrar_sesion,
    iniciar_sesion,
    obtener_token_csrf,
    obtener_usuario_opcional,
    validar_token_csrf,
)
from triage.usuarios.servicio import (
    autenticar_usuario,
    cambiar_contrasena_propia,
    cambiar_estado_usuario,
    crear_usuario,
    listar_usuarios,
    restablecer_contrasena_usuario,
)

router = APIRouter(tags=["acceso"])


def _plantillas(request: Request):
    return request.app.state.plantillas


def _contexto_usuario(request: Request, usuario, **valores):
    return {
        "usuario": usuario,
        "csrf_token": obtener_token_csrf(request),
        **valores,
    }


@router.get("/acceso", response_class=HTMLResponse, name="acceso")
def acceso(request: Request, sesion: Sesion):
    """Muestra un único formulario de acceso para cuentas internas."""

    if obtener_usuario_opcional(request, sesion) is not None:
        return RedirectResponse(
            url="/cotizaciones",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return _plantillas(request).TemplateResponse(
        request=request,
        name="usuarios/acceso.html",
        context={
            "csrf_token": obtener_token_csrf(request),
            "error": "",
        },
    )


@router.post("/acceso", response_class=HTMLResponse, name="iniciar_acceso")
def iniciar_acceso(
    request: Request,
    sesion: Sesion,
    correo: Annotated[str, Form()],
    contrasena: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
):
    """Autentica sin revelar si el correo o la contraseña fueron incorrectos."""

    validar_token_csrf(request, csrf_token)
    usuario = autenticar_usuario(sesion, correo, contrasena)
    if usuario is None:
        return _plantillas(request).TemplateResponse(
            request=request,
            name="usuarios/acceso.html",
            context={
                "csrf_token": obtener_token_csrf(request),
                "error": "Correo o contraseña incorrectos.",
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    iniciar_sesion(request, usuario)
    return RedirectResponse(
        url="/cotizaciones",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/salir", name="salir")
def salir(
    request: Request,
    csrf_token: Annotated[str, Form()],
):
    """Cierra explícitamente la sesión del navegador."""

    validar_token_csrf(request, csrf_token)
    cerrar_sesion(request)
    return RedirectResponse(
        url="/acceso",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/mi-cuenta/contrasena", response_class=HTMLResponse)
def ver_cambio_contrasena(request: Request, usuario: UsuarioActual):
    """Permite a cada persona reemplazar su propia contraseña."""

    return _plantillas(request).TemplateResponse(
        request=request,
        name="usuarios/cambiar_contrasena.html",
        context=_contexto_usuario(request, usuario, error="", guardado=False),
    )


@router.post("/mi-cuenta/contrasena", response_class=HTMLResponse)
def guardar_cambio_contrasena(
    request: Request,
    sesion: Sesion,
    usuario: UsuarioActual,
    csrf_token: Annotated[str, Form()],
    contrasena_actual: Annotated[str, Form()],
    contrasena_nueva: Annotated[str, Form()],
    confirmar_contrasena: Annotated[str, Form()],
):
    """Cambia la contraseña sólo después de verificar la actual."""

    validar_token_csrf(request, csrf_token)
    try:
        cambiar_contrasena_propia(
            sesion,
            usuario=usuario,
            contrasena_actual=contrasena_actual,
            contrasena_nueva=contrasena_nueva,
            confirmar_contrasena=confirmar_contrasena,
        )
    except ValueError as error:
        return _plantillas(request).TemplateResponse(
            request=request,
            name="usuarios/cambiar_contrasena.html",
            context=_contexto_usuario(
                request,
                usuario,
                error=str(error),
                guardado=False,
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    return _plantillas(request).TemplateResponse(
        request=request,
        name="usuarios/cambiar_contrasena.html",
        context=_contexto_usuario(request, usuario, error="", guardado=True),
    )


@router.get("/usuarios", response_class=HTMLResponse, name="administrar_usuarios")
def administrar_usuarios(
    request: Request,
    sesion: Sesion,
    admin: UsuarioAdmin,
    creado: int = 0,
    actualizado: int = 0,
):
    """Muestra las cuentas internas a una persona administradora."""

    return _plantillas(request).TemplateResponse(
        request=request,
        name="usuarios/administrar.html",
        context=_contexto_usuario(
            request,
            admin,
            usuarios=listar_usuarios(sesion),
            creado=bool(creado),
            actualizado=bool(actualizado),
            error="",
        ),
    )


@router.post("/usuarios", response_class=HTMLResponse, name="crear_usuario_interno")
def crear_usuario_interno(
    request: Request,
    sesion: Sesion,
    admin: UsuarioAdmin,
    csrf_token: Annotated[str, Form()],
    nombre: Annotated[str, Form()],
    correo: Annotated[str, Form()],
    contrasena_temporal: Annotated[str, Form()],
):
    """Crea una cuenta operativa no administradora sin registro público."""

    validar_token_csrf(request, csrf_token)
    try:
        crear_usuario(
            sesion,
            correo=correo,
            nombre=nombre,
            contrasena=contrasena_temporal,
            es_admin=False,
        )
    except ValueError as error:
        return _plantillas(request).TemplateResponse(
            request=request,
            name="usuarios/administrar.html",
            context=_contexto_usuario(
                request,
                admin,
                usuarios=listar_usuarios(sesion),
                creado=False,
                actualizado=False,
                error=str(error),
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    return RedirectResponse(
        url="/usuarios?creado=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/usuarios/{usuario_id}/estado", name="cambiar_estado_usuario_web")
def cambiar_estado_usuario_web(
    usuario_id: str,
    request: Request,
    sesion: Sesion,
    admin: UsuarioAdmin,
    csrf_token: Annotated[str, Form()],
    activo: Annotated[str, Form()],
):
    """Activa o desactiva una cuenta interna de forma reversible."""

    validar_token_csrf(request, csrf_token)
    if activo not in {"0", "1"}:
        raise HTTPException(status_code=422, detail="Estado de usuario no permitido")

    usuario_objetivo = sesion.get(Usuario, usuario_id)
    if usuario_objetivo is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    try:
        cambiar_estado_usuario(
            sesion,
            usuario_objetivo=usuario_objetivo,
            activo=activo == "1",
            usuario_actual=admin,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return RedirectResponse(
        url="/usuarios?actualizado=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/usuarios/{usuario_id}/contrasena",
    name="restablecer_contrasena_usuario_web",
)
def restablecer_contrasena_usuario_web(
    usuario_id: str,
    request: Request,
    sesion: Sesion,
    admin: UsuarioAdmin,
    csrf_token: Annotated[str, Form()],
    contrasena_temporal: Annotated[str, Form()],
):
    """Permite al administrador fijar una nueva contraseña temporal."""

    validar_token_csrf(request, csrf_token)
    usuario_objetivo = sesion.get(Usuario, usuario_id)
    if usuario_objetivo is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    try:
        restablecer_contrasena_usuario(
            sesion,
            usuario_objetivo=usuario_objetivo,
            contrasena_temporal=contrasena_temporal,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return RedirectResponse(
        url="/usuarios?actualizado=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )
