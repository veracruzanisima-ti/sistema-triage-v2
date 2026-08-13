"""Punto de entrada de Triage V2."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import Engine
from starlette.middleware.sessions import SessionMiddleware

from triage.base_datos import crear_fabrica_sesiones, crear_motor
from triage.config import Configuracion, obtener_configuracion
from triage.cotizaciones.rutas import router as router_cotizaciones
from triage.documentos.rutas import router as router_documentos
from triage.lectores.base import LectorDocumento
from triage.lectores.openai import LectorOpenAI
from triage.normalizacion.rutas import router as router_normalizacion
from triage.usuarios.rutas import router as router_usuarios
from triage.usuarios.seguridad import AccesoRequerido
from triage.usuarios.servicio import crear_admin_inicial_si_corresponde, hay_usuarios_activos

BASE_DIR = Path(__file__).resolve().parent


def crear_app(
    configuracion: Configuracion | None = None,
    *,
    motor: Engine | None = None,
    lector_documentos: LectorDocumento | None = None,
) -> FastAPI:
    """Construye la aplicación permitiendo inyectar infraestructura en pruebas."""

    configuracion = configuracion or obtener_configuracion()
    motor_base_datos = motor or crear_motor(configuracion.database_url)
    fabrica_sesiones = crear_fabrica_sesiones(motor_base_datos)
    lector = lector_documentos
    if lector is None and configuracion.openai_api_key.strip():
        lector = LectorOpenAI(
            api_key=configuracion.openai_api_key,
            modelo=configuracion.openai_model,
        )

    @asynccontextmanager
    async def ciclo_vida(_aplicacion: FastAPI) -> AsyncIterator[None]:
        """Prepara únicamente el administrador inicial; no ejecuta migraciones."""

        with fabrica_sesiones() as sesion:
            crear_admin_inicial_si_corresponde(sesion, configuracion)
            if configuracion.es_produccion and not hay_usuarios_activos(sesion):
                raise RuntimeError(
                    "No existe un usuario activo. Configura el administrador inicial."
                )
        yield

    aplicacion = FastAPI(
        title="Sistema Triage V2",
        version="0.1.0",
        docs_url=None if configuracion.es_produccion else "/docs",
        redoc_url=None,
        lifespan=ciclo_vida,
    )
    aplicacion.add_middleware(
        SessionMiddleware,
        secret_key=configuracion.clave_sesion,
        session_cookie="triage_sesion",
        max_age=configuracion.session_max_age_seconds,
        same_site="lax",
        https_only=configuracion.es_produccion,
    )
    aplicacion.state.configuracion = configuracion
    aplicacion.state.motor = motor_base_datos
    aplicacion.state.fabrica_sesiones = fabrica_sesiones
    aplicacion.state.lector_documentos = lector
    aplicacion.state.plantillas = Jinja2Templates(
        directory=str(BASE_DIR / "templates")
    )
    aplicacion.include_router(router_usuarios)
    aplicacion.include_router(router_cotizaciones)
    aplicacion.include_router(router_documentos)
    aplicacion.include_router(router_normalizacion)

    @aplicacion.exception_handler(AccesoRequerido)
    async def manejar_acceso_requerido(
        _request: Request,
        _error: AccesoRequerido,
    ) -> RedirectResponse:
        """Envía a la pantalla de acceso sin revelar contenido interno."""

        return RedirectResponse(
            url="/acceso",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @aplicacion.get("/health", tags=["operación"])
    def healthcheck() -> dict[str, str]:
        """Permite al despliegue verificar que el proceso está disponible."""

        return {"estado": "ok"}

    @aplicacion.get("/", include_in_schema=False)
    def inicio():
        """Lleva a la lista operativa; el acceso se valida al entrar."""

        return RedirectResponse(
            url="/cotizaciones",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return aplicacion


app = crear_app()
