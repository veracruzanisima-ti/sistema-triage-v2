"""Adaptadores de precio estable y oferta sobre el snapshot local EdiNadro."""

from __future__ import annotations

import re
from dataclasses import replace
from decimal import Decimal

from sqlalchemy import func, select

from triage.proveedores.base import ResultadoProveedor, SolicitudProveedor
from triage.proveedores.coincidencia_catalogo import (
    CandidatoCatalogo,
    normalizar_texto,
    seleccionar_candidato,
)
from triage.proveedores.nadro_modelos import ArticuloNadro, ImportacionNadro, OfertaNadro
from triage.proveedores.nadro_servicio import hay_catalogo_nadro, hay_ofertas_nadro


class AdaptadorNadro:
    """Consulta el precio farmacia estable de la última carga EdiNadro."""

    nombre = "NADRO"

    def __init__(self, fabrica_sesiones) -> None:
        self._fabrica_sesiones = fabrica_sesiones

    def consultar(self, solicitud: SolicitudProveedor) -> ResultadoProveedor:
        with self._fabrica_sesiones() as sesion:
            articulo = _seleccionar_articulo(sesion, solicitud)
            if articulo is None:
                return ResultadoProveedor(encontrado=False, fuente="EdiNadro")
            importacion = sesion.get(ImportacionNadro, articulo.importacion_id)
            return ResultadoProveedor(
                encontrado=True,
                fuente=_fuente(articulo, importacion),
                producto_exacto=articulo.descripcion,
                precio_antes_iva=articulo.precio_farmacia_sin_iva,
                disponibilidad="EdiNadro no incluye existencia en tiempo real.",
            )


class AdaptadorNadroOferta:
    """Expone sólo ofertas con descuento simple calculable sin inventar escalas."""

    nombre = "NADRO oferta"

    def __init__(self, fabrica_sesiones) -> None:
        self._fabrica_sesiones = fabrica_sesiones

    def consultar(self, solicitud: SolicitudProveedor) -> ResultadoProveedor:
        with self._fabrica_sesiones() as sesion:
            articulo = _seleccionar_articulo(sesion, solicitud)
            if articulo is None:
                return ResultadoProveedor(encontrado=False, fuente="EdiNadro · ofertas")
            oferta = sesion.scalar(
                select(OfertaNadro)
                .where(OfertaNadro.codigo_nadro == articulo.codigo_nadro)
                .order_by(OfertaNadro.descuento_factura_pct.desc())
            )
            if oferta is None or not _oferta_simple(oferta):
                return ResultadoProveedor(
                    encontrado=False,
                    fuente=f"EdiNadro · ofertas · código {articulo.codigo_nadro}",
                )
            precio = _precio_oferta(oferta)
            if precio <= 0:
                return ResultadoProveedor(
                    encontrado=False,
                    fuente=f"EdiNadro · ofertas · código {articulo.codigo_nadro}",
                )
            importacion = sesion.get(ImportacionNadro, articulo.importacion_id)
            return ResultadoProveedor(
                encontrado=True,
                fuente=_fuente(articulo, importacion, oferta=True),
                producto_exacto=articulo.descripcion,
                precio_antes_iva=precio,
                es_promocion=True,
                condiciones_promocion=(
                    f"Descuento en factura de {oferta.descuento_factura_pct.normalize()}% "
                    "reportado por EdiNadro."
                ),
                disponibilidad="EdiNadro no incluye existencia en tiempo real.",
            )


def adaptadores_nadro_disponibles(sesion, fabrica_sesiones) -> tuple[object, ...]:
    """Sólo expone NADRO cuando ya existe un snapshot utilizable."""

    if not hay_catalogo_nadro(sesion):
        return ()
    adaptadores: list[object] = [AdaptadorNadro(fabrica_sesiones)]
    if hay_ofertas_nadro(sesion):
        adaptadores.append(AdaptadorNadroOferta(fabrica_sesiones))
    return tuple(adaptadores)


def _seleccionar_articulo(sesion, solicitud: SolicitudProveedor) -> ArticuloNadro | None:
    consulta = select(ArticuloNadro).where(ArticuloNadro.precio_farmacia_sin_iva > 0)
    termino = _termino_amplio(solicitud)
    if termino:
        consulta = consulta.where(func.upper(ArticuloNadro.descripcion).contains(termino))
    articulos = list(sesion.scalars(consulta))
    if not articulos:
        return None

    solicitud_match = _solicitud_para_match(solicitud)
    candidatos = [
        CandidatoCatalogo(
            descripcion=_descripcion_para_match(articulo.descripcion),
            precio_observado=articulo.precio_farmacia_sin_iva,
            stock=None,
            fuente=articulo.codigo_nadro,
        )
        for articulo in articulos
        if _cumple_conteo_presentacion(solicitud_match, articulo.descripcion)
    ]
    seleccion = seleccionar_candidato(solicitud_match, candidatos)
    if seleccion is None:
        return None
    return next(
        articulo for articulo in articulos if articulo.codigo_nadro == seleccion.candidato.fuente
    )


