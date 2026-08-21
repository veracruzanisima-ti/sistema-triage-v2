"""Disponibilidad confirmada como requisito de una referencia estable."""

import re
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from triage.cotizaciones.servicio import crear_cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.historico.decisiones_modelos import DecisionPrecio, RolDecisionPrecio
from triage.historico.decisiones_servicio import (
    listar_selecciones_actuales,
    registrar_decision_precio,
)
from triage.historico.servicio import clave_producto, crear_observacion_precio
from triage.normalizacion.modelos import NormalizacionPartida
from triage.usuarios.modelos import Usuario


def _csrf(html: str) -> str:
    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF")
    return coincidencia.group(1)


def _preparar_producto(cliente: TestClient):
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario).limit(1))
        assert usuario is not None
        cotizacion = crear_cotizacion(sesion, "DISPONIBILIDAD-PRUEBA")
        cotizacion.codigo_postal_consulta = "91000"
        documento = Documento(
            cotizacion_id=cotizacion.id,
            nombre_original="disponibilidad.pdf",
            mime_type="application/pdf",
            tamano_bytes=10,
            sha256="f" * 64,
            estado=EstadoDocumento.REVISADO.value,
        )
        sesion.add(documento)
        sesion.flush()
        partida = PartidaDocumento(
            documento_id=documento.id,
            orden=1,
            producto_solicitado="DAPAGLIFLOZINA",
            concentracion="10 mg",
            forma_farmaceutica_dispositivo="tabletas",
            presentacion_solicitada="Caja con 28 tabletas",
            cantidad=Decimal("1"),
            unidad_medida="caja",
        )
        sesion.add(partida)
        sesion.flush()
        normalizacion = NormalizacionPartida(
            partida_documento_id=partida.id,
            producto="DAPAGLIFLOZINA",
            concentracion="10 mg",
            forma_dispositivo="tabletas",
            presentacion="Caja con 28 tabletas",
            confirmada_por_usuario_id=usuario.id,
        )
        sesion.add(normalizacion)
        sesion.commit()
        return cotizacion.id, partida.id, usuario.id


def _observacion(cliente, cotizacion_id, partida_id, usuario_id, *, proveedor, viable):
    with cliente.app.state.fabrica_sesiones() as sesion:
        return crear_observacion_precio(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_id,
            usuario_id=usuario_id,
            proveedor=proveedor,
            fuente=f"https://ejemplo.invalid/{proveedor.casefold().replace(' ', '-')}",
            precio_antes_iva=Decimal("700.00"),
            iva_porcentaje=None,
            precio_total=None,
            es_promocion=False,
            condiciones_promocion=None,
            disponibilidad=(
                "Disponible confirmado"
                if viable is True
                else "Agotado" if viable is False else "Consultar disponibilidad"
            ),
            entrega_viable=viable,
            codigo_postal="91000",
        )


def test_referencia_estable_exige_disponibilidad_confirmada(cliente: TestClient):
    cotizacion_id, partida_id, usuario_id = _preparar_producto(cliente)
    desconocida = _observacion(
        cliente,
        cotizacion_id,
        partida_id,
        usuario_id,
        proveedor="Proveedor por confirmar",
        viable=None,
    )
    agotada = _observacion(
        cliente,
        cotizacion_id,
        partida_id,
        usuario_id,
        proveedor="Proveedor agotado",
        viable=False,
    )
    disponible = _observacion(
        cliente,
        cotizacion_id,
        partida_id,
        usuario_id,
        proveedor="Proveedor disponible",
        viable=True,
    )

    with cliente.app.state.fabrica_sesiones() as sesion:
        with pytest.raises(ValueError, match="disponibilidad y entrega"):
            registrar_decision_precio(
                sesion,
                cotizacion_id=cotizacion_id,
                partida_id=partida_id,
                usuario_id=usuario_id,
                rol=RolDecisionPrecio.REFERENCIA_ESTABLE,
                observacion_id=desconocida.id,
            )
        with pytest.raises(ValueError, match="disponibilidad y entrega"):
            registrar_decision_precio(
                sesion,
                cotizacion_id=cotizacion_id,
                partida_id=partida_id,
                usuario_id=usuario_id,
                rol=RolDecisionPrecio.REFERENCIA_ESTABLE,
                observacion_id=agotada.id,
            )

        decision = registrar_decision_precio(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_id=partida_id,
            usuario_id=usuario_id,
            rol=RolDecisionPrecio.REFERENCIA_ESTABLE,
            observacion_id=disponible.id,
        )
        assert decision.observacion_precio_id == disponible.id


