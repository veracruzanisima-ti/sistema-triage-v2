"""Pruebas del resultado NO SE COTIZA sin confundirlo con exclusión."""

import re
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from triage.comercial.modelos import DecisionComercialPartida, EstadoComercial
from triage.comercial.servicio import (
    listar_decisiones_comerciales_actuales,
    registrar_decision_comercial,
)
from triage.cotizaciones.modelos import Cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.historico.decisiones_modelos import RolDecisionPrecio
from triage.historico.decisiones_servicio import registrar_decision_precio
from triage.historico.servicio import crear_observacion_precio
from triage.normalizacion.modelos import NormalizacionPartida
from triage.proveedores.modelos import ConsultaProveedor
from triage.proveedores.servicio import ejecutar_consulta, listar_productos_consultables
from triage.usuarios.modelos import Usuario


def _csrf(html: str) -> str:
    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF")
    return coincidencia.group(1)


def _preparar_partida(cliente: TestClient) -> tuple[str, str, str]:
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario))
        assert usuario is not None
        cotizacion = Cotizacion(referencia="DECISION-COMERCIAL", codigo_postal_consulta="91000")
        sesion.add(cotizacion)
        sesion.flush()
        documento = Documento(
            cotizacion_id=cotizacion.id,
            nombre_original="decision.pdf",
            mime_type="application/pdf",
            tamano_bytes=10,
            sha256="d" * 64,
            estado=EstadoDocumento.REVISADO.value,
        )
        sesion.add(documento)
        sesion.flush()
        partida = PartidaDocumento(
            documento_id=documento.id,
            orden=1,
            producto_solicitado="PRODUCTO CONTROLADO DE PRUEBA",
            presentacion_solicitada="Caja con 10 unidades",
            cantidad=Decimal("2"),
            incluida_cotizacion=True,
        )
        sesion.add(partida)
        sesion.flush()
        sesion.add(
            NormalizacionPartida(
                partida_documento_id=partida.id,
                producto="PRODUCTO CONTROLADO DE PRUEBA",
                presentacion="Caja con 10 unidades",
                confirmada_por_usuario_id=usuario.id,
            )
        )
        sesion.commit()
        return cotizacion.id, partida.id, usuario.id


class CanalQueNoDebeEjecutarse:
    nombre = "Canal bloqueado"

    def __init__(self) -> None:
        self.llamado = False

    def consultar(self, _solicitud):
        self.llamado = True
        raise AssertionError("no debía consultarse")


def test_no_se_cotiza_exige_motivo_y_conserva_trazabilidad(cliente: TestClient):
    cotizacion_id, partida_id, usuario_id = _preparar_partida(cliente)
    with cliente.app.state.fabrica_sesiones() as sesion:
        with pytest.raises(ValueError, match="indica el motivo"):
            registrar_decision_comercial(
                sesion,
                cotizacion_id=cotizacion_id,
                partida_id=partida_id,
                usuario_id=usuario_id,
                estado=EstadoComercial.NO_SE_COTIZA,
                motivo="  ",
            )
        assert list(sesion.scalars(select(DecisionComercialPartida))) == []

        decision = registrar_decision_comercial(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_id=partida_id,
            usuario_id=usuario_id,
            estado=EstadoComercial.NO_SE_COTIZA,
            motivo="  Restricción comercial validada manualmente  ",
        )
        assert decision.motivo == "Restricción comercial validada manualmente"
        assert decision.decidida_por_usuario_id == usuario_id
        assert decision.creada_en is not None
        assert decision.regla_referencia is None
        assert decision.fuente_validacion == "REVISION_HUMANA"


def test_no_se_cotiza_sigue_visible_y_no_exige_referencia(cliente: TestClient):
    cotizacion_id, partida_id, _ = _preparar_partida(cliente)
    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/revision-final")
    respuesta = cliente.post(
        f"/cotizaciones/{cotizacion_id}/revision-final/{partida_id}/estado-comercial",
        data={
            "csrf_token": _csrf(pagina.text),
            "estado": "NO_SE_COTIZA",
            "motivo": "Autorización comercial no disponible",
        },
        follow_redirects=False,
    )
    assert respuesta.status_code == 303

    revision = cliente.get(respuesta.headers["location"])
    assert "PRODUCTO CONTROLADO DE PRUEBA" in revision.text
    assert "Resultado comercial: NO SE COTIZA" in revision.text
    assert "Autorización comercial no disponible" in revision.text
    assert "Falta referencia estable" not in revision.text

    proveedores = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    assert "Resultado comercial: NO SE COTIZA" in proveedores.text
    assert f"/proveedores/{partida_id}/buscar-web" not in proveedores.text

    historico = cliente.get(f"/cotizaciones/{cotizacion_id}/historico")
    assert "No se admiten precios nuevos" in historico.text
    assert f"/historico/{partida_id}" not in historico.text


def test_no_se_cotiza_bloquea_busquedas_captura_y_seleccion_de_precio(
    cliente: TestClient,
):
    cotizacion_id, partida_id, usuario_id = _preparar_partida(cliente)
    canal = CanalQueNoDebeEjecutarse()
    with cliente.app.state.fabrica_sesiones() as sesion:
        registrar_decision_comercial(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_id=partida_id,
            usuario_id=usuario_id,
            estado=EstadoComercial.NO_SE_COTIZA,
            motivo="Decisión de prueba",
        )
        assert listar_productos_consultables(sesion, cotizacion_id) == []

        with pytest.raises(ValueError, match="NO SE COTIZA"):
            ejecutar_consulta(
                sesion,
                cotizacion_id=cotizacion_id,
                partida_documento_id=partida_id,
                usuario_id=usuario_id,
                proveedor=canal,
            )
        assert canal.llamado is False
        assert list(sesion.scalars(select(ConsultaProveedor))) == []

        with pytest.raises(ValueError, match="NO SE COTIZA"):
            crear_observacion_precio(
                sesion,
                cotizacion_id=cotizacion_id,
                partida_documento_id=partida_id,
                usuario_id=usuario_id,
                proveedor="Manual",
                fuente="Prueba",
                precio_antes_iva=Decimal("10"),
                iva_porcentaje=None,
                precio_total=None,
                es_promocion=False,
                condiciones_promocion=None,
                disponibilidad=None,
                entrega_viable=None,
            )
        with pytest.raises(ValueError, match="NO SE COTIZA"):
            registrar_decision_precio(
                sesion,
                cotizacion_id=cotizacion_id,
                partida_id=partida_id,
                usuario_id=usuario_id,
                rol=RolDecisionPrecio.REFERENCIA_ESTABLE,
                observacion_id=None,
            )


def test_rehabilitar_partida_agrega_evento_y_reactiva_flujo(cliente: TestClient):
    cotizacion_id, partida_id, usuario_id = _preparar_partida(cliente)
    with cliente.app.state.fabrica_sesiones() as sesion:
        registrar_decision_comercial(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_id=partida_id,
            usuario_id=usuario_id,
            estado=EstadoComercial.NO_SE_COTIZA,
            motivo="Primera decisión",
        )
        registrar_decision_comercial(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_id=partida_id,
            usuario_id=usuario_id,
            estado=EstadoComercial.COTIZABLE,
            motivo="Rehabilitada manualmente",
        )
        decisiones = list(sesion.scalars(select(DecisionComercialPartida)))
        assert len(decisiones) == 2
        actual = listar_decisiones_comerciales_actuales(sesion, cotizacion_id)[partida_id]
        assert actual.estado == EstadoComercial.COTIZABLE
        assert len(listar_productos_consultables(sesion, cotizacion_id)) == 1
