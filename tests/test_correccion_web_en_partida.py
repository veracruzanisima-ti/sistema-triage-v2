"""Flujo de corrección web desde proveedores hasta la partida exacta de preparación."""

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


def _preparar_caso_lercanidipino(cliente: TestClient) -> tuple[str, str]:
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario).limit(1))
        assert usuario is not None

        cotizacion = Cotizacion(
            referencia="CORRECCION-DIRECTA",
            referencia_fijada_manual=True,
            codigo_postal_consulta="91000",
        )
        sesion.add(cotizacion)
        sesion.flush()
        documento = Documento(
            cotizacion_id=cotizacion.id,
            nombre_original="correccion-directa.pdf",
            mime_type="application/pdf",
            tamano_bytes=10,
            sha256="e" * 64,
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
        return cotizacion.id, partida.id


def test_correccion_web_lleva_a_partida_y_ofrece_aplicarla_sin_guardar(
    cliente: TestClient,
):
    cotizacion_id, partida_id = _preparar_caso_lercanidipino(cliente)

    proveedores = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    assert proveedores.status_code == 200
    destino = (
        f"/cotizaciones/{cotizacion_id}/normalizacion"
        f"?partida_objetivo={partida_id}#partida-{partida_id}"
    )
    assert f'href="{destino}"' in proveedores.text

    preparacion = cliente.get(
        f"/cotizaciones/{cotizacion_id}/normalizacion",
        params={"partida_objetivo": partida_id},
    )
    assert preparacion.status_code == 200
    assert f'id="partida-{partida_id}"' in preparacion.text
    assert "Sugerencia de corrección: Lercanidipino" in preparacion.text
    assert "Farmacias Benavides" in preparacion.text
    assert 'data-sugerencia="Lercanidipino"' in preparacion.text
    assert ">Usar Lercanidipino</button>" in preparacion.text
    assert 'name="partida_0_producto" value="Lecardipino"' in preparacion.text
    assert "Nada cambia hasta que pulses Guardar preparación" in preparacion.text

    with cliente.app.state.fabrica_sesiones() as sesion:
        normalizacion = sesion.scalar(
            select(NormalizacionPartida).where(
                NormalizacionPartida.partida_documento_id == partida_id
            )
        )
        assert normalizacion is not None
        assert normalizacion.producto == "Lecardipino"


def test_sugerencia_deja_de_mostrarse_si_la_preparacion_ya_cambio(cliente: TestClient):
    cotizacion_id, partida_id = _preparar_caso_lercanidipino(cliente)

    with cliente.app.state.fabrica_sesiones() as sesion:
        normalizacion = sesion.scalar(
            select(NormalizacionPartida).where(
                NormalizacionPartida.partida_documento_id == partida_id
            )
        )
        assert normalizacion is not None
        normalizacion.producto = "Lercanidipino"
        sesion.commit()

    preparacion = cliente.get(
        f"/cotizaciones/{cotizacion_id}/normalizacion",
        params={"partida_objetivo": partida_id},
    )

    assert preparacion.status_code == 200
    assert "Sugerencia de corrección: Lercanidipino" not in preparacion.text
    assert "La sugerencia web que te trajo aquí ya no está vigente" in preparacion.text
    assert 'value="Lercanidipino"' in preparacion.text
