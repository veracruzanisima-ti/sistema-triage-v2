"""Coincidencia conservadora de tarjetas de catálogo y resultados web."""

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
_RUIDO = {
    "CAJA",
    "CON",
    "DE",
    "DEL",
    "EL",
    "EN",
    "LA",
    "LAS",
    "LOS",
    "PARA",
    "POR",
}
_FORMAS_CONOCIDAS = {
    "AMPOLLA",
    "CAPSULA",
    "CARTUCHO",
    "JERINGA",
    "PLUMA",
    "PRELLENADA",
    "TABLETA",
    "VIAL",
}
_UNIDADES_PRESENTACION = (
    "CAJA",
    "TABLETA",
    "CAPSULA",
    "AMPOLLA",
    "VIAL",
    "JERINGA",
    "PLUMA",
    "CARTUCHO",
)
_ALIASES_BUSQUEDA = {
    "TABLETA": ("tableta", "tabletas", "tab"),
    "VIAL": ("frasco ámpula", "frasco ampula", "F.A.", "vial"),
    "AMPOLLA": ("ampolla", "amp"),
    "JERINGA PRELLENADA": ("jeringa prellenada", "jga pre"),
}
_ETIQUETAS_PRESENTACION = {
    "TABLETA": ("tableta", "tabletas"),
    "CAPSULA": ("cápsula", "cápsulas"),
    "AMPOLLA": ("ampolla", "ampollas"),
    "VIAL": ("frasco ámpula", "frascos ámpula"),
    "JERINGA": ("jeringa", "jeringas"),
    "PLUMA": ("pluma", "plumas"),
    "CARTUCHO": ("cartucho", "cartuchos"),
}


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
    """Normaliza formato y sólo equivalencias lingüísticas seguras y explícitas."""

    valor = str(texto or "").upper().replace("µ", "U")
    valor = unicodedata.normalize("NFKD", valor)
    valor = "".join(c for c in valor if not unicodedata.combining(c))
    sustituciones = (
        (r"\bF\s*\.?\s*A\.?(?=[^A-Z0-9]|$)", "VIAL"),
        (r"\bFRASCO\s+(?:AMPULA|AMPOLLA)\b", "VIAL"),
        (r"\bJERINGAS?\s+PRELLENADAS?\b", "JERINGA PRELLENADA"),
        (r"\bJGA\s+PRE\b", "JERINGA PRELLENADA"),
        (r"\bJGA\b", "JERINGA"),
        (r"\bTABLETAS?\b|\bTABS?\b", "TABLETA"),
        (r"\bCAPSULAS?\b|\bCAP\b", "CAPSULA"),
        (r"\bAMPOLLAS?\b|\bAMP\b", "AMPOLLA"),
        # Conserva la equivalencia histórica de catálogos mexicanos para "ámpula".
        (r"\bAMPULAS?\b", "VIAL"),
        (r"\bCART(?:\s+DES)?\b", "CARTUCHO"),
    )
    for patron, reemplazo in sustituciones:
        valor = re.sub(patron, reemplazo, valor)
    valor = re.sub(r"(?<![0-9])\.|\.(?![0-9])", " ", valor)
    valor = re.sub(r"[^A-Z0-9./+%-]+", " ", valor)
    return re.sub(r"\s+", " ", valor).strip()


def extraer_medidas(texto: str | None) -> frozenset[tuple[str, Decimal]]:
    """Convierte sólo masa, volumen y unidades matemáticamente exactas."""

    normalizado = normalizar_texto(texto).replace(",", ".")
    patron = r"(?<![A-Z0-9])([0-9]+(?:\.[0-9]+)?)\s*(MG|KG|ML|UI|G|L|U)\b"
    medidas: set[tuple[str, Decimal]] = set()
    for valor, unidad in re.findall(patron, normalizado):
        unidad_base, factor = _FACTORES[unidad]
        medidas.add((unidad_base, (Decimal(valor) * factor).normalize()))
    return frozenset(medidas)


def extraer_conteos_presentacion(texto: str | None) -> frozenset[tuple[str, int]]:
    """Extrae cantidades sólo cuando están unidas a una forma de envase conocida."""

    normalizado = normalizar_texto(texto)
    conteos: set[tuple[str, int]] = set()
    for unidad in _UNIDADES_PRESENTACION:
        patrones = (
            rf"\b([0-9]{{1,4}})\s*{unidad}\b",
            rf"\b{unidad}\s*(?:(?:CON|C/?|X)\s*)?([0-9]{{1,4}})\b",
        )
        for patron in patrones:
            for cantidad in re.findall(patron, normalizado):
                conteos.add((unidad, int(cantidad)))
    return frozenset(conteos)


def extraer_presentacion_comercial(texto: str | None) -> str | None:
    """Devuelve un conteo comercial sólo cuando hay una lectura inequívoca."""

    conteos = {
        (unidad, cantidad)
        for unidad, cantidad in extraer_conteos_presentacion(texto)
        if unidad in _ETIQUETAS_PRESENTACION
    }
    if len(conteos) != 1:
        return None
    unidad, cantidad = conteos.pop()
    singular, plural = _ETIQUETAS_PRESENTACION[unidad]
    etiqueta = singular if cantidad == 1 else plural
    return f"Caja con {cantidad} {etiqueta}"


def _tokens(texto: str | None) -> frozenset[str]:
    return frozenset(
        token
        for token in re.findall(r"[A-Z][A-Z0-9+-]*", normalizar_texto(texto))
        if token not in _RUIDO and token not in _FACTORES
    )


