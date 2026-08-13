"""Pruebas de la copia operativa usada para búsquedas sin alterar la solicitud."""

import re

from fastapi.testclient import TestClient
from sqlalchemy import select

from triage.documentos.modelos import PartidaDocumento
from triage.normalizacion.modelos import NormalizacionPartida


def _csrf(html: str) -> str:
    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF")
    return coincidencia.group(1)


def _crear_cotizacion(cliente: TestClient) -> str:
    formulario = cliente.get("/cotizaciones/nueva")
    respuesta = cliente.post(
        "/cotizaciones",
        data={"referencia": "NORMALIZACION-PRUEBA", "csrf_token": _csrf(formulario.text)},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    return respuesta.headers["location"].rsplit("/", 1)[-1]


def _subir(cliente: TestClient, cotizacion_id: str) -> str:
    formulario = cliente.get(f"/cotizaciones/{cotizacion_id}/documentos/nuevo")
    respuesta = cliente.post(
        f"/cotizaciones/{cotizacion_id}/documentos",
        data={"csrf_token": _csrf(formulario.text)},
        files={"archivo": ("producto.pdf", b"pdf-ficticio", "application/pdf")},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    return respuesta.headers["location"]


def _revisar(
    cliente: TestClient,
    revision_url: str,
    *,
    incluida: bool = True,
) -> None:
    revision = cliente.get(revision_url)
    respuesta = cliente.post(
        revision_url + "/revision",
        data={
            "csrf_token": _csrf(revision.text),
            "tipo_documento": "Memorándum",
            "memorandum": "DAIS/SSMA/700/2026",
            "partidas_total": "2",
            "partida_0_producto": "LANTUS",
            "partida_0_marca": "Lantus",
            "partida_0_concentracion": "100 U / ml",
            "partida_0_forma": "vial",
            "partida_0_presentacion": "Frasco ámpula 10 ml",
            "partida_0_cantidad": "2",
            "partida_0_unidad": "cajas",
            "partida_0_incluir": "1" if incluida else "0",
            "partida_0_motivo_exclusion": "Prueba" if not incluida else "",
        },
        follow_redirects=False,
    )
    assert respuesta.status_code == 303


def test_solo_documentos_revisados_habilitan_preparacion(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    _subir(cliente, cotizacion_id)

    detalle = cliente.get(f"/cotizaciones/{cotizacion_id}")
    assert "Primero revisa un documento" in detalle.text
    assert f'/cotizaciones/{cotizacion_id}/normalizacion' not in detalle.text


def test_partidas_excluidas_no_entran_a_preparacion(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    revision_url = _subir(cliente, cotizacion_id)
    _revisar(cliente, revision_url, incluida=False)

    normalizacion = cliente.get(f"/cotizaciones/{cotizacion_id}/normalizacion")
    assert normalizacion.status_code == 200
    assert "Aún no hay partidas listas para preparar" in normalizacion.text


def test_guardar_preparacion_no_modifica_solicitud_revisada(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    revision_url = _subir(cliente, cotizacion_id)
    documento_id = revision_url.rsplit("/", 1)[-1]
    _revisar(cliente, revision_url)

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/normalizacion")
    assert pagina.status_code == 200
    assert "0 de 1 partidas" in cliente.get(f"/cotizaciones/{cotizacion_id}").text
    assert "LANTUS" in pagina.text
    assert "vial" in pagina.text
    partida_id = re.search(r'name="partida_0_id" value="([^"]+)"', pagina.text)
    assert partida_id is not None

    respuesta = cliente.post(
        f"/cotizaciones/{cotizacion_id}/normalizacion",
        data={
            "csrf_token": _csrf(pagina.text),
            "partidas_total": "1",
            "partida_0_id": partida_id.group(1),
            "partida_0_producto": "  LANTUS  ",
            "partida_0_marca": "Lantus",
            "partida_0_concentracion": "100 U / ml",
            "partida_0_forma": "vial",
            "partida_0_presentacion": "Frasco ámpula 10 ml",
        },
        follow_redirects=False,
    )
    assert respuesta.status_code == 303

    with cliente.app.state.fabrica_sesiones() as sesion:
        normalizada = sesion.get(NormalizacionPartida, partida_id.group(1))
        assert normalizada is not None
        assert normalizada.producto == "LANTUS"
        assert normalizada.forma_dispositivo == "vial"
        assert normalizada.presentacion == "Frasco ámpula 10 mL"

        original = sesion.scalar(
            select(PartidaDocumento).where(
                PartidaDocumento.documento_id == documento_id
            )
        )
        assert original is not None
        assert original.presentacion_solicitada == "Frasco ámpula 10 ml"
        assert original.forma_farmaceutica_dispositivo == "vial"

    comprobacion = cliente.get(f"/cotizaciones/{cotizacion_id}")
    assert "1 de 1 partidas" in comprobacion.text


def test_normalizacion_no_infiere_dispositivo_ni_marca(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    revision_url = _subir(cliente, cotizacion_id)
    _revisar(cliente, revision_url)

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/normalizacion")
    assert 'value="vial"' in pagina.text
    assert "SoloStar" not in pagina.text
