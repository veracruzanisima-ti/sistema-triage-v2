from decimal import Decimal
from types import SimpleNamespace

from triage.proveedores.vista_precios import preparar_vista_precios


def _observacion(
    identificador: str,
    proveedor: str,
    *,
    total: str | None = None,
    antes_iva: str | None = None,
    codigo_postal: str = "91193",
    entrega_viable: bool | None = True,
):
    return SimpleNamespace(
        id=identificador,
        proveedor=proveedor,
        precio_total=Decimal(total) if total is not None else None,
        precio_antes_iva=Decimal(antes_iva) if antes_iva is not None else None,
        codigo_postal=codigo_postal,
        entrega_viable=entrega_viable,
        disponibilidad_operativa=entrega_viable,
    )


def test_ordena_totales_de_menor_a_mayor_y_no_mezcla_base_antes_iva():
    observaciones = (
        _observacion("alto", "Proveedor alto", total="2660.50"),
        _observacion("antes", "Proveedor antes IVA", antes_iva="1200.00"),
        _observacion("bajo", "Proveedor bajo", total="1733.00"),
        _observacion("medio", "Proveedor medio", total="2113.68"),
    )

    vista = preparar_vista_precios(
        observaciones,
        referencia_id=None,
        codigo_postal="91193",
    )

    assert [observacion.id for observacion in vista.observaciones] == [
        "bajo",
        "medio",
        "alto",
        "antes",
    ]


def test_promocion_mas_cara_no_se_convierte_en_oportunidad_por_ser_promocion():
    referencia = _observacion("referencia", "Curitek", total="1733.00")
    promocion_mas_cara = _observacion("promo", "Guadalajara", total="2113.68")

    vista = preparar_vista_precios(
        (promocion_mas_cara, referencia),
        referencia_id=referencia.id,
        codigo_postal="91193",
    )

    assert vista.referencia is referencia
    assert vista.alternativas == (promocion_mas_cara,)
    assert vista.oportunidades == {}


def test_alternativa_realmente_mas_barata_si_es_oportunidad():
    referencia = _observacion("referencia", "Curitek", total="1733.00")
    barata = _observacion("barata", "Proveedor barato", total="1500.00")

    vista = preparar_vista_precios(
        (referencia, barata),
        referencia_id=referencia.id,
        codigo_postal="91193",
    )

    oportunidad = vista.oportunidades[barata.id]
    assert oportunidad.ahorro == Decimal("233.00")
    assert oportunidad.porcentaje == Decimal("13.4")
    assert oportunidad.base == "precio total"


def test_no_marca_oportunidad_si_el_codigo_postal_es_distinto():
    referencia = _observacion("referencia", "Curitek", total="1733.00")
    barata_otro_cp = _observacion(
        "barata",
        "Proveedor barato",
        total="1500.00",
        codigo_postal="91000",
    )

    vista = preparar_vista_precios(
        (referencia, barata_otro_cp),
        referencia_id=referencia.id,
        codigo_postal="91193",
    )

    assert vista.oportunidades == {}