def _termino_amplio(solicitud: SolicitudProveedor) -> str:
    valor = normalizar_texto(solicitud.marca) or normalizar_texto(solicitud.producto)
    tokens = re.findall(r"[A-Z][A-Z0-9+-]{2,}", valor)
    return tokens[0] if tokens else ""


def _solicitud_para_match(solicitud: SolicitudProveedor) -> SolicitudProveedor:
    forma = normalizar_texto(solicitud.forma_dispositivo)
    equivalencias = (
        (("PLUMA",), "PLUMA"),
        (("CARTUCHO",), "CARTUCHO"),
        (("VIAL", "AMPULA", "AMPOLLA"), "VIAL"),
        (("JERINGA",), "JERINGA"),
        (("TABLETA", "TABLETAS", "TAB"), "TAB"),
        (("CAPSULA", "CAPSULAS", "CAP"), "CAP"),
    )
    distintivos = [
        canonico
        for aliases, canonico in equivalencias
        if any(re.search(rf"\b{re.escape(alias)}\b", forma) for alias in aliases)
    ]
    return replace(solicitud, forma_dispositivo=" ".join(distintivos) or None)


def _descripcion_para_match(descripcion: str) -> str:
    texto = descripcion.upper()
    texto = re.sub(r"\bF\.?\s*A\.?\b", " VIAL ", texto)
    texto = re.sub(r"\bFAM\b", " VIAL ", texto)
    texto = re.sub(r"\bJGA\s+PRE\b", " JERINGA ", texto)
    texto = re.sub(r"\bJGA\b", " JERINGA ", texto)
    texto = re.sub(r"\bCART\s+DES\b", " CARTUCHO ", texto)
    texto = re.sub(r"\bCART\b", " CARTUCHO ", texto)
    texto = re.sub(r"\bAMP\b", " VIAL ", texto)
    texto = re.sub(r"\bTABLETAS?\b", " TAB ", texto)
    texto = re.sub(r"\bCAPSULAS?\b", " CAP ", texto)
    texto = re.sub(
        r"\b(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*(MG|G|ML|UI)\b",
        r"\1\3 \2\3",
        texto,
    )
    return normalizar_texto(texto)


def _cumple_conteo_presentacion(solicitud: SolicitudProveedor, descripcion: str) -> bool:
    """Evita mezclar cajas con distinta cantidad cuando el envase la declara."""

    forma = normalizar_texto(solicitud.forma_dispositivo)
    presentacion = normalizar_texto(solicitud.presentacion)
    grupos = (
        ("TAB", ("TABLETA", "TABLETAS", "TAB"), ("TAB",)),
        ("CAP", ("CAPSULA", "CAPSULAS", "CAP"), ("CAP",)),
        ("JERINGA", ("JERINGA", "JERINGAS"), ("JGA", "JERINGA")),
        ("PLUMA", ("PLUMA", "PLUMAS"), ("PLUMA",)),
        ("CARTUCHO", ("CARTUCHO", "CARTUCHOS"), ("CART", "CARTUCHO")),
    )
    for forma_canonica, aliases_solicitud, aliases_catalogo in grupos:
        if not re.search(rf"\b{forma_canonica}\b", forma):
            continue
        esperado = _conteo_junto_a_forma(presentacion, aliases_solicitud)
        if esperado is None:
            return True
        catalogo = normalizar_texto(descripcion)
        patrones = [
            rf"\b{re.escape(alias)}\s+(?:PRE\s+)?{esperado}\b"
            for alias in aliases_catalogo
        ] + [rf"\b{esperado}\s+{re.escape(alias)}\b" for alias in aliases_catalogo]
        return any(re.search(patron, catalogo) for patron in patrones)
    return True


def _conteo_junto_a_forma(texto: str, aliases: tuple[str, ...]) -> str | None:
    for alias in aliases:
        antes = re.search(rf"\b(\d{{1,3}})\s+{re.escape(alias)}\b", texto)
        if antes:
            return antes.group(1)
        despues = re.search(rf"\b{re.escape(alias)}\s+(\d{{1,3}})\b", texto)
        if despues:
            return despues.group(1)
    return None


def _oferta_simple(oferta: OfertaNadro) -> bool:
    return (
        oferta.descuento_factura_pct > 0
        and oferta.cantidad_con_cargo == 0
        and oferta.descuento_primera_escala_pct == 0
        and oferta.descuento_segunda_escala_pct == 0
        and oferta.cantidad_sin_cargo == 0
        and oferta.desde_piezas_primera_escala == 0
        and oferta.desde_piezas_segunda_escala == 0
    )


def _precio_oferta(oferta: OfertaNadro) -> Decimal:
    factor = Decimal("1") - (oferta.descuento_factura_pct / Decimal("100"))
    return (oferta.precio_farmacia_sin_iva * factor).quantize(Decimal("0.01"))


def _fuente(
    articulo: ArticuloNadro,
    importacion: ImportacionNadro | None,
    *,
    oferta: bool = False,
) -> str:
    partes = [
        "EdiNadro",
        "oferta" if oferta else "catálogo",
        f"código {articulo.codigo_nadro}",
    ]
    if importacion is not None:
        partes.append(f"carga {importacion.cargada_en.isoformat()}")
    return " · ".join(partes)
