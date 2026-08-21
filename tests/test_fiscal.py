"""Pruebas del prototipo fiscal explicable y reversible."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from triage.comercial.modelos import EstadoComercial
from triage.comercial.servicio import registrar_decision_comercial
from triage.cotizaciones.modelos import Cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.fiscal.modelos import TratamientoIVA
from triage.fiscal.servicio import (
    calcular_borrador_fiscal,
    construir_sugerencia_fiscal,
    listar_validaciones_fiscales_actuales,
    registrar_validacion_fiscal,
    retirar_validacion_fiscal,
)
from triage.historico.decisiones_modelos import RolDecisionPrecio
from triage.historico.decisiones_servicio import registrar_decision_precio
from triage.historico.servicio import crear_observacion_precio, listar_productos_historico
from triage.normalizacion.modelos import NormalizacionPartida
from triage.revision_final.servicio import listar_precierre
from triage.usuarios.modelos import Usuario


def _crear_producto(sesion, *, referencia: str = "FISCAL"):
    usuario = sesion.scalar(select(Usuario).limit(1))
    assert usuario is not None
    cotizacion = Cotizacion(referencia=referencia)
    sesion.add(cotizacion)
    sesion.flush()
    documento = Documento(
        cotizacion_id=cotizacion.id,
        nombre_original="fiscal.pdf",
        mime_type="application/pdf",
        tamano_bytes=10,
        sha256="a" * 64,
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
        presentacion_solicitada="Caja con 10",
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
        presentacion="Caja con 10",
        confirmada_por_usuario_id=usuario.id,
    )
    sesion.add(normalizacion)
    sesion.commit()
    return cotizacion, partida, normalizacion, usuario


def _agregar_referencia_y_proveedor(
    sesion,
    *,
    cotizacion_id: str,
    partida_id: str,
    usuario_id: str,
    tasa_referencia: str,
    tasa_independiente: str,
    con_cofepris: bool = False,
):
    evidencia = (
        {
            "fuente": "COFEPRIS",
            "numero_registro": "123M2026 SSA",
            "estado": "VIGENTE",
            "sha256_importacion": "b" * 64,
        }
        if con_cofepris
        else None
    )
    referencia = crear_observacion_precio(
        sesion,
        cotizacion_id=cotizacion_id,
        partida_documento_id=partida_id,
        usuario_id=usuario_id,
        proveedor="Proveedor referencia",
        fuente="captura de proveedor",
        precio_antes_iva=Decimal("100"),
        iva_porcentaje=Decimal(tasa_referencia),
        precio_total=None,
        es_promocion=False,
        condiciones_promocion=None,
        disponibilidad="Disponible",
        entrega_viable=True,
        evidencia_identidad=evidencia,
    )
    crear_observacion_precio(
        sesion,
        cotizacion_id=cotizacion_id,
        partida_documento_id=partida_id,
        usuario_id=usuario_id,
        proveedor="Proveedor independiente",
        fuente="segunda captura",
        precio_antes_iva=Decimal("98"),
        iva_porcentaje=Decimal(tasa_independiente),
        precio_total=None,
        es_promocion=False,
        condiciones_promocion=None,
        disponibilidad="Disponible",
        entrega_viable=True,
    )
    registrar_decision_precio(
        sesion,
        cotizacion_id=cotizacion_id,
        partida_id=partida_id,
        usuario_id=usuario_id,
        rol=RolDecisionPrecio.REFERENCIA_ESTABLE,
        observacion_id=referencia.id,
    )
    return referencia


def test_capas_coincidentes_proponen_tasa_con_confianza_alta(cliente: TestClient):
    with cliente.app.state.fabrica_sesiones() as sesion:
        cotizacion, partida, _, usuario = _crear_producto(sesion)
        referencia = _agregar_referencia_y_proveedor(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_id=partida.id,
            usuario_id=usuario.id,
            tasa_referencia="0",
            tasa_independiente="0",
            con_cofepris=True,
        )
        producto = listar_productos_historico(sesion, cotizacion.id)[0]
        sugerencia = construir_sugerencia_fiscal(
            sesion,
            cotizacion_id=cotizacion.id,
            producto=producto,
            referencia=referencia,
        )

        assert sugerencia.principal is not None
        assert sugerencia.principal.iva_porcentaje == Decimal("0.00")
        assert sugerencia.principal.puntos == 85
        assert sugerencia.nivel_confianza == "ALTA"
        assert not sugerencia.hay_conflicto
        assert {capa.capa for capa in sugerencia.principal.capas} == {
            "referencia_estable",
            "proveedor_historico_independiente",
            "identidad_cofepris_y_regla_legal",
        }


def test_senales_con_tasas_distintas_muestran_conflicto(cliente: TestClient):
    with cliente.app.state.fabrica_sesiones() as sesion:
        cotizacion, partida, _, usuario = _crear_producto(sesion, referencia="CONFLICTO")
        referencia = _agregar_referencia_y_proveedor(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_id=partida.id,
            usuario_id=usuario.id,
            tasa_referencia="0",
            tasa_independiente="16",
        )
        producto = listar_productos_historico(sesion, cotizacion.id)[0]
        sugerencia = construir_sugerencia_fiscal(
            sesion,
            cotizacion_id=cotizacion.id,
            producto=producto,
            referencia=referencia,
        )

        assert sugerencia.hay_conflicto
        assert sugerencia.nivel_confianza == "CONFLICTO"
        assert {candidato.iva_porcentaje for candidato in sugerencia.alternativas} == {
            Decimal("0.00"),
            Decimal("16.00"),
        }


def test_validacion_calcula_rubros_y_se_puede_retirar(cliente: TestClient):
    with cliente.app.state.fabrica_sesiones() as sesion:
        cotizacion, partida, _, usuario = _crear_producto(sesion, referencia="CALCULO")
        referencia = _agregar_referencia_y_proveedor(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_id=partida.id,
            usuario_id=usuario.id,
            tasa_referencia="16",
            tasa_independiente="16",
        )
        producto = listar_productos_historico(sesion, cotizacion.id)[0]
        sugerencia = construir_sugerencia_fiscal(
            sesion,
            cotizacion_id=cotizacion.id,
            producto=producto,
            referencia=referencia,
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
        validacion = listar_validaciones_fiscales_actuales(
            sesion,
            cotizacion_id=cotizacion.id,
            productos=[producto],
        )[partida.id]
        calculo = calcular_borrador_fiscal(
            producto=producto,
            referencia=referencia,
            sugerencia=sugerencia,
            validacion=validacion,
        )

        assert calculo is not None
        assert calculo.precio_unitario_sin_iva == Decimal("100.00")
        assert calculo.subtotal == Decimal("200.00")
        assert calculo.iva == Decimal("32.00")
        assert calculo.total == Decimal("232.00")
        assert calculo.validado

        retirar_validacion_fiscal(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_id=partida.id,
            usuario_id=usuario.id,
        )
        assert not listar_validaciones_fiscales_actuales(
            sesion,
            cotizacion_id=cotizacion.id,
            productos=[producto],
        )


def test_cambio_de_identidad_invalida_validacion_actual(cliente: TestClient):
    with cliente.app.state.fabrica_sesiones() as sesion:
        cotizacion, partida, normalizacion, usuario = _crear_producto(
            sesion,
            referencia="IDENTIDAD",
        )
        _agregar_referencia_y_proveedor(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_id=partida.id,
            usuario_id=usuario.id,
            tasa_referencia="0",
            tasa_independiente="0",
        )
        registrar_validacion_fiscal(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_id=partida.id,
            usuario_id=usuario.id,
            tratamiento_iva=TratamientoIVA.TASA,
            iva_porcentaje=Decimal("0"),
            observacion=None,
        )
        normalizacion.producto = "OTRO PRODUCTO"
        sesion.add(normalizacion)
        sesion.commit()
        productos = listar_productos_historico(sesion, cotizacion.id)

        assert not listar_validaciones_fiscales_actuales(
            sesion,
            cotizacion_id=cotizacion.id,
            productos=productos,
        )


def test_no_se_cotiza_bloquea_validacion_y_no_deja_pendiente_fiscal(cliente: TestClient):
    with cliente.app.state.fabrica_sesiones() as sesion:
        cotizacion, partida, _, usuario = _crear_producto(sesion, referencia="NO-COTIZA")
        registrar_decision_comercial(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_id=partida.id,
            usuario_id=usuario.id,
            estado=EstadoComercial.NO_SE_COTIZA,
            motivo="Producto controlado que no comercializamos",
        )

        try:
            registrar_validacion_fiscal(
                sesion,
                cotizacion_id=cotizacion.id,
                partida_id=partida.id,
                usuario_id=usuario.id,
                tratamiento_iva=TratamientoIVA.TASA,
                iva_porcentaje=Decimal("0"),
                observacion="Corrección manual",
            )
        except ValueError as error:
            assert "NO SE COTIZA" in str(error)
        else:
            raise AssertionError("una partida NO SE COTIZA no debe aceptar validación fiscal")

        item = listar_precierre(sesion, cotizacion.id)[0]
        assert item.pendientes == ()
        assert item.calculo_fiscal is None


def test_revision_final_muestra_capas_y_rubros_del_borrador(cliente: TestClient):
    with cliente.app.state.fabrica_sesiones() as sesion:
        cotizacion, partida, _, usuario = _crear_producto(sesion, referencia="UI-FISCAL")
        _agregar_referencia_y_proveedor(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_id=partida.id,
            usuario_id=usuario.id,
            tasa_referencia="0",
            tasa_independiente="0",
            con_cofepris=True,
        )
        cotizacion_id = cotizacion.id

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/revision-final")

    assert pagina.status_code == 200
    assert "Propuesta fiscal por capas" in pagina.text
    assert "Confianza ALTA" in pagina.text
    assert "85/100" in pagina.text
    assert "Precio unitario s/IVA" in pagina.text
    assert "Cálculo pendiente basado en la propuesta; no emitible" in pagina.text
