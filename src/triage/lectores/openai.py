"""Adaptador OpenAI para leer fotografías y PDF de solicitudes."""

import base64

from openai import OpenAI

from triage.lectores.base import ErrorLecturaDocumento
from triage.lectores.esquemas import LecturaDocumento

_INSTRUCCIONES = """
Lee este documento como fuente administrativa para una cotización.

Reglas obligatorias:
- Extrae únicamente información visible o explícita en el archivo.
- No busques en Internet y no agregues conocimiento comercial externo.
- No propongas marcas, sustitutos, proveedores, IVA, clasificación sanitaria ni cadena fría.
- Conserva la presentación solicitada con el mayor detalle visible.
- `marca_solicitada` sólo debe contener una marca que realmente aparezca en el documento.
- Si un dato no puede determinarse de forma responsable, devuelve null o una lista vacía.
- No inventes folios ni completes números parcialmente visibles.
- Una cantidad de partidas alta NO es evidencia de continuación.
- Marca `posible_continuacion` sólo cuando haya señales del propio documento, por ejemplo:
  texto de continuación, numeración de páginas/partidas que continúa, tabla cortada sin nuevo
  encabezado u otra evidencia documental concreta. Describe esas señales brevemente.
- Separa cada renglón solicitado como una partida distinta.
- No devuelvas una transcripción completa del documento.

El resultado será revisado y corregido por una persona antes de usarse para cotizar.
""".strip()


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
                "file_data": codificado,
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
                            {"type": "input_text", "text": _INSTRUCCIONES},
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

        for salida in respuesta.output:
            if salida.type != "message":
                continue
            for parte in salida.content:
                if parte.type == "output_text" and parte.parsed is not None:
                    return parte.parsed

        raise ErrorLecturaDocumento("OpenAI no devolvió una lectura estructurada")
