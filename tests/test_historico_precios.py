import re

from fastapi.testclient import TestClient
from sqlalchemy import select

from triage.historico.modelos import ObservacionPrecio


def _csrf(html: str) -> str:
    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF")
    return coincidencia.group(1)


def _crear_cotizacion(cliente: TestClient) -> str:
    cliente.app.state.configuracion.codigo_postal_consulta_default = "91000"
    formulario = cliente.get("/cotizaciones/nueva")
    respuesta = cliente.post(
        "/cotizaciones",
        data={"referencia": "HISTORICO-PRUEBA", "csrf_token": _csrf(formulario.text)},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    return respuesta.headers["location"].rsplit("/", 1)[-1]


def _subir_y_revisar(cliente: TestClient, cotizacion_id: str) -> str:
    formulario = cliente.get(f"/cotizaciones/{cotizacion_id}/documentos/nuevo")
    subida = cliente.post(
        f"/cotizaciones/{cotizacion_id}/documentos",
        data={"csrf_token": _csrf(formulario.text)},
        files={"archivo": ("historico.pdf", b"pdf-ficticio", "application/pdf")},
        follow_redirects=False,
    )
    assert subida.status_code == 303
    revision_url = subida.headers["location"]

    revision = cliente.get(revision_url)
    guardado = cliente.post(
        revision_url + "/revision",
        data={
            "csrf_token": _csrf(revision.text),
            "tipo_documento": "Memorándum",
            "memorandum": "DAIS/SSMA/701/2026",
            "partidas_total": "1",
            "partida_0_producto": "LANTUS",
            "partida_0_marca": "Lantus",
            "partida_0_concentracion": "100 U/mL",
            "partida_0_forma": "vial",
            "partida_0_presentacion": "Frasco ámpula 10 mL",
            "partida_0_cantidad": "2",
            "partida_0_unidad": "cajas",
            "partida_0_incluir": "1",
        },
        follow_redirects=False,
    )
    assert guardado.status_code == 303
    return revision_url


def _preparar(cliente: TestClient, cotizacion_id: str) -> str:
    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/normalizacion")
    partida = re.search(r'name="partida_0_id" value="([^"]+)"', pagina.text)
    assert partida is not None
    partida_id = partida.group(1)

    respuesta = cliente.post(
        f"/cotizaciones/{cotizacion_id}/normalizacion",
        data={
            "csrf_token": _csrf(pagina.text),
            "partidas_total": "1",
            "partida_0_id": partida_id,
            "partida_0_producto": "LANTUS",
            "partida_0_marca": "Lantus",
            "partida_0_concentracion": "100 U/mL",
            "partida_0_forma": "vial",
            "partida_0_presentacion": "Frasco ámpula 10 mL",
        },
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    return partida_id


def test_historico_solo_muestra_productos_preparados(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    _subir_y_revisar(cliente, cotizacion_id)

    vacio = cliente.get(f"/cotizaciones/{cotizacion_id}/historico")
    assert vacio.status_code == 200
    assert "Aún no hay productos preparados" in vacio.text

    _preparar(cliente, cotizacion_id)
    listo = cliente.get(f"/cotizaciones/{cotizacion_id}/historico")
    assert listo.status_code == 200
    assert "LANTUS" in listo.text
    assert "Frasco ámpula 10 mL" in listo.text


def test_capturas_de_precio_son_append_only(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    _subir_y_revisar(cliente, cotizacion_id)
    partida_id = _preparar(cliente, cotizacion_id)

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/historico")
    primera = cliente.post(
        f"/cotizaciones/{cotizacion_id}/historico/{partida_id}",
        data={
            "csrf_token": _csrf(pagina.text),
            "proveedor": "Proveedor Uno",
            "fuente": "Portal proveedor uno",
            "precio_antes_iva": "100.00",
            "iva_porcentaje": "16.00",
            "precio_total": "116.00",
            "es_promocion": "1",
            "condiciones_promocion": "Vigencia de prueba",
            "disponibilidad": "12 piezas",
            "entrega_viable": "si",
        },
        follow_redirects=False,
    )
    assert primera.status_code == 303

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/historico")
    segunda = cliente.post(
        f"/cotizaciones/{cotizacion_id}/historico/{partida_id}",
        data={
            "csrf_token": _csrf(pagina.text),
            "proveedor": "Proveedor Dos",
            "fuente": "Cotización manual dos",
            "precio_total": "108.50",
            "disponibilidad": "Disponible",
            "entrega_viable": "",
        },
        follow_redirects=False,
    )
    assert segunda.status_code == 303

    with cliente.app.state.fabrica_sesiones() as sesion:
        observaciones = list(
            sesion.scalars(
                select(ObservacionPrecio).order_by(ObservacionPrecio.creado_en.asc())
            )
        )
        assert len(observaciones) == 2
        assert observaciones[0].proveedor == "Proveedor Uno"
        assert str(observaciones[0].precio_total) == "116.00"
        assert observaciones[0].es_promocion is True
        assert observaciones[0].entrega_viable is True
        assert observaciones[0].codigo_postal == "91000"
        assert observaciones[1].proveedor == "Proveedor Dos"
        assert str(observaciones[1].precio_total) == "108.50"
        assert observaciones[1].codigo_postal == "91000"
        assert observaciones[0].id != observaciones[1].id
        assert observaciones[0].clave_producto == observaciones[1].clave_producto
        assert len(observaciones[0].clave_producto) == 64


def test_historico_rechaza_observacion_sin_precio(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    _subir_y_revisar(cliente, cotizacion_id)
    partida_id = _preparar(cliente, cotizacion_id)

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/historico")
    respuesta = cliente.post(
        f"/cotizaciones/{cotizacion_id}/historico/{partida_id}",
        data={
            "csrf_token": _csrf(pagina.text),
            "proveedor": "Proveedor sin precio",
            "fuente": "Fuente sin precio",
            "precio_antes_iva": "",
            "iva_porcentaje": "",
            "precio_total": "",
            "disponibilidad": "Disponible",
            "entrega_viable": "",
        },
    )
    assert respuesta.status_code == 422
    assert "captura al menos un precio observado" in respuesta.text

    with cliente.app.state.fabrica_sesiones() as sesion:
        assert list(sesion.scalars(select(ObservacionPrecio))) == []


def test_historico_no_infiere_iva_ni_clasificacion_comercial(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    _subir_y_revisar(cliente, cotizacion_id)
    partida_id = _preparar(cliente, cotizacion_id)

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/historico")
    respuesta = cliente.post(
        f"/cotizaciones/{cotizacion_id}/historico/{partida_id}",
        data={
            "csrf_token": _csrf(pagina.text),
            "proveedor": "Proveedor Total",
            "fuente": "Fuente con total únicamente",
            "precio_total": "250.00",
            "entrega_viable": "no",
        },
        follow_redirects=False,
    )
    assert respuesta.status_code == 303

    with cliente.app.state.fabrica_sesiones() as sesion:
        observacion = sesion.scalar(select(ObservacionPrecio))
        assert observacion is not None
        assert observacion.precio_antes_iva is None
        assert observacion.iva_porcentaje is None
        assert str(observacion.precio_total) == "250.00"
        assert observacion.codigo_postal == "91000"
        assert observacion.entrega_viable is False
        assert not hasattr(observacion, "referencia_estable")
        assert not hasattr(observacion, "oportunidad_adquisicion")
