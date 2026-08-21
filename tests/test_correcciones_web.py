"""Pruebas de sugerencias informativas para posibles erratas de producto."""

from decimal import Decimal

from triage.proveedores.correcciones_web import sugerir_correccion_producto_web
from triage.proveedores.modelos import CandidatoWebDescartado


def _descartado(
    producto: str,
    *,
    proveedor: str = "Farmacias Benavides",
    motivos: list[str] | None = None,
) -> CandidatoWebDescartado:
    return CandidatoWebDescartado(
        consulta_web_id="consulta-prueba",
        proveedor=proveedor,
        producto_observado=producto,
        url="https://farmacia.example/producto",
        precio_observado=Decimal("100"),
        motivos=motivos or ["producto distinto"],
        intento_busqueda=1,
    )


def test_sugiere_lercanidipino_sin_aceptar_el_resultado_descartado():
    correccion = sugerir_correccion_producto_web(
        "Lecardipino",
        "Lecardipino",
        [_descartado("Evipress 10 mg Lercanidipino 30 Tabletas")],
    )

    assert correccion is not None
    assert correccion.valor == "Lercanidipino"
    assert correccion.fuentes == ("Farmacias Benavides",)
    assert correccion.ambigua is False


def test_no_sugiere_nombres_claramente_distintos():
    correccion = sugerir_correccion_producto_web(
        "Lecardipino",
        "Lecardipino",
        [_descartado("Losartan 50 mg 30 tabletas")],
    )

    assert correccion is None


def test_no_sugiere_si_hay_otro_conflicto_de_identidad():
    correccion = sugerir_correccion_producto_web(
        "Lecardipino",
        "Lecardipino",
        [
            _descartado(
                "Lercanidipino 20 mg 30 tabletas",
                motivos=["producto distinto", "concentración distinta"],
            )
        ],
    )

    assert correccion is None


def test_no_usa_sugerencia_de_una_busqueda_que_ya_quedo_obsoleta():
    correccion = sugerir_correccion_producto_web(
        "Lercanidipino",
        "Lecardipino",
        [_descartado("Evipress 10 mg Lercanidipino 30 Tabletas")],
    )

    assert correccion is None


def test_varias_correcciones_plausibles_se_marcan_ambiguas():
    correccion = sugerir_correccion_producto_web(
        "Lecardipino",
        "Lecardipino",
        [
            _descartado("Lercanidipino 10 mg 30 tabletas", proveedor="Fuente A"),
            _descartado("Lecardipina 10 mg 30 tabletas", proveedor="Fuente B"),
        ],
    )

    assert correccion is not None
    assert correccion.valor is None
    assert correccion.ambigua is True


def test_primera_version_no_intenta_corregir_nombres_compuestos():
    correccion = sugerir_correccion_producto_web(
        "Acido acetilsalicilico",
        "Acido acetilsalicilico",
        [_descartado("Acido acetilsalicilico 100 mg")],
    )

    assert correccion is None
