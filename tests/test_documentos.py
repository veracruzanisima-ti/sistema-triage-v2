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


def test_formulario_ofrece_cola_arrastrar_y_quitar(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    formulario = cliente.get(f"/cotizaciones/{cotizacion_id}/documentos/nuevo")

    assert formulario.status_code == 200
    assert "Arrastra aquí tus fotos o PDF" in formulario.text
    assert "Seleccionar archivos" in formulario.text
    assert 'id="cola-archivos"' in formulario.text
    assert "archivo.multiple = true" in formulario.text
    assert 'className = "archivo-quitar"' in formulario.text
    assert "Leyendo documento" in formulario.text
    assert 'id="leer-documento"' in formulario.text
    assert "disabled" in formulario.text


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


def test_cola_procesa_documentos_secuencialmente(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    formulario = cliente.get(f"/cotizaciones/{cotizacion_id}/documentos/nuevo")
    token = _extraer_csrf(formulario.text)

    primero = cliente.post(
        f"/cotizaciones/{cotizacion_id}/documentos/cola",
        data={"csrf_token": token},
        files={"archivo": ("primero.pdf", b"pdf-uno", "application/pdf")},
    )
    segundo = cliente.post(
        f"/cotizaciones/{cotizacion_id}/documentos/cola",
        data={"csrf_token": token},
        files={"archivo": ("segundo.jpg", b"imagen-dos", "image/jpeg")},
    )

    assert primero.status_code == 200
    assert segundo.status_code == 200
    assert primero.json()["ok"] is True
    assert segundo.json()["ok"] is True
    assert primero.json()["revision_url"] != segundo.json()["revision_url"]
    assert cliente.get(primero.json()["revision_url"]).status_code == 200
    assert cliente.get(segundo.json()["revision_url"]).status_code == 200


def test_revision_ofrece_una_partida_extra_y_agregado_dinamico(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    formulario = cliente.get(f"/cotizaciones/{cotizacion_id}/documentos/nuevo")
    subida = cliente.post(
        f"/cotizaciones/{cotizacion_id}/documentos",
        data={"csrf_token": _extraer_csrf(formulario.text)},
        files={"archivo": ("solicitud-prueba.pdf", b"pdf-ficticio", "application/pdf")},
        follow_redirects=False,
    )
    revision = cliente.get(subida.headers["location"])

    assert 'id="partidas-total"' in revision.text
    assert 'name="partidas_total" value="2"' in revision.text
    assert 'id="agregar-partida"' in revision.text
    assert "+ Agregar otra partida" in revision.text
    assert 'id="plantilla-partida"' in revision.text
    assert "beforeunload" in revision.text
    assert 'type="number" min="0" step="1" inputmode="numeric" value="2"' in revision.text
    assert 'value="2.000"' not in revision.text


def test_revision_rechaza_cantidad_fraccionaria(cliente: TestClient):
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

    respuesta = cliente.post(
        revision_url + "/revision",
        data={
            "csrf_token": _extraer_csrf(revision.text),
            "partidas_total": "2",
            "partida_0_producto": "PRODUCTO DE PRUEBA",
            "partida_0_cantidad": "2.5",
            "partida_0_unidad": "cajas",
        },
    )

    assert respuesta.status_code == 422
    assert "La cantidad debe ser un número entero" in respuesta.text


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
    assert 'value="4"' in comprobacion.text
    assert 'value="4.000"' not in comprobacion.text
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


def test_cola_rechaza_archivo_no_permitido_como_json(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    formulario = cliente.get(f"/cotizaciones/{cotizacion_id}/documentos/nuevo")

    respuesta = cliente.post(
        f"/cotizaciones/{cotizacion_id}/documentos/cola",
        data={"csrf_token": _extraer_csrf(formulario.text)},
        files={"archivo": ("notas.txt", b"contenido", "text/plain")},
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["ok"] is False
    assert "Sólo se admiten PDF, JPG, PNG o WEBP" in respuesta.json()["error"]


def test_documento_aparece_en_detalle_con_estados_coloreados(cliente: TestClient):
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
    assert "Eliminar" in detalle.text
    assert "estado-en-proceso" in detalle.text
    assert "estado-analizado" in detalle.text


def test_eliminar_documento_borra_registro_y_extraccion(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    formulario = cliente.get(f"/cotizaciones/{cotizacion_id}/documentos/nuevo")
    subida = cliente.post(
        f"/cotizaciones/{cotizacion_id}/documentos",
        data={"csrf_token": _extraer_csrf(formulario.text)},
        files={"archivo": ("archivo-personal-por-error.jpg", b"imagen-ficticia", "image/jpeg")},
        follow_redirects=False,
    )
    revision_url = subida.headers["location"]
    documento_id = revision_url.rsplit("/", 1)[-1]
    detalle = cliente.get(f"/cotizaciones/{cotizacion_id}")

    eliminado = cliente.post(
        f"/cotizaciones/{cotizacion_id}/documentos/{documento_id}/eliminar",
        data={"csrf_token": _extraer_csrf(detalle.text)},
        follow_redirects=False,
    )

    assert eliminado.status_code == 303
    assert cliente.get(revision_url).status_code == 404
    detalle_final = cliente.get(f"/cotizaciones/{cotizacion_id}")
    assert "MEMO/PRUEBA/001/2026" not in detalle_final.text
    assert "archivo-personal-por-error.jpg" not in detalle_final.text
