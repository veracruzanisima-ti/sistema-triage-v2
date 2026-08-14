from decimal import Decimal

import pytest
from sqlalchemy import select

from triage.cotizaciones.modelos import Cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.historico.modelos import ObservacionPrecio
from triage.normalizacion.modelos import NormalizacionPartida
from triage.proveedores.base import ResultadoProveedor, SolicitudProveedor
from triage.proveedores.modelos import ConsultaProveedor, EstadoConsultaProveedor
from triage.proveedores.servicio import (
    ErrorConsultaProveedor,
    ejecutar_consulta,
    ejecutar_consultas_configuradas,
)
from triage.usuarios.modelos import Usuario


def _preparar_producto(cliente, codigo_postal: str | None = "91000") -> tuple[str, str, str]:
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario))
        assert usuario is not None
        cotizacion = Cotizacion(
            referencia="PROVEEDORES-PRUEBA",
            codigo_postal_consulta=codigo_postal,
        )
        sesion.add(cotizacion)
        sesion.flush()
        documento = Documento(
            cotizacion_id=cotizacion.id,
            nombre_original="prueba.pdf",
            mime_type="application/pdf",
            tamano_bytes=10,
            sha256="a" * 64,
            estado=EstadoDocumento.REVISADO.value,
        )
        sesion.add(documento)
        sesion.flush()
        partida = PartidaDocumento(
            documento_id=documento.id,
            orden=1,
            producto_solicitado="LANTUS",
            incluida_cotizacion=True,
        )
        sesion.add(partida)
        sesion.flush()
        sesion.add(
            NormalizacionPartida(
                partida_documento_id=partida.id,
                producto="LANTUS",
                marca="Lantus",
                concentracion="100 U/mL",
                forma_dispositivo="vial",
                presentacion="10 mL",
                confirmada_por_usuario_id=usuario.id,
            )
        )
        sesion.commit()
        return cotizacion.id, partida.id, usuario.id


class CanalExitoso:
    nombre = "Canal Prueba"

    def consultar(self, solicitud: SolicitudProveedor) -> ResultadoProveedor:
        assert solicitud.forma_dispositivo == "vial"
        assert solicitud.codigo_postal == "91000"
        return ResultadoProveedor(
            encontrado=True,
            fuente="fuente de prueba",
            producto_exacto="LANTUS VIAL 10 mL",
            precio_total=Decimal("123.45"),
            disponibilidad="5 piezas",
            es_promocion=True,
        )


class CanalVacio:
    nombre = "Canal Vacío"

    def consultar(self, solicitud: SolicitudProveedor) -> ResultadoProveedor:
        assert solicitud.producto == "LANTUS"
        return ResultadoProveedor(encontrado=False, fuente="fuente de prueba")


class CanalConError:
    nombre = "Canal Error"

    def consultar(self, solicitud: SolicitudProveedor) -> ResultadoProveedor:
        raise RuntimeError("detalle interno de prueba")


def test_consulta_exitosa_crea_observacion_append_only_con_cp(cliente):
    cotizacion_id, partida_id, usuario_id = _preparar_producto(cliente)
    with cliente.app.state.fabrica_sesiones() as sesion:
        intento = ejecutar_consulta(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_id,
            usuario_id=usuario_id,
            proveedor=CanalExitoso(),
        )
        assert intento.estado == EstadoConsultaProveedor.EXITOSA.value
        assert intento.observacion_precio_id is not None
        assert intento.criterios_busqueda["codigo_postal"] == "91000"
        observacion = sesion.get(ObservacionPrecio, intento.observacion_precio_id)
        assert observacion is not None
        assert observacion.proveedor == "Canal Prueba"
        assert observacion.codigo_postal == "91000"
        assert str(observacion.precio_total) == "123.45"


