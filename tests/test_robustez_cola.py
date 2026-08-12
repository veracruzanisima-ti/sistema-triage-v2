"""Regresiones para que una caída temporal no duplique ni arruine la cola documental."""

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
        data={"referencia": "COLA-ROBUSTA", "csrf_token": _csrf(formulario.text)},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    return respuesta.headers["location"].rsplit("/", 1)[-1]


def test_interfaz_prepara_reintento_y_pausa_sin_descartar_pendientes(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    formulario = cliente.get(f"/cotizaciones/{cotizacion_id}/documentos/nuevo")

    assert formulario.status_code == 200
    assert 'datos.append("clave_idempotencia", item.claveIdempotencia)' in formulario.text
    assert "new Set([502, 503, 504])" in formulario.text
    assert "Reintentar pendientes" in formulario.text
    assert "Cola pausada" in formulario.text
    assert "archivo-estado-pausado" in formulario.text


def test_reintento_con_misma_clave_reutiliza_documento(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    formulario = cliente.get(f"/cotizaciones/{cotizacion_id}/documentos/nuevo")
    token = _csrf(formulario.text)
    datos = {"csrf_token": token, "clave_idempotencia": "cola-prueba-001"}
    archivo = {"archivo": ("documento-reintento.pdf", b"mismo-pdf", "application/pdf")}

    primero = cliente.post(
        f"/cotizaciones/{cotizacion_id}/documentos/cola",
        data=datos,
        files=archivo,
    )
    segundo = cliente.post(
        f"/cotizaciones/{cotizacion_id}/documentos/cola",
        data=datos,
        files=archivo,
    )

    assert primero.status_code == 200
    assert segundo.status_code == 200
    assert primero.json()["ok"] is True
    assert segundo.json()["ok"] is True
    assert primero.json()["documento_id"] == segundo.json()["documento_id"]

    detalle = cliente.get(f"/cotizaciones/{cotizacion_id}")
    assert detalle.text.count("documento-reintento.pdf") == 1


def test_clave_de_reintento_no_puede_reutilizarse_para_otro_archivo(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    formulario = cliente.get(f"/cotizaciones/{cotizacion_id}/documentos/nuevo")
    token = _csrf(formulario.text)
    datos = {"csrf_token": token, "clave_idempotencia": "cola-prueba-002"}

    primero = cliente.post(
        f"/cotizaciones/{cotizacion_id}/documentos/cola",
        data=datos,
        files={"archivo": ("primero.pdf", b"contenido-uno", "application/pdf")},
    )
    segundo = cliente.post(
        f"/cotizaciones/{cotizacion_id}/documentos/cola",
        data=datos,
        files={"archivo": ("otro.pdf", b"contenido-distinto", "application/pdf")},
    )

    assert primero.status_code == 200
    assert segundo.status_code == 422
    assert segundo.json()["ok"] is False
    assert "identificador de reintento" in segundo.json()["error"]
