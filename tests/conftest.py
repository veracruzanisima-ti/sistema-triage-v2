"""Fixtures compartidas para probar la aplicación sin servicios externos."""

import re
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from triage.base_datos import Base
from triage.config import Configuracion
from triage.main import crear_app
from triage.usuarios.servicio import crear_usuario

CORREO_PRUEBA = "raquel.pruebas@veracruzanisima.local"
CONTRASENA_PRUEBA = "contrasena-prueba-segura"


def extraer_csrf(html: str) -> str:
    """Obtiene el token generado por la interfaz sin acoplar la prueba al backend."""

    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF en el formulario")
    return coincidencia.group(1)


@pytest.fixture()
def cliente_sin_acceso(tmp_path) -> Iterator[TestClient]:
    """Entrega una app aislada con un usuario válido pero sin sesión iniciada."""

    ruta_db = tmp_path / "triage_prueba.sqlite3"
    configuracion = Configuracion(
        app_env="test",
        database_url=f"sqlite+pysqlite:///{ruta_db}",
    )
    aplicacion = crear_app(configuracion)
    Base.metadata.create_all(bind=aplicacion.state.motor)

    with aplicacion.state.fabrica_sesiones() as sesion:
        crear_usuario(
            sesion,
            correo=CORREO_PRUEBA,
            nombre="Raquel Pruebas",
            contrasena=CONTRASENA_PRUEBA,
            es_admin=True,
        )

    with TestClient(aplicacion) as cliente_prueba:
        yield cliente_prueba

    aplicacion.state.motor.dispose()


@pytest.fixture()
def cliente(cliente_sin_acceso: TestClient) -> TestClient:
    """Inicia sesión usando el mismo formulario que utilizará una persona."""

    formulario = cliente_sin_acceso.get("/acceso")
    token = extraer_csrf(formulario.text)
    respuesta = cliente_sin_acceso.post(
        "/acceso",
        data={
            "correo": CORREO_PRUEBA,
            "contrasena": CONTRASENA_PRUEBA,
            "csrf_token": token,
        },
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/cotizaciones"
    return cliente_sin_acceso
