from decimal import Decimal
from types import SimpleNamespace

from triage.proveedores.correcciones_concentracion_web import (
    sugerir_correccion_concentracion_web,
)


CRITERIOS = {
    "producto": "ACETATO DE METILPREDNISOLONA",
    "marca": None,
    "concentracion": "40 mg / 2 mL",
    "forma_dispositivo": "Suspensión inyectable",
    "presentacion": "Frasco ámpula 2 mL",
}


def _descartado(proveedor: str, producto: str, *, intento: int = 1):
    return SimpleNamespace(
        proveedor=proveedor,
        producto_observado=producto,
        url=f"https://{proveedor.casefold().replace(' ', '-')}.example/producto",
        precio_observado=Decimal("100.00"),
        motivos=["producto distinto"],
        intento_busqueda=intento,
    )


def _sugerir(descartados, **cambios):
    argumentos = {
        "producto_actual": "ACETATO DE METILPREDNISOLONA",
        "marca_actual": None,
        "concentracion_actual": "40 mg / 2 mL",
        "forma_actual": "Suspensión inyectable",
        "presentacion_actual": "Frasco ámpula 2 mL",
        "criterios_busqueda": CRITERIOS,
        "descartados": descartados,
    }
    argumentos.update(cambios)
    return sugerir_correccion_concentracion_web(**argumentos)


def test_dos_fuentes_independientes_sugieren_40_mg_por_ml():
    sugerencia = _sugerir(
        [
            _descartado(
                "Farmatodo",
                "Metilprednisolona Suspensión Inyectable 40 mg/mL Frasco Ámpula 2 mL",
            ),
            _descartado(
                "Curitek",
                "ACETATO DE METILPREDNISOLONA 40 MG/ML INYECTABLE VIAL 2 ML",
            ),
        ]
    )

    assert sugerencia is not None
    assert sugerencia.valor == "40 mg/mL"
    assert sugerencia.fuentes == ("Farmatodo", "Curitek")
    assert sugerencia.ambigua is False


def test_una_sola_fuente_no_basta_aunque_aparezca_en_dos_intentos():
    sugerencia = _sugerir(
        [
            _descartado(
                "Farmatodo",
                "Metilprednisolona Suspensión Inyectable 40 mg/mL Vial 2 mL",
                intento=1,
            ),
            _descartado(
                "Farmatodo",
                "Metilprednisolona Suspensión Inyectable 40 mg/mL Vial 2 mL",
                intento=2,
            ),
        ]
    )

    assert sugerencia is None


def test_concentraciones_alternativas_en_conflicto_no_eligen_una():
    sugerencia = _sugerir(
        [
            _descartado(
                "Farmatodo",
                "Metilprednisolona Suspensión Inyectable 40 mg/mL Vial 2 mL",
            ),
            _descartado(
                "Curitek",
                "Acetato de Metilprednisolona Suspensión Inyectable 20 mg/mL Vial 2 mL",
            ),
        ]
    )

    assert sugerencia is not None
    assert sugerencia.valor is None
    assert sugerencia.ambigua is True


def test_conflicto_de_forma_o_presentacion_no_apoya_sugerencia():
    sugerencia = _sugerir(
        [
            _descartado(
                "Farmacia Tabletas",
                "Metilprednisolona 40 mg/mL TABLETAS caja con 30",
            ),
            _descartado(
                "Farmacia Vial 5",
                "Metilprednisolona Suspensión Inyectable 40 mg/mL Vial 5 mL",
            ),
        ]
    )

    assert sugerencia is None


def test_marca_sin_nombre_generico_no_sugiere_concentracion_por_si_sola():
    sugerencia = _sugerir(
        [
            _descartado("Farmacia Uno", "Depo-Medrol 40 mg/mL Suspensión Vial 2 mL"),
            _descartado("Farmacia Dos", "Depo-Medrol 40 mg/mL Suspensión Vial 2 mL"),
        ]
    )

    assert sugerencia is None


def test_sugerencia_se_invalida_si_la_preparacion_cambio_despues_de_buscar():
    sugerencia = _sugerir(
        [
            _descartado(
                "Farmatodo",
                "Metilprednisolona Suspensión Inyectable 40 mg/mL Vial 2 mL",
            ),
            _descartado(
                "Curitek",
                "Acetato de Metilprednisolona 40 mg/mL Suspensión Inyectable Vial 2 mL",
            ),
        ],
        concentracion_actual="40 mg/mL",
    )

    assert sugerencia is None
