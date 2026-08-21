"""Sugiere revisar una concentración cuando varias fuentes web convergen en otra razón."""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlsplit

from triage.proveedores.base import SolicitudProveedor
from triage.proveedores.coincidencia_catalogo import (
    CandidatoCatalogo,
    evaluar_candidato,
    extraer_medidas,
    extraer_relaciones_concentracion,
    normalizar_texto,
)
from triage.proveedores.modelos import CandidatoWebDescartado

_TOKENS_SAL_O_FORMULACION = {
    "ACETATO",
    "CLORHIDRATO",
    "FOSFATO",
    "HIDROCLORURO",
    "SODICA",
    "SODICO",
    "SUCCINATO",
}
_MOTIVOS_INCOMPATIBLES = {
    "marca distinta",
    "forma o dispositivo distinto",
    "presentación distinta",
}


@dataclass(frozen=True)
class CorreccionConcentracionWeb:
    """Posible corrección informativa; nunca sustituye la revisión del documento."""

    valor: str | None
    fuentes: tuple[str, ...] = ()
    ambigua: bool = False


def _limpiar(valor: object | None) -> str | None:
    texto = " ".join(str(valor or "").split())
    return texto or None


def _fuente(candidato: CandidatoWebDescartado) -> tuple[str, str]:
    proveedor = _limpiar(candidato.proveedor)
    if proveedor:
        return f"proveedor:{proveedor.casefold()}", proveedor
    dominio = (urlsplit(candidato.url).hostname or candidato.url).casefold()
    return f"url:{dominio}", dominio


def _tokens_producto_significativos(producto: str | None) -> frozenset[str]:
    return frozenset(
        token
        for token in re.findall(r"\b[A-Z][A-Z0-9+-]{5,}\b", normalizar_texto(producto))
        if token not in _TOKENS_SAL_O_FORMULACION
    )


def _formatear_relacion(relacion: tuple[str, Decimal, str]) -> str:
    numerador, valor, denominador = relacion
    etiquetas_numerador = {"MG": "mg", "U": "U"}
    etiquetas_denominador = {"ML": "mL"}
    cantidad = format(valor.normalize(), "f")
    return (
        f"{cantidad} {etiquetas_numerador.get(numerador, numerador)}"
        f"/{etiquetas_denominador.get(denominador, denominador)}"
    )


def _criterios_siguen_vigentes(
    *,
    producto_actual: str | None,
    marca_actual: str | None,
    concentracion_actual: str | None,
    forma_actual: str | None,
    presentacion_actual: str | None,
    criterios_busqueda: Mapping[str, object],
) -> bool:
    pares = (
        (producto_actual, criterios_busqueda.get("producto")),
        (marca_actual, criterios_busqueda.get("marca")),
        (concentracion_actual, criterios_busqueda.get("concentracion")),
        (forma_actual, criterios_busqueda.get("forma_dispositivo")),
        (presentacion_actual, criterios_busqueda.get("presentacion")),
    )
    return all(
        normalizar_texto(actual)
        == normalizar_texto(buscado if isinstance(buscado, str) else None)
        for actual, buscado in pares
    )


def _presentacion_sin_conflicto_explicito(
    presentacion_actual: str | None,
    observado: str,
) -> bool:
    """Rechaza sólo contradicciones de medida visibles; la falta de dato sigue siendo revisable."""

    esperadas = extraer_medidas(presentacion_actual)
    observadas = extraer_medidas(observado)
    for unidad, valor in esperadas:
        valores_observados = {
            valor_observado
            for unidad_observada, valor_observado in observadas
            if unidad_observada == unidad
        }
        if valores_observados and valor not in valores_observados:
            return False
    return True


def sugerir_correccion_concentracion_web(
    *,
    producto_actual: str | None,
    marca_actual: str | None,
    concentracion_actual: str | None,
    forma_actual: str | None,
    presentacion_actual: str | None,
    criterios_busqueda: Mapping[str, object],
    descartados: Sequence[CandidatoWebDescartado],
) -> CorreccionConcentracionWeb | None:
    """Sugiere otra concentración sólo con convergencia independiente y sin choques duros."""

    if not _criterios_siguen_vigentes(
        producto_actual=producto_actual,
        marca_actual=marca_actual,
        concentracion_actual=concentracion_actual,
        forma_actual=forma_actual,
        presentacion_actual=presentacion_actual,
        criterios_busqueda=criterios_busqueda,
    ):
        return None

    relaciones_actuales = extraer_relaciones_concentracion(concentracion_actual)
    if len(relaciones_actuales) != 1:
        return None
    relacion_actual = next(iter(relaciones_actuales))

    tokens_producto = _tokens_producto_significativos(producto_actual)
    if not tokens_producto:
        return None

    solicitud = SolicitudProveedor(
        partida_documento_id="sugerencia-concentracion",
        producto=producto_actual,
        marca=marca_actual,
        concentracion=concentracion_actual,
        forma_dispositivo=forma_actual,
        presentacion=presentacion_actual,
    )
    por_relacion: dict[tuple[str, Decimal, str], dict[str, str]] = {}
    for candidato in descartados:
        observado = _limpiar(candidato.producto_observado)
        if observado is None:
            continue
        if tokens_producto.isdisjoint(_tokens_producto_significativos(observado)):
            continue
        if not _presentacion_sin_conflicto_explicito(presentacion_actual, observado):
            continue

        relaciones = extraer_relaciones_concentracion(observado)
        if len(relaciones) != 1:
            continue
        relacion = next(iter(relaciones))
        if relacion == relacion_actual:
            continue

        evaluacion = evaluar_candidato(
            solicitud,
            CandidatoCatalogo(
                descripcion=observado,
                precio_observado=candidato.precio_observado or Decimal("1"),
                stock=None,
                fuente=candidato.url,
            ),
        )
        if set(evaluacion.motivos) & _MOTIVOS_INCOMPATIBLES:
            continue

        clave_fuente, etiqueta_fuente = _fuente(candidato)
        por_relacion.setdefault(relacion, {}).setdefault(clave_fuente, etiqueta_fuente)

    if not por_relacion:
        return None
    if len(por_relacion) > 1:
        return CorreccionConcentracionWeb(valor=None, ambigua=True)

    relacion, fuentes = next(iter(por_relacion.items()))
    if len(fuentes) < 2:
        return None
    return CorreccionConcentracionWeb(
        valor=_formatear_relacion(relacion),
        fuentes=tuple(fuentes.values()),
    )
