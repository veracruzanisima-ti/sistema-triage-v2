from fastapi.testclient import TestClient

from triage.main import app

cliente = TestClient(app)


def test_healthcheck_responde_ok():
    respuesta = cliente.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}


def test_inicio_es_html_y_explica_estado_fundacional():
    respuesta = cliente.get("/")

    assert respuesta.status_code == 200
    assert "text/html" in respuesta.headers["content-type"]
    assert "Sistema Triage" in respuesta.text
    assert "Aún no procesa documentos reales" in respuesta.text
