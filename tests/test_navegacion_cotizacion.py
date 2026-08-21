"""Navegación del flujo de selección de precios sin volver arriba entre partidas."""

import re
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from triage.comercial.modelos import EstadoComercial
from triage.comercial.servicio import registrar_decision_comercial
from triage.cotizaciones.servicio import crear_cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.historico.servicio import crear_observacion_precio
from triage.normalizacion.modelos import NormalizacionPartida
from triage.usuarios.modelos import Usuario


def _csrf(html: str) -> str:
    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF")
    return coincidencia.group(1)


def _preparar_tres_partidas(cliente: TestClient):
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario).limit(1))
        assert usuario is not None
        cotizacion = crear_cotizacion(sesion, "NAVEGACION-COTIZACION")
        documento = Documento(
            cotizacion_id=cotizacion.id,
            nombre_original="navegacion.pdf",
            mime_type="application/pdf",
            tamano_bytes=10,
            sha256="d" * 64,
            estado=EstadoDocumento.REVISADO.value,
        )
        sesion.add(documento)
        sesion.flush()

        partidas = []
        for orden, nombre in enumerate(("PRODUCTO UNO", "PRODUCTO DOS", "PRODUCTO TRES"), 1):
            partida = PartidaDocumento(
                documento_id=documento.id,
                orden=orden,
                producto_solicitado=nombre,
                cantidad=Decimal("1"),
                unidad_medida="caja",
            )
            sesion.add(partida)
            sesion.flush()
            sesion.add(
                NormalizacionPartida(
                    partida_documento_id=partida.id,
                    producto=nombre,
                    presentacion="Caja",
                    confirmada_por_usuario_id=usuario.id,
                )
            )
            partidas.append(partida)
        sesion.commit()

        observaciones = {}
        for partida in (partidas[0], partidas[2]):
            observacion = crear_observacion_precio(
                sesion,
                cotizacion_id=cotizacion.id,
                partida_documento_id=partida.id,
                usuario_id=usuario.id,
                proveedor=f"Proveedor {partida.orden}",
                fuente=f"Fuente {partida.orden}",
                precio_antes_iva=Decimal("100.00") + Decimal(partida.orden),
                iva_porcentaje=None,
                precio_total=None,
                es_promocion=False,
                condiciones_promocion=None,
                disponibilidad="Disponible",
                entrega_viable=True,
            )
            observaciones[partida.id] = observacion.id

        registrar_decision_comercial(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_id=partidas[1].id,
            usuario_id=usuario.id,
            estado=EstadoComercial.NO_SE_COTIZA,
            motivo="No se cotiza durante esta prueba",
        )
        return cotizacion.id, tuple(partida.id for partida in partidas), observaciones


def _cotizar(
    cliente: TestClient,
    *,
    cotizacion_id: str,
    partida_id: str,
    observacion_id: str,
):
    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    assert pagina.status_code == 200
    return cliente.post(
        f"/cotizaciones/{cotizacion_id}/decisiones-precio/{partida_id}",
        data={
            "csrf_token": _csrf(pagina.text),
            "rol": "REFERENCIA_ESTABLE",
            "observacion_id": observacion_id,
            "volver": "proveedores",
        },
        follow_redirects=False,
    )


def test_cotizar_avanza_a_la_siguiente_pendiente_y_salta_no_se_cotiza(
    cliente: TestClient,
):
    cotizacion_id, partidas, observaciones = _preparar_tres_partidas(cliente)

    respuesta = _cotizar(
        cliente,
        cotizacion_id=cotizacion_id,
        partida_id=partidas[0],
        observacion_id=observaciones[partidas[0]],
    )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == (
        f"/cotizaciones/{cotizacion_id}/proveedores#estado-busqueda-{partidas[2]}"
    )


def test_cotizar_ultima_pendiente_vuelve_sin_ancla(cliente: TestClient):
    cotizacion_id, partidas, observaciones = _preparar_tres_partidas(cliente)
    primera = _cotizar(
        cliente,
        cotizacion_id=cotizacion_id,
        partida_id=partidas[0],
        observacion_id=observaciones[partidas[0]],
    )
    assert primera.status_code == 303

    ultima = _cotizar(
        cliente,
        cotizacion_id=cotizacion_id,
        partida_id=partidas[2],
        observacion_id=observaciones[partidas[2]],
    )

    assert ultima.status_code == 303
    assert ultima.headers["location"] == f"/cotizaciones/{cotizacion_id}/proveedores"


def test_cotizar_fuera_de_orden_regresa_a_una_pendiente_anterior(cliente: TestClient):
    cotizacion_id, partidas, observaciones = _preparar_tres_partidas(cliente)

    respuesta = _cotizar(
        cliente,
        cotizacion_id=cotizacion_id,
        partida_id=partidas[2],
        observacion_id=observaciones[partidas[2]],
    )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == (
        f"/cotizaciones/{cotizacion_id}/proveedores#estado-busqueda-{partidas[0]}"
    )
