"""Infraestructura mínima y compartible de base de datos."""

from collections.abc import Generator

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base declarativa común para los modelos persistentes de Triage."""


def crear_motor(database_url: str) -> Engine:
    """Crea el motor SQL sin esconder una base efímera si falta configuración."""

    url = database_url.strip()
    if not url:
        raise ValueError("DATABASE_URL no puede estar vacía")

    argumentos_conexion = (
        {"check_same_thread": False} if url.lower().startswith("sqlite") else {}
    )
    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args=argumentos_conexion,
    )


def crear_fabrica_sesiones(motor: Engine):
    """Construye sesiones independientes por petición web."""

    return sessionmaker(bind=motor, class_=Session, expire_on_commit=False)


def obtener_sesion(request: Request) -> Generator[Session, None, None]:
    """Entrega una sesión corta y siempre la cierra al terminar la petición."""

    fabrica_sesiones = request.app.state.fabrica_sesiones
    with fabrica_sesiones() as sesion:
        yield sesion
