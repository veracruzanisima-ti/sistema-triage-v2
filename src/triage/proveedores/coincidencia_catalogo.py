"""Coincidencia conservadora de tarjetas de catálogo."""

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from triage.proveedores.base import SolicitudProveedor

_FACTORES = {
    "MG": ("MG", Decimal("1")),
    "G": ("MG", Decimal("1000")),
    "KG": ("MG", Decimal("1000000")),
    "ML": ("ML", Decimal("1")),
    "L": ("ML", Decimal("1000")),
    "U": ("U", Decimal("1")),
    "UI": ("U", Decimal("1")),
}
_RUIDO = {"CON", "DE", "DEL", "EL", "EN", "LA", "LAS", "LOS", "PARA", "POR"}


@dataclass(frozen=True)
class CandidatoCatalogo:
    descripcion: str
    precio_observado: Decimal
    stock: int | None
    fuente: str


@dataclass(frozen=True)
class EvaluacionCatalogo:
    candidato: CandidatoCatalogo
    coincide: bool
    puntaje: int
    motivos: tuple[str, ...]


def normalizar_texto(texto: str | None) -> str:
    valor = str(texto or "").upper().replace("µ", "U")
    valor = unicodedata.normalize("NFKD", valor)
    valor = "".join(c for c in valor if not unicodedata.combining(c))
    # En catálogos mexicanos el mismo frasco inyectable puede publicarse como
    # "vial", "frasco ámpula" o simplemente "ámpula". Canonizamos sólo esa
    # terminología; plumas, cartuchos y otros dispositivos siguen siendo distintos.
    valor = re.sub(r"\bFRASCO\s+(?:AMPULA|AMPOLLA)\b", "VIAL", valor)
    valor = re.sub(r"\b(?:AMPULA|AMPOLLA)\b", "VIAL", valor)
    valor = re.sub(r"[^A-Z0-9./+%-]+", " ", valor)
    return re.sub(r"\s+", " ", valor).strip()


def extraer_medidas(texto: str | None) -> frozenset[tuple[str, Decimal]]:
    normalizado = normalizar_texto(texto).replace(",", ".")
    patron = r"(?<![A-Z0-9])([0-9]+(?:\.[0-9]+)?)\s*(MG|KG|ML|UI|G|L|U)\b"
    medidas: set[tuple[str, Decimal]] = set()
    for valor, unidad in re.findall(patron, normalizado):
        unidad_base, factor = _FACTORES[unidad]
        medidas.add((unidad_base, (Decimal(valor) * factor).normalize()))
    return frozenset(medidas)


def _tokens(texto: str | None) -> frozenset[str]:
    return frozenset(
        token
        for token in re.findall(r"[A-Z][A-Z0-9+-]*", normalizar_texto(texto))
        if token not in _RUIDO and token not in _FACTORES
    )


def termino_busqueda(solicitud: SolicitudProveedor) -> str:
    return normalizar_texto(solicitud.marca) or normalizar_texto(solicitud.producto)


def evaluar_candidato(
    solicitud: SolicitudProveedor,
    candidato: CandidatoCatalogo,
) -> EvaluacionCatalogo:
    motivos: list[str] = []
    tokens_candidato = _tokens(candidato.descripcion)
    tokens_marca = _tokens(solicitud.marca)
    tokens_producto = _tokens(solicitud.producto)
    tokens_forma = _tokens(solicitud.forma_dispositivo)

    if candidato.precio_observado <= 0:
        motivos.append("precio no utilizable")
    if candidato.stock is not None and candidato.stock <= 0:
        motivos.append("sin disponibilidad")
    if tokens_marca and not tokens_marca.issubset(tokens_candidato):
        motivos.append("marca distinta")
    elif not tokens_marca and tokens_producto and not (tokens_producto & tokens_candidato):
        motivos.append("producto distinto")
    if tokens_forma and not tokens_forma.issubset(tokens_candidato):
        motivos.append("forma o dispositivo distinto")

    identidad = " ".join(
        parte or "" for parte in (solicitud.concentracion, solicitud.presentacion)
    )
    medidas = extraer_medidas(identidad)
    medidas_candidato = extraer_medidas(candidato.descripcion)
    if medidas and not medidas.issubset(medidas_candidato):
        motivos.append("medida o concentración distinta")

    puntaje = 0
    if not motivos:
        puntaje = (
            4 * len(tokens_marca & tokens_candidato)
            + 2 * len(tokens_producto & tokens_candidato)
            + 3 * len(tokens_forma & tokens_candidato)
            + 5 * len(medidas)
        )
    return EvaluacionCatalogo(candidato, not motivos, puntaje, tuple(motivos))


def seleccionar_candidato(
    solicitud: SolicitudProveedor,
    candidatos: list[CandidatoCatalogo],
) -> EvaluacionCatalogo | None:
    validos = [evaluar_candidato(solicitud, candidato) for candidato in candidatos]
    validos = [evaluacion for evaluacion in validos if evaluacion.coincide]
    if not validos:
        return None
    validos.sort(key=lambda evaluacion: evaluacion.puntaje, reverse=True)
    if validos[0].puntaje <= 0:
        return None
    if len(validos) > 1 and validos[0].puntaje == validos[1].puntaje:
        return None
    return validos[0]
