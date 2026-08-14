"""Descubrimiento opcional de nuevas fuentes públicas para un producto preparado."""

import logging
from decimal import Decimal
from typing import Protocol

from google import genai
from google.genai import types
from openai import OpenAI
from pydantic import BaseModel, Field, HttpUrl, ValidationError

from triage.proveedores.base import SolicitudProveedor

logger = logging.getLogger(__name__)


class CandidatoWeb(BaseModel):
    """Precio visible en una fuente web que aún requiere revisión humana."""

    proveedor: str
    producto_exacto: str
    url: HttpUrl
    precio_total: Decimal | None = Field(default=None, gt=0)
    coincidencia_exacta: bool
    es_promocion: bool = False
    condiciones_promocion: str | None = None
    disponibilidad: str | None = None
    entrega_viable: bool | None = None


class ResultadoDescubrimientoWeb(BaseModel):
    candidatos: list[CandidatoWeb] = Field(default_factory=list, max_length=5)


class CandidatoWebRespuesta(BaseModel):
    """Contrato simple y portable para salida estructurada de modelos externos."""

    proveedor: str
    producto_exacto: str
    url: str
    precio_total: float | None = None
    coincidencia_exacta: bool
    es_promocion: bool = False
    condiciones_promocion: str | None = None
    disponibilidad: str | None = None
    entrega_viable: bool | None = None


class ResultadoDescubrimientoWebRespuesta(BaseModel):
    """Evita formatos y restricciones JSON Schema que no necesita el modelo externo."""

    candidatos: list[CandidatoWebRespuesta] = Field(default_factory=list)


class DescubridorWeb(Protocol):
    """Contrato pequeño para poder sustituir el proveedor de IA en pruebas."""

    modelo: str

    def buscar(self, solicitud: SolicitudProveedor) -> tuple[CandidatoWeb, ...]:
        """Busca candidatos públicos sin tomar una decisión comercial."""


class ErrorDescubrimientoWeb(Exception):
    """Fallo externo sanitizado para mostrarlo sin filtrar detalles internos."""


_INSTRUCCIONES = """
Busca en la web pública de México opciones reales para comprar el producto descrito abajo.

Reglas obligatorias:
- Devuelve máximo 5 candidatos.
- Sólo incluye páginas que muestren un precio numérico visible del producto.
- `url` debe ser la URL directa de la página fuente encontrada mediante la búsqueda web.
- No inventes precios, disponibilidad, promociones, envío ni impuestos.
- No calcules ni infieras IVA. El precio público encontrado se reporta únicamente como
  `precio_total`.
- `es_promocion` sólo puede ser true si la fuente lo declara explícitamente como oferta,
  promoción, descuento, precio especial o equivalente.
- `entrega_viable` sólo puede ser true o false cuando la fuente permita determinarlo de forma
  explícita para el contexto indicado. En cualquier otro caso devuelve null.
- `coincidencia_exacta` exige respetar la identidad preparada: producto, marca cuando exista,
  concentración, forma/dispositivo y presentación. No conviertas cajas, dosis ni tamaños.
- Puedes devolver una coincidencia no exacta con `coincidencia_exacta=false` para explicar por
  qué fue descartada, pero Triage no la guardará como precio utilizable.
- El código postal sirve como contexto de disponibilidad/precio. No afirmes cobertura sólo por
  conocer el código postal.
- Prioriza farmacias, distribuidores y comercios con página de producto identificable.
- No tomes ninguna decisión sobre qué opción debe cotizarse o comprarse.
""".strip()


def _descripcion_solicitud(solicitud: SolicitudProveedor) -> str:
    return "\n".join(
        (
            f"Producto: {solicitud.producto or 'sin nombre'}",
            f"Marca: {solicitud.marca or 'no especificada'}",
            f"Concentración: {solicitud.concentracion or 'no especificada'}",
            f"Forma/dispositivo: {solicitud.forma_dispositivo or 'no especificado'}",
            f"Presentación: {solicitud.presentacion or 'no especificada'}",
            f"Código postal de consulta: {solicitud.codigo_postal or 'no configurado'}",
        )
    )


def _convertir_candidato(candidato: CandidatoWebRespuesta) -> CandidatoWeb | None:
    """Aplica validación local fuerte después de recibir un esquema externo simple."""

    try:
        return CandidatoWeb(
            proveedor=candidato.proveedor,
            producto_exacto=candidato.producto_exacto,
            url=candidato.url,
            precio_total=(
                Decimal(str(candidato.precio_total))
                if candidato.precio_total is not None
                else None
            ),
            coincidencia_exacta=candidato.coincidencia_exacta,
            es_promocion=candidato.es_promocion,
            condiciones_promocion=candidato.condiciones_promocion,
            disponibilidad=candidato.disponibilidad,
            entrega_viable=candidato.entrega_viable,
        )
    except (ValidationError, ValueError):
        return None


def _convertir_resultado(resultado: ResultadoDescubrimientoWebRespuesta) -> tuple[CandidatoWeb, ...]:
    candidatos: list[CandidatoWeb] = []
    for candidato_respuesta in resultado.candidatos[:5]:
        candidato = _convertir_candidato(candidato_respuesta)
        if candidato is not None:
            candidatos.append(candidato)
    return tuple(candidatos)


