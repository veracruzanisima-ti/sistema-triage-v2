"""Lectura Gemini con respuestas ficticias, sin conexión a Google."""

from types import SimpleNamespace

import pytest
from google.genai import types

from triage.lectores.base import ErrorLecturaDocumento
from triage.lectores.esquemas import LecturaDocumento, PartidaLeida
from triage.lectores.gemini import LectorGemini
from triage.lectores.instrucciones import INSTRUCCIONES_LECTURA


def _lector(monkeypatch, respuesta=None, error=None):
    argumentos = {}

    def generar(**kwargs):
        argumentos.update(kwargs)
        if error:
            raise error
        return respuesta

    monkeypatch.setattr(
        "triage.lectores.gemini.genai.Client",
        lambda **kwargs: SimpleNamespace(models=SimpleNamespace(generate_content=generar)),
    )
    return LectorGemini(api_key="clave-ficticia", modelo="modelo-ficticio"), argumentos


@pytest.mark.parametrize("mime", ["application/pdf", "image/jpeg", "image/png", "image/webp"])
def test_gemini_conserva_original_normalizado_y_null(monkeypatch, mime):
    lectura = LecturaDocumento(
        partidas=[
            PartidaLeida(
                texto_original="Paraceta mol ?? mg",
                producto_solicitado="Paraceta mol",
                nombre_normalizado="Paracetamol",
                concentracion=None,
                sustancia_activa=None,
                cantidad=None,
                advertencias=["Concentración ilegible"],
            )
        ]
    )
    lector, argumentos = _lector(monkeypatch, SimpleNamespace(parsed=lectura))
    assert lector.leer(contenido=b"ficticio", mime_type=mime, nombre_archivo="ficticio") == lectura
    assert argumentos["config"].system_instruction == INSTRUCCIONES_LECTURA
    assert argumentos["config"].response_schema is LecturaDocumento
    archivo = argumentos["contents"][0].inline_data
    assert archivo.data == b"ficticio"
    assert archivo.mime_type == mime


def test_gemini_valida_json_cuando_no_hay_parsed(monkeypatch):
    lector, _ = _lector(
        monkeypatch,
        SimpleNamespace(
            text='{"partidas":[{"producto_solicitado":"FICTICIO","concentracion":null}]}'
        ),
    )
    resultado = lector.leer(contenido=b"ficticio", mime_type="image/png", nombre_archivo="foto")
    assert resultado.partidas[0].producto_solicitado == "FICTICIO"
    assert resultado.partidas[0].concentracion is None


def test_gemini_acepta_fin_normal_con_enums_del_sdk(monkeypatch):
    lector, _ = _lector(
        monkeypatch,
        SimpleNamespace(
            parsed=LecturaDocumento(tipo_documento="FICTICIO"),
            candidates=[SimpleNamespace(finish_reason=types.FinishReason.STOP)],
            prompt_feedback=SimpleNamespace(
                block_reason=types.BlockedReason.BLOCKED_REASON_UNSPECIFIED
            ),
        ),
    )
    resultado = lector.leer(contenido=b"ficticio", mime_type="image/png", nombre_archivo="foto")
    assert resultado.tipo_documento == "FICTICIO"


@pytest.mark.parametrize(
    "respuesta",
    [
        SimpleNamespace(text="JSON inválido"),
        SimpleNamespace(parsed={"partidas": [{"cantidad": 2.5}]}),
        SimpleNamespace(),
        SimpleNamespace(prompt_feedback=SimpleNamespace(block_reason="SAFETY")),
        SimpleNamespace(candidates=[SimpleNamespace(finish_reason="MAX_TOKENS")]),
        SimpleNamespace(candidates=[SimpleNamespace(finish_reason="SAFETY")]),
    ],
)
def test_gemini_controla_rechazos_incompletos_y_estructura_invalida(monkeypatch, respuesta):
    lector, _ = _lector(monkeypatch, respuesta)
    with pytest.raises(ErrorLecturaDocumento):
        lector.leer(contenido=b"ficticio", mime_type="image/png", nombre_archivo="foto")


def test_gemini_error_no_expone_respuesta_privada(monkeypatch, caplog):
    lector, _ = _lector(monkeypatch, error=TimeoutError("dato-privado-ficticio"))
    with pytest.raises(ErrorLecturaDocumento) as error:
        lector.leer(contenido=b"ficticio", mime_type="image/png", nombre_archivo="foto")
    assert "TimeoutError" in str(error.value)
    assert "dato-privado-ficticio" not in str(error.value) + caplog.text


@pytest.mark.parametrize("contenido,mime", [(b"", "image/png"), (b"ficticio", "text/plain")])
def test_gemini_entrada_invalida_no_llama_api(monkeypatch, contenido, mime):
    lector, argumentos = _lector(monkeypatch)
    with pytest.raises(ErrorLecturaDocumento):
        lector.leer(contenido=contenido, mime_type=mime, nombre_archivo="foto")
    assert argumentos == {}
