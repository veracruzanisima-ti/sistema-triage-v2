"""Regresión end-to-end del recorrido mínimo que probará el equipo interno."""

import re

from fastapi.testclient import TestClient


def _csrf(html: str) -> str:
    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF")
    return coincidencia.group(1)


def _crear_cotizacion(cliente: TestClient) -> str:
    nueva = cliente.get("/cotizaciones/nueva")
    creada = cliente.post(
        "/cotizaciones",
        data={"referencia": "", "csrf_token": _csrf(nueva.text)},
        follow_redirects=False,
    )
    assert creada.status_code == 303
    return creada.headers["location"].rsplit("/", 1)[-1]


def _subir_y_revisar(cliente: TestClient, cotizacion_id: str) -> None:
    carga = cliente.get(f"/cotizaciones/{cotizacion_id}/documentos/nuevo")
    subida = cliente.post(
        f"/cotizaciones/{cotizacion_id}/documentos",
        data={"csrf_token": _csrf(carga.text)},
        files={"archivo": ("piloto.pdf", b"pdf-ficticio", "application/pdf")},
        follow_redirects=False,
    )
    assert subida.status_code == 303
    revision_url = subida.headers["location"]
    revision = cliente.get(revision_url)
    guardado = cliente.post(
        revision_url + "/revision",
        data={
            "csrf_token": _csrf(revision.text),
            "tipo_documento": "Memorándum de prueba",
            "memorandum": "MEMO/PRUEBA/001/2026",
            "folios": "FOLIO-001",
            "fecha_documento": "13 de agosto de 2026",
            "municipio": "Municipio de prueba",
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


def _preparar_producto(cliente: TestClient, cotizacion_id: str) -> str:
    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/normalizacion")
    partida = re.search(r'name="partida_0_id" value="([^"]+)"', pagina.text)
    assert partida is not None
    partida_id = partida.group(1)
    guardado = cliente.post(
        f"/cotizaciones/{cotizacion_id}/normalizacion",
        data={
            "csrf_token": _csrf(pagina.text),
            "partidas_total": "1",
            "partida_0_id": partida_id,
            "partida_0_producto": "PRODUCTO DE PRUEBA",
            "partida_0_marca": "MARCA DE PRUEBA",
            "partida_0_concentracion": "100 mg",
            "partida_0_forma": "tabletas",
            "partida_0_presentacion": "Caja con 10 unidades",
        },
        follow_redirects=False,
    )
    assert guardado.status_code == 303
    return partida_id


def _agregar_precio(cliente: TestClient, cotizacion_id: str, partida_id: str) -> None:
    historico = cliente.get(f"/cotizaciones/{cotizacion_id}/historico")
    respuesta = cliente.post(
        f"/cotizaciones/{cotizacion_id}/historico/{partida_id}",
        data={
            "csrf_token": _csrf(historico.text),
            "proveedor": "Proveedor de prueba",
            "fuente": "Fuente ficticia de prueba",
            "precio_antes_iva": "100.00",
            "iva_porcentaje": "",
            "precio_total": "",
            "condiciones_promocion": "",
            "disponibilidad": "Disponible para prueba",
            "entrega_viable": "",
        },
        follow_redirects=False,
    )
    assert respuesta.status_code == 303


def test_flujo_minimo_del_piloto_permanece_conectado(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    _subir_y_revisar(cliente, cotizacion_id)

    detalle = cliente.get(f"/cotizaciones/{cotizacion_id}")
    assert "MEMO/PRUEBA/001/2026" in detalle.text

    partida_id = _preparar_producto(cliente, cotizacion_id)
    _agregar_precio(cliente, cotizacion_id, partida_id)

    proveedores = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    assert proveedores.status_code == 200
    assert "Aún no hay proveedores automáticos configurados" in proveedores.text
    assert "Usar para cotizar" in proveedores.text

    observacion = re.search(r'name="observacion_id" value="([^"]+)"', proveedores.text)
    assert observacion is not None
    elegida = cliente.post(
        f"/cotizaciones/{cotizacion_id}/decisiones-precio/{partida_id}",
        data={
            "csrf_token": _csrf(proveedores.text),
            "rol": "REFERENCIA_ESTABLE",
            "observacion_id": observacion.group(1),
            "volver": "proveedores",
        },
        follow_redirects=False,
    )
    assert elegida.status_code == 303
    assert elegida.headers["location"] == f"/cotizaciones/{cotizacion_id}/proveedores"

    precios_confirmados = cliente.get(elegida.headers["location"])
    assert "Usado para cotizar" in precios_confirmados.text
    assert "Revisar cotización" in precios_confirmados.text

    detalle = cliente.get(f"/cotizaciones/{cotizacion_id}")
    assert "Siguiente paso: Revisa cotización" in detalle.text
