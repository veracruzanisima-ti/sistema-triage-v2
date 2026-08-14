"""Descubrimiento opcional de nuevas fuentes públicas para un producto preparado."""

from decimal import Decimal
from typing import Protocol

from openai import OpenAI
from pydantic import BaseModel, Field, HttpUrl

from triage.proveedores.base import SolicitudProveedor


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
                text_format=ResultadoDescubrimientoWeb,
            )
        except Exception as error:
            raise ErrorDescubrimientoWeb(
                f"La búsqueda web no pudo completarse ({type(error).__name__})"
            ) from error

        for salida in respuesta.output:
            if salida.type != "message":
                continue
            for parte in salida.content:
                if parte.type == "output_text" and parte.parsed is not None:
                    return tuple(parte.parsed.candidatos)

        raise ErrorDescubrimientoWeb("La búsqueda web no devolvió candidatos estructurados")
