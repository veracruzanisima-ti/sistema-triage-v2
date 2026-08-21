"""La revisión final prioriza lectura rápida sin ocultar los conteos auditables."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from triage.cotizaciones.modelos import Cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.normalizacion.modelos import NormalizacionPartida
from triage.usuarios.modelos import Usuario


def test_revision_muestra_estados_compactos_y_conserva_detalle(cliente: TestClient):
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario).limit(1))
        assert usuario is not None
        cotizacion = Cotizacion(
            referencia="RESUMEN-VISUAL",
            referencia_fijada_manual=True,
        )
        sesion.add(cotizacion)
        sesion.flush()
        documento = Documento(
            cotizacion_id=cotizacion.id,
            nombre_original="resumen-visual.pdf",
            mime_type="application/pdf",
            tamano_bytes=10,
            sha256="7" * 64,
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
        cotizacion_id = cotizacion.id

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/revision-final")

    assert pagina.status_code == 200
    assert 'aria-label="Resumen de avance de la cotización"' in pagina.text
    assert ">Preparación</span>" in pagina.text
    assert ">Referencias</span>" in pagina.text
    assert ">Fiscal</span>" in pagina.text
    assert ">Precio final</span>" in pagina.text
    assert ">Alertas</span>" in pagina.text
    assert "Ver conteos detallados" in pagina.text
    assert "1 incluidas" in pagina.text
    assert "0 con referencia estable" in pagina.text
    assert "1 fiscales pendientes" in pagina.text
    assert "1 precios finales pendientes" in pagina.text
