import re
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from triage.cotizaciones.modelos import Cotizacion
from triage.proveedores.base import SolicitudProveedor
from triage.proveedores.nadro_adaptador import AdaptadorNadro, AdaptadorNadroOferta
from triage.proveedores.nadro_modelos import ArticuloNadro, ImportacionNadro, OfertaNadro
from triage.proveedores.nadro_servicio import ErrorImportacionNadro, importar_snapshot_nadro
from triage.usuarios.modelos import Usuario


def _rellenar(valor: str, ancho: int) -> str:
    assert len(valor) <= ancho
    return valor.ljust(ancho)


def _catalogo(
    *,
    codigo: str = "00000545",
    descripcion: str = "LANTUS 100UI 10ML F.A.",
    precio_farmacia: str = "000213316",
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
        precio_farmacia,
        "0",
        "120826",
        "3664798057973",
        "00000",
        precio_farmacia,
    )
    linea = "".join(partes)
    assert len(linea) == 114
    return linea


def _oferta(
    *,
    codigo: str = "00000545",
    descripcion: str = "LANTUS 100UI 10ML F.A.",
    precio_farmacia: str = "000213316",
    descuento_factura: str = "01250",
) -> str:
    partes = (
        codigo,
        "3664798057973",
        "3664798057974",
        "3664798057975",
        "4",
        _rellenar(descripcion, 35),
        precio_farmacia,
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


def _bytes(*lineas: str) -> bytes:
    return ("\r\n".join(lineas) + "\r\n").encode("cp1252")


def _usuario_id(cliente) -> str:
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario))
        assert usuario is not None
        return usuario.id


def _csrf(html: str) -> str:
    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF")
    return coincidencia.group(1)


def test_importa_snapshot_normalizado_con_hashes_y_oferta(cliente):
    usuario_id = _usuario_id(cliente)
    datos_catalogo = _bytes(_catalogo())
    datos_ofertas = _bytes(_oferta())

    with cliente.app.state.fabrica_sesiones() as sesion:
        importacion = importar_snapshot_nadro(
            sesion,
            usuario_id=usuario_id,
            nombre_catalogo="AutoIICX.dat",
            datos_catalogo=datos_catalogo,
            nombre_ofertas="Oferta.dat",
            datos_ofertas=datos_ofertas,
        )

        articulo = sesion.get(ArticuloNadro, "00000545")
        oferta = sesion.scalar(select(OfertaNadro))
        assert articulo is not None
        assert oferta is not None
        assert importacion.articulos_cargados == 1
        assert importacion.ofertas_cargadas == 1
        assert len(importacion.sha256_catalogo) == 64
        assert len(importacion.sha256_ofertas) == 64
        assert articulo.descripcion == "LANTUS 100UI 10ML F.A."
        assert articulo.requiere_refrigeracion is True
        assert articulo.precio_farmacia_sin_iva == Decimal("2133.16")
        assert oferta.descuento_factura_pct == Decimal("12.50")


def test_archivo_corrupto_conserva_snapshot_anterior(cliente):
    usuario_id = _usuario_id(cliente)

    with cliente.app.state.fabrica_sesiones() as sesion:
        importar_snapshot_nadro(
            sesion,
            usuario_id=usuario_id,
            nombre_catalogo="AutoIICX.dat",
            datos_catalogo=_bytes(_catalogo()),
            nombre_ofertas="Oferta.dat",
            datos_ofertas=_bytes(_oferta()),
        )

        with pytest.raises(ErrorImportacionNadro, match="114 caracteres"):
            importar_snapshot_nadro(
                sesion,
                usuario_id=usuario_id,
                nombre_catalogo="AutoIICX.dat",
                datos_catalogo=b"archivo corrupto\r\n",
                nombre_ofertas="Oferta.dat",
                datos_ofertas=_bytes(_oferta()),
            )

        articulo = sesion.get(ArticuloNadro, "00000545")
        assert articulo is not None
        assert articulo.descripcion == "LANTUS 100UI 10ML F.A."
        assert sesion.scalar(select(func.count()).select_from(ImportacionNadro)) == 1
        assert sesion.scalar(select(func.count()).select_from(OfertaNadro)) == 1


def test_adaptadores_separan_precio_estable_de_oferta(cliente):
    usuario_id = _usuario_id(cliente)
    catalogo = _bytes(
        _catalogo(),
        _catalogo(
            codigo="00000546",
            descripcion="LANTUS 100UI 3ML PLUMA 5",
            precio_farmacia="000250000",
        ),
    )

    with cliente.app.state.fabrica_sesiones() as sesion:
        importar_snapshot_nadro(
            sesion,
            usuario_id=usuario_id,
            nombre_catalogo="AutoIICX.dat",
            datos_catalogo=catalogo,
            nombre_ofertas="Oferta.dat",
            datos_ofertas=_bytes(_oferta()),
        )

    solicitud = SolicitudProveedor(
        partida_documento_id="partida-prueba",
        producto="Insulina glargina",
        marca="Lantus",
        concentracion="100 UI/mL",
        forma_dispositivo="vial",
        presentacion="10 mL",
        codigo_postal="91000",
    )
    estable = AdaptadorNadro(cliente.app.state.fabrica_sesiones).consultar(solicitud)
    promocion = AdaptadorNadroOferta(cliente.app.state.fabrica_sesiones).consultar(solicitud)

    assert estable.encontrado is True
    assert estable.producto_exacto == "LANTUS 100UI 10ML F.A."
    assert estable.precio_antes_iva == Decimal("2133.16")
    assert estable.es_promocion is False
    assert promocion.encontrado is True
    assert promocion.producto_exacto == "LANTUS 100UI 10ML F.A."
    assert promocion.precio_antes_iva == Decimal("1866.52")
    assert promocion.es_promocion is True


def test_carga_nadro_se_vuelve_consultable_sin_reiniciar_app(cliente):
    with cliente.app.state.fabrica_sesiones() as sesion:
        cotizacion = Cotizacion(
            referencia="NADRO-SIN-REINICIO",
            codigo_postal_consulta="91000",
        )
        sesion.add(cotizacion)
        sesion.commit()
        cotizacion_id = cotizacion.id

    antes = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    assert antes.status_code == 200
    assert "Aún no hay proveedores automáticos configurados." in antes.text
    assert "Actualizar NADRO" in antes.text

    formulario = cliente.get(
        f"/proveedores/nadro/actualizar?cotizacion_id={cotizacion_id}"
    )
    assert formulario.status_code == 200
    respuesta = cliente.post(
        "/proveedores/nadro/actualizar",
        data={
            "csrf_token": _csrf(formulario.text),
            "cotizacion_id": cotizacion_id,
        },
        files={
            "catalogo": (
                "AutoIICX.dat",
                _bytes(_catalogo()),
                "application/octet-stream",
            ),
            "ofertas": (
                "Oferta.dat",
                _bytes(_oferta()),
                "application/octet-stream",
            ),
        },
        follow_redirects=False,
    )
    assert respuesta.status_code == 303

    despues = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    assert despues.status_code == 200
    assert "2 fuente(s) configurada(s)" in despues.text
    assert "NADRO" in despues.text