def termino_busqueda(solicitud: SolicitudProveedor) -> str:
    return normalizar_texto(solicitud.marca) or normalizar_texto(solicitud.producto)


def _decimal_legible(valor: Decimal) -> str:
    return format(valor.normalize(), "f")


def _variantes_medida(unidad_base: str, valor_base: Decimal) -> tuple[str, ...]:
    if unidad_base == "MG":
        return (
            f"{_decimal_legible(valor_base)} mg",
            f"{_decimal_legible(valor_base / Decimal('1000'))} g",
        )
    if unidad_base == "ML":
        return (
            f"{_decimal_legible(valor_base)} mL",
            f"{_decimal_legible(valor_base / Decimal('1000'))} L",
        )
    if unidad_base == "U":
        legible = _decimal_legible(valor_base)
        return (f"{legible} U", f"{legible} UI")
    return ()


def terminos_busqueda_ampliada(solicitud: SolicitudProveedor) -> tuple[str, ...]:
    """Lista abreviaturas y unidades exactas para un único segundo descubrimiento."""

    identidad = " ".join(
        parte or ""
        for parte in (
            solicitud.forma_dispositivo,
            solicitud.concentracion,
            solicitud.presentacion,
        )
    )
    normalizada = normalizar_texto(identidad)
    terminos: list[str] = []
    for canonico, aliases in _ALIASES_BUSQUEDA.items():
        if set(canonico.split()).issubset(set(normalizada.split())):
            terminos.append(" | ".join(aliases))
    for unidad_base, valor in sorted(extraer_medidas(identidad)):
        variantes = _variantes_medida(unidad_base, valor)
        if variantes:
            terminos.append(" | ".join(variantes))
    return tuple(dict.fromkeys(terminos))


def _agregar_motivo(motivos: list[str], motivo: str) -> None:
    if motivo not in motivos:
        motivos.append(motivo)


def _motivo_medidas(
    esperadas: frozenset[tuple[str, Decimal]],
    observadas: frozenset[tuple[str, Decimal]],
    *,
    distinto: str,
) -> str | None:
    faltantes = esperadas - observadas
    if not faltantes:
        return None
    unidades_observadas = {unidad for unidad, _ in observadas}
    if any(unidad in unidades_observadas for unidad, _ in faltantes):
        return distinto
    return "faltan datos suficientes para comprobar coincidencia"


def _conteos_requeridos_presentacion(texto: str | None) -> frozenset[tuple[str, int]]:
    """Evita exigir el contenedor exterior si ya existe un conteo interno inequívoco."""

    conteos = extraer_conteos_presentacion(texto)
    conteos_especificos = {
        (unidad, cantidad) for unidad, cantidad in conteos if unidad != "CAJA"
    }
    if not conteos_especificos:
        return conteos

    cantidades_especificas = {cantidad for _, cantidad in conteos_especificos}
    return frozenset(
        (unidad, cantidad)
        for unidad, cantidad in conteos
        if unidad != "CAJA" or cantidad not in cantidades_especificas
    )


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
        _agregar_motivo(motivos, "precio no utilizable")
    if candidato.stock is not None and candidato.stock <= 0:
        _agregar_motivo(motivos, "sin disponibilidad")
    if tokens_marca and not tokens_marca.issubset(tokens_candidato):
        _agregar_motivo(motivos, "marca distinta")
    elif not tokens_marca and tokens_producto and not tokens_producto.issubset(tokens_candidato):
        _agregar_motivo(motivos, "producto distinto")

    if tokens_forma and not tokens_forma.issubset(tokens_candidato):
        formas_observadas = tokens_candidato & _FORMAS_CONOCIDAS
        motivo_forma = (
            "forma o dispositivo distinto"
            if formas_observadas
            else "faltan datos suficientes para comprobar coincidencia"
        )
        _agregar_motivo(motivos, motivo_forma)

    medidas_candidato = extraer_medidas(candidato.descripcion)
    medidas_concentracion = extraer_medidas(solicitud.concentracion)
    motivo_concentracion = _motivo_medidas(
        medidas_concentracion,
        medidas_candidato,
        distinto="concentración distinta",
    )
    if motivo_concentracion:
        _agregar_motivo(motivos, motivo_concentracion)

    medidas_presentacion = extraer_medidas(solicitud.presentacion) - medidas_concentracion
    motivo_presentacion = _motivo_medidas(
        medidas_presentacion,
        medidas_candidato,
        distinto="presentación distinta",
    )
    if motivo_presentacion:
        _agregar_motivo(motivos, motivo_presentacion)

    conteos_esperados = _conteos_requeridos_presentacion(solicitud.presentacion)
    conteos_observados = extraer_conteos_presentacion(candidato.descripcion)
    conteos_faltantes = conteos_esperados - conteos_observados
    if conteos_faltantes:
        unidades_observadas = {unidad for unidad, _ in conteos_observados}
        motivo_conteo = (
            "presentación distinta"
            if any(unidad in unidades_observadas for unidad, _ in conteos_faltantes)
            else "faltan datos suficientes para comprobar coincidencia"
        )
        _agregar_motivo(motivos, motivo_conteo)

    puntaje = 0
    if not motivos:
        puntaje = (
            4 * len(tokens_marca & tokens_candidato)
            + 2 * len(tokens_producto & tokens_candidato)
            + 3 * len(tokens_forma & tokens_candidato)
            + 5 * len(medidas_concentracion | medidas_presentacion)
            + 5 * len(conteos_esperados)
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
