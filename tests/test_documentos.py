"""Pruebas del flujo subir -> leer -> revisar -> guardar."""

import re

from fastapi.testclient import TestClient


def _extraer_csrf(html: str) -> str:
    """Obtiene el token CSRF de un formulario renderizado para estas pruebas."""

    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF en el formulario")
    return coincidencia.group(1)


def _crear_cotizacion(cliente: TestClient) -> str:
    formulario = cliente.get("/cotizaciones/nueva")
    respuesta = cliente.post(
        "/cotizaciones",
        data={
            "referencia": "COTIZACION-DE-PRUEBA",
            "csrf_token": _extraer_csrf(formulario.text),
        },
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    return respuesta.headers["location"].rsplit("/", 1)[-1]


def test_subir_documento_muestra_lectura_estructurada(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    formulario = cliente.get(f"/cotizaciones/{cotizacion_id}/documentos/nuevo")

    respuesta = cliente.post(
        f"/cotizaciones/{cotizacion_id}/documentos",
        data={"csrf_token": _extraer_csrf(formulario.text)},
        files={"archivo": ("solicitud-prueba.jpg", b"imagen-ficticia", "image/jpeg")},
        follow_redirects=False,
    )

    assert respuesta.status_code == 303
    revision = cliente.get(respuesta.headers["location"])
    assert revision.status_code == 200
    assert "MEMO/PRUEBA/001/2026" in revision.text
    assert "PRODUCTO DE PRUEBA" in revision.text
    assert "Caja con 10 unidades" in revision.text
    assert "Ver por qué el lector lo sugirió" in revision.text


def test_revision_humana_corrige_y_persiste_partidas(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    formulario = cliente.get(f"/cotizaciones/{cotizacion_id}/documentos/nuevo")
    subida = cliente.post(
        f"/cotizaciones/{cotizacion_id}/documentos",
        data={"csrf_token": _extraer_csrf(formulario.text)},
        files={"archivo": ("solicitud-prueba.pdf", b"pdf-ficticio", "application/pdf")},
        follow_redirects=False,
    )
    revision_url = subida.headers["location"]
    revision = cliente.get(revision_url)

    guardado = cliente.post(
        revision_url + "/revision",
        data={
            "csrf_token": _extraer_csrf(revision.text),
            "partidas_total": "3",
            "tipo_documento": "Memorándum corregido",
            "memorandum": "MEMO/CORREGIDO/002/2026",
            "folios": "F-10, F-11",
            "fecha_documento": "12 de agosto de 2026",
            "municipio": "Xalapa",
            "partida_0_producto": "PRODUCTO CORREGIDO",
            "partida_0_marca": "MARCA VISIBLE",
            "partida_0_concentracion": "200 mg",
            "partida_0_forma": "tabletas",
            "partida_0_presentacion": "Caja con 20 tabletas",
            "partida_0_cantidad": "4",
            "partida_0_unidad": "cajas",
            "partida_1_producto": "SEGUNDA PARTIDA AGREGADA",
            "partida_1_cantidad": "1",
            "partida_1_unidad": "pieza",
        },
        follow_redirects=False,
    )

    assert guardado.status_code == 303
    comprobacion = cliente.get(guardado.headers["location"])
    assert "Revisión guardada" in comprobacion.text
    assert "MEMO/CORREGIDO/002/2026" in comprobacion.text
    assert "PRODUCTO CORREGIDO" in comprobacion.text
    assert "SEGUNDA PARTIDA AGREGADA" in comprobacion.text
    atributos_checkbox = comprobacion.text.split('name="parece_fragmento"', 1)[1].split(">", 1)[0]
    assert "checked" not in atributos_checkbox


def test_archivo_no_permitido_se_rechaza_sin_crear_lectura(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    formulario = cliente.get(f"/cotizaciones/{cotizacion_id}/documentos/nuevo")

    respuesta = cliente.post(
        f"/cotizaciones/{cotizacion_id}/documentos",
        data={"csrf_token": _extraer_csrf(formulario.text)},
        files={"archivo": ("notas.txt", b"contenido", "text/plain")},
    )

    assert respuesta.status_code == 422
    assert "Sólo se admiten PDF, JPG, PNG o WEBP" in respuesta.text


def test_documento_aparece_en_detalle_de_cotizacion(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    formulario = cliente.get(f"/cotizaciones/{cotizacion_id}/documentos/nuevo")
    cliente.post(
        f"/cotizaciones/{cotizacion_id}/documentos",
        data={"csrf_token": _extraer_csrf(formulario.text)},
        files={"archivo": ("solicitud-prueba.jpg", b"imagen-ficticia", "image/jpeg")},
    )

    detalle = cliente.get(f"/cotizaciones/{cotizacion_id}")
    assert detalle.status_code == 200
    assert "MEMO/PRUEBA/001/2026" in detalle.text
    assert "Revisar" in detalle.text
