"""Pruebas de la decisión humana de excluir o reintegrar una partida."""

import re

from fastapi.testclient import TestClient
from sqlalchemy import select

from triage.documentos.modelos import PartidaDocumento


def _csrf(html: str) -> str:
    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF")
    return coincidencia.group(1)


def _crear_cotizacion(cliente: TestClient) -> str:
    formulario = cliente.get("/cotizaciones/nueva")
    respuesta = cliente.post(
        "/cotizaciones",
        data={"referencia": "EXCLUSION-PRUEBA", "csrf_token": _csrf(formulario.text)},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    return respuesta.headers["location"].rsplit("/", 1)[-1]


def _datos_midazolam(token: str, *, incluida: bool, motivo: str = "") -> dict[str, str]:
    return {
        "csrf_token": token,
        "partidas_total": "2",
        "partida_0_producto": "MIDAZOLAM",
        "partida_0_concentracion": "5 mg/ml",
        "partida_0_forma": "solución inyectable",
        "partida_0_presentacion": "Caja con 5 ampolletas",
        "partida_0_cantidad": "2",
        "partida_0_unidad": "cajas",
        "partida_0_incluir": "1" if incluida else "0",
        "partida_0_motivo_exclusion": motivo,
    }


def _partida_persistida(cliente: TestClient, documento_id: str) -> PartidaDocumento:
    with cliente.app.state.fabrica_sesiones() as sesion:
        partida = sesion.scalar(
            select(PartidaDocumento).where(PartidaDocumento.documento_id == documento_id)
        )
        assert partida is not None
        sesion.expunge(partida)
        return partida


def test_partida_restringida_puede_excluirse_y_reintegrarse(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    formulario = cliente.get(f"/cotizaciones/{cotizacion_id}/documentos/nuevo")
    subida = cliente.post(
        f"/cotizaciones/{cotizacion_id}/documentos",
        data={"csrf_token": _csrf(formulario.text)},
        files={"archivo": ("restriccion.pdf", b"pdf-ficticio", "application/pdf")},
        follow_redirects=False,
    )
    revision_url = subida.headers["location"]
    documento_id = revision_url.rsplit("/", 1)[-1]
    revision = cliente.get(revision_url)

    preparado = cliente.post(
        revision_url + "/revision",
        data=_datos_midazolam(_csrf(revision.text), incluida=True),
        follow_redirects=False,
    )
    assert preparado.status_code == 303

    alerta = cliente.get(preparado.headers["location"])
    assert "Posible rechazo - requiere revisión" in alerta.text
    assert "Excluir de cotización" in alerta.text
    assert "Ver detalle de la regla" in alerta.text

    motivo = "POL-COM-001 · R16 · Midazolam (en todas sus presentaciones)."
    excluido = cliente.post(
        revision_url + "/revision",
        data=_datos_midazolam(_csrf(alerta.text), incluida=False, motivo=motivo),
        follow_redirects=False,
    )
    assert excluido.status_code == 303

    partida = _partida_persistida(cliente, documento_id)
    assert partida.incluida_cotizacion is False
    assert partida.motivo_exclusion == motivo

    comprobacion = cliente.get(excluido.headers["location"])
    assert "1 partida excluida de la cotización" in comprobacion.text
    assert "Reintegrar" in comprobacion.text
    assert 'name="partida_0_incluir" value="0"' in comprobacion.text

    reintegrado = cliente.post(
        revision_url + "/revision",
        data=_datos_midazolam(_csrf(comprobacion.text), incluida=True),
        follow_redirects=False,
    )
    assert reintegrado.status_code == 303

    partida_reintegrada = _partida_persistida(cliente, documento_id)
    assert partida_reintegrada.incluida_cotizacion is True
    assert partida_reintegrada.motivo_exclusion is None

    comprobacion_final = cliente.get(reintegrado.headers["location"])
    assert 'name="partida_0_incluir" value="1"' in comprobacion_final.text
    assert "1 partida requiere revisión por posible restricción" in comprobacion_final.text
