import re

from fastapi.testclient import TestClient

from tests.conftest import CONTRASENA_PRUEBA, CORREO_PRUEBA


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


def test_login_sin_csrf_es_rechazado(cliente_sin_acceso: TestClient):
    respuesta = cliente_sin_acceso.post(
        "/acceso",
        data={
            "correo": CORREO_PRUEBA,
            "contrasena": CONTRASENA_PRUEBA,
        },
    )

    assert respuesta.status_code == 422


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
