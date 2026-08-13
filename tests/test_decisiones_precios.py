import re

from fastapi.testclient import TestClient

from triage.historico.decisiones_modelos import RolDecisionPrecio


def _csrf(html: str) -> str:
    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF")
    return coincidencia.group(1)


def test_roles_de_decision_son_explicitos():
    assert RolDecisionPrecio.REFERENCIA_ESTABLE.value == "REFERENCIA_ESTABLE"
    assert RolDecisionPrecio.OPORTUNIDAD_ADQUISICION.value == "OPORTUNIDAD_ADQUISICION"


def test_pantalla_de_decisiones_se_integra_al_flujo(cliente: TestClient):
    nueva = cliente.get("/cotizaciones/nueva")
    creada = cliente.post(
        "/cotizaciones",
        data={"referencia": "DECISION-PRUEBA", "csrf_token": _csrf(nueva.text)},
        follow_redirects=False,
    )
    cotizacion_id = creada.headers["location"].rsplit("/", 1)[-1]

    detalle = cliente.get(f"/cotizaciones/{cotizacion_id}")
    assert "Decidir referencias" not in detalle.text

    decisiones = cliente.get(f"/cotizaciones/{cotizacion_id}/decisiones-precio")
    assert decisiones.status_code == 200
    assert "Decisiones de precio" in decisiones.text
