"""Confirmación humana de una fuente web pendiente antes de usarla para cotizar."""

import re
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from triage.cotizaciones.servicio import crear_cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.historico.confirmaciones_web import confirmar_fuente_web_y_usar_como_referencia
from triage.historico.decisiones_servicio import listar_selecciones_actuales
from triage.historico.modelos import ObservacionPrecio, OrigenObservacionPrecio
from triage.historico.servicio import clave_producto, crear_observacion_precio
from triage.normalizacion.modelos import NormalizacionPartida
from triage.usuarios.modelos import Usuario


def _csrf(html: str) -> str:
    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF")
    return coincidencia.group(1)


def _preparar_enalapril(cliente: TestClient):
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario).limit(1))
        assert usuario is not None
        cotizacion = crear_cotizacion(sesion, "CONFIRMACION-WEB")
        cotizacion.codigo_postal_consulta = "91193"
        documento = Documento(
            cotizacion_id=cotizacion.id,
            nombre_original="enalapril.pdf",
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
            producto_solicitado="ENALAPRIL",
            concentracion="10 mg",
            forma_farmaceutica_dispositivo="tabletas",
            presentacion_solicitada="Caja con 30 tabletas de 10 mg",
            cantidad=Decimal("1"),
            unidad_medida="caja",
        )
        sesion.add(partida)
        sesion.flush()
        normalizacion = NormalizacionPartida(
            partida_documento_id=partida.id,
            producto="ENALAPRIL",
            concentracion="10 mg",
            forma_dispositivo="tabletas",
            presentacion="Caja con 30 tabletas de 10 mg",
            confirmada_por_usuario_id=usuario.id,
        )
        sesion.add(normalizacion)
        sesion.commit()
        return cotizacion.id, partida.id, usuario.id


def _web(
    cliente: TestClient,
    *,
    cotizacion_id: str,
    partida_id: str,
    usuario_id: str,
    disponibilidad: str,
    promocion: bool = False,
):
    with cliente.app.state.fabrica_sesiones() as sesion:
        return crear_observacion_precio(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_id,
            usuario_id=usuario_id,
            proveedor="Farmacia Sanorim",
            fuente="https://farmacia.example/enalapril-10-mg-30-tabletas",
            precio_antes_iva=None,
            iva_porcentaje=None,
            precio_total=Decimal("29.00"),
            es_promocion=promocion,
            condiciones_promocion="Oferta de prueba" if promocion else None,
            disponibilidad=disponibilidad,
            entrega_viable=None,
            codigo_postal="91193",
            producto_observado="Enalapril 10 Mg Caja con 30 Tabletas",
            origen=OrigenObservacionPrecio.WEB,
        )


def test_usuario_verifica_fuente_pendiente_y_la_usa_para_cotizar(cliente: TestClient):
    cotizacion_id, partida_id, usuario_id = _preparar_enalapril(cliente)
    original = _web(
        cliente,
        cotizacion_id=cotizacion_id,
        partida_id=partida_id,
        usuario_id=usuario_id,
        disponibilidad="Disponibilidad por confirmar",
    )

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    assert pagina.status_code == 200
    assert "Por confirmar" in pagina.text
    assert "Verifiqué fuente · usar para cotizar" in pagina.text
    assert "confirmas que abriste la fuente" in pagina.text

    respuesta = cliente.post(
        f"/cotizaciones/{cotizacion_id}/decisiones-precio/{partida_id}"
        f"/confirmar-web/{original.id}",
        data={"csrf_token": _csrf(pagina.text)},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == f"/cotizaciones/{cotizacion_id}/proveedores"

    with cliente.app.state.fabrica_sesiones() as sesion:
        original_actual = sesion.get(ObservacionPrecio, original.id)
        assert original_actual is not None
        assert original_actual.origen == OrigenObservacionPrecio.WEB.value
        assert original_actual.entrega_viable is None
        assert original_actual.disponibilidad == "Disponibilidad por confirmar"

        normalizacion = sesion.get(NormalizacionPartida, partida_id)
        assert normalizacion is not None
        observaciones = list(
            sesion.scalars(
                select(ObservacionPrecio)
                .where(ObservacionPrecio.clave_producto == clave_producto(normalizacion))
                .order_by(ObservacionPrecio.creado_en.asc())
            )
        )
        assert len(observaciones) == 2
        confirmada = observaciones[-1]
        assert confirmada.id != original.id
        assert confirmada.origen == OrigenObservacionPrecio.MANUAL.value
        assert confirmada.entrega_viable is True
        assert confirmada.precio_total == Decimal("29.00")
        assert confirmada.fuente == original.fuente
        assert confirmada.capturada_por_usuario_id == usuario_id
        evidencia = confirmada.evidencia_identidad or {}
        assert evidencia["confirmacion_manual_fuente_web"]["observacion_web_id"] == original.id

        seleccion = listar_selecciones_actuales(sesion, cotizacion_id)[partida_id]
        assert seleccion.referencia_estable_id == confirmada.id

    pagina_repetida = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    respuesta_repetida = cliente.post(
        f"/cotizaciones/{cotizacion_id}/decisiones-precio/{partida_id}"
        f"/confirmar-web/{original.id}",
        data={"csrf_token": _csrf(pagina_repetida.text)},
        follow_redirects=False,
    )
    assert respuesta_repetida.status_code == 303

    with cliente.app.state.fabrica_sesiones() as sesion:
        normalizacion = sesion.get(NormalizacionPartida, partida_id)
        assert normalizacion is not None
        observaciones = list(
            sesion.scalars(
                select(ObservacionPrecio).where(
                    ObservacionPrecio.clave_producto == clave_producto(normalizacion)
                )
            )
        )
        assert len(observaciones) == 2


def test_atajo_no_aparece_para_agotado_ni_promocion(cliente: TestClient):
    cotizacion_id, partida_id, usuario_id = _preparar_enalapril(cliente)
    agotada = _web(
        cliente,
        cotizacion_id=cotizacion_id,
        partida_id=partida_id,
        usuario_id=usuario_id,
        disponibilidad="Agotado",
    )
    promocion = _web(
        cliente,
        cotizacion_id=cotizacion_id,
        partida_id=partida_id,
        usuario_id=usuario_id,
        disponibilidad="Disponibilidad por confirmar",
        promocion=True,
    )

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    assert pagina.status_code == 200
    assert "Confirmar con proveedor" in pagina.text
    assert "Verifiqué fuente · usar para cotizar" not in pagina.text

    with cliente.app.state.fabrica_sesiones() as sesion:
        with pytest.raises(ValueError, match="falta de disponibilidad"):
            confirmar_fuente_web_y_usar_como_referencia(
                sesion,
                cotizacion_id=cotizacion_id,
                partida_id=partida_id,
                usuario_id=usuario_id,
                observacion_web_id=agotada.id,
            )
        with pytest.raises(ValueError, match="promoción"):
            confirmar_fuente_web_y_usar_como_referencia(
                sesion,
                cotizacion_id=cotizacion_id,
                partida_id=partida_id,
                usuario_id=usuario_id,
                observacion_web_id=promocion.id,
            )
