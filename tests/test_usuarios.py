import re

import pytest
from fastapi.testclient import TestClient

from triage.config import Configuracion

CORREO_PRUEBA = "raquel.pruebas@veracruzanisima.local"
CONTRASENA_PRUEBA = "contrasena-prueba-segura"


def _csrf(html: str) -> str:
    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF")
    return coincidencia.group(1)


def test_cotizaciones_requieren_sesion(cliente_sin_acceso: TestClient):
    respuesta = cliente_sin_acceso.get("/cotizaciones", follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/acceso"


def test_credenciales_incorrectas_no_revelan_el_motivo(cliente_sin_acceso: TestClient):
    formulario = cliente_sin_acceso.get("/acceso")
    respuesta = cliente_sin_acceso.post(
        "/acceso",
        data={
            "correo": CORREO_PRUEBA,
            "contrasena": "esta-contrasena-no-es-correcta",
            "csrf_token": _csrf(formulario.text),
        },
    )

    assert respuesta.status_code == 401
    assert "Correo o contraseña incorrectos" in respuesta.text


def test_login_con_csrf_incorrecto_es_rechazado(cliente_sin_acceso: TestClient):
    cliente_sin_acceso.get("/acceso")
    respuesta = cliente_sin_acceso.post(
        "/acceso",
        data={
            "correo": CORREO_PRUEBA,
            "contrasena": CONTRASENA_PRUEBA,
            "csrf_token": "token-incorrecto",
        },
    )

    assert respuesta.status_code == 403


def test_cookie_de_sesion_es_httponly_y_samesite(cliente_sin_acceso: TestClient):
    formulario = cliente_sin_acceso.get("/acceso")
    respuesta = cliente_sin_acceso.post(
        "/acceso",
        data={
            "correo": CORREO_PRUEBA,
            "contrasena": CONTRASENA_PRUEBA,
            "csrf_token": _csrf(formulario.text),
        },
        follow_redirects=False,
    )

    cookie = respuesta.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


def test_salir_elimina_la_sesion(cliente: TestClient):
    pagina = cliente.get("/cotizaciones")
    respuesta = cliente.post(
        "/salir",
        data={"csrf_token": _csrf(pagina.text)},
        follow_redirects=False,
    )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/acceso"

    protegida = cliente.get("/cotizaciones", follow_redirects=False)
    assert protegida.status_code == 303
    assert protegida.headers["location"] == "/acceso"


def test_produccion_requiere_clave_de_sesion_propia():
    with pytest.raises(ValueError, match="APP_SECRET_KEY"):
        Configuracion(
            app_env="production",
            app_secret_key="demasiado-corta",
            database_url="postgresql://usuario:clave@db.example/triage",
        )
