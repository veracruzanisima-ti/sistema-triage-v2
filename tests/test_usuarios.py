import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from triage.config import Configuracion
from triage.usuarios.modelos import Usuario
from triage.usuarios.servicio import crear_usuario

CORREO_PRUEBA = "raquel.pruebas@veracruzanisima.local"
CONTRASENA_PRUEBA = "contrasena-prueba-segura"


def _csrf(html: str) -> str:
    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF")
    return coincidencia.group(1)


def _cerrar_sesion(cliente: TestClient) -> None:
    pagina = cliente.get("/cotizaciones")
    respuesta = cliente.post(
        "/salir",
        data={"csrf_token": _csrf(pagina.text)},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303


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
    assert respuesta.headers["location"] == "/cotizaciones"


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
    _cerrar_sesion(cliente)

    protegida = cliente.get("/cotizaciones", follow_redirects=False)
    assert protegida.status_code == 303
    assert protegida.headers["location"] == "/acceso"


def test_admin_puede_crear_usuario_operativo(cliente: TestClient):
    pagina = cliente.get("/usuarios")
    assert pagina.status_code == 200

    respuesta = cliente.post(
        "/usuarios",
        data={
            "csrf_token": _csrf(pagina.text),
            "nombre": "Integrante Piloto",
            "correo": "integrante@veracruzanisima.local",
            "contrasena_temporal": "temporal-segura-123",
        },
        follow_redirects=False,
    )
    assert respuesta.status_code == 303

    with cliente.app.state.fabrica_sesiones() as sesion:
        cuenta = sesion.scalar(
            select(Usuario).where(
                Usuario.correo == "integrante@veracruzanisima.local"
            )
        )
        assert cuenta is not None
        assert cuenta.activo is True
        assert cuenta.es_admin is False
        assert "temporal-segura-123" not in cuenta.password_hash


def test_usuario_operativo_no_puede_administrar_cuentas(cliente: TestClient):
    with cliente.app.state.fabrica_sesiones() as sesion:
        crear_usuario(
            sesion,
            correo="operativo@veracruzanisima.local",
            nombre="Usuario Operativo",
            contrasena="operativo-segura-123",
        )

    _cerrar_sesion(cliente)
    _iniciar_sesion(
        cliente,
        "operativo@veracruzanisima.local",
        "operativo-segura-123",
    )

    respuesta = cliente.get("/usuarios")
    assert respuesta.status_code == 403


def test_admin_no_puede_desactivar_su_propia_cuenta(cliente: TestClient):
    with cliente.app.state.fabrica_sesiones() as sesion:
        admin = sesion.scalar(select(Usuario).where(Usuario.correo == CORREO_PRUEBA))
        assert admin is not None
        admin_id = admin.id

    pagina = cliente.get("/usuarios")
    respuesta = cliente.post(
        f"/usuarios/{admin_id}/estado",
        data={"csrf_token": _csrf(pagina.text), "activo": "0"},
        follow_redirects=False,
    )
    assert respuesta.status_code == 422

    with cliente.app.state.fabrica_sesiones() as sesion:
        admin = sesion.get(Usuario, admin_id)
        assert admin is not None
        assert admin.activo is True


def test_desactivar_usuario_corta_su_acceso(cliente: TestClient):
    correo = "desactivar@veracruzanisima.local"
    contrasena = "desactivar-segura-123"
    with cliente.app.state.fabrica_sesiones() as sesion:
        cuenta = crear_usuario(
            sesion,
            correo=correo,
            nombre="Cuenta Desactivable",
            contrasena=contrasena,
        )
        cuenta_id = cuenta.id

    with TestClient(cliente.app) as navegador_usuario:
        _iniciar_sesion(navegador_usuario, correo, contrasena)
        assert navegador_usuario.get("/cotizaciones").status_code == 200

        pagina_admin = cliente.get("/usuarios")
        desactivar = cliente.post(
            f"/usuarios/{cuenta_id}/estado",
            data={"csrf_token": _csrf(pagina_admin.text), "activo": "0"},
            follow_redirects=False,
        )
        assert desactivar.status_code == 303

        protegida = navegador_usuario.get("/cotizaciones", follow_redirects=False)
        assert protegida.status_code == 303
        assert protegida.headers["location"] == "/acceso"


def test_cambiar_contrasena_exige_la_actual_y_permanece_utilizable(cliente: TestClient):
    pagina = cliente.get("/mi-cuenta/contrasena")
    incorrecta = cliente.post(
        "/mi-cuenta/contrasena",
        data={
            "csrf_token": _csrf(pagina.text),
            "contrasena_actual": "incorrecta-segura-123",
            "contrasena_nueva": "nueva-contrasena-segura-123",
            "confirmar_contrasena": "nueva-contrasena-segura-123",
        },
    )
    assert incorrecta.status_code == 422
    assert "contraseña actual no es correcta" in incorrecta.text

    pagina = cliente.get("/mi-cuenta/contrasena")
    correcta = cliente.post(
        "/mi-cuenta/contrasena",
        data={
            "csrf_token": _csrf(pagina.text),
            "contrasena_actual": CONTRASENA_PRUEBA,
            "contrasena_nueva": "nueva-contrasena-segura-123",
            "confirmar_contrasena": "nueva-contrasena-segura-123",
        },
    )
    assert correcta.status_code == 200
    assert "Contraseña actualizada" in correcta.text

    _cerrar_sesion(cliente)
    _iniciar_sesion(
        cliente,
        CORREO_PRUEBA,
        "nueva-contrasena-segura-123",
    )


def test_inicio_del_piloto_muestra_guia_y_advertencia(cliente: TestClient):
    respuesta = cliente.get("/cotizaciones")

    assert respuesta.status_code == 200
    assert "Piloto interno" in respuesta.text
    assert "No cargues información sensible real" in respuesta.text
    assert 'href="/usuarios"' in respuesta.text
    assert 'href="/mi-cuenta/contrasena"' in respuesta.text


def test_produccion_requiere_clave_de_sesion_propia():
    with pytest.raises(ValueError, match="APP_SECRET_KEY"):
        Configuracion(
            app_env="production",
            app_secret_key="demasiado-corta",
            database_url="postgresql://usuario:clave@db.example/triage",
        )
