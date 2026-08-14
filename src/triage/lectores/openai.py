"""Adaptador OpenAI para leer fotografías y PDF de solicitudes."""

import base64
import logging

from openai import OpenAI

from triage.lectores.base import ErrorLecturaDocumento
from triage.lectores.esquemas import LecturaDocumento
from triage.lectores.instrucciones import INSTRUCCIONES_LECTURA

logger = logging.getLogger(__name__)


def _registrar_uso(modelo: str, respuesta) -> None:
    """Registra sólo métricas de consumo; nunca contenido del documento."""

    uso = getattr(respuesta, "usage", None)
    if uso is None:
        return
    logger.info(
        "OpenAI lector model=%s input_tokens=%s output_tokens=%s total_tokens=%s",
        modelo,
        getattr(uso, "input_tokens", None),
        getattr(uso, "output_tokens", None),
        getattr(uso, "total_tokens", None),
    )


class LectorOpenAI:
    """Implementa lectura multimodal mediante Responses API y salida Pydantic."""

    def __init__(self, *, api_key: str, modelo: str) -> None:
        if not api_key.strip():
            raise ValueError("OPENAI_API_KEY es obligatoria para crear el lector")
        if not modelo.strip():
            raise ValueError("OPENAI_MODEL no puede estar vacío")

        self.modelo = modelo.strip()
        self._cliente = OpenAI(api_key=api_key)

    def leer(
        self,
        *,
        contenido: bytes,
        mime_type: str,
        nombre_archivo: str,
    ) -> LecturaDocumento:
        """Envía el archivo sin persistirlo en GitHub ni en el disco de la app."""

        codificado = base64.b64encode(contenido).decode("ascii")
        if mime_type == "application/pdf":
            entrada_archivo = {
                "type": "input_file",
                "filename": nombre_archivo,
                "file_data": f"data:{mime_type};base64,{codificado}",
            }
        else:
            entrada_archivo = {
                "type": "input_image",
                "image_url": f"data:{mime_type};base64,{codificado}",
                "detail": "high",
            }

        try:
            respuesta = self._cliente.responses.parse(
                model=self.modelo,
                store=False,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": INSTRUCCIONES_LECTURA},
                            entrada_archivo,
                        ],
                    }
                ],
                text_format=LecturaDocumento,
            )
        except Exception as error:
            raise ErrorLecturaDocumento(
                f"OpenAI no pudo procesar el archivo ({type(error).__name__})"
            ) from error

        _registrar_uso(self.modelo, respuesta)
        for salida in respuesta.output:
            if salida.type != "message":
                continue
            for parte in salida.content:
                if parte.type == "output_text" and parte.parsed is not None:
                    return parte.parsed

        raise ErrorLecturaDocumento("OpenAI no devolvió una lectura estructurada")
