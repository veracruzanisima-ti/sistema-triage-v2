"""Integración visual de la sugerencia de posible corrección de producto."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from triage.cotizaciones.modelos import Cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.historico.servicio import clave_producto
from triage.normalizacion.modelos import NormalizacionPartida
from triage.proveedores.modelos import (
    CandidatoWebDescartado,
    ConsultaWeb,
    EstadoConsultaWeb,
)
from triage.usuarios.modelos import Usuario


def test_pantalla_sugiere_lercanidipino_pero_conserva_el_descarte(cliente: TestClient):
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario).limit(1))
        assert usuario is not None

        cotizacion = Cotizacion(
            referencia="CORRECCION-WEB",
            referencia_fijada_manual=True,
            codigo_postal_consulta="91000",
        )
        sesion.add(cotizacion)
        sesion.flush()
        documento = Documento(
            cotizacion_id=cotizacion.id,
            nombre_original="correccion.pdf",
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
            producto_solicitado="LECARDIPINO",
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
            producto="Lecardipino",
            concentracion="10 mg",
            forma_dispositivo="tabletas",
            presentacion="Caja con 30 tabletas de 10 mg",
            confirmada_por_usuario_id=usuario.id,
        )
        sesion.add(normalizacion)
        sesion.flush()

        consulta = ConsultaWeb(
            cotizacion_id=cotizacion.id,
            partida_documento_id=partida.id,
            clave_producto=clave_producto(normalizacion),
            modelo="modelo-prueba",
            estado=EstadoConsultaWeb.COMPLETADA.value,
            criterios_busqueda={
                "producto": "Lecardipino",
                "marca": None,
                "concentracion": "10 mg",
                "forma_dispositivo": "tabletas",
                "presentacion": "Caja con 30 tabletas de 10 mg",
                "codigo_postal": "91000",
            },
            terminos_ampliados=["tableta | tabletas | tab", "10 mg | 0.01 g"],
            intentos=2,
            candidatos=1,
            guardados=0,
            descartados=1,
            ejecutada_por_usuario_id=usuario.id,
        )
        sesion.add(consulta)
        sesion.flush()
        sesion.add(
            CandidatoWebDescartado(
                consulta_web_id=consulta.id,
                proveedor="Farmacias Benavides",
                producto_observado="Evipress 10 mg Lercanidipino 30 Tabletas",
                url="https://farmacia.example/evipress",
                precio_observado=Decimal("1299"),
                motivos=["producto distinto"],
                intento_busqueda=1,
            )
        )
        sesion.commit()
        cotizacion_id = cotizacion.id

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")

    assert pagina.status_code == 200
    assert "¿Quisiste decir Lercanidipino?" in pagina.text
    assert "Producto preparado actualmente: <strong>Lecardipino</strong>" in pagina.text
    assert "Farmacias Benavides" in pagina.text
    assert "Triage mantuvo esos resultados descartados" in pagina.text
    assert "Aún no hay precios observados" in pagina.text
    assert "producto distinto" in pagina.text