def _registrar_uso_openai(modelo: str, respuesta) -> None:
    """Registra métricas de consumo sin registrar la consulta ni sus resultados."""

    uso = getattr(respuesta, "usage", None)
    if uso is None:
        return
    logger.info(
        "OpenAI web model=%s input_tokens=%s output_tokens=%s total_tokens=%s",
        modelo,
        getattr(uso, "input_tokens", None),
        getattr(uso, "output_tokens", None),
        getattr(uso, "total_tokens", None),
    )


def _registrar_uso_gemini(modelo: str, respuesta) -> None:
    """Registra métricas Gemini sin registrar consulta, producto ni resultados."""

    uso = getattr(respuesta, "usage_metadata", None)
    if uso is None:
        return
    logger.info(
        "Gemini web model=%s input_tokens=%s output_tokens=%s total_tokens=%s",
        modelo,
        getattr(uso, "prompt_token_count", None),
        getattr(uso, "candidates_token_count", None),
        getattr(uso, "total_token_count", None),
    )


class DescubridorWebOpenAI:
    """Usa Responses API con web_search y devuelve candidatos estructurados."""

    def __init__(self, *, api_key: str, modelo: str) -> None:
        if not api_key.strip():
            raise ValueError("OPENAI_API_KEY es obligatoria para búsqueda web")
        if not modelo.strip():
            raise ValueError("OPENAI_MODEL no puede estar vacío")
        self.modelo = modelo.strip()
        self._cliente = OpenAI(api_key=api_key)

    def buscar(self, solicitud: SolicitudProveedor) -> tuple[CandidatoWeb, ...]:
        """Busca sólo con datos operativos del producto, sin datos personales."""

        descripcion = _descripcion_solicitud(solicitud)
        try:
            respuesta = self._cliente.responses.parse(
                model=self.modelo,
                store=False,
                tools=[
                    {
                        "type": "web_search",
                        "user_location": {
                            "type": "approximate",
                            "country": "MX",
                            "timezone": "America/Mexico_City",
                        },
                    }
                ],
                input=f"{_INSTRUCCIONES}\n\n{descripcion}",
                text_format=ResultadoDescubrimientoWebRespuesta,
            )
        except Exception as error:
            logger.warning(
                "Fallo de web_search OpenAI tipo=%s status=%s code=%s param=%s request_id=%s",
                type(error).__name__,
                getattr(error, "status_code", None),
                getattr(error, "code", None),
                getattr(error, "param", None),
                getattr(error, "request_id", None),
            )
            raise ErrorDescubrimientoWeb(
                "La búsqueda web no pudo completarse. "
                "Intenta de nuevo o registra el precio manualmente."
            ) from error

        _registrar_uso_openai(self.modelo, respuesta)
        for salida in respuesta.output:
            if salida.type != "message":
                continue
            for parte in salida.content:
                if parte.type == "output_text" and parte.parsed is not None:
                    return _convertir_resultado(parte.parsed)

        raise ErrorDescubrimientoWeb("La búsqueda web no devolvió candidatos estructurados")


class DescubridorWebGemini:
    """Usa Gemini con Google Search y el mismo contrato de candidatos que OpenAI."""

    def __init__(self, *, api_key: str, modelo: str) -> None:
        if not api_key.strip():
            raise ValueError("GEMINI_API_KEY es obligatoria para búsqueda web")
        if not modelo.strip():
            raise ValueError("GEMINI_MODEL_WEB no puede estar vacío")
        self.modelo = modelo.strip()
        self._cliente = genai.Client(
            api_key=api_key,
            http_options={"timeout": 80_000},
        )

    def buscar(self, solicitud: SolicitudProveedor) -> tuple[CandidatoWeb, ...]:
        """Busca con Google Search usando sólo la identidad operativa y el CP."""

        descripcion = _descripcion_solicitud(solicitud)
        try:
            respuesta = self._cliente.models.generate_content(
                model=self.modelo,
                contents=f"{_INSTRUCCIONES}\n\n{descripcion}",
                config=types.GenerateContentConfig(
                    tools=[{"google_search": {}}],
                    response_mime_type="application/json",
                    response_schema=ResultadoDescubrimientoWebRespuesta,
                ),
            )
        except Exception as error:
            logger.warning(
                "Fallo de Google Search Gemini tipo=%s",
                type(error).__name__,
            )
            raise ErrorDescubrimientoWeb(
                "La búsqueda web no pudo completarse con Gemini. "
                "Intenta de nuevo o registra el precio manualmente."
            ) from error

        _registrar_uso_gemini(self.modelo, respuesta)
        parsed = getattr(respuesta, "parsed", None)
        if isinstance(parsed, ResultadoDescubrimientoWebRespuesta):
            return _convertir_resultado(parsed)

        texto = getattr(respuesta, "text", None)
        if texto:
            try:
                resultado = ResultadoDescubrimientoWebRespuesta.model_validate_json(texto)
            except ValidationError as error:
                raise ErrorDescubrimientoWeb(
                    "Gemini devolvió resultados web con una estructura no válida."
                ) from error
            return _convertir_resultado(resultado)

        raise ErrorDescubrimientoWeb("Gemini no devolvió candidatos web estructurados")
