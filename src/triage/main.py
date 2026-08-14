"""Punto de entrada de Triage V2."""

from collections.abc import AsyncIterator, Sequence
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
from triage.historico.decisiones_rutas import router as router_decisiones_precio
from triage.historico.rutas import router as router_historico
from triage.lectores.base import LectorDocumento
from triage.lectores.gemini import LectorGemini
from triage.lectores.openai import LectorOpenAI
from triage.modelos_ia_rutas import router as router_modelos_ia
from triage.normalizacion.rutas import router as router_normalizacion
from triage.proveedores.base import ProveedorProducto
from triage.proveedores.descubrimiento_web import (
    DescubridorWeb,
    DescubridorWebGemini,
    DescubridorWebOpenAI,
)
from triage.proveedores.rutas import router as router_proveedores
from triage.revision_final.rutas import router as router_revision_final
from triage.usuarios.rutas import router as router_usuarios
from triage.usuarios.seguridad import AccesoRequerido
from triage.usuarios.servicio import crear_admin_inicial_si_corresponde, hay_usuarios_activos

BASE_DIR = Path(__file__).resolve().parent


def _modelos_unicos(*modelos: str) -> tuple[str, ...]:
    """Conserva el orden al armar el pequeño catálogo del piloto."""

    resultado: list[str] = []
    for modelo in modelos:
        limpio = modelo.strip()
        if limpio and limpio not in resultado:
            resultado.append(limpio)
    return tuple(resultado)


def crear_app(
    configuracion: Configuracion | None = None,
    *,
    motor: Engine | None = None,
    lector_documentos: LectorDocumento | None = None,
    proveedores_productos: Sequence[ProveedorProducto] | None = None,
    descubridor_web: DescubridorWeb | None = None,
) -> FastAPI:
    """Construye la aplicación permitiendo inyectar infraestructura en pruebas."""

    configuracion = configuracion or obtener_configuracion()
    motor_base_datos = motor or crear_motor(configuracion.database_url)
    fabrica_sesiones = crear_fabrica_sesiones(motor_base_datos)

    lectores_ia: dict[str, LectorDocumento] = {}
    clave_lector_default = ""
    if lector_documentos is not None:
        clave_lector_default = "inyectado:lector"
        lectores_ia[clave_lector_default] = lector_documentos
    elif configuracion.openai_api_key.strip():
        for modelo in _modelos_unicos(configuracion.modelo_openai_lector, "gpt-5", "gpt-5.4-mini"):
            lectores_ia[f"openai:{modelo}"] = LectorOpenAI(
                api_key=configuracion.openai_api_key,
                modelo=modelo,
            )
        clave_lector_default = f"openai:{configuracion.modelo_openai_lector}"

    if configuracion.gemini_api_key.strip():
        modelo = configuracion.gemini_model_lector.strip()
        lectores_ia[f"gemini:{modelo}"] = LectorGemini(
            api_key=configuracion.gemini_api_key,
            modelo=modelo,
        )

    lector = lectores_ia.get(clave_lector_default) or next(iter(lectores_ia.values()), None)

    descubridores_ia: dict[str, DescubridorWeb] = {}
    clave_web_default = ""
    if descubridor_web is not None:
        clave_web_default = "inyectado:web"
        descubridores_ia[clave_web_default] = descubridor_web
    elif configuracion.openai_api_key.strip():
        for modelo in _modelos_unicos(configuracion.modelo_openai_web, "gpt-5", "gpt-5.4-mini"):
            descubridores_ia[f"openai:{modelo}"] = DescubridorWebOpenAI(
                api_key=configuracion.openai_api_key,
                modelo=modelo,
            )
        clave_web_default = f"openai:{configuracion.modelo_openai_web}"

    if configuracion.gemini_api_key.strip():
        modelo = configuracion.gemini_model_web.strip()
        descubridores_ia[f"gemini:{modelo}"] = DescubridorWebGemini(
            api_key=configuracion.gemini_api_key,
            modelo=modelo,
        )

    buscador_web = descubridores_ia.get(clave_web_default) or next(
        iter(descubridores_ia.values()), None
    )

    proveedores_por_nombre: dict[str, ProveedorProducto] = {}
    for adaptador in proveedores_productos or ():
        nombre = adaptador.nombre.strip()
        if not nombre:
            raise ValueError("un proveedor configurado no tiene nombre")
        clave = nombre.casefold()
        if clave in proveedores_por_nombre:
            raise ValueError(f"proveedor duplicado: {nombre}")
        proveedores_por_nombre[clave] = adaptador

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
    aplicacion.state.lectores_ia = lectores_ia
    aplicacion.state.clave_lector_default = clave_lector_default
    aplicacion.state.proveedores_productos = proveedores_por_nombre
    aplicacion.state.descubridor_web = buscador_web
    aplicacion.state.descubridores_ia = descubridores_ia
    aplicacion.state.clave_web_default = clave_web_default
    aplicacion.state.plantillas = Jinja2Templates(
        directory=str(BASE_DIR / "templates")
    )
    aplicacion.include_router(router_usuarios)
    aplicacion.include_router(router_modelos_ia)
    aplicacion.include_router(router_cotizaciones)
    aplicacion.include_router(router_documentos)
    aplicacion.include_router(router_normalizacion)
    aplicacion.include_router(router_historico)
    aplicacion.include_router(router_decisiones_precio)
    aplicacion.include_router(router_proveedores)
    aplicacion.include_router(router_revision_final)

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
