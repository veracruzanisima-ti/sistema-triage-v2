from decimal import Decimal

from triage.proveedores.base import SolicitudProveedor
from triage.proveedores.coincidencia_catalogo import (
    CandidatoCatalogo,
    evaluar_candidato,
    extraer_relaciones_concentracion,
)


def _candidato(descripcion: str) -> CandidatoCatalogo:
    return CandidatoCatalogo(
        descripcion=descripcion,
        precio_observado=Decimal("100.00"),
        stock=1,
        fuente="prueba",
    )


def _solicitud(concentracion: str) -> SolicitudProveedor:
    return SolicitudProveedor(
        partida_documento_id="metilprednisolona-1",
        producto="ACETATO DE METILPREDNISOLONA",
        marca=None,
        concentracion=concentracion,
        forma_dispositivo="Suspensión inyectable vial",
        presentacion="Frasco ámpula 2 mL",
    )


def test_relacion_concentracion_conserva_el_denominador():
    assert extraer_relaciones_concentracion("40 mg / 2 mL") == frozenset(
        {("MG", Decimal("2E+1"), "ML")}
    )
    assert extraer_relaciones_concentracion("40 mg/mL") == frozenset(
        {("MG", Decimal("4E+1"), "ML")}
    )
    assert extraer_relaciones_concentracion("100 UI por mL") == frozenset(
        {("U", Decimal("1E+2"), "ML")}
    )


def test_40_mg_en_2_ml_no_equivale_a_40_mg_por_ml():
    resultado = evaluar_candidato(
        _solicitud("40 mg / 2 mL"),
        _candidato(
            "ACETATO DE METILPREDNISOLONA 40 MG/ML "
            "SUSPENSION INYECTABLE VIAL 2 ML"
        ),
    )

    assert resultado.coincide is False
    assert "concentración distinta" in resultado.motivos


def test_40_mg_en_2_ml_si_equivale_a_20_mg_por_ml_con_envase_2_ml():
    resultado = evaluar_candidato(
        _solicitud("40 mg / 2 mL"),
        _candidato(
            "ACETATO DE METILPREDNISOLONA 20 MG/ML "
            "SUSPENSION INYECTABLE VIAL 2 ML"
        ),
    )

    assert resultado.coincide is True
    assert resultado.motivos == ()


def test_relacion_solicitada_requiere_relacion_visible_en_candidato():
    resultado = evaluar_candidato(
        _solicitud("40 mg / 2 mL"),
        _candidato(
            "ACETATO DE METILPREDNISOLONA 40 MG "
            "SUSPENSION INYECTABLE VIAL 2 ML"
        ),
    )

    assert resultado.coincide is False
    assert "faltan datos suficientes para comprobar coincidencia" in resultado.motivos
