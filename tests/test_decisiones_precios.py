import re
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from triage.cotizaciones.servicio import crear_cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.historico.decisiones_modelos import RolDecisionPrecio
from triage.historico.decisiones_servicio import registrar_decision_precio
from triage.historico.servicio import crear_observacion_precio
from triage.normalizacion.modelos import NormalizacionPartida
from triage.usuarios.modelos import Usuario


def _csrf(html: str) -> str:
    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF")
    return coincidencia.group(1)


def test_roles_de_decision_son_explicitos():
    assert RolDecisionPrecio.REFERENCIA_ESTABLE.value == "REFERENCIA_ESTABLE"
    assert RolDecisionPrecio.OPORTUNIDAD_ADQUISICION.value == "OPORTUNIDAD_ADQUISICION"


def test_pantalla_de_decisiones_se_integra_al_flujo(cliente: TestClient):
    nueva = cliente.get("/cotizaciones/nueva")
    creada = cliente.post(
        "/cotizaciones",
        data={"referencia": "DECISION-PRUEBA", "csrf_token": _csrf(nueva.text)},
        follow_redirects=False,
    )
    cotizacion_id = creada.headers["location"].rsplit("/", 1)[-1]

    detalle = cliente.get(f"/cotizaciones/{cotizacion_id}")
    assert "Decidir referencias" not in detalle.text

    decisiones = cliente.get(f"/cotizaciones/{cotizacion_id}/decisiones-precio")
    assert decisiones.status_code == 200
    assert "Decisiones de precio" in decisiones.text


def test_promocion_no_puede_usarse_como_referencia_estable(cliente: TestClient):
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario))
        assert usuario is not None
        cotizacion = crear_cotizacion(sesion, "PROMO-PRUEBA")
        documento = Documento(
            cotizacion_id=cotizacion.id,
            nombre_original="promo.pdf",
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
            producto_solicitado="PRODUCTO PROMO",
            cantidad=Decimal("1"),
            unidad_medida="caja",
        )
        sesion.add(partida)
        sesion.flush()
        sesion.add(
            NormalizacionPartida(
                partida_documento_id=partida.id,
                producto="PRODUCTO PROMO",
                presentacion="Caja",
                confirmada_por_usuario_id=usuario.id,
            )
        )
        sesion.commit()

        observacion = crear_observacion_precio(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_documento_id=partida.id,
            usuario_id=usuario.id,
            proveedor="Proveedor promo",
            fuente="Fuente promo",
            precio_antes_iva=Decimal("80.00"),
            iva_porcentaje=None,
            precio_total=None,
            es_promocion=True,
            condiciones_promocion="Oferta temporal",
            disponibilidad="Disponible",
            entrega_viable=True,
        )

        with pytest.raises(ValueError, match="promoción"):
            registrar_decision_precio(
                sesion,
                cotizacion_id=cotizacion.id,
                partida_id=partida.id,
                usuario_id=usuario.id,
                rol=RolDecisionPrecio.REFERENCIA_ESTABLE,
                observacion_id=observacion.id,
            )
