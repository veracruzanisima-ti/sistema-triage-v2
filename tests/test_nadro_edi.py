from decimal import Decimal

import pytest

from triage.proveedores.nadro_edi import (
    ErrorFormatoNadro,
    agrupar_ofertas_por_codigo,
    aplicar_movimientos,
    parsear_linea_material,
    parsear_linea_oferta,
)


def _rellenar(valor: str, ancho: int) -> str:
    assert len(valor) <= ancho
    return valor.ljust(ancho)


def _material(
    *,
    movimiento: str = "A",
    codigo: str = "00123456",
    descripcion: str = "LANTUS 100 UI/ML FAM 10 ML",
    vigencia: str = "1",
    refrigeracion: str = "1",
) -> str:
    partes = (
        movimiento,
        codigo,
        "1",
        "2",
        "3",
        " ",
        vigencia,
        refrigeracion,
        "4",
        "4",
        _rellenar(descripcion, 35),
        _rellenar("SANOFI", 10),
        "001234.50",
        "000987.65",
        "0",
        "130826",
        "07501234567890",
    )
    linea = "".join(partes)
    assert len(linea) == 101
    return linea


def _oferta(*, codigo: str = "00123456", descripcion: str = "LANTUS 100 UI/ML FAM 10 ML") -> str:
    partes = (
        codigo,
        "07501234567890",
        "07501234567891",
        "07501234567892",
        "4",
        _rellenar(descripcion, 35),
        "000987.65",
        "010",
        "015",
        "020",
        "02",
        "05",
        "10",
        "01250",
    )
    linea = "".join(partes)
    assert len(linea) == 115
    return linea


def test_parsea_material_segun_posiciones_oficiales():
    registro = parsear_linea_material(_material())

    assert registro.codigo_nadro == "00123456"
    assert registro.descripcion == "LANTUS 100 UI/ML FAM 10 ML"
    assert registro.laboratorio == "SANOFI"
    assert registro.precio_publico_sin_iva == Decimal("1234.50")
    assert registro.precio_farmacia_sin_iva == Decimal("987.65")
    assert registro.codigo_ean == "07501234567890"
    assert registro.fecha_ultimo_movimiento == "130826"
    assert registro.vigente is True
    assert registro.requiere_refrigeracion is True


def test_parsea_oferta_sin_convertirla_en_decision_comercial():
    oferta = parsear_linea_oferta(_oferta())

    assert oferta.codigo_nadro == "00123456"
    assert oferta.precio_farmacia_sin_iva == Decimal("987.65")
    assert oferta.cantidad_con_cargo == 10
    assert oferta.descuento_primera_escala_pct == Decimal("15")
    assert oferta.descuento_segunda_escala_pct == Decimal("20")
    assert oferta.cantidad_sin_cargo == 2
    assert oferta.desde_piezas_primera_escala == 5
    assert oferta.desde_piezas_segunda_escala == 10
    assert oferta.descuento_factura_pct == Decimal("12.5")


def test_aplica_altas_cambios_y_bajas_sobre_una_base_existente():
    original = parsear_linea_material(_material(descripcion="LANTUS ORIGINAL"))
    cambio = parsear_linea_material(_material(movimiento="C", descripcion="LANTUS CAMBIO"))
    baja = parsear_linea_material(_material(movimiento="B"))

    actualizado = aplicar_movimientos({original.codigo_nadro: original}, (cambio,))
    assert actualizado[original.codigo_nadro].descripcion == "LANTUS CAMBIO"

    actualizado = aplicar_movimientos(actualizado, (baja,))
    assert original.codigo_nadro not in actualizado


def test_agrupa_varias_ofertas_del_mismo_codigo():
    primera = parsear_linea_oferta(_oferta())
    segunda = parsear_linea_oferta(_oferta())

    agrupadas = agrupar_ofertas_por_codigo((primera, segunda))

    assert len(agrupadas["00123456"]) == 2


def test_rechaza_registros_con_ancho_distinto_al_documentado():
    with pytest.raises(ErrorFormatoNadro, match="101 caracteres"):
        parsear_linea_material("demasiado corto")
