"""La paleta visual mantiene significado consistente sin depender sólo del color."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from triage.cotizaciones.servicio import crear_cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.historico.modelos import OrigenObservacionPrecio
from triage.historico.servicio import crear_observacion_precio
from triage.normalizacion.modelos import NormalizacionPartida
from triage.usuarios.modelos import Usuario


def _preparar(cliente: TestClient) -> tuple[str, str, str]:
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario).limit(1))
        assert usuario is not None
        cotizacion = crear_cotizacion(sesion, "PALETA-SEMANTICA")
        cotizacion.codigo_postal_consulta = "91000"
        documento = Documento(
            cotizacion_id=cotizacion.id,
            nombre_original="paleta.pdf",
            mime_type="application/pdf",
            tamano_bytes=10,
            sha256="9" * 64,
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
        sesion.add(
            NormalizacionPartida(
                partida_documento_id=partida.id,
                producto="DAPAGLIFLOZINA",
                concentracion="10 mg",
                forma_dispositivo="tabletas",
                presentacion="Caja con 28 tabletas",
                confirmada_por_usuario_id=usuario.id,
            )
        )
        sesion.commit()
        return cotizacion.id, partida.id, usuario.id


def _guardar(
    cliente: TestClient,
    cotizacion_id: str,
    partida_id: str,
    usuario_id: str,
    *,
    proveedor: str,
    entrega_viable: bool | None,
    promocion: bool = False,
):
    with cliente.app.state.fabrica_sesiones() as sesion:
        crear_observacion_precio(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_id,
            usuario_id=usuario_id,
            proveedor=proveedor,
            fuente=f"https://ejemplo.invalid/{proveedor.casefold().replace(' ', '-')}",
            precio_antes_iva=None,
            iva_porcentaje=None,
            precio_total=Decimal("800.00"),
            es_promocion=promocion,
            condiciones_promocion="Precio temporal" if promocion else None,
            disponibilidad=(
                "Disponible"
                if entrega_viable is True
                else "Agotado" if entrega_viable is False else "Disponible reportado; falta confirmar"
            ),
            entrega_viable=entrega_viable,
            codigo_postal="91000",
            producto_observado="Dapagliflozina 10 mg 28 tabletas",
            origen=OrigenObservacionPrecio.WEB,
        )


def test_proveedores_diferencia_pendiente_identidad_promocion_y_disponibilidad(
    cliente: TestClient,
):
    cotizacion_id, partida_id, usuario_id = _preparar(cliente)
    _guardar(
        cliente,
        cotizacion_id,
        partida_id,
        usuario_id,
        proveedor="Farmacia promoción pendiente",
        entrega_viable=None,
        promocion=True,
    )
    _guardar(
        cliente,
        cotizacion_id,
        partida_id,
        usuario_id,
        proveedor="Farmacia sin existencia",
        entrega_viable=False,
    )
    _guardar(
        cliente,
        cotizacion_id,
        partida_id,
        usuario_id,
        proveedor="Farmacia disponible",
        entrega_viable=True,
    )

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")

    assert pagina.status_code == 200
    assert 'class="estado estado-pendiente">Por confirmar</span>' in pagina.text
    assert 'class="estado estado-identidad">Nombre genérico visible</span>' in pagina.text
    assert 'class="estado estado-promocion">Oferta / promoción</span>' in pagina.text
    assert 'class="estado estado-no-disponible">Sin disponibilidad</span>' in pagina.text
    assert 'class="estado estado-disponible">Disponible</span>' in pagina.text


def test_historico_reutiliza_mismos_colores_semanticos(cliente: TestClient):
    cotizacion_id, partida_id, usuario_id = _preparar(cliente)
    _guardar(
        cliente,
        cotizacion_id,
        partida_id,
        usuario_id,
        proveedor="Histórico promoción",
        entrega_viable=None,
        promocion=True,
    )
    _guardar(
        cliente,
        cotizacion_id,
        partida_id,
        usuario_id,
        proveedor="Histórico agotado",
        entrega_viable=False,
    )
    _guardar(
        cliente,
        cotizacion_id,
        partida_id,
        usuario_id,
        proveedor="Histórico disponible",
        entrega_viable=True,
    )

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/historico")

    assert pagina.status_code == 200
    assert 'class="estado estado-pendiente">Por confirmar</span>' in pagina.text
    assert 'class="estado estado-promocion">Promoción</span>' in pagina.text
    assert 'class="estado estado-no-disponible">No viable</span>' in pagina.text
    assert 'class="estado estado-disponible">Disponible confirmado</span>' in pagina.text


def test_base_define_familias_semanticas_suaves(cliente: TestClient):
    pagina = cliente.get("/cotizaciones")

    assert pagina.status_code == 200
    for clase in (
        ".estado-neutral",
        ".estado-identidad",
        ".estado-disponible",
        ".estado-pendiente",
        ".estado-promocion",
        ".estado-no-disponible",
        ".estado-atencion",
    ):
        assert clase in pagina.text
