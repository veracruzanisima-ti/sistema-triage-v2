from decimal import Decimal

from triage.proveedores.base import SolicitudProveedor
from triage.proveedores.coincidencia_catalogo import (
    CandidatoCatalogo,
    evaluar_candidato,
    extraer_medidas,
    seleccionar_candidato,
    termino_busqueda,
)


def solicitud() -> SolicitudProveedor:
    return SolicitudProveedor(
        partida_documento_id="p1",
        producto="PRODUCTO ALFA",
        marca="Marca Alfa",
        concentracion="100 U/mL",
        forma_dispositivo="vial",
        presentacion="Frasco 10 mL",
    )


def candidato(texto: str, stock: int = 3) -> CandidatoCatalogo:
    return CandidatoCatalogo(texto, Decimal("100.00"), stock, "fuente de prueba")


def test_catalogo_convierte_medidas_equivalentes():
    assert extraer_medidas("1.6 kg 1 L") == extraer_medidas("1600 g 1000 mL")


def test_catalogo_rechaza_volumen_distinto():
    resultado = evaluar_candidato(
        solicitud(), candidato("MARCA ALFA PRODUCTO ALFA VIAL 100 U/ML 3 ML")
    )
    assert resultado.coincide is False
    assert "medida o concentración distinta" in resultado.motivos


def test_catalogo_rechaza_dispositivo_distinto():
    resultado = evaluar_candidato(
        solicitud(), candidato("MARCA ALFA PRODUCTO ALFA PLUMA 100 U/ML 10 ML")
    )
    assert resultado.coincide is False
    assert "forma o dispositivo distinto" in resultado.motivos


def test_catalogo_reconoce_ampula_como_vial():
    solicitud_lantus = SolicitudProveedor(
        partida_documento_id="lantus-1",
        producto="Insulina glargina",
        marca="LANTUS",
        concentracion="100 UI/mL",
        forma_dispositivo="Solución inyectable - vial",
        presentacion="Frasco vial de 10 mL",
    )
    resultado = evaluar_candidato(
        solicitud_lantus,
        candidato("Lantus 100UI/ml Solución Inyectable Ámpula, 10 ml"),
    )

    assert resultado.coincide is True
    assert resultado.motivos == ()


def test_catalogo_prefiere_marca_explicita_para_busqueda():
    assert termino_busqueda(solicitud()) == "MARCA ALFA"


def test_catalogo_no_resuelve_empate_automaticamente():
    candidatos = [
        candidato("MARCA ALFA PRODUCTO ALFA VIAL 100 U/ML 10 ML A"),
        candidato("MARCA ALFA PRODUCTO ALFA VIAL 100 U/ML 10 ML B"),
    ]
    assert seleccionar_candidato(solicitud(), candidatos) is None
