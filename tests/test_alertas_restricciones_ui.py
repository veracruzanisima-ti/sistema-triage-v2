"""Prueba integrada de alertas provisionales dentro de la revisión humana."""

import re

from fastapi.testclient import TestClient


def _csrf(html: str) -> str:
    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF")
    return coincidencia.group(1)


def _crear_cotizacion(cliente: TestClient) -> str:
    formulario = cliente.get("/cotizaciones/nueva")
    respuesta = cliente.post(
        "/cotizaciones",
        data={"referencia": "RESTRICCIONES-PRUEBA", "csrf_token": _csrf(formulario.text)},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    return respuesta.headers["location"].rsplit("/", 1)[-1]


def test_partida_restringida_se_marca_pero_puede_guardarse(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    formulario = cliente.get(f"/cotizaciones/{cotizacion_id}/documentos/nuevo")
    subida = cliente.post(
        f"/cotizaciones/{cotizacion_id}/documentos",
        data={"csrf_token": _csrf(formulario.text)},
        files={"archivo": ("solicitud-prueba.pdf", b"pdf-ficticio", "application/pdf")},
        follow_redirects=False,
    )
    revision_url = subida.headers["location"]
    revision = cliente.get(revision_url)

    guardado = cliente.post(
        revision_url + "/revision",
        data={
            "csrf_token": _csrf(revision.text),
            "partidas_total": "2",
            "partida_0_producto": "MIDAZOLAM",
            "partida_0_concentracion": "5 mg/ml",
            "partida_0_forma": "solución inyectable",
            "partida_0_presentacion": "Caja con 5 ampolletas",
            "partida_0_cantidad": "2",
            "partida_0_unidad": "cajas",
        },
        follow_redirects=False,
    )

    assert guardado.status_code == 303
    comprobacion = cliente.get(guardado.headers["location"])
    assert comprobacion.status_code == 200
    assert "Posible rechazo - requiere revisión" in comprobacion.text
    assert "Midazolam (en todas sus presentaciones)." in comprobacion.text
    assert "POL-COM-001" in comprobacion.text
    assert "Pendiente de validación del Responsable Sanitario" in comprobacion.text
    assert "La partida permanece disponible" in comprobacion.text
