"""Operaciones de usuarios internos sin depender de la interfaz web."""

from sqlalchemy import select
from sqlalchemy.orm import Session
from pwdlib import PasswordHash

from triage.config import Configuracion
from triage.usuarios.modelos import Usuario

_HASHER = PasswordHash.recommended()
_HASH_FALSO = _HASHER.hash("usuario-inexistente-no-es-una-clave-real")
_MINIMO_CONTRASENA = 12


def normalizar_correo(correo: str) -> str:
    """Normaliza el identificador de acceso sin inventar equivalencias."""

    return correo.strip().casefold()


def hash_contrasena(contrasena: str) -> str:
    """Genera un hash Argon2 para una contraseña que cumple el mínimo local."""

    if len(contrasena) < _MINIMO_CONTRASENA:
        raise ValueError("la contraseña requiere al menos 12 caracteres")
    return _HASHER.hash(contrasena)


def verificar_contrasena(contrasena: str, password_hash: str) -> bool:
    """Verifica una contraseña sin almacenar ni registrar su valor."""

    return _HASHER.verify(contrasena, password_hash)


def crear_usuario(
    sesion: Session,
    *,
    correo: str,
    nombre: str,
    contrasena: str,
    es_admin: bool = False,
) -> Usuario:
    """Crea una cuenta interna explícita y activa."""

    correo_normalizado = normalizar_correo(correo)
    nombre_limpio = " ".join(nombre.split())
    if not correo_normalizado or "@" not in correo_normalizado:
        raise ValueError("correo inválido")
    if not nombre_limpio:
        raise ValueError("nombre obligatorio")
    if sesion.scalar(select(Usuario).where(Usuario.correo == correo_normalizado)):
        raise ValueError("ya existe un usuario con ese correo")

    usuario = Usuario(
        correo=correo_normalizado,
        nombre=nombre_limpio,
        password_hash=hash_contrasena(contrasena),
        es_admin=es_admin,
    )
    sesion.add(usuario)
    sesion.commit()
    sesion.refresh(usuario)
    return usuario


def autenticar_usuario(sesion: Session, correo: str, contrasena: str) -> Usuario | None:
    """Autentica con un mensaje indistinguible para correos inexistentes/inactivos."""

    correo_normalizado = normalizar_correo(correo)
    usuario = sesion.scalar(select(Usuario).where(Usuario.correo == correo_normalizado))
    hash_a_verificar = usuario.password_hash if usuario is not None else _HASH_FALSO
    contrasena_valida = verificar_contrasena(contrasena, hash_a_verificar)

    if usuario is None or not usuario.activo or not contrasena_valida:
        return None
    return usuario


def hay_usuarios_activos(sesion: Session) -> bool:
    """Indica si la aplicación ya cuenta con al menos una persona habilitada."""

    consulta = select(Usuario.id).where(Usuario.activo.is_(True)).limit(1)
    return sesion.scalar(consulta) is not None


def crear_admin_inicial_si_corresponde(
    sesion: Session,
    configuracion: Configuracion,
) -> Usuario | None:
    """Crea un único administrador inicial sólo cuando la base aún está vacía."""

    if hay_usuarios_activos(sesion):
        return None

    correo = configuracion.bootstrap_admin_email.strip()
    nombre = configuracion.bootstrap_admin_name.strip()
    contrasena = configuracion.bootstrap_admin_password
    if not (correo and nombre and contrasena):
        return None

    return crear_usuario(
        sesion,
        correo=correo,
        nombre=nombre,
        contrasena=contrasena,
        es_admin=True,
    )
