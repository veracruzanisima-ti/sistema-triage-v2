"""Catálogo ficticio: sugerencias verificables sin sustituir la evidencia."""

import pytest

from triage.lectores.catalogo import ProductoCatalogo, sugerir_desde_catalogo
from triage.lectores.esquemas import PartidaLeida


def _partida():
    return PartidaLeida(
        producto_solicitado="Paraceta mol",
        texto_original="Paraceta mol 500 mg caja 10 tabletas",
        nombre_normalizado="Paracetamol",
        sustancia_activa="Paracetamol",
        concentracion="500 mg",
        forma_farmaceutica_dispositivo="tableta",
        presentacion_solicitada="Caja con 10 tabletas",
        cantidad=None,
    )


def _producto(**cambios):
    valores = dict(
        id="FICTICIO-001",
        fuente="catalogo-ficticio-v1",
        nombre_comercial="Marca ficticia",
        sustancia_activa="Paracetamol",
        concentracion="500 mg",
        forma_farmaceutica_dispositivo="tableta",
        presentacion="Caja con 10 tabletas",
    )
    return ProductoCatalogo(**(valores | cambios))


def test_sugerencia_se_verifica_y_no_modifica_extraccion():
    partida = _partida()
    antes = partida.model_dump()
    producto = _producto()
    resultado = sugerir_desde_catalogo(partida, [producto])
    assert [s.producto for s in resultado] == [producto]
    assert resultado[0].producto.id == "FICTICIO-001"
    assert resultado[0].producto.fuente == "catalogo-ficticio-v1"
    assert partida.model_dump() == antes


@pytest.mark.parametrize(
    "cambios",
    [
        {"concentracion": "650 mg"},
        {"sustancia_activa": "Ibuprofeno"},
        {"forma_farmaceutica_dispositivo": "solución"},
        {"presentacion": "Caja con 20 tabletas"},
        {"fuente": ""},
    ],
)
def test_catalogo_incompatible_no_sugiere(cambios):
    assert sugerir_desde_catalogo(_partida(), [_producto(**cambios)]) == []


@pytest.mark.parametrize(
    "campo",
    [
        "sustancia_activa",
        "concentracion",
        "forma_farmaceutica_dispositivo",
        "presentacion_solicitada",
    ],
)
def test_identidad_incompleta_no_se_completa_con_catalogo(campo):
    partida = _partida().model_copy(update={campo: None})
    assert sugerir_desde_catalogo(partida, [_producto()]) == []
    assert getattr(partida, campo) is None


def test_no_sustituye_marca_solicitada():
    partida = _partida().model_copy(update={"marca_solicitada": "Otra marca ficticia"})
    assert sugerir_desde_catalogo(partida, [_producto()]) == []
