import re
from types import SimpleNamespace


def _csrf(html: str) -> str:
    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF")
    return coincidencia.group(1)


def _configurar_catalogo_prueba(cliente) -> None:
    cliente.app.state.lectores_ia = {
        "openai:gpt-5": SimpleNamespace(modelo="gpt-5"),
        "openai:gpt-5.4-mini": SimpleNamespace(modelo="gpt-5.4-mini"),
    }
    cliente.app.state.descubridores_ia = {
        "openai:gpt-5": SimpleNamespace(modelo="gpt-5"),
        "openai:gpt-5.4-mini": SimpleNamespace(modelo="gpt-5.4-mini"),
    }
    cliente.app.state.clave_lector_default = "openai:gpt-5"
    cliente.app.state.clave_web_default = "openai:gpt-5"


def test_selector_muestra_modelos_y_gemini_desactivado_sin_clave(cliente):
    _configurar_catalogo_prueba(cliente)

    pagina = cliente.get("/modelos-ia")

    assert pagina.status_code == 200
    assert "GPT-5" in pagina.text
    assert "GPT-5.4 mini" in pagina.text
    assert "Gemini 3.6 Flash" in pagina.text
    assert "Falta API key" in pagina.text
    assert 'value="gemini:gemini-3.6-flash"' in pagina.text
    assert 'value="gemini:gemini-3.6-flash"' in pagina.text and "disabled" in pagina.text


def test_selector_guarda_lector_y_web_en_la_sesion(cliente):
    _configurar_catalogo_prueba(cliente)
    pagina = cliente.get("/modelos-ia")

    respuesta = cliente.post(
        "/modelos-ia",
        data={
            "csrf_token": _csrf(pagina.text),
            "modelo_lector": "openai:gpt-5.4-mini",
            "modelo_web": "openai:gpt-5.4-mini",
        },
        follow_redirects=False,
    )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/modelos-ia?guardado=1"

    resultado = cliente.get(respuesta.headers["location"])
    assert "Modelos actualizados para esta sesión" in resultado.text
    assert 'value="openai:gpt-5.4-mini" selected' in resultado.text


def test_selector_rechaza_modelo_no_disponible(cliente):
    _configurar_catalogo_prueba(cliente)
    pagina = cliente.get("/modelos-ia")

    respuesta = cliente.post(
        "/modelos-ia",
        data={
            "csrf_token": _csrf(pagina.text),
            "modelo_lector": "gemini:gemini-3.6-flash",
            "modelo_web": "openai:gpt-5",
        },
    )

    assert respuesta.status_code == 422
    assert "no está disponible" in respuesta.text
