"""Adaptador OpenAI para leer fotografías y PDF de solicitudes."""

import base64
import logging

from openai import OpenAI
from pydantic import ValidationError

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
        self._cliente = OpenAI(api_key=api_key, timeout=80.0, max_retries=1)

    def leer(
        self,
        *,
        contenido: bytes,
        mime_type: str,
        nombre_archivo: str,
    ) -> LecturaDocumento:
        """Envía el archivo sin persistirlo en GitHub ni en el disco de la app."""

        if not contenido:
            raise ErrorLecturaDocumento("El archivo está vacío")
        if mime_type not in {"application/pdf", "image/jpeg", "image/png", "image/webp"}:
            raise ErrorLecturaDocumento("El formato del archivo no es compatible con el lector")

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
                instructions=INSTRUCCIONES_LECTURA,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": "Extrae los datos visibles del archivo.",
                            },
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
        if getattr(respuesta, "status", None) == "incomplete":
            raise ErrorLecturaDocumento("OpenAI devolvió una lectura incompleta; puedes capturarla")
        for salida in getattr(respuesta, "output", []) or []:
            if salida.type != "message":
                continue
            for parte in salida.content:
                if parte.type == "refusal":
                    raise ErrorLecturaDocumento("OpenAI rechazó la lectura; puedes capturarla")

        lectura = getattr(respuesta, "output_parsed", None)
        if lectura is None:
            for salida in getattr(respuesta, "output", []) or []:
                if salida.type == "message":
                    lectura = next(
                        (
                            getattr(parte, "parsed", None)
                            for parte in salida.content
                            if parte.type == "output_text"
                            and getattr(parte, "parsed", None) is not None
                        ),
                        None,
                    )
                    if lectura is not None:
                        break
        if lectura is not None:
            try:
                return LecturaDocumento.model_validate(lectura)
            except ValidationError as error:
                raise ErrorLecturaDocumento("OpenAI devolvió una lectura no válida") from error

        raise ErrorLecturaDocumento("OpenAI no devolvió una lectura estructurada")
