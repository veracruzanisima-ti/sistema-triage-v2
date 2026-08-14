from decimal import Decimal

import pytest

from triage.proveedores.nadro_edi import (
    ErrorFormatoNadro,
    agrupar_ofertas_por_codigo,
    aplicar_movimientos,
    parsear_linea_catalogo,
    parsear_linea_material,
    parsear_linea_oferta,
)


def _rellenar(valor: str, ancho: int) -> str:
    assert len(valor) <= ancho
    return valor.ljust(ancho)


def _catalogo(
    *,
    codigo: str = "00000545",
    descripcion: str = "LANTUS 100UI 10ML F.A.",
    refrigeracion: str = "1",
) -> str:
    partes = (
        "A",
        codigo,
        "1",
        "A",
        "1",
        " ",
        "0",
        refrigeracion,
        "4",
        "4",
        _rellenar(descripcion, 35),
        _rellenar("PASTEUR", 10),
        "000322700",
        "000213316",
        "0",
        "120826",
        "3664798057973",
        "00000",
        "000213316",
    )
    linea = "".join(partes)
    assert len(linea) == 114
    return linea


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
        "000123450",
        "000098765",
        "0",
        "130826",
        "07501234567890",
    )
    linea = "".join(partes)
    assert len(linea) == 101
    return linea


def _oferta(
    *,
    codigo: str = "00123456",
    descripcion: str = "LANTUS 100 UI/ML FAM 10 ML",
    descuento_factura: str = "01250",
) -> str:
    partes = (
        codigo,
        "07501234567890",
        "07501234567891",
        "07501234567892",
        "4",
        _rellenar(descripcion, 35),
        "000098765",
        "000",
        "000",
        "000",
        "00",
        "00",
        "00",
        descuento_factura,
    )
    linea = "".join(partes)
    assert len(linea) == 115
    return linea


def test_parsea_catalogo_inicial_extendido_segun_posiciones_oficiales():
    registro = parsear_linea_catalogo(_catalogo())

    assert registro.codigo_nadro == "00000545"
    assert registro.descripcion == "LANTUS 100UI 10ML F.A."
    assert registro.laboratorio == "PASTEUR"
    assert registro.precio_publico_sin_iva == Decimal("3227")
    assert registro.precio_venta == Decimal("2133.16")
    assert registro.precio_farmacia_sin_iva == Decimal("2133.16")
    assert registro.codigo_ean == "3664798057973"
    assert registro.requiere_refrigeracion is True


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


def test_parsea_oferta_y_deriva_descuento_simple_sin_iva():
    oferta = parsear_linea_oferta(_oferta())

    assert oferta.codigo_nadro == "00123456"
    assert oferta.precio_farmacia_sin_iva == Decimal("987.65")
    assert oferta.descuento_factura_pct == Decimal("12.5")
    assert oferta.es_descuento_simple_factura is True
    assert oferta.precio_promocional_sin_iva == Decimal("864.19")


def test_no_deriva_precio_promocional_si_hay_una_escala_no_modelada():
    linea = list(_oferta())
    linea[98:101] = "015"
    oferta = parsear_linea_oferta("".join(linea))

    assert oferta.es_descuento_simple_factura is False
    assert oferta.precio_promocional_sin_iva is None


def test_aplica_altas_cambios_y_bajas_sobre_una_base_existente():
    original = parsear_linea_material(_material(descripcion="LANTUS ORIGINAL"))
    cambio = parsear_linea_material(_material(movimiento="C", descripcion="LANTUS CAMBIO"))
    baja = parsear_linea_material(_material(movimiento="B"))

    actualizado = aplicar_movimientos({original.codigo_nadro: original}, (cambio,))
    assert actualizado[original.codigo_nadro].descripcion == "LANTUS CAMBIO"

    actualizado = aplicar_movimientos(actualizado, (baja,))
    assert original.codigo_nadro not in actualizado


def test_no_inventa_significado_para_movimiento_en_blanco_observado_en_archivo_real():
    registro = parsear_linea_material(_material(movimiento=" "))

    with pytest.raises(ErrorFormatoNadro, match="movimiento NADRO no reconocido"):
        aplicar_movimientos({}, (registro,))


def test_agrupa_varias_ofertas_del_mismo_codigo():
    primera = parsear_linea_oferta(_oferta())
    segunda = parsear_linea_oferta(_oferta())

    agrupadas = agrupar_ofertas_por_codigo((primera, segunda))

    assert len(agrupadas["00123456"]) == 2


def test_rechaza_registros_con_ancho_distinto_al_documentado():
    with pytest.raises(ErrorFormatoNadro, match="101 caracteres"):
        parsear_linea_material("demasiado corto")

    with pytest.raises(ErrorFormatoNadro, match="114 caracteres"):
        parsear_linea_catalogo("demasiado corto")
