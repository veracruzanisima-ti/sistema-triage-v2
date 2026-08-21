"""Pruebas de conservación y revisión humana contra el documento original."""

import re
from hashlib import sha256

from fastapi.testclient import TestClient

from triage.cotizaciones.modelos import Cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento
from triage.lectores.esquemas import LecturaDocumento


class LectorVacio:
    """Simula una lectura válida en transporte pero sin datos extraídos."""

    modelo = "lector-vacio-original"

    def leer(self, *, contenido: bytes, mime_type: str, nombre_archivo: str) -> LecturaDocumento:
        assert contenido
        assert mime_type
        assert nombre_archivo
        return LecturaDocumento()


def _csrf(html: str) -> str:
    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF")
    return coincidencia.group(1)


def _crear_cotizacion(cliente: TestClient, referencia: str = "ORIGINAL-PRUEBA") -> str:
    formulario = cliente.get("/cotizaciones/nueva")
    respuesta = cliente.post(
        "/cotizaciones",
        data={"referencia": referencia, "csrf_token": _csrf(formulario.text)},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    return respuesta.headers["location"].rsplit("/", 1)[-1]


def _subir(
    cliente: TestClient,
    cotizacion_id: str,
    *,
    nombre: str,
    contenido: bytes,
    mime_type: str,
):
    formulario = cliente.get(f"/cotizaciones/{cotizacion_id}/documentos/nuevo")
    respuesta = cliente.post(
        f"/cotizaciones/{cotizacion_id}/documentos",
        data={"csrf_token": _csrf(formulario.text)},
        files={"archivo": (nombre, contenido, mime_type)},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    return respuesta


def test_revision_muestra_y_sirve_imagen_original(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    contenido = b"imagen-original-exacta"
    subida = _subir(
        cliente,
        cotizacion_id,
        nombre="evidencia solicitud.jpg",
        contenido=contenido,
        mime_type="image/jpeg",
    )
    revision_url = subida.headers["location"]
    documento_id = revision_url.rsplit("/", 1)[-1]

    revision = cliente.get(revision_url)
    original = cliente.get(
        f"/cotizaciones/{cotizacion_id}/documentos/{documento_id}/original"
    )

    assert revision.status_code == 200
    assert "Abrir original" in revision.text
    assert "Ver documento original para comparar" in revision.text
    assert "visor-original-imagen" in revision.text
    assert original.status_code == 200
    assert original.content == contenido
    assert original.headers["content-type"].startswith("image/jpeg")
    assert original.headers["cache-control"] == "private, no-store"
    assert original.headers["x-content-type-options"] == "nosniff"
    assert "inline" in original.headers["content-disposition"]


def test_error_del_lector_conserva_original_y_permite_captura_manual(cliente: TestClient):
    cliente.app.state.lector_documentos = LectorVacio()
    cotizacion_id = _crear_cotizacion(cliente)
    contenido = b"pdf-original-aunque-falle-lector"
    subida = _subir(
        cliente,
        cotizacion_id,
        nombre="no-leido.pdf",
        contenido=contenido,
        mime_type="application/pdf",
    )
    revision_url = subida.headers["location"]
    documento_id = revision_url.rsplit("/", 1)[-1]
    revision = cliente.get(revision_url)

    assert "El lector no pudo completar la lectura" in revision.text
    assert "Puedes capturar manualmente" in revision.text
    assert "Captura manual" in revision.text
    assert 'id="formulario-revision"' in revision.text
    assert "visor-original-pdf" in revision.text

    guardado = cliente.post(
        revision_url + "/revision",
        data={
            "csrf_token": _csrf(revision.text),
            "partidas_total": "1",
            "tipo_documento": "Solicitud manual",
            "memorandum": "MEMO/MANUAL/001",
            "folios": "F-001",
            "municipio": "Xalapa",
            "partida_0_producto": "PRODUCTO CAPTURADO MANUALMENTE",
            "partida_0_cantidad": "3",
            "partida_0_unidad": "cajas",
        },
        follow_redirects=False,
    )

    assert guardado.status_code == 303
    comprobacion = cliente.get(guardado.headers["location"])
    assert "Revisión guardada" in comprobacion.text
    assert "MEMO/MANUAL/001" in comprobacion.text
    assert "PRODUCTO CAPTURADO MANUALMENTE" in comprobacion.text

    original = cliente.get(
        f"/cotizaciones/{cotizacion_id}/documentos/{documento_id}/original"
    )
    assert original.content == contenido


def test_documento_anterior_sin_original_muestra_aviso_sin_romper_revision(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente)
    with cliente.app.state.fabrica_sesiones() as sesion:
        documento = Documento(
            cotizacion_id=cotizacion_id,
            nombre_original="historico-sin-original.pdf",
            mime_type="application/pdf",
            tamano_bytes=123,
            sha256=sha256(b"archivo-no-conservado").hexdigest(),
            contenido_original=None,
            estado=EstadoDocumento.ERROR.value,
            error_lector="Lectura histórica sin archivo persistido",
        )
        sesion.add(documento)
        sesion.commit()
        sesion.refresh(documento)
        documento_id = documento.id

    revision = cliente.get(f"/cotizaciones/{cotizacion_id}/documentos/{documento_id}")
    original = cliente.get(
        f"/cotizaciones/{cotizacion_id}/documentos/{documento_id}/original"
    )

    assert revision.status_code == 200
    assert "Original no disponible" in revision.text
    assert 'id="formulario-revision"' in revision.text
    assert original.status_code == 404


def test_original_no_puede_consultarse_desde_otra_cotizacion(cliente: TestClient):
    cotizacion_id = _crear_cotizacion(cliente, "ORIGINAL-A")
    otra_cotizacion_id = _crear_cotizacion(cliente, "ORIGINAL-B")
    subida = _subir(
        cliente,
        cotizacion_id,
        nombre="privado.png",
        contenido=b"contenido-privado",
        mime_type="image/png",
    )
    documento_id = subida.headers["location"].rsplit("/", 1)[-1]

    respuesta = cliente.get(
        f"/cotizaciones/{otra_cotizacion_id}/documentos/{documento_id}/original"
    )

    assert respuesta.status_code == 404


def test_original_requiere_sesion(cliente_sin_acceso: TestClient):
    with cliente_sin_acceso.app.state.fabrica_sesiones() as sesion:
        cotizacion = Cotizacion(referencia="ORIGINAL-SIN-SESION")
        sesion.add(cotizacion)
        sesion.flush()
        documento = Documento(
            cotizacion_id=cotizacion.id,
            nombre_original="privado.pdf",
            mime_type="application/pdf",
            tamano_bytes=7,
            sha256=sha256(b"privado").hexdigest(),
            contenido_original=b"privado",
        )
        sesion.add(documento)
        sesion.commit()
        cotizacion_id = cotizacion.id
        documento_id = documento.id

    respuesta = cliente_sin_acceso.get(
        f"/cotizaciones/{cotizacion_id}/documentos/{documento_id}/original",
        follow_redirects=False,
    )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/acceso"
