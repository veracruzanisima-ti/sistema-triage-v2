"""La navegación conserva contexto visual sin alterar decisiones de negocio."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from triage.cotizaciones.modelos import Cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.normalizacion.modelos import NormalizacionPartida
from triage.usuarios.modelos import Usuario


def _preparar_partida(cliente: TestClient) -> tuple[str, str]:
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario).limit(1))
        assert usuario is not None
        cotizacion = Cotizacion(
            referencia="UX-FOCO-PARTIDA",
            referencia_fijada_manual=True,
            codigo_postal_consulta="91000",
        )
        sesion.add(cotizacion)
        sesion.flush()
        documento = Documento(
            cotizacion_id=cotizacion.id,
            nombre_original="ux-foco.pdf",
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
        return cotizacion.id, partida.id


def test_proveedores_expone_destino_estable_y_captura_manual_en_partida(
    cliente: TestClient,
):
    cotizacion_id, partida_id = _preparar_partida(cliente)

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")

    assert pagina.status_code == 200
    assert f'id="partida-proveedor-{partida_id}"' in pagina.text
    assert f'data-partida-proveedor="{partida_id}"' in pagina.text
    assert "triage-foco-proveedores" in pagina.text
    assert "tarjeta-enfocada" in pagina.text
    assert (
        f"/cotizaciones/{cotizacion_id}/historico?volver=proveedores"
        f"&partida_objetivo={partida_id}#partida-{partida_id}"
    ) in pagina.text


def test_revision_final_recuerda_partida_tras_acciones_y_acepta_enlace_directo(
    cliente: TestClient,
):
    cotizacion_id, partida_id = _preparar_partida(cliente)

    pagina = cliente.get(
        f"/cotizaciones/{cotizacion_id}/revision-final",
        params={"partida_objetivo": partida_id},
    )

    assert pagina.status_code == 200
    assert f'id="partida-revision-{partida_id}"' in pagina.text
    assert f'data-partida-revision="{partida_id}"' in pagina.text
    assert "triage-foco-revision-final" in pagina.text
    assert 'parametros.get("partida_objetivo")' in pagina.text
    assert "tarjeta-enfocada" in pagina.text
