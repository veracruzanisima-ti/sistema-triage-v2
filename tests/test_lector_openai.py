"""Pruebas del adaptador OpenAI sin consumir la API real."""

import base64
from types import SimpleNamespace

import pytest

from triage.lectores.base import ErrorLecturaDocumento
from triage.lectores.esquemas import LecturaDocumento, PartidaLeida
from triage.lectores.openai import LectorOpenAI


class RespuestasFalsas:
    """Captura la petición que el adaptador intentaría enviar a Responses API."""

    def __init__(self) -> None:
        self.argumentos = None

    def parse(self, **argumentos):
        self.argumentos = argumentos
        lectura = LecturaDocumento(tipo_documento="Memorándum")
        parte = SimpleNamespace(type="output_text", parsed=lectura)
        mensaje = SimpleNamespace(type="message", content=[parte])
        return SimpleNamespace(output=[mensaje])


class ClienteFalso:
    def __init__(self) -> None:
        self.responses = RespuestasFalsas()


def test_pdf_se_envia_como_data_url_base64():
    contenido = b"%PDF-1.4 documento ficticio"
    lector = LectorOpenAI(api_key="sk-prueba-no-real", modelo="gpt-5")
    cliente = ClienteFalso()
    lector._cliente = cliente

    lectura = lector.leer(
        contenido=contenido,
        mime_type="application/pdf",
        nombre_archivo="solicitud-prueba.pdf",
    )

    assert lectura.tipo_documento == "Memorándum"
    assert cliente.responses.argumentos is not None
    assert cliente.responses.argumentos["store"] is False

    entrada = cliente.responses.argumentos["input"][0]["content"][1]
    assert entrada["type"] == "input_file"
    assert entrada["filename"] == "solicitud-prueba.pdf"
    prefijo = "data:application/pdf;base64,"
    assert entrada["file_data"].startswith(prefijo)
    assert base64.b64decode(entrada["file_data"][len(prefijo) :]) == contenido


def _lector_con_respuesta(monkeypatch, respuesta=None, error=None):
    lector = LectorOpenAI(api_key="sk-prueba-no-real", modelo="gpt-5")
    argumentos = {}

    def parse(**kwargs):
        argumentos.update(kwargs)
        if error:
            raise error
        return respuesta

    monkeypatch.setattr(lector._cliente.responses, "parse", parse)
    return lector, argumentos


@pytest.mark.parametrize("mime", ["image/jpeg", "image/png", "image/webp"])
def test_vision_extrae_sin_completar_dosis_ilegible(monkeypatch, mime):
    lectura = LecturaDocumento(
        partidas=[
            PartidaLeida(
                texto_original="Paraceta mol ?? mg caja 10 tabletas, 2 cajas",
                producto_solicitado="Paraceta mol",
                nombre_normalizado="Paracetamol",
                sustancia_activa=None,
                concentracion=None,
                presentacion_solicitada="Caja con 10 tabletas",
                cantidad=2,
                advertencias=["Concentración ilegible"],
            )
        ]
    )
    lector, argumentos = _lector_con_respuesta(
        monkeypatch, SimpleNamespace(output_parsed=lectura, output=[], status="completed")
    )
    resultado = lector.leer(contenido=b"imagen ficticia", mime_type=mime, nombre_archivo="foto")
    assert resultado == lectura
    assert resultado.partidas[0].concentracion is None
    assert resultado.partidas[0].sustancia_activa is None
    assert argumentos["text_format"] is LecturaDocumento
    assert argumentos["store"] is False
    assert "Nunca completes dosis" in argumentos["instructions"]
    imagen = argumentos["input"][0]["content"][1]
    assert imagen["type"] == "input_image"
    assert imagen["detail"] == "high"
    assert base64.b64decode(imagen["image_url"].split(",", 1)[1]) == b"imagen ficticia"


@pytest.mark.parametrize(
    "respuesta, mensaje",
    [
        (SimpleNamespace(output=[], status="incomplete"), "incompleta"),
        (SimpleNamespace(output=[]), "no devolvió"),
        (
            SimpleNamespace(
                output=[
                    SimpleNamespace(
                        type="message",
                        content=[SimpleNamespace(type="refusal", refusal="contenido privado")],
                    )
                ]
            ),
            "rechazó",
        ),
        (SimpleNamespace(output=[], output_parsed={"partidas": [{"cantidad": 1.5}]}), "no válida"),
        (SimpleNamespace(output=[], output_parsed={"campo_desconocido": "dato"}), "no válida"),
    ],
)
def test_respuestas_inutilizables_son_errores_controlados(monkeypatch, respuesta, mensaje):
    lector, _ = _lector_con_respuesta(monkeypatch, respuesta)
    with pytest.raises(ErrorLecturaDocumento, match=mensaje):
        lector.leer(contenido=b"ficticio", mime_type="image/png", nombre_archivo="foto.png")


def test_error_api_no_expone_contenido_ni_credenciales(monkeypatch, caplog):
    lector, _ = _lector_con_respuesta(monkeypatch, error=TimeoutError("dato-sensible-ficticio"))
    with pytest.raises(ErrorLecturaDocumento) as error:
        lector.leer(contenido=b"ficticio", mime_type="image/png", nombre_archivo="foto.png")
    assert "TimeoutError" in str(error.value)
    assert "dato-sensible-ficticio" not in str(error.value) + caplog.text


@pytest.mark.parametrize("contenido,mime", [(b"", "image/png"), (b"ficticio", "text/plain")])
def test_entrada_invalida_no_consume_api(monkeypatch, contenido, mime):
    lector, argumentos = _lector_con_respuesta(monkeypatch)
    with pytest.raises(ErrorLecturaDocumento):
        lector.leer(contenido=contenido, mime_type=mime, nombre_archivo="ficticio")
    assert argumentos == {}


@pytest.mark.parametrize("cantidad", [True, "2", 2.5, -1])
def test_cantidad_no_se_inventa_ni_se_redondea(cantidad):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        PartidaLeida(cantidad=cantidad)
