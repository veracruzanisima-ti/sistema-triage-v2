"""Regresiones del precio unitario final confirmado manualmente."""

from decimal import Decimal

import pytest
from sqlalchemy import select

from triage.comercial.modelos import EstadoComercial
from triage.comercial.precio_venta_modelos import EstadoPrecioVenta, PrecioVentaPartida
from triage.comercial.precio_venta_servicio import (
    listar_precios_venta_actuales,
    registrar_precio_venta,
    retirar_precio_venta,
)
from triage.comercial.servicio import registrar_decision_comercial
from triage.cotizaciones.modelos import Cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.fiscal.modelos import TratamientoIVA
from triage.fiscal.servicio import registrar_validacion_fiscal
from triage.historico.decisiones_modelos import RolDecisionPrecio
from triage.historico.decisiones_servicio import registrar_decision_precio
from triage.historico.servicio import crear_observacion_precio, listar_productos_historico
from triage.normalizacion.modelos import NormalizacionPartida
from triage.revision_final.servicio import listar_precierre
from triage.usuarios.modelos import Usuario


def _preparar(sesion):
    usuario = sesion.scalar(select(Usuario).limit(1))
    assert usuario is not None
    cotizacion = Cotizacion(referencia="PRECIO-VENTA", referencia_fijada_manual=True)
    sesion.add(cotizacion)
    sesion.flush()
    documento = Documento(
        cotizacion_id=cotizacion.id,
        nombre_original="precio.pdf",
        mime_type="application/pdf",
        tamano_bytes=10,
        sha256="p" * 64,
        estado=EstadoDocumento.REVISADO.value,
    )
    sesion.add(documento)
    sesion.flush()
    partida = PartidaDocumento(
        documento_id=documento.id,
        orden=1,
        producto_solicitado="PRODUCTO PRUEBA",
        marca_solicitada="MARCA A",
        concentracion="10 mg",
        forma_farmaceutica_dispositivo="tabletas",
        presentacion_solicitada="Caja con 10 tabletas",
        cantidad=Decimal("2"),
        unidad_medida="cajas",
    )
    sesion.add(partida)
    sesion.flush()
    normalizacion = NormalizacionPartida(
        partida_documento_id=partida.id,
        producto="PRODUCTO PRUEBA",
        marca="MARCA A",
        concentracion="10 mg",
        forma_dispositivo="tabletas",
        presentacion="Caja con 10 tabletas",
        confirmada_por_usuario_id=usuario.id,
    )
    sesion.add(normalizacion)
    sesion.commit()
    return cotizacion, partida, normalizacion, usuario


def _seleccionar_referencia(
    sesion,
    *,
    cotizacion,
    partida,
    usuario,
    proveedor="Proveedor A",
    precio="100",
):
    observacion = crear_observacion_precio(
        sesion,
        cotizacion_id=cotizacion.id,
        partida_documento_id=partida.id,
        usuario_id=usuario.id,
        proveedor=proveedor,
        fuente=f"https://example.invalid/{proveedor.replace(' ', '-').lower()}",
        precio_antes_iva=Decimal(precio),
        iva_porcentaje=Decimal("16"),
        precio_total=(Decimal(precio) * Decimal("1.16")),
        es_promocion=False,
        condiciones_promocion=None,
        disponibilidad="Disponible",
        entrega_viable=True,
    )
    registrar_decision_precio(
        sesion,
        cotizacion_id=cotizacion.id,
        partida_id=partida.id,
        usuario_id=usuario.id,
        rol=RolDecisionPrecio.REFERENCIA_ESTABLE,
        observacion_id=observacion.id,
    )
    return observacion


def _actuales(sesion, cotizacion_id):
    productos = listar_productos_historico(sesion, cotizacion_id)
    return listar_precios_venta_actuales(
        sesion,
        cotizacion_id=cotizacion_id,
        productos=productos,
    )


def test_precio_final_exige_referencia_estable(cliente):
    with cliente.app.state.fabrica_sesiones() as sesion:
        cotizacion, partida, _, usuario = _preparar(sesion)

        with pytest.raises(ValueError, match="referencia estable"):
            registrar_precio_venta(
                sesion,
                cotizacion_id=cotizacion.id,
                partida_id=partida.id,
                usuario_id=usuario.id,
                precio_unitario_sin_iva=Decimal("150"),
                observacion=None,
            )


