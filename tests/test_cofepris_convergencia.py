"""Convergencia COFEPRIS para marcas con varios registros vigentes."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from triage.cotizaciones.modelos import Cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.historico.modelos import ObservacionPrecio
from triage.normalizacion.modelos import NormalizacionPartida
from triage.proveedores.base import SolicitudProveedor
from triage.proveedores.cofepris_modelos import ImportacionCofepris, RegistroCofepris
from triage.proveedores.cofepris_servicio import resolver_identidad_cofepris
from triage.proveedores.coincidencia_catalogo import CandidatoCatalogo, evaluar_candidato
from triage.proveedores.descubrimiento_web import CandidatoWeb
from triage.proveedores.servicio import ejecutar_descubrimiento_web
from triage.usuarios.modelos import Usuario


def _snapshot(sesion, usuario_id: str) -> ImportacionCofepris:
    importacion = ImportacionCofepris(
        cargada_por_usuario_id=usuario_id,
        archivo="cofepris-convergencia.xlsx",
        sha256="a" * 64,
        registros_cargados=2,
        registros_vigentes=2,
        registros_sin_identidad_util=0,
        numeros_registro_duplicados=0,
    )
    sesion.add(importacion)
    sesion.flush()
    return importacion


def _registro(
    importacion_id: str,
    *,
    numero: str,
    distintiva: str,
    generica: str,
    componentes: list[str],
    cantidad: str,
    forma: str = "SOLUCION INYECTABLE",
) -> RegistroCofepris:
    return RegistroCofepris(
        numero_registro=numero,
        importacion_id=importacion_id,
        denominacion_distintiva=distintiva,
        denominacion_distintiva_normalizada=distintiva.upper(),
        denominacion_generica=generica,
        componentes_genericos_normalizados=componentes,
        estado="VIGENTE",
        forma_farmaceutica=forma,
        via_administracion="SUBCUTANEA",
        tipo_medicamento="ALOPATICO",
        presentacion="CAJA",
        cantidad=cantidad,
        fraccion_sanitaria="IV",
        sustancia_quimica=generica,
        titular="TITULAR DE PRUEBA",
        fecha_emision="2026-01-01",
    )


def _usuario(cliente: TestClient) -> Usuario:
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario).limit(1))
        assert usuario is not None
        sesion.expunge(usuario)
        return usuario


def test_varios_registros_de_marca_convergen_al_mismo_generico(cliente: TestClient):
    usuario = _usuario(cliente)
    with cliente.app.state.fabrica_sesiones() as sesion:
        importacion = _snapshot(sesion, usuario.id)
        sesion.add_all(
            [
                _registro(
                    importacion.id,
                    numero="LANTUS-VIAL",
                    distintiva="LANTUS",
                    generica="INSULINA GLARGINA",
                    componentes=["INSULINA GLARGINA"],
                    cantidad="1 FRASCO AMPULA 10 ML",
                ),
                _registro(
                    importacion.id,
                    numero="LANTUS-PLUMA",
                    distintiva="LANTUS",
                    generica="INSULINA GLARGINA",
                    componentes=["INSULINA GLARGINA"],
                    cantidad="5 PLUMAS 3 ML",
                ),
            ]
        )
        sesion.commit()

        evidencia = resolver_identidad_cofepris(
            sesion,
            producto_solicitado="INSULINA GLARGINA",
            producto_observado="Lantus 100 U/mL solución inyectable ámpula 10 mL",
        )

        assert evidencia is not None
        assert evidencia.denominacion_distintiva == "LANTUS"
        assert evidencia.denominacion_generica == "INSULINA GLARGINA"
        assert set(evidencia.numeros_registro) == {"LANTUS-VIAL", "LANTUS-PLUMA"}
        assert evidencia.como_json()["registros_coincidentes"] == 2


def test_registros_de_marca_que_divergen_siguen_sin_resolverse(cliente: TestClient):
    usuario = _usuario(cliente)
    with cliente.app.state.fabrica_sesiones() as sesion:
        importacion = _snapshot(sesion, usuario.id)
        sesion.add_all(
            [
                _registro(
                    importacion.id,
                    numero="MARCA-1",
                    distintiva="MARCA MIXTA",
                    generica="INSULINA GLARGINA",
                    componentes=["INSULINA GLARGINA"],
                    cantidad="1 FRASCO AMPULA 10 ML",
                ),
                _registro(
                    importacion.id,
                    numero="MARCA-2",
                    distintiva="MARCA MIXTA",
                    generica="INSULINA GLARGINA / OTRO PRINCIPIO",
                    componentes=["INSULINA GLARGINA", "OTRO PRINCIPIO"],
                    cantidad="5 PLUMAS 3 ML",
                ),
            ]
        )
        sesion.commit()

        assert (
            resolver_identidad_cofepris(
                sesion,
                producto_solicitado="INSULINA GLARGINA",
                producto_observado="Marca Mixta 100 U/mL",
            )
            is None
        )


def test_filas_equivalentes_duplicadas_no_se_convierten_en_convergencia(cliente: TestClient):
    usuario = _usuario(cliente)
    with cliente.app.state.fabrica_sesiones() as sesion:
        importacion = _snapshot(sesion, usuario.id)
        sesion.add_all(
            [
                _registro(
                    importacion.id,
                    numero="DUP-A",
                    distintiva="TRAYENTA",
                    generica="LINAGLIPTINA",
                    componentes=["LINAGLIPTINA"],
                    cantidad="30 TABLETAS",
                    forma="TABLETA",
                ),
                _registro(
                    importacion.id,
                    numero="DUP-B",
                    distintiva="TRAYENTA",
                    generica="LINAGLIPTINA",
                    componentes=["LINAGLIPTINA"],
                    cantidad="30 TABLETAS",
                    forma="TABLETA",
                ),
            ]
        )
        sesion.commit()

        assert (
            resolver_identidad_cofepris(
                sesion,
                producto_solicitado="LINAGLIPTINA",
                producto_observado="TRAYENTA 5 mg 30 tabletas",
            )
            is None
        )


def test_marca_que_ya_muestra_generico_no_cae_como_producto_distinto():
    evaluacion = evaluar_candidato(
        SolicitudProveedor(
            partida_documento_id="partida",
            producto="DAPAGLIFLOZINA",
            marca=None,
            concentracion="10 mg",
            forma_dispositivo="tabletas",
            presentacion=None,
        ),
        CandidatoCatalogo(
            descripcion="Forxiga 10 mg | Dapagliflozina | Tableta | Laboratorio AstraZeneca",
            precio_observado=Decimal("1858.61"),
            stock=None,
            fuente="https://ejemplo.invalid/forxiga",
        ),
    )

    assert "producto distinto" not in evaluacion.motivos


class _DescubridorLantus:
    modelo = "cofepris-convergencia-prueba"

    def buscar(self, _solicitud, *, terminos_adicionales=()):
        return (
            CandidatoWeb(
                proveedor="Farmacia de prueba",
                producto_exacto="Lantus 100 U/mL Solución Inyectable Ámpula 10 mL",
                url="https://ejemplo.invalid/lantus",
                precio_total=Decimal("2113.68"),
                coincidencia_exacta=True,
                disponibilidad="Disponible",
                entrega_viable=True,
            ),
        )


def test_descubrimiento_guarda_marca_si_registros_cofepris_convergen(cliente: TestClient):
    usuario = _usuario(cliente)
    with cliente.app.state.fabrica_sesiones() as sesion:
        importacion = _snapshot(sesion, usuario.id)
        sesion.add_all(
            [
                _registro(
                    importacion.id,
                    numero="LANTUS-VIAL",
                    distintiva="LANTUS",
                    generica="INSULINA GLARGINA",
                    componentes=["INSULINA GLARGINA"],
                    cantidad="1 FRASCO AMPULA 10 ML",
                ),
                _registro(
                    importacion.id,
                    numero="LANTUS-PLUMA",
                    distintiva="LANTUS",
                    generica="INSULINA GLARGINA",
                    componentes=["INSULINA GLARGINA"],
                    cantidad="5 PLUMAS 3 ML",
                ),
            ]
        )
        cotizacion = Cotizacion(
            referencia="COFEPRIS-CONVERGENCIA",
            codigo_postal_consulta="91000",
        )
        sesion.add(cotizacion)
        sesion.flush()
        documento = Documento(
            cotizacion_id=cotizacion.id,
            nombre_original="cofepris-convergencia.pdf",
            mime_type="application/pdf",
            tamano_bytes=10,
            sha256="b" * 64,
            estado=EstadoDocumento.REVISADO.value,
        )
        sesion.add(documento)
        sesion.flush()
        partida = PartidaDocumento(
            documento_id=documento.id,
            orden=1,
            producto_solicitado="INSULINA GLARGINA",
            concentracion="100 U/mL",
            forma_farmaceutica_dispositivo="Solución inyectable",
            presentacion_solicitada="10 mL",
            cantidad=Decimal("1"),
            unidad_medida="frasco",
        )
        sesion.add(partida)
        sesion.flush()
        sesion.add(
            NormalizacionPartida(
                partida_documento_id=partida.id,
                producto="INSULINA GLARGINA",
                concentracion="100 U/mL",
                forma_dispositivo="Solución inyectable",
                presentacion="10 mL",
                confirmada_por_usuario_id=usuario.id,
            )
        )
        sesion.commit()

        resumen = ejecutar_descubrimiento_web(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_documento_id=partida.id,
            usuario_id=usuario.id,
            descubridor=_DescubridorLantus(),
        )

        assert resumen.guardados == 1
        assert resumen.descartados == 0
        observacion = sesion.scalar(select(ObservacionPrecio))
        assert observacion is not None
        assert observacion.evidencia_identidad is not None
        assert observacion.evidencia_identidad["registros_coincidentes"] == 2
        assert set(observacion.evidencia_identidad["numeros_registro"]) == {
            "LANTUS-VIAL",
            "LANTUS-PLUMA",
        }
