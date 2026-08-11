import re

import pytest
from fastapi.testclient import TestClient

from triage.base_datos import Base
from triage.config import Configuracion
from triage.main import crear_app


def _csrf(html: str) -> str:
    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF")
    return coincidencia.group(1)


def _iniciar_sesion(cliente: TestClient, correo: str, contrasena: str) -> None:
    formulario = cliente.get("/acceso")
    respuesta = cliente.post(
        "/acceso",
        data={
            "correo": correo,
            "contrasena": contrasena,
            "csrf_token": _csrf(formulario.text),
        },
        follow_redirects=False,
    )
    assert respuesta.status_code == 303


def test_crear_cotizacion_la_guarda_y_la_muestra(cliente):
    formulario = cliente.get("/cotizaciones/nueva")
    respuesta = cliente.post(
        "/cotizaciones",
        data={
            "referencia": "  DAIS/SSMA/944/2026  ",
            "csrf_token": _csrf(formulario.text),
        },
    )

    assert respuesta.status_code == 200
    assert "DAIS/SSMA/944/2026" in respuesta.text
    assert "En Proceso" in respuesta.text

    listado = cliente.get("/cotizaciones")
    assert "DAIS/SSMA/944/2026" in listado.text


def test_cotizacion_puede_finalizarse_explicitamente(cliente):
    formulario = cliente.get("/cotizaciones/nueva")
    creada = cliente.post(
        "/cotizaciones",
        data={
            "referencia": "CASC 388/08/2026",
            "csrf_token": _csrf(formulario.text),
        },
    )
    cotizacion_id = creada.url.path.rsplit("/", 1)[-1]

    respuesta = cliente.post(
        f"/cotizaciones/{cotizacion_id}/estado",
        data={
            "estado": "FINALIZADA",
            "csrf_token": _csrf(creada.text),
        },
    )

    assert respuesta.status_code == 200
    assert "Finalizada" in respuesta.text


def test_post_sin_csrf_es_rechazado(cliente):
    respuesta = cliente.post(
        "/cotizaciones",
        data={"referencia": "NO DEBE GUARDARSE"},
    )

    assert respuesta.status_code == 403


def test_cotizacion_sobrevive_a_otra_instancia_de_la_app(tmp_path):
    ruta_db = tmp_path / "triage_compartida.sqlite3"
    correo = "admin@veracruzanisima.local"
    contrasena = "administrador-prueba-seguro"
    configuracion = Configuracion(
        app_env="test",
        database_url=f"sqlite+pysqlite:///{ruta_db}",
        bootstrap_admin_email=correo,
        bootstrap_admin_name="Administrador Prueba",
        bootstrap_admin_password=contrasena,
    )

    app_primera = crear_app(configuracion)
    Base.metadata.create_all(bind=app_primera.state.motor)
    with TestClient(app_primera) as primera_sesion:
        _iniciar_sesion(primera_sesion, correo, contrasena)
        formulario = primera_sesion.get("/cotizaciones/nueva")
        primera_sesion.post(
            "/cotizaciones",
            data={
                "referencia": "DAIS/SSMA/951/2026",
                "csrf_token": _csrf(formulario.text),
            },
        )
    app_primera.state.motor.dispose()

    app_segunda = crear_app(configuracion)
    with TestClient(app_segunda) as segunda_sesion:
        _iniciar_sesion(segunda_sesion, correo, contrasena)
        respuesta = segunda_sesion.get("/cotizaciones")
    app_segunda.state.motor.dispose()

    assert respuesta.status_code == 200
    assert "DAIS/SSMA/951/2026" in respuesta.text


def test_produccion_rechaza_sqlite_local():
    with pytest.raises(ValueError, match="base de datos compartida"):
        Configuracion(
            app_env="production",
            database_url="sqlite+pysqlite:///./no_permitida.sqlite3",
        )
