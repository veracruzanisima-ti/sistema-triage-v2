from types import SimpleNamespace

from triage.cotizaciones.rutas import _siguiente_paso
from triage.documentos.modelos import EstadoDocumento
from triage.historico.decisiones_servicio import SeleccionActual
from triage.normalizacion.servicio import ResumenNormalizacion


def _documento(estado: EstadoDocumento, documento_id: str = "doc-1"):
    return SimpleNamespace(id=documento_id, estado=estado.value)


def test_siguiente_paso_sube_documento_si_cotizacion_esta_vacia():
    paso = _siguiente_paso(
        "cot-1",
        [],
        ResumenNormalizacion(total=0, preparados=0),
    )

    assert paso["etapa"] == "Sube y analiza"
    assert paso["accion"] == "Subir y analizar"
    assert paso["url"] == "/cotizaciones/cot-1/documentos/nuevo"


def test_siguiente_paso_prioriza_revision_humana():
    paso = _siguiente_paso(
        "cot-1",
        [_documento(EstadoDocumento.ANALIZADO, "doc-pendiente")],
        ResumenNormalizacion(total=1, preparados=0),
    )

    assert paso["etapa"] == "Revisa"
    assert paso["url"] == "/cotizaciones/cot-1/documentos/doc-pendiente"


def test_siguiente_paso_confirma_producto_despues_de_revisar():
    paso = _siguiente_paso(
        "cot-1",
        [_documento(EstadoDocumento.REVISADO)],
        ResumenNormalizacion(total=2, preparados=1),
    )

    assert paso["etapa"] == "Confirma producto"
    assert paso["accion"] == "Confirmar producto"
    assert paso["url"] == "/cotizaciones/cot-1/normalizacion"


def test_siguiente_paso_busca_precio_cuando_productos_estan_confirmados():
    paso = _siguiente_paso(
        "cot-1",
        [_documento(EstadoDocumento.REVISADO)],
        ResumenNormalizacion(total=2, preparados=2),
    )

    assert paso["etapa"] == "Busca precio"
    assert paso["accion"] == "Buscar precios"
    assert paso["url"] == "/cotizaciones/cot-1/proveedores"


def test_siguiente_paso_revisa_cotizacion_cuando_todas_tienen_referencia():
    paso = _siguiente_paso(
        "cot-1",
        [_documento(EstadoDocumento.REVISADO)],
        ResumenNormalizacion(total=2, preparados=2),
        {
            "partida-1": SeleccionActual(referencia_estable_id="obs-1"),
            "partida-2": SeleccionActual(referencia_estable_id="obs-2"),
        },
    )

    assert paso["etapa"] == "Revisa cotización"
    assert paso["accion"] == "Revisar cotización"
    assert paso["url"] == "/cotizaciones/cot-1/revision-final"


def test_interfaces_operativas_incluyen_control_para_volver_arriba(cliente):
    pagina = cliente.get("/cotizaciones/nueva")

    assert pagina.status_code == 200
    assert 'id="volver-arriba"' in pagina.text
    assert "↑ Volver arriba" in pagina.text
    assert "window.scrollTo" in pagina.text
    assert "prefers-reduced-motion" in pagina.text