def test_busqueda_unificada_continua_si_una_fuente_falla(cliente):
    cotizacion_id, _, usuario_id = _preparar_producto(cliente)
    with cliente.app.state.fabrica_sesiones() as sesion:
        resumen = ejecutar_consultas_configuradas(
            sesion,
            cotizacion_id=cotizacion_id,
            usuario_id=usuario_id,
            proveedores=(CanalExitoso(), CanalVacio(), CanalConError()),
        )
        assert resumen.intentos == 3
        assert resumen.precios_encontrados == 1
        assert resumen.no_encontrados == 1
        assert resumen.errores == 1
        assert len(list(sesion.scalars(select(ConsultaProveedor)))) == 3
        assert len(list(sesion.scalars(select(ObservacionPrecio)))) == 1


def test_busqueda_unificada_se_expone_como_accion_principal(cliente):
    cotizacion_id, _, _ = _preparar_producto(cliente)
    cliente.app.state.proveedores_productos = {
        "canal prueba": CanalExitoso(),
        "canal vacío": CanalVacio(),
    }

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    assert pagina.status_code == 200
    assert f'/cotizaciones/{cotizacion_id}/proveedores/consultar' in pagina.text
    assert "Buscar precios" in pagina.text

    respuesta = cliente.post(
        f"/cotizaciones/{cotizacion_id}/proveedores/consultar",
        data={"csrf_token": pagina.cookies.get("csrf_token", "") or ""},
        follow_redirects=False,
    )
    if respuesta.status_code == 422:
        import re

        token = re.search(r'name="csrf_token" value="([^"]+)"', pagina.text)
        assert token is not None
        respuesta = cliente.post(
            f"/cotizaciones/{cotizacion_id}/proveedores/consultar",
            data={"csrf_token": token.group(1)},
            follow_redirects=False,
        )
    assert respuesta.status_code == 303
    assert "resultado=unificada" in respuesta.headers["location"]
    resultado = cliente.get(respuesta.headers["location"])
    assert "Búsqueda completada: 1 precio(s) encontrado(s)." in resultado.text


def test_consulta_automatica_exige_codigo_postal(cliente):
    cotizacion_id, partida_id, usuario_id = _preparar_producto(
        cliente,
        codigo_postal=None,
    )
    with cliente.app.state.fabrica_sesiones() as sesion:
        with pytest.raises(ValueError, match="código postal"):
            ejecutar_consulta(
                sesion,
                cotizacion_id=cotizacion_id,
                partida_documento_id=partida_id,
                usuario_id=usuario_id,
                proveedor=CanalVacio(),
            )
        assert list(sesion.scalars(select(ConsultaProveedor))) == []


def test_no_encontrado_deja_traza_sin_inventar_precio(cliente):
    cotizacion_id, partida_id, usuario_id = _preparar_producto(cliente)
    with cliente.app.state.fabrica_sesiones() as sesion:
        intento = ejecutar_consulta(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_id,
            usuario_id=usuario_id,
            proveedor=CanalVacio(),
        )
        assert intento.estado == EstadoConsultaProveedor.NO_ENCONTRADO.value
        assert intento.criterios_busqueda["codigo_postal"] == "91000"
        assert intento.observacion_precio_id is None
        assert list(sesion.scalars(select(ObservacionPrecio))) == []


def test_error_se_sanitiza_y_permanece_trazable(cliente):
    cotizacion_id, partida_id, usuario_id = _preparar_producto(cliente)
    with cliente.app.state.fabrica_sesiones() as sesion:
        with pytest.raises(ErrorConsultaProveedor):
            ejecutar_consulta(
                sesion,
                cotizacion_id=cotizacion_id,
                partida_documento_id=partida_id,
                usuario_id=usuario_id,
                proveedor=CanalConError(),
            )
        intento = sesion.scalar(select(ConsultaProveedor))
        assert intento is not None
        assert intento.estado == EstadoConsultaProveedor.ERROR.value
        assert intento.criterios_busqueda["codigo_postal"] == "91000"
        assert intento.mensaje_error == "El proveedor no pudo completar la consulta."
        assert "detalle interno" not in intento.mensaje_error
