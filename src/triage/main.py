"""Punto de entrada de Triage V2."""

from pathlib import Path

from fastapi import FastAPI, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import Engine

from triage.base_datos import crear_fabrica_sesiones, crear_motor
from triage.config import Configuracion, obtener_configuracion
from triage.cotizaciones.rutas import router as router_cotizaciones

BASE_DIR = Path(__file__).resolve().parent


def crear_app(
    configuracion: Configuracion | None = None,
    *,
    motor: Engine | None = None,
) -> FastAPI:
    """Construye la aplicación permitiendo inyectar infraestructura en pruebas."""

    configuracion = configuracion or obtener_configuracion()
    motor_base_datos = motor or crear_motor(configuracion.database_url)

    aplicacion = FastAPI(
        title="Sistema Triage V2",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
    )
    aplicacion.state.configuracion = configuracion
    aplicacion.state.motor = motor_base_datos
    aplicacion.state.fabrica_sesiones = crear_fabrica_sesiones(motor_base_datos)
    aplicacion.state.plantillas = Jinja2Templates(
        directory=str(BASE_DIR / "templates")
    )
    aplicacion.include_router(router_cotizaciones)

    @aplicacion.get("/health", tags=["operación"])
    def healthcheck() -> dict[str, str]:
        """Permite al despliegue verificar que el proceso está disponible."""

        return {"estado": "ok"}

    @aplicacion.get("/", include_in_schema=False)
    def inicio():
        """Lleva a la lista operativa sin exponer complejidad técnica."""

        return RedirectResponse(
            url="/cotizaciones",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return aplicacion


app = crear_app()
