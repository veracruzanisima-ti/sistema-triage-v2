"""Pruebas del descubrimiento web sin consumir servicios externos."""

import re
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import select

from triage.cotizaciones.modelos import Cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.historico.modelos import ObservacionPrecio, OrigenObservacionPrecio
from triage.normalizacion.modelos import NormalizacionPartida
from triage.proveedores.base import SolicitudProveedor
from triage.proveedores.descubrimiento_web import (
    CandidatoWeb,
    CandidatoWebRespuesta,
    DescubridorWebOpenAI,
    ResultadoDescubrimientoWebRespuesta,
)
from triage.proveedores.servicio import ejecutar_descubrimiento_web
from triage.usuarios.modelos import Usuario


def _csrf(html: str) -> str:
    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF")
    return coincidencia.group(1)


def _preparar_producto(cliente) -> tuple[str, str, str]:
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario))
        assert usuario is not None
        cotizacion = Cotizacion(
            referencia="WEB-PRUEBA",
            codigo_postal_consulta="91000",
        )
        sesion.add(cotizacion)
        sesion.flush()
        documento = Documento(
            cotizacion_id=cotizacion.id,
            nombre_original="web.pdf",
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
            producto_solicitado="LANTUS",
            incluida_cotizacion=True,
        )
        sesion.add(partida)
        sesion.flush()
        sesion.add(
            NormalizacionPartida(
                partida_documento_id=partida.id,
                producto="LANTUS",
                marca="Lantus",
                concentracion="100 U/mL",
                forma_dispositivo="vial",
                presentacion="10 mL",
                confirmada_por_usuario_id=usuario.id,
            )
        )
        sesion.commit()
        return cotizacion.id, partida.id, usuario.id


class DescubridorFalso:
    def buscar(self, solicitud: SolicitudProveedor):
        assert solicitud.producto == "LANTUS"
        assert solicitud.codigo_postal == "91000"
        return (
            CandidatoWeb(
                proveedor="Farmacia Exacta",
                producto_exacto="Lantus 100 U/mL vial 10 mL",
                url="https://ejemplo.invalid/lantus",
                precio_total=Decimal("1234.50"),
                coincidencia_exacta=True,
                disponibilidad="Disponible",
            ),
            CandidatoWeb(
                proveedor="Farmacia Parecida",
                producto_exacto="Lantus pluma 3 mL",
                url="https://ejemplo.invalid/lantus-pluma",
                precio_total=Decimal("800.00"),
                coincidencia_exacta=False,
            ),
            CandidatoWeb(
                proveedor="Farmacia Mal Clasificada",
                producto_exacto="Lantus pluma 3 mL",
                url="https://ejemplo.invalid/falso-exacto",
                precio_total=Decimal("700.00"),
                coincidencia_exacta=True,
            ),
        )


def test_descubrimiento_web_guarda_solo_coincidencias_exactas(cliente):
    cotizacion_id, partida_id, usuario_id = _preparar_producto(cliente)
    with cliente.app.state.fabrica_sesiones() as sesion:
        resumen = ejecutar_descubrimiento_web(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_id,
            usuario_id=usuario_id,
            descubridor=DescubridorFalso(),
        )
        assert resumen.candidatos == 3
        assert resumen.guardados == 1
        assert resumen.descartados == 2

        observaciones = list(sesion.scalars(select(ObservacionPrecio)))
        assert len(observaciones) == 1
        observacion = observaciones[0]
        assert observacion.proveedor == "Farmacia Exacta"
        assert observacion.producto_observado == "Lantus 100 U/mL vial 10 mL"
        assert observacion.origen == OrigenObservacionPrecio.WEB.value
        assert observacion.codigo_postal == "91000"
        assert observacion.iva_porcentaje is None
        assert observacion.precio_antes_iva is None
        assert str(observacion.precio_total) == "1234.50"
        assert observacion.fuente.startswith("https://ejemplo.invalid/lantus")


def test_descubrimiento_web_aparece_como_accion_secundaria(cliente):
    cotizacion_id, partida_id, _ = _preparar_producto(cliente)
    cliente.app.state.descubridor_web = DescubridorFalso()

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    assert pagina.status_code == 200
    assert "Buscar más opciones en web" in pagina.text

    respuesta = cliente.post(
        f"/cotizaciones/{cotizacion_id}/proveedores/{partida_id}/buscar-web",
        data={"csrf_token": _csrf(pagina.text)},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    assert "resultado=web" in respuesta.headers["location"]

    resultado = cliente.get(respuesta.headers["location"])
    assert "1 opción(es) exacta(s) guardada(s)" in resultado.text
    assert "Farmacia Exacta" in resultado.text
    assert "La fuente mostró:" in resultado.text
    assert "Ver fuente" in resultado.text


class RespuestasFalsas:
    def __init__(self) -> None:
        self.argumentos = None

    def parse(self, **argumentos):
        self.argumentos = argumentos
        resultado = ResultadoDescubrimientoWebRespuesta(
            candidatos=[
                CandidatoWebRespuesta(
                    proveedor="Farmacia Web",
                    producto_exacto="Lantus 100 U/mL vial 10 mL",
                    url="https://ejemplo.invalid/producto",
                    precio_total=999.0,
                    coincidencia_exacta=True,
                )
            ]
        )
        parte = SimpleNamespace(type="output_text", parsed=resultado)
        mensaje = SimpleNamespace(type="message", content=[parte])
        return SimpleNamespace(output=[mensaje])


class ClienteFalso:
    def __init__(self) -> None:
        self.responses = RespuestasFalsas()


def test_openai_web_search_no_almacena_y_solo_recibe_contexto_operativo():
    descubridor = DescubridorWebOpenAI(api_key="sk-prueba-no-real", modelo="gpt-5")
    cliente = ClienteFalso()
    descubridor._cliente = cliente

    candidatos = descubridor.buscar(
        SolicitudProveedor(
            partida_documento_id="partida-1",
            producto="LANTUS",
            marca="Lantus",
            concentracion="100 U/mL",
            forma_dispositivo="vial",
            presentacion="10 mL",
            codigo_postal="91000",
        )
    )

    assert len(candidatos) == 1
    assert str(candidatos[0].precio_total) == "999.0"
    argumentos = cliente.responses.argumentos
    assert argumentos is not None
    assert argumentos["store"] is False
    assert argumentos["tools"][0]["type"] == "web_search"
    assert argumentos["tools"][0]["user_location"]["country"] == "MX"
    assert argumentos["text_format"] is ResultadoDescubrimientoWebRespuesta
    assert "LANTUS" in argumentos["input"]
    assert "91000" in argumentos["input"]
    assert "paciente" not in argumentos["input"].casefold()


def _claves_json(valor) -> set[str]:
    if isinstance(valor, dict):
        claves = set(valor)
        for hijo in valor.values():
            claves.update(_claves_json(hijo))
        return claves
    if isinstance(valor, list):
        claves: set[str] = set()
        for hijo in valor:
            claves.update(_claves_json(hijo))
        return claves
    return set()


def test_schema_externo_no_usa_formatos_ni_restricciones_innecesarias():
    schema = ResultadoDescubrimientoWebRespuesta.model_json_schema()
    claves = _claves_json(schema)

    assert "format" not in claves
    assert "exclusiveMinimum" not in claves
    assert "maxItems" not in claves
    assert "pattern" not in claves
