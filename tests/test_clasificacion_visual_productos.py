"""Clasificación visual descriptiva sin inferir patente ni equivalencias no demostradas."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from triage.cotizaciones.modelos import Cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.historico.modelos import OrigenObservacionPrecio
from triage.historico.servicio import crear_observacion_precio
from triage.normalizacion.modelos import NormalizacionPartida
from triage.usuarios.modelos import Usuario


def _preparar(cliente: TestClient) -> tuple[str, str, str]:
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario).limit(1))
        assert usuario is not None
        cotizacion = Cotizacion(
            referencia="CLASIFICACION-VISUAL",
            codigo_postal_consulta="91000",
        )
        sesion.add(cotizacion)
        sesion.flush()
        documento = Documento(
            cotizacion_id=cotizacion.id,
            nombre_original="clasificacion.pdf",
            mime_type="application/pdf",
            tamano_bytes=10,
            sha256="c" * 64,
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
    producto_observado: str,
    evidencia_identidad=None,
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
            es_promocion=False,
            condiciones_promocion=None,
            disponibilidad="Disponible",
            entrega_viable=True,
            codigo_postal="91000",
            producto_observado=producto_observado,
            origen=OrigenObservacionPrecio.WEB,
            evidencia_identidad=evidencia_identidad,
        )


def test_ui_distingue_marca_comercial_generico_visible_y_marca_propia_declarada(
    cliente: TestClient,
):
    cotizacion_id, partida_id, usuario_id = _preparar(cliente)
    _guardar(
        cliente,
        cotizacion_id,
        partida_id,
        usuario_id,
        proveedor="Farmacia Marca",
        producto_observado="Forxiga 10 mg 28 tabletas",
        evidencia_identidad={
            "fuente": "COFEPRIS",
            "numero_registro": "REG-FORXIGA",
            "denominacion_distintiva": "FORXIGA",
            "denominacion_generica": "DAPAGLIFLOZINA",
            "estado": "VIGENTE",
            "importacion_id": "snapshot-prueba",
            "sha256_importacion": "d" * 64,
        },
    )
    _guardar(
        cliente,
        cotizacion_id,
        partida_id,
        usuario_id,
        proveedor="Farmacia Genérico",
        producto_observado="Dapagliflozina 10 mg 28 tabletas",
    )
    _guardar(
        cliente,
        cotizacion_id,
        partida_id,
        usuario_id,
        proveedor="Farmacia Marca Propia",
        producto_observado="Dapagliflozina 10 mg Marca Propia 28 tabletas",
    )

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")

    assert pagina.status_code == 200
    assert pagina.text.count("Marca comercial") == 1
    assert pagina.text.count("Nombre genérico visible") == 1
    assert pagina.text.count("Marca propia declarada") == 1
    assert "FORXIGA" in pagina.text
    assert "→ DAPAGLIFLOZINA" in pagina.text
    assert "Fuente web" in pagina.text
    assert "Patente" not in pagina.text


def test_cofepris_con_misma_distintiva_y_generica_se_muestra_como_generico_registrado(
    cliente: TestClient,
):
    cotizacion_id, partida_id, usuario_id = _preparar(cliente)
    _guardar(
        cliente,
        cotizacion_id,
        partida_id,
        usuario_id,
        proveedor="Farmacia Registro",
        producto_observado="Dapagliflozina 10 mg 28 tabletas",
        evidencia_identidad={
            "fuente": "COFEPRIS",
            "numero_registro": "REG-GENERICO",
            "denominacion_distintiva": "DAPAGLIFLOZINA",
            "denominacion_generica": "DAPAGLIFLOZINA",
            "estado": "VIGENTE",
            "importacion_id": "snapshot-prueba",
            "sha256_importacion": "e" * 64,
        },
    )

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")

    assert pagina.status_code == 200
    assert "Nombre genérico registrado" in pagina.text
    assert "Marca comercial" not in pagina.text
    assert "Patente" not in pagina.text
