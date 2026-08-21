"""Sugerencias conservadoras de posibles erratas a partir de resultados web descartados."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from urllib.parse import urlsplit

from triage.proveedores.coincidencia_catalogo import normalizar_texto
from triage.proveedores.modelos import CandidatoWebDescartado

_UMBRAL_SIMILITUD = 0.82
_LONGITUD_MINIMA = 6
_MOTIVOS_IDENTIDAD_INCOMPATIBLES = {
    "marca distinta",
    "forma o dispositivo distinto",
    "concentración distinta",
    "presentación distinta",
    "faltan datos suficientes para comprobar coincidencia",
}


@dataclass(frozen=True)
class CorreccionProductoWeb:
    """Posible corrección informativa; nunca representa una identidad validada."""

    valor: str | None
    fuentes: tuple[str, ...] = ()
    ambigua: bool = False


def _fuente(candidato: CandidatoWebDescartado) -> tuple[str, str]:
    proveedor = " ".join((candidato.proveedor or "").split())
    if proveedor:
        return f"proveedor:{proveedor.casefold()}", proveedor
    dominio = (urlsplit(candidato.url).hostname or candidato.url).casefold()
    return f"url:{dominio}", dominio


def _termino_parecido(producto: str, observado: str | None) -> tuple[str, float] | None:
    """Busca una sola palabra muy parecida; no intenta resolver equivalencias farmacológicas."""

    solicitado = normalizar_texto(producto)
    if (
        not solicitado
        or " " in solicitado
        or not solicitado.isalpha()
        or len(solicitado) < _LONGITUD_MINIMA
    ):
        return None

    candidatos = re.findall(r"\b[A-Z]{6,}\b", normalizar_texto(observado))
    mejores: list[tuple[float, str]] = []
    for termino in candidatos:
        if termino == solicitado or termino[:2] != solicitado[:2]:
            continue
        if abs(len(termino) - len(solicitado)) > 3:
            continue
        similitud = SequenceMatcher(None, solicitado, termino).ratio()
        if similitud >= _UMBRAL_SIMILITUD:
            mejores.append((similitud, termino))
    if not mejores:
        return None
    similitud, termino = max(mejores)
    return termino, similitud


def sugerir_correccion_producto_web(
    producto_actual: str | None,
    producto_buscado: object,
    descartados: Sequence[CandidatoWebDescartado],
) -> CorreccionProductoWeb | None:
    """Sugiere una errata sólo si la búsqueda sigue vigente y no hay otros choques de identidad."""

    actual = normalizar_texto(producto_actual)
    buscado = normalizar_texto(producto_buscado if isinstance(producto_buscado, str) else None)
    if not actual or actual != buscado:
        return None

    por_termino: dict[str, dict[str, object]] = {}
    for candidato in descartados:
        motivos = set(candidato.motivos or ())
        if "producto distinto" not in motivos:
            continue
        if motivos & _MOTIVOS_IDENTIDAD_INCOMPATIBLES:
            continue
        parecido = _termino_parecido(actual, candidato.producto_observado)
        if parecido is None:
            continue
        termino, similitud = parecido
        clave_fuente, etiqueta_fuente = _fuente(candidato)
        registro = por_termino.setdefault(
            termino,
            {"similitud": similitud, "fuentes": {}},
        )
        registro["similitud"] = max(float(registro["similitud"]), similitud)
        fuentes = registro["fuentes"]
        assert isinstance(fuentes, dict)
        fuentes.setdefault(clave_fuente, etiqueta_fuente)

    if not por_termino:
        return None
    if len(por_termino) > 1:
        return CorreccionProductoWeb(valor=None, ambigua=True)

    termino, datos = next(iter(por_termino.items()))
    fuentes = datos["fuentes"]
    assert isinstance(fuentes, dict)
    return CorreccionProductoWeb(
        valor=termino.capitalize(),
        fuentes=tuple(str(etiqueta) for etiqueta in fuentes.values()),
    )
