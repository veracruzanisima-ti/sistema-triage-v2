"""Presentación de precios para la consulta operativa sin alterar el histórico."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from triage.historico.modelos import ObservacionPrecio


@dataclass(frozen=True)
class OportunidadCompraVista:
    """Comparación explicable contra la referencia estable actual."""

    ahorro: Decimal
    porcentaje: Decimal
    base: str


@dataclass(frozen=True)
class VistaPreciosPartida:
    """Separa la referencia visible de las alternativas plegables."""

    referencia: ObservacionPrecio | None
    observaciones: tuple[ObservacionPrecio, ...]
    alternativas: tuple[ObservacionPrecio, ...]
    oportunidades: dict[str, OportunidadCompraVista]


def _clave_orden(observacion: ObservacionPrecio) -> tuple[int, Decimal, str]:
    """Ordena sin comparar un total contra un importe registrado sólo antes de IVA."""

    proveedor = (observacion.proveedor or "").casefold()
    if observacion.precio_total is not None:
        return (0, observacion.precio_total, proveedor)
    if observacion.precio_antes_iva is not None:
        return (1, observacion.precio_antes_iva, proveedor)
    return (2, Decimal("Infinity"), proveedor)


def _comparacion_misma_base(
    observacion: ObservacionPrecio,
    referencia: ObservacionPrecio,
) -> tuple[Decimal, Decimal, str] | None:
    if observacion.precio_total is not None and referencia.precio_total is not None:
        return observacion.precio_total, referencia.precio_total, "precio total"
    if (
        observacion.precio_antes_iva is not None
        and referencia.precio_antes_iva is not None
    ):
        return (
            observacion.precio_antes_iva,
            referencia.precio_antes_iva,
            "precio antes de IVA",
        )
    return None


def preparar_vista_precios(
    observaciones: Sequence[ObservacionPrecio],
    *,
    referencia_id: str | None,
    codigo_postal: str | None,
) -> VistaPreciosPartida:
    """Ordena alternativas y detecta precios realmente menores que la referencia."""

    ordenadas = tuple(sorted(observaciones, key=_clave_orden))
    referencia = next(
        (observacion for observacion in ordenadas if observacion.id == referencia_id),
        None,
    )
    alternativas = tuple(
        observacion
        for observacion in ordenadas
        if referencia is None or observacion.id != referencia.id
    )

    oportunidades: dict[str, OportunidadCompraVista] = {}
    if referencia is not None:
        for observacion in alternativas:
            if observacion.disponibilidad_operativa is not True:
                continue
            if codigo_postal and (
                observacion.codigo_postal != codigo_postal
                or referencia.codigo_postal != codigo_postal
            ):
                continue
            comparacion = _comparacion_misma_base(observacion, referencia)
            if comparacion is None:
                continue
            precio, precio_referencia, base = comparacion
            if precio >= precio_referencia or precio_referencia <= 0:
                continue
            ahorro = precio_referencia - precio
            porcentaje = (ahorro / precio_referencia * Decimal("100")).quantize(
                Decimal("0.1")
            )
            oportunidades[observacion.id] = OportunidadCompraVista(
                ahorro=ahorro,
                porcentaje=porcentaje,
                base=base,
            )

    return VistaPreciosPartida(
        referencia=referencia,
        observaciones=ordenadas,
        alternativas=alternativas,
        oportunidades=oportunidades,
    )
