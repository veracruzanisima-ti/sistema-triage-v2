from types import SimpleNamespace

from sqlalchemy import select

from triage.cotizaciones.modelos import Cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.normalizacion.modelos import NormalizacionPartida
from triage.usuarios.modelos import Usuario


def _crear_producto_consultable(cliente) -> tuple[str, str]:
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario))
        assert usuario is not None

        cotizacion = Cotizacion(
            referencia="ESTADO-BUSQUEDA-UI",
            codigo_postal_consulta="91000",
        )
        sesion.add(cotizacion)
        sesion.flush()

        documento = Documento(
            cotizacion_id=cotizacion.id,
            nombre_original="estado-busqueda.pdf",
            mime_type="application/pdf",
            tamano_bytes=10,
            sha256="e" * 64,
            estado=EstadoDocumento.REVISADO.value,
        )
        sesion.add(documento)
        sesion.flush()

        partida = PartidaDocumento(
            documento_id=documento.id,
            orden=1,
            producto_solicitado="LANTUS",
            incluida_cotizacion=True,
        )
        sesion.add(partida)
        sesion.flush()

        sesion.add(
            NormalizacionPartida(
                partida_documento_id=partida.id,
                producto="LANTUS",
                marca="Lantus",
                concentracion="100 U/mL",
                forma_dispositivo="vial",
                presentacion="10 mL",
                confirmada_por_usuario_id=usuario.id,
            )
        )
        sesion.commit()
        return cotizacion.id, partida.id


def test_busquedas_de_precio_muestran_estado_visual_inmediato(cliente):
    cotizacion_id, partida_id = _crear_producto_consultable(cliente)
    cliente.app.state.proveedores_productos = {
        "proveedor prueba": SimpleNamespace(nombre="Proveedor Prueba")
    }
    cliente.app.state.descubridor_web = object()

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")

    assert pagina.status_code == 200
    assert "data-form-busqueda" in pagina.text
    assert "Buscando precios en proveedores configurados…" in pagina.text
    assert "Buscando más opciones en web para este producto…" in pagina.text
    assert f'id="estado-busqueda-{partida_id}"' in pagina.text
    assert 'aria-live="polite"' in pagina.text
    assert 'boton.textContent = "Buscando…"' in pagina.text
    assert "estado.hidden = false" in pagina.text


def test_resultado_web_se_reubica_en_la_tarjeta_del_producto(cliente):
    cotizacion_id, _ = _crear_producto_consultable(cliente)
    cliente.app.state.descubridor_web = object()

    pagina = cliente.get(
        f"/cotizaciones/{cotizacion_id}/proveedores"
        "?resultado=web&web_guardados=0&web_descartados=5"
    )

    assert pagina.status_code == 200
    assert "triage-ultima-busqueda-web" in pagina.text
    assert "Búsqueda web · ${producto}" in pagina.text
    assert "La web sí devolvió ${descartados} resultado(s)" in pagina.text
    assert 'form[action*="/buscar-web"]' in pagina.text
    assert "mensajeGlobal.remove()" in pagina.text
    assert "aviso.scrollIntoView" in pagina.text
