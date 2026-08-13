"""Sesiones, CSRF y dependencias de acceso interno."""

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from triage.base_datos import obtener_sesion
from triage.usuarios.modelos import Usuario

Sesion = Annotated[Session, Depends(obtener_sesion)]
_CLAVE_USUARIO = "usuario_id"
_CLAVE_CSRF = "csrf_token"


class AccesoRequerido(Exception):
    """Señala que una ruta interna fue solicitada sin sesión válida."""


def obtener_token_csrf(request: Request) -> str:
    """Mantiene un token aleatorio ligado a la sesión firmada del navegador."""

    token = request.session.get(_CLAVE_CSRF)
    if not isinstance(token, str) or not token:
        token = secrets.token_urlsafe(32)
        request.session[_CLAVE_CSRF] = token
    return token


def validar_token_csrf(request: Request, token_recibido: str) -> None:
    """Rechaza operaciones POST que no provengan del formulario de la sesión."""

    token_esperado = request.session.get(_CLAVE_CSRF)
    if (
        not isinstance(token_esperado, str)
        or not token_esperado
        or not token_recibido
        or not secrets.compare_digest(token_esperado, token_recibido)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Formulario vencido o inválido. Recarga la página e intenta de nuevo.",
        )


def iniciar_sesion(request: Request, usuario: Usuario) -> None:
    """Renueva completamente la sesión después de autenticar."""

    request.session.clear()
    request.session[_CLAVE_USUARIO] = usuario.id
    request.session[_CLAVE_CSRF] = secrets.token_urlsafe(32)


def cerrar_sesion(request: Request) -> None:
    """Elimina cualquier identidad y token asociado al navegador."""

    request.session.clear()


def obtener_usuario_opcional(request: Request, sesion: Sesion) -> Usuario | None:
    """Recupera la identidad de la sesión sin asumir que sigue habilitada."""

    usuario_id = request.session.get(_CLAVE_USUARIO)
    if not isinstance(usuario_id, str) or not usuario_id:
        return None

    usuario = sesion.get(Usuario, usuario_id)
    if usuario is None or not usuario.activo:
        request.session.clear()
        return None
    return usuario


def requerir_usuario(request: Request, sesion: Sesion) -> Usuario:
    """Bloquea rutas internas hasta tener una persona autenticada y activa."""

    usuario = obtener_usuario_opcional(request, sesion)
    if usuario is None:
        raise AccesoRequerido
    return usuario


UsuarioActual = Annotated[Usuario, Depends(requerir_usuario)]


def requerir_admin(usuario: UsuarioActual) -> Usuario:
    """Reserva funciones administrativas a cuentas marcadas como administradoras."""

    if not usuario.es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta acción requiere una cuenta administradora.",
        )
    return usuario


UsuarioAdmin = Annotated[Usuario, Depends(requerir_admin)]
