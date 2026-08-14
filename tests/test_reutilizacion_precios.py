"""Regresión de reutilización diaria sin ocultar decisiones humanas."""

import re
from decimal import Decimal

from sqlalchemy import select

from triage.cotizaciones.modelos import Cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.historico.decisiones_modelos import RolDecisionPrecio
from triage.historico.decisiones_servicio import registrar_decision_precio
from triage.historico.modelos import ObservacionPrecio
from triage.historico.servicio import crear_observacion_precio
from triage.normalizacion.modelos import NormalizacionPartida
from triage.proveedores.base import ResultadoProveedor, SolicitudProveedor
from triage.proveedores.modelos import ConsultaProveedor
from triage.proveedores.servicio import ejecutar_consultas_configuradas
from triage.usuarios.modelos import Usuario


def _csrf(html: str) -> str:
    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF")
    return coincidencia.group(1)


def _agregar_producto(
    sesion,
    *,
    usuario_id: str,
    cotizacion: Cotizacion,
    orden: int,
    sha: str,
) -> PartidaDocumento:
    documento = Documento(
        cotizacion_id=cotizacion.id,
        nombre_original=f"reutilizacion-{orden}.pdf",
        mime_type="application/pdf",
        tamano_bytes=10,
        sha256=sha * 64,
        estado=EstadoDocumento.REVISADO.value,
    )
    sesion.add(documento)
    sesion.flush()
    partida = PartidaDocumento(
        documento_id=documento.id,
        orden=orden,
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
            confirmada_por_usuario_id=usuario_id,
        )
    )
    sesion.flush()
    return partida


def _crear_cotizacion_con_producto(
    sesion,
    *,
    usuario_id: str,
    referencia: str,
    codigo_postal: str = "91000",
    sha: str = "a",
) -> tuple[Cotizacion, PartidaDocumento]:
    cotizacion = Cotizacion(
        referencia=referencia,
        codigo_postal_consulta=codigo_postal,
    )
    sesion.add(cotizacion)
    sesion.flush()
    partida = _agregar_producto(
        sesion,
        usuario_id=usuario_id,
        cotizacion=cotizacion,
        orden=1,
        sha=sha,
    )
    sesion.commit()
    return cotizacion, partida


class CanalContador:
    nombre = "Canal Contador"

    def __init__(self) -> None:
        self.consultas = 0

    def consultar(self, solicitud: SolicitudProveedor) -> ResultadoProveedor:
        self.consultas += 1
        return ResultadoProveedor(
            encontrado=True,
            fuente="fuente contador",
            producto_exacto="Lantus 100 U/mL vial 10 mL",
            precio_total=Decimal("1000.00"),
            disponibilidad="Disponible",
        )


def test_partidas_identicas_se_consultan_una_sola_vez(cliente):
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario))
        assert usuario is not None
        cotizacion, _ = _crear_cotizacion_con_producto(
            sesion,
            usuario_id=usuario.id,
            referencia="DUPLICADA",
        )
        _agregar_producto(
            sesion,
            usuario_id=usuario.id,
            cotizacion=cotizacion,
            orden=2,
            sha="b",
        )
        sesion.commit()

        canal = CanalContador()
        resumen = ejecutar_consultas_configuradas(
            sesion,
            cotizacion_id=cotizacion.id,
            usuario_id=usuario.id,
            proveedores=(canal,),
        )

        assert canal.consultas == 1
        assert resumen.intentos == 1
        assert resumen.partidas_duplicadas_omitidas == 1
        assert len(list(sesion.scalars(select(ConsultaProveedor)))) == 1
        assert len(list(sesion.scalars(select(ObservacionPrecio)))) == 1


def _precio_cotizado_hoy(sesion, usuario_id: str) -> ObservacionPrecio:
    cotizacion, partida = _crear_cotizacion_con_producto(
        sesion,
        usuario_id=usuario_id,
        referencia="COTIZADA-HOY",
        sha="c",
    )
    observacion = crear_observacion_precio(
        sesion,
        cotizacion_id=cotizacion.id,
        partida_documento_id=partida.id,
        usuario_id=usuario_id,
        proveedor="Proveedor Hoy",
        fuente="Fuente de hoy",
        precio_antes_iva=None,
        iva_porcentaje=None,
        precio_total=Decimal("950.00"),
        es_promocion=False,
        condiciones_promocion=None,
        disponibilidad="Disponible",
        entrega_viable=True,
        codigo_postal="91000",
    )
    registrar_decision_precio(
        sesion,
        cotizacion_id=cotizacion.id,
        partida_id=partida.id,
        usuario_id=usuario_id,
        rol=RolDecisionPrecio.REFERENCIA_ESTABLE,
        observacion_id=observacion.id,
    )
    return observacion


