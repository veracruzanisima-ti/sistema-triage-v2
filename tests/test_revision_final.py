"""Pruebas de la revisión consolidada previa al cierre."""

import re

from fastapi.testclient import TestClient


def _csrf(html: str) -> str:
    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF")
    return coincidencia.group(1)


def test_revision_final_identifica_referencia_pendiente(cliente: TestClient):
    nueva = cliente.get("/cotizaciones/nueva")
    creada = cliente.post(
        "/cotizaciones",
        data={"referencia": "REVISION-FINAL", "csrf_token": _csrf(nueva.text)},
        follow_redirects=False,
    )
    cotizacion_id = creada.headers["location"].rsplit("/", 1)[-1]

    carga = cliente.get(f"/cotizaciones/{cotizacion_id}/documentos/nuevo")
    subida = cliente.post(
        f"/cotizaciones/{cotizacion_id}/documentos",
        data={"csrf_token": _csrf(carga.text)},
        files={"archivo": ("revision.pdf", b"pdf-ficticio", "application/pdf")},
        follow_redirects=False,
    )
    revision_url = subida.headers["location"]
    revision = cliente.get(revision_url)
    guardado = cliente.post(
        revision_url + "/revision",
        data={
            "csrf_token": _csrf(revision.text),
            "tipo_documento": "Memorándum",
            "memorandum": "MEMO/REVISION/001/2026",
            "partidas_total": "1",
            "partida_0_producto": "PRODUCTO DE PRUEBA",
            "partida_0_marca": "MARCA DE PRUEBA",
            "partida_0_concentracion": "100 mg",
            "partida_0_forma": "tabletas",
            "partida_0_presentacion": "Caja con 10 unidades",
            "partida_0_cantidad": "2",
            "partida_0_unidad": "cajas",
            "partida_0_incluir": "1",
        },
        follow_redirects=False,
    )
    assert guardado.status_code == 303

    preparacion = cliente.get(f"/cotizaciones/{cotizacion_id}/normalizacion")
    partida = re.search(r'name="partida_0_id" value="([^"]+)"', preparacion.text)
    assert partida is not None
    preparada = cliente.post(
        f"/cotizaciones/{cotizacion_id}/normalizacion",
        data={
            "csrf_token": _csrf(preparacion.text),
            "partidas_total": "1",
            "partida_0_id": partida.group(1),
            "partida_0_producto": "PRODUCTO DE PRUEBA",
            "partida_0_marca": "MARCA DE PRUEBA",
            "partida_0_concentracion": "100 mg",
            "partida_0_forma": "tabletas",
            "partida_0_presentacion": "Caja con 10 unidades",
        },
        follow_redirects=False,
    )
    assert preparada.status_code == 303

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/revision-final")
    assert pagina.status_code == 200
    assert "Revisión consolidada" in pagina.text
    assert "Falta referencia estable" in pagina.text
    assert "PRODUCTO DE PRUEBA" in pagina.text
