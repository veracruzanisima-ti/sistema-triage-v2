"""Adaptador Gemini para leer fotografías y PDF de solicitudes."""

import logging

from google import genai
from google.genai import types
from pydantic import ValidationError

from triage.lectores.base import ErrorLecturaDocumento
from triage.lectores.esquemas import LecturaDocumento
from triage.lectores.instrucciones import INSTRUCCIONES_LECTURA

logger = logging.getLogger(__name__)


def _registrar_uso(modelo: str, respuesta) -> None:
    """Registra sólo métricas de consumo; nunca contenido del documento."""

    uso = getattr(respuesta, "usage_metadata", None)
    if uso is None:
        return
    logger.info(
        "Gemini lector model=%s input_tokens=%s output_tokens=%s total_tokens=%s",
        modelo,
        getattr(uso, "prompt_token_count", None),
        getattr(uso, "candidates_token_count", None),
        getattr(uso, "total_token_count", None),
    )


class LectorGemini:
    """Implementa lectura multimodal de Gemini con salida Pydantic."""

    def __init__(self, *, api_key: str, modelo: str) -> None:
        if not api_key.strip():
            raise ValueError("GEMINI_API_KEY es obligatoria para crear el lector")
        if not modelo.strip():
            raise ValueError("GEMINI_MODEL_LECTOR no puede estar vacío")

        self.modelo = modelo.strip()
        self._cliente = genai.Client(
            api_key=api_key,
            http_options={"timeout": 80_000},
        )

    def leer(
        self,
        *,
        contenido: bytes,
        mime_type: str,
        nombre_archivo: str,
    ) -> LecturaDocumento:
        """Procesa el archivo en memoria; el nombre sólo se conserva para trazabilidad local."""

        del nombre_archivo
        try:
            respuesta = self._cliente.models.generate_content(
                model=self.modelo,
                contents=[
                    types.Part.from_bytes(data=contenido, mime_type=mime_type),
                    INSTRUCCIONES_LECTURA,
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=LecturaDocumento,
                ),
            )
        except Exception as error:
            raise ErrorLecturaDocumento(
                f"Gemini no pudo procesar el archivo ({type(error).__name__})"
            ) from error

        _registrar_uso(self.modelo, respuesta)
        parsed = getattr(respuesta, "parsed", None)
        if isinstance(parsed, LecturaDocumento):
            return parsed

        texto = getattr(respuesta, "text", None)
        if texto:
            try:
                return LecturaDocumento.model_validate_json(texto)
            except ValidationError as error:
                raise ErrorLecturaDocumento("Gemini devolvió una lectura no válida") from error

        raise ErrorLecturaDocumento("Gemini no devolvió una lectura estructurada")