def test_precio_realmente_cotizado_hoy_se_reutiliza_sin_consulta(cliente):
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario))
        assert usuario is not None
        observacion = _precio_cotizado_hoy(sesion, usuario.id)
        nueva, _ = _crear_cotizacion_con_producto(
            sesion,
            usuario_id=usuario.id,
            referencia="NUEVA-HOY",
            sha="d",
        )
        canal = CanalContador()

        resumen = ejecutar_consultas_configuradas(
            sesion,
            cotizacion_id=nueva.id,
            usuario_id=usuario.id,
            proveedores=(canal,),
        )

        assert canal.consultas == 0
        assert resumen.intentos == 0
        assert resumen.productos_reutilizados_hoy == 1
        assert sesion.get(ObservacionPrecio, observacion.id) is not None
        assert len(list(sesion.scalars(select(ObservacionPrecio)))) == 1


def test_cp_distinto_obliga_a_consultar_de_nuevo(cliente):
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario))
        assert usuario is not None
        _precio_cotizado_hoy(sesion, usuario.id)
        nueva, _ = _crear_cotizacion_con_producto(
            sesion,
            usuario_id=usuario.id,
            referencia="OTRO-CP",
            codigo_postal="94294",
            sha="e",
        )
        canal = CanalContador()

        resumen = ejecutar_consultas_configuradas(
            sesion,
            cotizacion_id=nueva.id,
            usuario_id=usuario.id,
            proveedores=(canal,),
        )

        assert canal.consultas == 1
        assert resumen.productos_reutilizados_hoy == 0
        assert resumen.precios_encontrados == 1


def test_referencia_retirada_no_se_reutiliza(cliente):
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario))
        assert usuario is not None
        cotizacion, partida = _crear_cotizacion_con_producto(
            sesion,
            usuario_id=usuario.id,
            referencia="RETIRADA",
            sha="f",
        )
        observacion = crear_observacion_precio(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_documento_id=partida.id,
            usuario_id=usuario.id,
            proveedor="Proveedor Retirado",
            fuente="Fuente retirada",
            precio_antes_iva=None,
            iva_porcentaje=None,
            precio_total=Decimal("900.00"),
            es_promocion=False,
            condiciones_promocion=None,
            disponibilidad="Disponible",
            entrega_viable=True,
            codigo_postal="91000",
        )
        registrar_decision_precio(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_id=partida.id,
            usuario_id=usuario.id,
            rol=RolDecisionPrecio.REFERENCIA_ESTABLE,
            observacion_id=observacion.id,
        )
        registrar_decision_precio(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_id=partida.id,
            usuario_id=usuario.id,
            rol=RolDecisionPrecio.REFERENCIA_ESTABLE,
            observacion_id=None,
        )

        nueva, _ = _crear_cotizacion_con_producto(
            sesion,
            usuario_id=usuario.id,
            referencia="DESPUES-RETIRADA",
            sha="1",
        )
        canal = CanalContador()
        resumen = ejecutar_consultas_configuradas(
            sesion,
            cotizacion_id=nueva.id,
            usuario_id=usuario.id,
            proveedores=(canal,),
        )

        assert canal.consultas == 1
        assert resumen.productos_reutilizados_hoy == 0


def test_interfaz_ofrece_usar_precio_de_hoy_y_revalidarlo(cliente):
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario))
        assert usuario is not None
        _precio_cotizado_hoy(sesion, usuario.id)
        nueva, partida = _crear_cotizacion_con_producto(
            sesion,
            usuario_id=usuario.id,
            referencia="UI-REUTILIZA",
            sha="2",
        )
        cotizacion_id = nueva.id
        partida_id = partida.id

    canal = CanalContador()
    cliente.app.state.proveedores_productos = {"canal contador": canal}
    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    assert pagina.status_code == 200
    assert "Este producto ya se cotizó hoy." in pagina.text
    assert "Usar precio de hoy" in pagina.text
    assert "Revalidar precio" in pagina.text

    respuesta = cliente.post(
        f"/cotizaciones/{cotizacion_id}/proveedores/{partida_id}/revalidar",
        data={"csrf_token": _csrf(pagina.text)},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    assert "resultado=revalidada" in respuesta.headers["location"]
    assert canal.consultas == 1

    with cliente.app.state.fabrica_sesiones() as sesion:
        assert len(list(sesion.scalars(select(ObservacionPrecio)))) == 2