def test_precio_final_se_guarda_y_alimenta_calculo_final(cliente):
    with cliente.app.state.fabrica_sesiones() as sesion:
        cotizacion, partida, _, usuario = _preparar(sesion)
        referencia = _seleccionar_referencia(
            sesion,
            cotizacion=cotizacion,
            partida=partida,
            usuario=usuario,
        )
        evento = registrar_precio_venta(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_id=partida.id,
            usuario_id=usuario.id,
            precio_unitario_sin_iva=Decimal("150"),
            observacion="Autorizado para esta cotización",
        )
        registrar_validacion_fiscal(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_id=partida.id,
            usuario_id=usuario.id,
            tratamiento_iva=TratamientoIVA.TASA,
            iva_porcentaje=Decimal("16"),
            observacion=None,
        )

        actual = _actuales(sesion, cotizacion.id)[partida.id]
        precierre = listar_precierre(sesion, cotizacion.id)[0]

        assert evento.precio_unitario_sin_iva == Decimal("150.00")
        assert actual.referencia_estable_id == referencia.id
        assert actual.observacion == "Autorizado para esta cotización"
        assert precierre.calculo_venta is not None
        assert precierre.calculo_venta.precio_unitario_sin_iva == Decimal("150.00")
        assert precierre.calculo_venta.subtotal == Decimal("300.00")
        assert precierre.calculo_venta.iva == Decimal("48.00")
        assert precierre.calculo_venta.total == Decimal("348.00")
        assert "Confirmar precio unitario final" not in precierre.pendientes


def test_precio_final_se_invalida_si_cambia_referencia_estable(cliente):
    with cliente.app.state.fabrica_sesiones() as sesion:
        cotizacion, partida, _, usuario = _preparar(sesion)
        _seleccionar_referencia(
            sesion,
            cotizacion=cotizacion,
            partida=partida,
            usuario=usuario,
            proveedor="Proveedor A",
        )
        registrar_precio_venta(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_id=partida.id,
            usuario_id=usuario.id,
            precio_unitario_sin_iva=Decimal("150"),
            observacion=None,
        )
        _seleccionar_referencia(
            sesion,
            cotizacion=cotizacion,
            partida=partida,
            usuario=usuario,
            proveedor="Proveedor B",
            precio="95",
        )

        assert partida.id not in _actuales(sesion, cotizacion.id)
        assert "Confirmar precio unitario final sin IVA" in listar_precierre(
            sesion, cotizacion.id
        )[0].pendientes


def test_precio_final_se_invalida_si_cambia_identidad(cliente):
    with cliente.app.state.fabrica_sesiones() as sesion:
        cotizacion, partida, normalizacion, usuario = _preparar(sesion)
        _seleccionar_referencia(
            sesion,
            cotizacion=cotizacion,
            partida=partida,
            usuario=usuario,
        )
        registrar_precio_venta(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_id=partida.id,
            usuario_id=usuario.id,
            precio_unitario_sin_iva=Decimal("150"),
            observacion=None,
        )
        normalizacion.presentacion = "Caja con 20 tabletas"
        sesion.add(normalizacion)
        sesion.commit()

        assert partida.id not in _actuales(sesion, cotizacion.id)


def test_retirar_precio_final_es_append_only(cliente):
    with cliente.app.state.fabrica_sesiones() as sesion:
        cotizacion, partida, _, usuario = _preparar(sesion)
        _seleccionar_referencia(
            sesion,
            cotizacion=cotizacion,
            partida=partida,
            usuario=usuario,
        )
        registrar_precio_venta(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_id=partida.id,
            usuario_id=usuario.id,
            precio_unitario_sin_iva=Decimal("150"),
            observacion=None,
        )
        retiro = retirar_precio_venta(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_id=partida.id,
            usuario_id=usuario.id,
        )

        eventos = list(
            sesion.scalars(
                select(PrecioVentaPartida).where(
                    PrecioVentaPartida.cotizacion_id == cotizacion.id,
                    PrecioVentaPartida.partida_documento_id == partida.id,
                )
            )
        )
        assert len(eventos) == 2
        assert retiro.estado == EstadoPrecioVenta.PENDIENTE.value
        assert partida.id not in _actuales(sesion, cotizacion.id)


def test_no_se_cotiza_bloquea_precio_final(cliente):
    with cliente.app.state.fabrica_sesiones() as sesion:
        cotizacion, partida, _, usuario = _preparar(sesion)
        _seleccionar_referencia(
            sesion,
            cotizacion=cotizacion,
            partida=partida,
            usuario=usuario,
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
                precio_unitario_sin_iva=Decimal("150"),
                observacion=None,
            )
