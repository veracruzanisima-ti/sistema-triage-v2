"""Descubrimiento opcional de nuevas fuentes públicas para un producto preparado."""

import logging
from decimal import Decimal
from typing import Protocol

from openai import APITimeoutError, OpenAI
from pydantic import BaseModel, Field, HttpUrl, ValidationError

from triage.proveedores.base import SolicitudProveedor

logger = logging.getLogger(__name__)

_TIMEOUT_BUSQUEDA_WEB_SEGUNDOS = 80.0


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
    """Contrato deliberadamente simple para Structured Outputs de OpenAI."""

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
    """Contrato pequeño para poder sustituir OpenAI en pruebas."""

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

        descripcion = "\n".join(
            (
                f"Producto: {solicitud.producto or 'sin nombre'}",
                f"Marca: {solicitud.marca or 'no especificada'}",
                f"Concentración: {solicitud.concentracion or 'no especificada'}",
                f"Forma/dispositivo: {solicitud.forma_dispositivo or 'no especificado'}",
                f"Presentación: {solicitud.presentacion or 'no especificada'}",
                f"Código postal de consulta: {solicitud.codigo_postal or 'no configurado'}",
            )
        )
        try:
            respuesta = self._cliente.with_options(
                timeout=_TIMEOUT_BUSQUEDA_WEB_SEGUNDOS,
                max_retries=0,
            ).responses.parse(
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
        except APITimeoutError as error:
            logger.warning(
                "Timeout de web_search OpenAI model=%s request_id=%s",
                self.modelo,
                getattr(error, "request_id", None),
            )
            raise ErrorDescubrimientoWeb(
                "La búsqueda web tardó más de lo esperado. Intenta nuevamente."
            ) from error
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

        for salida in respuesta.output:
            if salida.type != "message":
                continue
            for parte in salida.content:
                if parte.type != "output_text" or parte.parsed is None:
                    continue
                candidatos: list[CandidatoWeb] = []
                for candidato_respuesta in parte.parsed.candidatos[:5]:
                    candidato = _convertir_candidato(candidato_respuesta)
                    if candidato is not None:
                        candidatos.append(candidato)
                return tuple(candidatos)

        raise ErrorDescubrimientoWeb("La búsqueda web no devolvió candidatos estructurados")
