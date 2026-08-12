"""Pruebas de la referencia administrativa derivada de documentos revisados."""

import re

from fastapi.testclient import TestClient

from triage.cotizaciones.servicio import (
    obtener_cotizacion,
    sincronizar_referencia_cotizacion,
)
from triage.documentos.modelos import Documento, EstadoDocumento


def _csrf(html: str) -> str:
    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF")
    return coincidencia.group(1)


def _crear_sin_referencia(cliente: TestClient) -> str:
    formulario = cliente.get("/cotizaciones/nueva")
    respuesta = cliente.post(
        "/cotizaciones",
        data={"referencia": "", "csrf_token": _csrf(formulario.text)},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    return respuesta.headers["location"].rsplit("/", 1)[-1]


def _subir_documento(cliente: TestClient, cotizacion_id: str, nombre: str) -> str:
    formulario = cliente.get(f"/cotizaciones/{cotizacion_id}/documentos/nuevo")
    respuesta = cliente.post(
        f"/cotizaciones/{cotizacion_id}/documentos",
        data={"csrf_token": _csrf(formulario.text)},
        files={"archivo": (nombre, b"archivo-ficticio", "application/pdf")},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    return respuesta.headers["location"]


def _guardar_revision(
    cliente: TestClient,
    revision_url: str,
    memorandum: str,
) -> None:
    revision = cliente.get(revision_url)
    respuesta = cliente.post(
        revision_url + "/revision",
        data={
            "csrf_token": _csrf(revision.text),
            "tipo_documento": "Memorándum",
            "memorandum": memorandum,
            "folios": "FOLIO-001",
            "fecha_documento": "11 de agosto de 2026",
            "municipio": "Xalapa, Veracruz",
            "partidas_total": "2",
            "partida_0_producto": "PRODUCTO DE PRUEBA",
            "partida_0_concentracion": "100 mg",
            "partida_0_presentacion": "Caja con 10 unidades",
            "partida_0_cantidad": "2",
            "partida_0_unidad": "cajas",
            "partida_0_incluir": "1",
        },
        follow_redirects=False,
    )
    assert respuesta.status_code == 303


def test_referencia_se_sincroniza_solo_despues_de_revision_humana(cliente: TestClient):
    cotizacion_id = _crear_sin_referencia(cliente)
    revision_url = _subir_documento(cliente, cotizacion_id, "primero.pdf")

    listado_analizado = cliente.get("/cotizaciones")
    assert "Sin referencia identificada" in listado_analizado.text

    _guardar_revision(cliente, revision_url, "DAIS/SSMA/321/2026")

    listado_revisado = cliente.get("/cotizaciones")
    assert "DAIS/SSMA/321/2026" in listado_revisado.text
    with cliente.app.state.fabrica_sesiones() as sesion:
        cotizacion = obtener_cotizacion(sesion, cotizacion_id)
        assert cotizacion is not None
        assert cotizacion.referencia == "DAIS/SSMA/321/2026"
        assert cotizacion.referencia_fijada_manual is False


def test_referencia_manual_no_se_sobrescribe_por_otra_revision(cliente: TestClient):
    cotizacion_id = _crear_sin_referencia(cliente)
    revision_url = _subir_documento(cliente, cotizacion_id, "primero.pdf")
    _guardar_revision(cliente, revision_url, "DAIS/SSMA/400/2026")

    detalle = cliente.get(f"/cotizaciones/{cotizacion_id}")
    cambio = cliente.post(
        f"/cotizaciones/{cotizacion_id}/referencia",
        data={
            "csrf_token": _csrf(detalle.text),
            "accion": "guardar",
            "referencia": "REFERENCIA MANUAL 2026",
        },
        follow_redirects=False,
    )
    assert cambio.status_code == 303

    _guardar_revision(cliente, revision_url, "DAIS/SSMA/401/2026")

    with cliente.app.state.fabrica_sesiones() as sesion:
        cotizacion = obtener_cotizacion(sesion, cotizacion_id)
        assert cotizacion is not None
        assert cotizacion.referencia == "REFERENCIA MANUAL 2026"
        assert cotizacion.referencia_fijada_manual is True


def test_varias_referencias_revisadas_generan_conflicto_sin_adivinar(cliente: TestClient):
    cotizacion_id = _crear_sin_referencia(cliente)
    with cliente.app.state.fabrica_sesiones() as sesion:
        for indice, referencia in enumerate(
            ("DAIS/SSMA/500/2026", "DAIS/SSMA/501/2026"),
            start=1,
        ):
            sesion.add(
                Documento(
                    cotizacion_id=cotizacion_id,
                    nombre_original=f"documento-{indice}.pdf",
                    mime_type="application/pdf",
                    tamano_bytes=10,
                    sha256=str(indice) * 64,
                    estado=EstadoDocumento.REVISADO.value,
                    memorandum=referencia,
                )
            )
        sesion.commit()
        referencias = sincronizar_referencia_cotizacion(sesion, cotizacion_id)
        cotizacion = obtener_cotizacion(sesion, cotizacion_id)
        assert cotizacion is not None
        assert cotizacion.referencia is None
        assert referencias == ["DAIS/SSMA/500/2026", "DAIS/SSMA/501/2026"]

    detalle = cliente.get(f"/cotizaciones/{cotizacion_id}")
    assert "Se detectaron varias referencias en documentos revisados" in detalle.text
    assert "Usar DAIS/SSMA/500/2026" in detalle.text
    assert "Usar DAIS/SSMA/501/2026" in detalle.text


def test_puede_volver_a_deteccion_automatica(cliente: TestClient):
    cotizacion_id = _crear_sin_referencia(cliente)
    revision_url = _subir_documento(cliente, cotizacion_id, "unico.pdf")
    _guardar_revision(cliente, revision_url, "DAIS/SSMA/600/2026")

    detalle = cliente.get(f"/cotizaciones/{cotizacion_id}")
    cliente.post(
        f"/cotizaciones/{cotizacion_id}/referencia",
        data={
            "csrf_token": _csrf(detalle.text),
            "accion": "guardar",
            "referencia": "TEMPORAL MANUAL",
        },
        follow_redirects=False,
    )

    detalle_manual = cliente.get(f"/cotizaciones/{cotizacion_id}")
    regreso = cliente.post(
        f"/cotizaciones/{cotizacion_id}/referencia",
        data={
            "csrf_token": _csrf(detalle_manual.text),
            "accion": "automatica",
            "referencia": "",
        },
        follow_redirects=False,
    )
    assert regreso.status_code == 303

    with cliente.app.state.fabrica_sesiones() as sesion:
        cotizacion = obtener_cotizacion(sesion, cotizacion_id)
        assert cotizacion is not None
        assert cotizacion.referencia == "DAIS/SSMA/600/2026"
        assert cotizacion.referencia_fijada_manual is False


def test_listado_ofrece_editar_o_anadir_referencia(cliente: TestClient):
    cotizacion_id = _crear_sin_referencia(cliente)
    listado = cliente.get("/cotizaciones")
    assert "Añadir referencia" in listado.text
    assert f'/cotizaciones/{cotizacion_id}#referencia-cotizacion' in listado.text
