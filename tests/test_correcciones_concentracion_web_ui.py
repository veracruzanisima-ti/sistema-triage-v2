"""Integración visual de la alerta conservadora de concentración."""

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


def test_metilprednisolona_alerta_inconsistencia_sin_autocorregir(
    cliente: TestClient,
):
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario).limit(1))
        assert usuario is not None
        cotizacion = Cotizacion(
            referencia="CONCENTRACION-WEB",
            referencia_fijada_manual=True,
            codigo_postal_consulta="91000",
        )
        sesion.add(cotizacion)
        sesion.flush()
        documento = Documento(
            cotizacion_id=cotizacion.id,
            nombre_original="solicitud.pdf",
            mime_type="application/pdf",
            tamano_bytes=12,
            sha256="d" * 64,
            contenido_original=b"%PDF-prueba%",
            estado=EstadoDocumento.REVISADO.value,
        )
        sesion.add(documento)
        sesion.flush()
        partida = PartidaDocumento(
            documento_id=documento.id,
            orden=1,
            producto_solicitado="ACETATO DE METILPREDNISOLONA",
            concentracion="40 mg / 2 mL",
            forma_farmaceutica_dispositivo="Suspensión inyectable",
            presentacion_solicitada="Frasco ámpula 2 mL",
            cantidad=Decimal("1"),
            unidad_medida="frasco",
        )
        sesion.add(partida)
        sesion.flush()
        normalizacion = NormalizacionPartida(
            partida_documento_id=partida.id,
            producto="ACETATO DE METILPREDNISOLONA",
            concentracion="40 mg / 2 mL",
            forma_dispositivo="Suspensión inyectable",
            presentacion="Frasco ámpula 2 mL",
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
                "producto": normalizacion.producto,
                "marca": None,
                "concentracion": normalizacion.concentracion,
                "forma_dispositivo": normalizacion.forma_dispositivo,
                "presentacion": normalizacion.presentacion,
                "codigo_postal": "91000",
            },
            terminos_ampliados=["40 mg | 0.04 g", "2 mL | 0.002 L"],
            intentos=2,
            candidatos=2,
            guardados=0,
            descartados=2,
            ejecutada_por_usuario_id=usuario.id,
        )
        sesion.add(consulta)
        sesion.flush()
        sesion.add_all(
            [
                CandidatoWebDescartado(
                    consulta_web_id=consulta.id,
                    proveedor="Farmatodo",
                    producto_observado=(
                        "Metilprednisolona Suspensión Inyectable 40 mg/mL "
                        "Frasco Ámpula 2 mL"
                    ),
                    url="https://farmatodo.example/metilprednisolona",
                    precio_observado=Decimal("143.50"),
                    motivos=["producto distinto"],
                    intento_busqueda=1,
                ),
                CandidatoWebDescartado(
                    consulta_web_id=consulta.id,
                    proveedor="Curitek",
                    producto_observado=(
                        "ACETATO DE METILPREDNISOLONA 40 MG/ML "
                        "INYECTABLE VIAL 2 ML"
                    ),
                    url="https://curitek.example/metilprednisolona",
                    precio_observado=Decimal("85.00"),
                    motivos=["faltan datos suficientes para comprobar coincidencia"],
                    intento_busqueda=1,
                ),
            ]
        )
        sesion.commit()
        cotizacion_id = cotizacion.id
        partida_id = partida.id
        documento_id = documento.id

    proveedores = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    assert proveedores.status_code == 200
    assert "Posible corrección de concentración: 40 mg/mL" in proveedores.text
    assert "2 fuentes independientes convergen en 40 mg/mL" in proveedores.text
    assert "Revisar concentración contra original" in proveedores.text

    preparacion = cliente.get(
        f"/cotizaciones/{cotizacion_id}/normalizacion?partida_objetivo={partida_id}"
        f"#partida-{partida_id}"
    )
    assert preparacion.status_code == 200
    assert "Posible inconsistencia en la solicitud" in preparacion.text
    assert "La solicitud revisada conserva: <strong>40 mg / 2 mL</strong>" in preparacion.text
    assert "otra concentración: <strong>40 mg/mL</strong>" in preparacion.text
    assert "Usar 40 mg/mL" not in preparacion.text
    assert 'data-sugerencia="40 mg/mL"' not in preparacion.text
    assert "Abrir original" in preparacion.text
    assert f"/documentos/{documento_id}/original" in preparacion.text

    with cliente.app.state.fabrica_sesiones() as sesion:
        normalizacion_actual = sesion.get(NormalizacionPartida, partida_id)
        assert normalizacion_actual is not None
        assert normalizacion_actual.concentracion == "40 mg / 2 mL"
