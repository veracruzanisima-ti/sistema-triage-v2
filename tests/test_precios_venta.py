"""Pruebas de la decisión manual de precio final de venta."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from triage.comercial.modelos import EstadoComercial
from triage.comercial.precios_venta_modelos import PrecioFinalVentaPartida
from triage.comercial.precios_venta_servicio import (
    listar_precios_venta_actuales,
    registrar_precio_venta,
    retirar_precio_venta,
)
from triage.comercial.servicio import registrar_decision_comercial
from triage.cotizaciones.modelos import Cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.historico.servicio import listar_productos_historico
from triage.normalizacion.modelos import NormalizacionPartida
from triage.usuarios.modelos import Usuario


def _crear_producto(sesion, *, referencia: str = "PRECIO-VENTA"):
    usuario = sesion.scalar(select(Usuario).limit(1))
    assert usuario is not None
    cotizacion = Cotizacion(referencia=referencia, referencia_fijada_manual=True)
    sesion.add(cotizacion)
    sesion.flush()
    documento = Documento(
        cotizacion_id=cotizacion.id,
        nombre_original="precio-venta.pdf",
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
        producto_solicitado="PARACETAMOL",
        marca_solicitada="MARCA",
        concentracion="500 mg",
        forma_farmaceutica_dispositivo="tabletas",
        presentacion_solicitada="Caja con 10 tabletas",
        cantidad=Decimal("2"),
        unidad_medida="cajas",
    )
    sesion.add(partida)
    sesion.flush()
    normalizacion = NormalizacionPartida(
        partida_documento_id=partida.id,
        producto="PARACETAMOL",
        marca="MARCA",
        concentracion="500 mg",
        forma_dispositivo="tabletas",
        presentacion="Caja con 10 tabletas",
        confirmada_por_usuario_id=usuario.id,
    )
    sesion.add(normalizacion)
    sesion.commit()
    return cotizacion, partida, normalizacion, usuario


def test_precio_final_manual_es_append_only_y_reversible(cliente: TestClient):
    with cliente.app.state.fabrica_sesiones() as sesion:
        cotizacion, partida, _, usuario = _crear_producto(sesion)
        evento = registrar_precio_venta(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_id=partida.id,
            usuario_id=usuario.id,
            precio_unitario_sin_iva=Decimal("150.125"),
            fuente_comercial="Autorización de Dirección",
            observacion="Prueba de captura manual",
        )
        productos = listar_productos_historico(sesion, cotizacion.id)
        actual = listar_precios_venta_actuales(
            sesion,
            cotizacion_id=cotizacion.id,
            productos=productos,
        )[partida.id]

        assert evento.precio_unitario_sin_iva == Decimal("150.13")
        assert actual.precio_unitario_sin_iva == Decimal("150.13")
        assert actual.fuente_comercial == "Autorización de Dirección"
        assert actual.validada_por_nombre == usuario.nombre

        retirar_precio_venta(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_id=partida.id,
            usuario_id=usuario.id,
        )
        assert not listar_precios_venta_actuales(
            sesion,
            cotizacion_id=cotizacion.id,
            productos=listar_productos_historico(sesion, cotizacion.id),
        )
        eventos = list(
            sesion.scalars(
                select(PrecioFinalVentaPartida).where(
                    PrecioFinalVentaPartida.cotizacion_id == cotizacion.id,
                    PrecioFinalVentaPartida.partida_documento_id == partida.id,
                )
            )
        )
        assert len(eventos) == 2


def test_precio_final_rechaza_valor_no_positivo_y_fuente_vacia(cliente: TestClient):
    with cliente.app.state.fabrica_sesiones() as sesion:
        cotizacion, partida, _, usuario = _crear_producto(sesion, referencia="PRECIO-INVALIDO")

        with pytest.raises(ValueError, match="mayor que cero"):
            registrar_precio_venta(
                sesion,
                cotizacion_id=cotizacion.id,
                partida_id=partida.id,
                usuario_id=usuario.id,
                precio_unitario_sin_iva=Decimal("0"),
                fuente_comercial="Dirección",
                observacion=None,
            )
        with pytest.raises(ValueError, match="fuente o criterio"):
            registrar_precio_venta(
                sesion,
                cotizacion_id=cotizacion.id,
                partida_id=partida.id,
                usuario_id=usuario.id,
                precio_unitario_sin_iva=Decimal("100"),
                fuente_comercial="   ",
                observacion=None,
            )


def test_cambio_de_identidad_invalida_precio_final_actual(cliente: TestClient):
    with cliente.app.state.fabrica_sesiones() as sesion:
        cotizacion, partida, normalizacion, usuario = _crear_producto(
            sesion,
            referencia="PRECIO-IDENTIDAD",
        )
        registrar_precio_venta(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_id=partida.id,
            usuario_id=usuario.id,
            precio_unitario_sin_iva=Decimal("100"),
            fuente_comercial="Dirección",
            observacion=None,
        )
        normalizacion.producto = "PARACETAMOL NUEVA IDENTIDAD"
        sesion.add(normalizacion)
        sesion.commit()

        assert not listar_precios_venta_actuales(
            sesion,
            cotizacion_id=cotizacion.id,
            productos=listar_productos_historico(sesion, cotizacion.id),
        )


def test_no_se_cotiza_bloquea_nuevo_precio_final(cliente: TestClient):
    with cliente.app.state.fabrica_sesiones() as sesion:
        cotizacion, partida, _, usuario = _crear_producto(
            sesion,
            referencia="PRECIO-NO-COTIZA",
        )
        registrar_decision_comercial(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_id=partida.id,
            usuario_id=usuario.id,
            estado=EstadoComercial.NO_SE_COTIZA,
            motivo="Decisión comercial de prueba",
        )

        with pytest.raises(ValueError, match="NO SE COTIZA"):
            registrar_precio_venta(
                sesion,
                cotizacion_id=cotizacion.id,
                partida_id=partida.id,
                usuario_id=usuario.id,
                precio_unitario_sin_iva=Decimal("100"),
                fuente_comercial="Dirección",
                observacion=None,
            )
