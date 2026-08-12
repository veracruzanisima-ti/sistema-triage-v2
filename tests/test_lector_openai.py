"""Pruebas del adaptador OpenAI sin consumir la API real."""

import base64
from types import SimpleNamespace

from triage.lectores.esquemas import LecturaDocumento
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
