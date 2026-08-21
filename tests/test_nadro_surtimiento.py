"""Regla comercial de surtimiento NADRO sin confundirla con stock inmediato."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from triage.cotizaciones.servicio import crear_cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.historico.modelos import OrigenObservacionPrecio
from triage.historico.servicio import crear_observacion_precio
from triage.normalizacion.modelos import NormalizacionPartida
from triage.usuarios.modelos import Usuario


def _preparar_partida(cliente: TestClient):
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario).limit(1))
        assert usuario is not None
        cotizacion = crear_cotizacion(sesion, "NADRO-SURTIBLE")
        cotizacion.codigo_postal_consulta = "91193"
        documento = Documento(
            cotizacion_id=cotizacion.id,
            nombre_original="nadro.pdf",
            mime_type="application/pdf",
            tamano_bytes=10,
            sha256="7" * 64,
            estado=EstadoDocumento.REVISADO.value,
        )
        sesion.add(documento)
        sesion.flush()
        partida = PartidaDocumento(
            documento_id=documento.id,
            orden=1,
            producto_solicitado="INSULINA GLARGINA",
            concentracion="100 UI/mL",
            forma_farmaceutica_dispositivo="vial",
            presentacion_solicitada="10 mL",
            cantidad=Decimal("1"),
            unidad_medida="pieza",
        )
        sesion.add(partida)
        sesion.flush()
        sesion.add(
            NormalizacionPartida(
                partida_documento_id=partida.id,
                producto="INSULINA GLARGINA",
                marca="LANTUS",
                concentracion="100 UI/mL",
                forma_dispositivo="vial",
                presentacion="10 mL",
                confirmada_por_usuario_id=usuario.id,
            )
        )
        sesion.commit()
        return cotizacion.id, partida.id, usuario.id


def test_nadro_surtible_puede_usarse_sin_afirmar_stock_inmediato(cliente: TestClient):
    cotizacion_id, partida_id, usuario_id = _preparar_partida(cliente)
    with cliente.app.state.fabrica_sesiones() as sesion:
        crear_observacion_precio(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_id,
            usuario_id=usuario_id,
            proveedor="NADRO",
            fuente="EdiNadro · catálogo · código 00000545",
            precio_antes_iva=Decimal("2133.16"),
            iva_porcentaje=None,
            precio_total=None,
            es_promocion=False,
            condiciones_promocion=None,
            disponibilidad=(
                "Surtible por NADRO según regla comercial de Veracruzanísima; "
                "EdiNadro no informa existencia inmediata en tiempo real."
            ),
            entrega_viable=True,
            codigo_postal="91193",
            producto_observado="LANTUS 100UI 10ML F.A.",
            origen=OrigenObservacionPrecio.ADAPTADOR,
        )

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    assert pagina.status_code == 200
    assert "Surtible por NADRO" in pagina.text
    assert "capacidad de surtimiento bajo pedido" in pagina.text
    assert "no afirma existencia física inmediata" in pagina.text
    assert ">Usar para cotizar</button>" in pagina.text
    assert "Disponibilidad por confirmar" not in pagina.text


def test_oferta_nadro_surtible_sigue_siendo_promocion_no_referencia(cliente: TestClient):
    cotizacion_id, partida_id, usuario_id = _preparar_partida(cliente)
    with cliente.app.state.fabrica_sesiones() as sesion:
        crear_observacion_precio(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_id,
            usuario_id=usuario_id,
            proveedor="NADRO oferta",
            fuente="EdiNadro · oferta · código 00000545",
            precio_antes_iva=Decimal("1866.52"),
            iva_porcentaje=None,
            precio_total=None,
            es_promocion=True,
            condiciones_promocion="Descuento en factura reportado por EdiNadro.",
            disponibilidad=(
                "Surtible por NADRO según regla comercial de Veracruzanísima; "
                "EdiNadro no informa existencia inmediata en tiempo real."
            ),
            entrega_viable=True,
            codigo_postal="91193",
            producto_observado="LANTUS 100UI 10ML F.A.",
            origen=OrigenObservacionPrecio.ADAPTADOR,
        )

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    assert pagina.status_code == 200
    assert "Surtible por NADRO" in pagina.text
    assert "Oferta / promoción" in pagina.text
    assert "no se usa automáticamente como referencia estable" in pagina.text
    assert ">Usar para cotizar</button>" not in pagina.text