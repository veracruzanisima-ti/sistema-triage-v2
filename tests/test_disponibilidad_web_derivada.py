"""La evidencia web explícita puede habilitar una referencia sin reescribir el dato crudo."""

import re
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from triage.cotizaciones.servicio import crear_cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.historico.disponibilidad import resolver_disponibilidad_operativa
from triage.historico.modelos import ObservacionPrecio, OrigenObservacionPrecio
from triage.historico.servicio import crear_observacion_precio
from triage.normalizacion.modelos import NormalizacionPartida
from triage.usuarios.modelos import Usuario


@pytest.mark.parametrize(
    ("entrega_viable", "disponibilidad", "esperado"),
    [
        (None, "100 disponibles (texto en página).", True),
        (None, "Disponible (Agregar al carrito).", True),
        (None, "En existencia", True),
        (None, "Consulta disponibilidad", None),
        (None, "Ingresa un código postal para ver disponibilidad", None),
        (None, "Sujeto a disponibilidad", None),
        (None, "Agotado", False),
        (None, "Sin existencias", False),
        (True, "Agotado", False),
        (False, "100 disponibles", False),
    ],
)
def test_resolver_disponibilidad_operativa_conservador(
    entrega_viable: bool | None,
    disponibilidad: str,
    esperado: bool | None,
):
    assert (
        resolver_disponibilidad_operativa(
            entrega_viable=entrega_viable,
            disponibilidad=disponibilidad,
        )
        is esperado
    )


def test_observacion_solo_infiere_texto_para_origen_web():
    web = ObservacionPrecio(
        origen=OrigenObservacionPrecio.WEB.value,
        disponibilidad="100 disponibles",
        entrega_viable=None,
    )
    manual = ObservacionPrecio(
        origen=OrigenObservacionPrecio.MANUAL.value,
        disponibilidad="100 disponibles",
        entrega_viable=None,
    )

    assert web.disponibilidad_operativa is True
    assert manual.disponibilidad_operativa is None


def _csrf(html: str) -> str:
    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF")
    return coincidencia.group(1)


def test_resultado_web_existente_con_stock_explicito_se_puede_cotizar(
    cliente: TestClient,
):
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario).limit(1))
        assert usuario is not None
        cotizacion = crear_cotizacion(sesion, "WEB-STOCK-EXPLICITO")
        cotizacion.codigo_postal_consulta = "91193"
        documento = Documento(
            cotizacion_id=cotizacion.id,
            nombre_original="stock.pdf",
            mime_type="application/pdf",
            tamano_bytes=10,
            sha256="8" * 64,
            estado=EstadoDocumento.REVISADO.value,
        )
        sesion.add(documento)
        sesion.flush()
        partida = PartidaDocumento(
            documento_id=documento.id,
            orden=1,
            producto_solicitado="LINAGLIPTINA",
            concentracion="5 mg",
            forma_farmaceutica_dispositivo="tabletas",
            presentacion_solicitada="Caja con 30 tabletas",
            cantidad=Decimal("1"),
            unidad_medida="caja",
        )
        sesion.add(partida)
        sesion.flush()
        normalizacion = NormalizacionPartida(
            partida_documento_id=partida.id,
            producto="LINAGLIPTINA",
            concentracion="5 mg",
            forma_dispositivo="tabletas",
            presentacion="Caja con 30 tabletas",
            confirmada_por_usuario_id=usuario.id,
        )
        sesion.add(normalizacion)
        sesion.commit()

        observacion = crear_observacion_precio(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_documento_id=partida.id,
            usuario_id=usuario.id,
            proveedor="Farmatodo",
            fuente="https://ejemplo.invalid/trayenta",
            precio_antes_iva=None,
            iva_porcentaje=None,
            precio_total=Decimal("2301.00"),
            es_promocion=False,
            condiciones_promocion=None,
            disponibilidad="100 disponibles (texto en página).",
            entrega_viable=None,
            codigo_postal="91193",
            producto_observado="Trayenta (Linagliptina) 5 mg, 30 tabletas",
            origen=OrigenObservacionPrecio.WEB,
        )
        cotizacion_id = cotizacion.id
        partida_id = partida.id
        observacion_id = observacion.id

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    assert pagina.status_code == 200
    assert "100 disponibles (texto en página)." in pagina.text
    assert 'class="estado estado-disponible">Disponible</span>' in pagina.text
    assert ">Usar para cotizar</button>" in pagina.text
    assert "Disponibilidad por confirmar" not in pagina.text

    respuesta = cliente.post(
        f"/cotizaciones/{cotizacion_id}/decisiones-precio/{partida_id}",
        data={
            "csrf_token": _csrf(pagina.text),
            "rol": "REFERENCIA_ESTABLE",
            "observacion_id": observacion_id,
            "volver": "proveedores",
        },
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