def test_seleccion_antigua_sin_disponibilidad_deja_de_ser_vigente(cliente: TestClient):
    cotizacion_id, partida_id, usuario_id = _preparar_producto(cliente)
    desconocida = _observacion(
        cliente,
        cotizacion_id,
        partida_id,
        usuario_id,
        proveedor="Referencia antigua",
        viable=None,
    )

    with cliente.app.state.fabrica_sesiones() as sesion:
        normalizacion = sesion.get(NormalizacionPartida, partida_id)
        assert normalizacion is not None
        sesion.add(
            DecisionPrecio(
                cotizacion_id=cotizacion_id,
                partida_documento_id=partida_id,
                clave_producto=clave_producto(normalizacion),
                rol=RolDecisionPrecio.REFERENCIA_ESTABLE.value,
                observacion_precio_id=desconocida.id,
                decidida_por_usuario_id=usuario_id,
            )
        )
        sesion.commit()

        selecciones = listar_selecciones_actuales(sesion, cotizacion_id)
        assert selecciones[partida_id].referencia_estable_id is None


def test_ui_solo_ofrece_cotizar_disponibilidad_confirmada(cliente: TestClient):
    cotizacion_id, partida_id, usuario_id = _preparar_producto(cliente)
    _observacion(
        cliente,
        cotizacion_id,
        partida_id,
        usuario_id,
        proveedor="Proveedor por confirmar",
        viable=None,
    )
    _observacion(
        cliente,
        cotizacion_id,
        partida_id,
        usuario_id,
        proveedor="Proveedor agotado",
        viable=False,
    )
    _observacion(
        cliente,
        cotizacion_id,
        partida_id,
        usuario_id,
        proveedor="Proveedor disponible",
        viable=True,
    )

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    assert pagina.status_code == 200
    assert "Disponibilidad por confirmar" in pagina.text
    assert "Sin disponibilidad" in pagina.text
    assert "Disponible confirmado" in pagina.text
    assert pagina.text.count("Confirmar con proveedor") == 2
    assert pagina.text.count(">Usar para cotizar</button>") == 1
    assert (
        f"/cotizaciones/{cotizacion_id}/historico?volver=proveedores"
        f"&partida_objetivo={partida_id}#partida-{partida_id}"
    ) in pagina.text


def test_confirmacion_manual_abre_partida_y_regresa_a_proveedores(cliente: TestClient):
    cotizacion_id, partida_id, _ = _preparar_producto(cliente)
    pagina = cliente.get(
        f"/cotizaciones/{cotizacion_id}/historico",
        params={"volver": "proveedores", "partida_objetivo": partida_id},
    )
    assert pagina.status_code == 200
    assert f'id="partida-{partida_id}"' in pagina.text
    assert "Confirma esta partida con la evidencia real del proveedor" in pagina.text
    assert "Sí, viable y confirmada" in pagina.text

    respuesta = cliente.post(
        f"/cotizaciones/{cotizacion_id}/historico/{partida_id}",
        data={
            "csrf_token": _csrf(pagina.text),
            "proveedor": "Proveedor confirmado",
            "fuente": "Mensaje de WhatsApp del proveedor",
            "precio_total": "725.00",
            "disponibilidad": "12 piezas confirmadas",
            "entrega_viable": "si",
            "volver": "proveedores",
        },
        follow_redirects=False,
    )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == (
        f"/cotizaciones/{cotizacion_id}/proveedores#estado-busqueda-{partida_id}"
    )