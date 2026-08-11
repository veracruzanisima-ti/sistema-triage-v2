def test_healthcheck_responde_ok(cliente):
    respuesta = cliente.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}


def test_inicio_lleva_al_listado_de_cotizaciones(cliente):
    respuesta = cliente.get("/", follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/cotizaciones"


def test_listado_inicial_es_simple_y_comprensible(cliente):
    respuesta = cliente.get("/cotizaciones")

    assert respuesta.status_code == 200
    assert "text/html" in respuesta.headers["content-type"]
    assert "Cotizaciones" in respuesta.text
    assert "Nueva cotización" in respuesta.text
    assert "Todavía no hay cotizaciones" in respuesta.text
