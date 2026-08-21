"""Distingue evidencia histórica de la evaluación local vigente de descartes web."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from triage.cotizaciones.modelos import Cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.normalizacion.modelos import NormalizacionPartida
from triage.proveedores.cofepris_modelos import ImportacionCofepris, RegistroCofepris
from triage.proveedores.modelos import CandidatoWebDescartado, ConsultaWeb, EstadoConsultaWeb
from triage.proveedores.reevaluacion_rutas import evaluar_descarte_con_reglas_actuales
from triage.usuarios.modelos import Usuario


def _registro(
    importacion_id: str,
    *,
    numero: str,
    cantidad: str,
) -> RegistroCofepris:
    return RegistroCofepris(
        numero_registro=numero,
        importacion_id=importacion_id,
        denominacion_distintiva="FORXIGA",
        denominacion_distintiva_normalizada="FORXIGA",
        denominacion_generica="DAPAGLIFLOZINA",
        componentes_genericos_normalizados=["DAPAGLIFLOZINA"],
        estado="VIGENTE",
        forma_farmaceutica="TABLETA",
        via_administracion="ORAL",
        tipo_medicamento="ALOPATICO",
        presentacion="CAJA",
        cantidad=cantidad,
        fraccion_sanitaria="IV",
        sustancia_quimica="DAPAGLIFLOZINA",
        titular="TITULAR DE PRUEBA",
        fecha_emision="2026-01-01",
    )


def _preparar_caso(cliente: TestClient):
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario).limit(1))
        assert usuario is not None

        importacion = ImportacionCofepris(
            cargada_por_usuario_id=usuario.id,
            archivo="cofepris-dapagliflozina.xlsx",
            sha256="d" * 64,
            registros_cargados=2,
            registros_vigentes=2,
            registros_sin_identidad_util=0,
            numeros_registro_duplicados=0,
        )
        sesion.add(importacion)
        sesion.flush()
        sesion.add_all(
            [
                _registro(importacion.id, numero="FORXIGA-28", cantidad="28 TABLETAS"),
                _registro(importacion.id, numero="FORXIGA-30", cantidad="30 TABLETAS"),
            ]
        )

        cotizacion = Cotizacion(
            referencia="DESCARTES-HISTORICOS",
            codigo_postal_consulta="91193",
        )
        sesion.add(cotizacion)
        sesion.flush()
        documento = Documento(
            cotizacion_id=cotizacion.id,
            nombre_original="dapagliflozina.pdf",
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
            producto_solicitado="DAPAGLIFLOZINA",
            concentracion="10 mg",
            forma_farmaceutica_dispositivo="tabletas",
            presentacion_solicitada="Caja con 28 tabletas de 10 mg",
            cantidad=Decimal("1"),
            unidad_medida="caja",
        )
        sesion.add(partida)
        sesion.flush()
        normalizacion = NormalizacionPartida(
            partida_documento_id=partida.id,
            producto="DAPAGLIFLOZINA",
            concentracion="10 mg",
            forma_dispositivo="tabletas",
            presentacion="Caja con 28 tabletas de 10 mg",
            confirmada_por_usuario_id=usuario.id,
        )
        sesion.add(normalizacion)
        sesion.flush()
        consulta = ConsultaWeb(
            cotizacion_id=cotizacion.id,
            partida_documento_id=partida.id,
            clave_producto="historica-dapagliflozina",
            modelo="modelo-antiguo",
            estado=EstadoConsultaWeb.COMPLETADA.value,
            criterios_busqueda={
                "producto": "DAPAGLIFLOZINA",
                "marca": None,
                "concentracion": "10 mg",
                "forma_dispositivo": "tabletas",
                "presentacion": "Caja con 28 tabletas de 10 mg",
                "codigo_postal": "91193",
            },
            terminos_ampliados=[],
            intentos=1,
            candidatos=1,
            guardados=0,
            descartados=1,
            ejecutada_por_usuario_id=usuario.id,
        )
        sesion.add(consulta)
        sesion.flush()
        descartado = CandidatoWebDescartado(
            consulta_web_id=consulta.id,
            proveedor="Farmacias Guadalajara",
            producto_observado="Forxiga 10 mg, 28 Tabletas",
            url="https://ejemplo.invalid/forxiga-28",
            precio_observado=Decimal("1347.96"),
            motivos=[
                "producto distinto",
                "faltan datos suficientes para comprobar coincidencia",
            ],
            intento_busqueda=1,
        )
        sesion.add(descartado)
        sesion.commit()
        return cotizacion.id, partida.id, descartado.id


def test_ui_separa_motivo_historico_de_evaluacion_actual(cliente: TestClient):
    cotizacion_id, partida_id, descartado_id = _preparar_caso(cliente)

    proveedores = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    assert proveedores.status_code == 200
    assert "Motivo registrado en esa búsqueda" in proveedores.text
    assert "Evaluar con reglas actuales" in proveedores.text

    respuesta = cliente.get(
        f"/cotizaciones/{cotizacion_id}/proveedores/{partida_id}"
        f"/descartados/{descartado_id}/evaluacion-actual"
    )
    assert respuesta.status_code == 200
    assert "Motivo registrado en aquella búsqueda" in respuesta.text
    assert "producto distinto" in respuesta.text
    assert "Compatible hoy" in respuesta.text
    assert "Esto no recupera automáticamente el precio" in respuesta.text

    with cliente.app.state.fabrica_sesiones() as sesion:
        descartado = sesion.get(CandidatoWebDescartado, descartado_id)
        assert descartado is not None
        assert descartado.motivos == [
            "producto distinto",
            "faltan datos suficientes para comprobar coincidencia",
        ]


def test_generico_visible_sin_conteo_pierde_producto_distinto_pero_sigue_incompleto(
    cliente: TestClient,
):
    cotizacion_id, partida_id, _ = _preparar_caso(cliente)
    with cliente.app.state.fabrica_sesiones() as sesion:
        normalizacion = sesion.get(NormalizacionPartida, partida_id)
        assert normalizacion is not None
        candidato = CandidatoWebDescartado(
            consulta_web_id="solo-evaluacion",
            proveedor="Farmacias Especializadas",
            producto_observado=(
                "Forxiga 10 mg | Dapagliflozina | Tableta | Laboratorio AstraZeneca"
            ),
            url="https://ejemplo.invalid/forxiga-sin-conteo",
            precio_observado=Decimal("1858.61"),
            motivos=["producto distinto"],
            intento_busqueda=1,
        )
        evaluacion = evaluar_descarte_con_reglas_actuales(
            sesion,
            normalizacion=normalizacion,
            descartado=candidato,
            codigo_postal="91193",
        )

    assert "producto distinto" not in evaluacion.motivos
    assert evaluacion.motivos == (
        "faltan datos suficientes para comprobar coincidencia",
    )
    assert cotizacion_id
