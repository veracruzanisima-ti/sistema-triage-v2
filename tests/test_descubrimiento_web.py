"""Pruebas del descubrimiento web sin consumir servicios externos."""

import re
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import Text, select

from triage.cotizaciones.modelos import Cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.historico.modelos import ObservacionPrecio, OrigenObservacionPrecio
from triage.normalizacion.modelos import NormalizacionPartida
from triage.proveedores.base import SolicitudProveedor
from triage.proveedores.descubrimiento_web import (
    CandidatoWeb,
    CandidatoWebRespuesta,
    DescubridorWebGemini,
    DescubridorWebOpenAI,
    ResultadoDescubrimientoWebRespuesta,
)
from triage.proveedores.modelos import CandidatoWebDescartado, ConsultaWeb
from triage.proveedores.servicio import ejecutar_descubrimiento_web
from triage.usuarios.modelos import Usuario


def _csrf(html: str) -> str:
    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if coincidencia is None:
        raise AssertionError("no se encontró token CSRF")
    return coincidencia.group(1)


def _preparar_producto(
    cliente,
    *,
    producto: str = "LANTUS",
    marca: str | None = "Lantus",
    concentracion: str = "100 U/mL",
    forma_dispositivo: str = "vial",
    presentacion: str = "10 mL",
) -> tuple[str, str, str]:
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario))
        assert usuario is not None
        cotizacion = Cotizacion(
            referencia="WEB-PRUEBA",
            codigo_postal_consulta="91000",
        )
        sesion.add(cotizacion)
        sesion.flush()
        documento = Documento(
            cotizacion_id=cotizacion.id,
            nombre_original="web.pdf",
            mime_type="application/pdf",
            tamano_bytes=10,
            sha256="b" * 64,
            estado=EstadoDocumento.REVISADO.value,
        )
        sesion.add(documento)
        sesion.flush()
        partida = PartidaDocumento(
            documento_id=documento.id,
            orden=1,
            producto_solicitado=producto,
            marca_solicitada=marca,
            concentracion=concentracion,
            forma_farmaceutica_dispositivo=forma_dispositivo,
            presentacion_solicitada=presentacion,
            incluida_cotizacion=True,
        )
        sesion.add(partida)
        sesion.flush()
        sesion.add(
            NormalizacionPartida(
                partida_documento_id=partida.id,
                producto=producto,
                marca=marca,
                concentracion=concentracion,
                forma_dispositivo=forma_dispositivo,
                presentacion=presentacion,
                confirmada_por_usuario_id=usuario.id,
            )
        )
        sesion.commit()
        return cotizacion.id, partida.id, usuario.id


class DescubridorFalso:
    modelo = "web-falso"

    def buscar(self, solicitud: SolicitudProveedor, *, terminos_adicionales=()):
        assert solicitud.producto == "LANTUS"
        assert solicitud.codigo_postal == "91000"
        assert terminos_adicionales == ()
        return (
            CandidatoWeb(
                proveedor="Farmacia Exacta",
                producto_exacto="Lantus 100 U/mL vial 10 mL",
                url="https://ejemplo.invalid/lantus",
                precio_total=Decimal("1234.50"),
                coincidencia_exacta=True,
                disponibilidad="Disponible",
            ),
            CandidatoWeb(
                proveedor="Farmacia Parecida",
                producto_exacto="Lantus pluma 3 mL",
                url="https://ejemplo.invalid/lantus-pluma",
                precio_total=Decimal("800.00"),
                coincidencia_exacta=False,
            ),
            CandidatoWeb(
                proveedor="Farmacia Mal Clasificada",
                producto_exacto="Lantus pluma 3 mL",
                url="https://ejemplo.invalid/falso-exacto",
                precio_total=Decimal("700.00"),
                coincidencia_exacta=True,
            ),
        )


def test_descubrimiento_web_guarda_solo_coincidencias_exactas(cliente):
    cotizacion_id, partida_id, usuario_id = _preparar_producto(cliente)
    with cliente.app.state.fabrica_sesiones() as sesion:
        resumen = ejecutar_descubrimiento_web(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_id,
            usuario_id=usuario_id,
            descubridor=DescubridorFalso(),
        )
        assert resumen.candidatos == 3
        assert resumen.guardados == 1
        assert resumen.descartados == 2
        assert resumen.intentos == 1

        observaciones = list(sesion.scalars(select(ObservacionPrecio)))
        assert len(observaciones) == 1
        observacion = observaciones[0]
        assert observacion.proveedor == "Farmacia Exacta"
        assert observacion.producto_observado == "Lantus 100 U/mL vial 10 mL"
        assert observacion.origen == OrigenObservacionPrecio.WEB.value
        assert observacion.codigo_postal == "91000"
        assert observacion.iva_porcentaje is None
        assert observacion.precio_antes_iva is None
        assert str(observacion.precio_total) == "1234.50"
        assert observacion.fuente.startswith("https://ejemplo.invalid/lantus")

        consulta = sesion.scalar(select(ConsultaWeb))
        assert consulta is not None
        assert consulta.modelo == "web-falso"
        assert consulta.intentos == 1
        descartados = list(sesion.scalars(select(CandidatoWebDescartado)))
        assert len(descartados) == 2
        assert all(resultado.motivos for resultado in descartados)
        assert all(resultado.precio_observado is not None for resultado in descartados)


class DescubridorConDescarteLargo:
    modelo = "web-texto-largo"
    proveedor_largo = "P" * 300
    producto_largo = "X" * 800
    url_larga = "https://ejemplo.invalid/" + ("ruta" * 300)

    def buscar(self, _solicitud: SolicitudProveedor, *, terminos_adicionales=()):
        assert terminos_adicionales == ()
        return (
            CandidatoWeb(
                proveedor="Farmacia Exacta",
                producto_exacto="Lantus 100 U/mL vial 10 mL",
                url="https://ejemplo.invalid/lantus-valido",
                precio_total=Decimal("1234.50"),
                coincidencia_exacta=True,
            ),
            CandidatoWeb(
                proveedor=self.proveedor_largo,
                producto_exacto=self.producto_largo,
                url=self.url_larga,
                precio_total=Decimal("999.00"),
                coincidencia_exacta=False,
            ),
        )


def test_descarte_largo_no_impide_guardar_candidato_valido(cliente):
    cotizacion_id, partida_id, usuario_id = _preparar_producto(cliente)
    descubridor = DescubridorConDescarteLargo()

    with cliente.app.state.fabrica_sesiones() as sesion:
        resumen = ejecutar_descubrimiento_web(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_id,
            usuario_id=usuario_id,
            descubridor=descubridor,
        )

        assert resumen.guardados == 1
        assert resumen.descartados == 1
        observaciones = list(sesion.scalars(select(ObservacionPrecio)))
        assert len(observaciones) == 1
        assert observaciones[0].proveedor == "Farmacia Exacta"

        descartado = sesion.scalar(select(CandidatoWebDescartado))
        assert descartado is not None
        assert descartado.proveedor == descubridor.proveedor_largo
        assert descartado.producto_observado == descubridor.producto_largo
        assert descartado.url == descubridor.url_larga
        assert "proveedor excede el límite del histórico cotizable" in descartado.motivos
        assert "producto observado excede el límite del histórico cotizable" in (
            descartado.motivos
        )
        assert "URL excede el límite del histórico cotizable" in descartado.motivos

    for columna in (
        CandidatoWebDescartado.__table__.c.proveedor,
        CandidatoWebDescartado.__table__.c.producto_observado,
        CandidatoWebDescartado.__table__.c.url,
    ):
        assert isinstance(columna.type, Text)


class DescubridorSoloExacto:
    modelo = "web-solo-exacto"

    def buscar(self, _solicitud: SolicitudProveedor, *, terminos_adicionales=()):
        assert terminos_adicionales == ()
        return (
            CandidatoWeb(
                proveedor="Farmacia Exacta",
                producto_exacto="Lantus 100 U/mL vial 10 mL",
                url="https://ejemplo.invalid/lantus-unico",
                precio_total=Decimal("1200.00"),
                coincidencia_exacta=True,
            ),
        )


def test_busqueda_totalmente_exitosa_no_muestra_detalle_vacio(cliente):
    cotizacion_id, partida_id, usuario_id = _preparar_producto(cliente)
    with cliente.app.state.fabrica_sesiones() as sesion:
        resumen = ejecutar_descubrimiento_web(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_id,
            usuario_id=usuario_id,
            descubridor=DescubridorSoloExacto(),
        )
        assert resumen.guardados == 1
        assert resumen.descartados == 0
        assert resumen.intentos == 1

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    assert pagina.status_code == 200
    assert "Ver resultados descartados" not in pagina.text


def test_descubrimiento_web_aparece_como_accion_secundaria(cliente):
    cotizacion_id, partida_id, _ = _preparar_producto(cliente)
    cliente.app.state.descubridor_web = DescubridorFalso()

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    assert pagina.status_code == 200
    assert "Buscar más opciones en web" in pagina.text

    respuesta = cliente.post(
        f"/cotizaciones/{cotizacion_id}/proveedores/{partida_id}/buscar-web",
        data={"csrf_token": _csrf(pagina.text)},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    assert "resultado=web" in respuesta.headers["location"]

    resultado = cliente.get(respuesta.headers["location"])
    assert "1 opción(es) exacta(s) guardada(s)" in resultado.text
    assert "Farmacia Exacta" in resultado.text
    assert "La fuente mostró:" in resultado.text
    assert "Ver fuente" in resultado.text
    assert "Ver resultados descartados (2)" in resultado.text
    assert "Motivo registrado en esa búsqueda:" in resultado.text
    assert "Evaluar con reglas actuales" in resultado.text
    assert "forma o dispositivo distinto" in resultado.text


def _buscar_web_desde_ui(cliente, cotizacion_id: str, partida_id: str):
    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    respuesta = cliente.post(
        f"/cotizaciones/{cotizacion_id}/proveedores/{partida_id}/buscar-web",
        data={"csrf_token": _csrf(pagina.text)},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    return cliente.get(respuesta.headers["location"])


class DescubridorLinagliptinaAlternativa:
    modelo = "web-linagliptina-alternativa"

    def __init__(self) -> None:
        self.presentaciones: list[str | None] = []

    def buscar(self, solicitud: SolicitudProveedor, *, terminos_adicionales=()):
        self.presentaciones.append(solicitud.presentacion)
        assert solicitud.producto == "LINAGLIPTINA"
        candidato = CandidatoWeb(
            proveedor="Farmacia Uno",
            producto_exacto="Trayenta 5Mg 30 Tab (Linagliptina)",
            url="https://uno.invalid/trayenta-30",
            precio_total=Decimal("850.00"),
            coincidencia_exacta=True,
        )
        if solicitud.presentacion == "30 tabletas":
            return (candidato,)
        return (
            candidato,
            CandidatoWeb(
                proveedor="Farmacia Dos",
                producto_exacto="LINAGLIPTINA Trayenta 5 mg 30 tabletas",
                url="https://dos.invalid/trayenta-30",
                precio_total=Decimal("860.00"),
                coincidencia_exacta=True,
            ),
        )


def test_presentacion_alternativa_requiere_confirmacion_y_nueva_busqueda(cliente):
    cotizacion_id, partida_id, usuario_id = _preparar_producto(
        cliente,
        producto="LINAGLIPTINA",
        marca=None,
        concentracion="5 mg",
        forma_dispositivo="tabletas",
        presentacion="Caja con 28 tabletas",
    )
    descubridor = DescubridorLinagliptinaAlternativa()
    cliente.app.state.descubridor_web = descubridor

    resultado = _buscar_web_desde_ui(cliente, cotizacion_id, partida_id)
    assert "Posible presentación comercial encontrada: Caja con 30 tabletas" in (
        resultado.text
    )
    assert "Solicitud original: Caja con 28 tabletas" in resultado.text
    assert "2 fuentes independientes señalan la misma presentación" in resultado.text
    assert "Usar 30 tabletas para buscar" in resultado.text
    coincidencia_accion = re.search(
        r'action="([^"]+/presentacion-alternativa/[^"]+)"', resultado.text
    )
    assert coincidencia_accion is not None
    accion = coincidencia_accion.group(1)

    with cliente.app.state.fabrica_sesiones() as sesion:
        partida = sesion.get(PartidaDocumento, partida_id)
        normalizacion = sesion.get(NormalizacionPartida, partida_id)
        assert partida is not None
        assert normalizacion is not None
        actualizada_antes = normalizacion.actualizada_en
        assert partida.presentacion_solicitada == "Caja con 28 tabletas"
        assert normalizacion.presentacion == "Caja con 28 tabletas"
        assert list(sesion.scalars(select(ObservacionPrecio))) == []

    csrf_invalido = cliente.post(
        accion,
        data={"csrf_token": "token-incorrecto"},
        follow_redirects=False,
    )
    assert csrf_invalido.status_code == 403
    with cliente.app.state.fabrica_sesiones() as sesion:
        normalizacion = sesion.get(NormalizacionPartida, partida_id)
        assert normalizacion is not None
        assert normalizacion.presentacion == "Caja con 28 tabletas"

    confirmacion = cliente.post(
        accion,
        data={"csrf_token": _csrf(resultado.text)},
        follow_redirects=False,
    )
    assert confirmacion.status_code == 303
    assert "resultado=presentacion_actualizada" in confirmacion.headers["location"]
    confirmada = cliente.get(confirmacion.headers["location"])
    assert "La solicitud original no cambió" in confirmada.text
    assert "Busca precios nuevamente para comprobar la coincidencia" in confirmada.text
    assert "Posible presentación comercial encontrada" not in confirmada.text

    with cliente.app.state.fabrica_sesiones() as sesion:
        partida = sesion.get(PartidaDocumento, partida_id)
        normalizacion = sesion.get(NormalizacionPartida, partida_id)
        assert partida is not None
        assert normalizacion is not None
        assert partida.presentacion_solicitada == "Caja con 28 tabletas"
        assert normalizacion.presentacion == "30 tabletas"
        assert normalizacion.confirmada_por_usuario_id == usuario_id
        assert normalizacion.actualizada_en != actualizada_antes
        assert list(sesion.scalars(select(ObservacionPrecio))) == []

    segunda_busqueda = _buscar_web_desde_ui(cliente, cotizacion_id, partida_id)
    assert "1 opción(es) exacta(s) guardada(s)" in segunda_busqueda.text
    assert descubridor.presentaciones[-1] == "30 tabletas"
    with cliente.app.state.fabrica_sesiones() as sesion:
        assert len(list(sesion.scalars(select(ObservacionPrecio)))) == 1
        partida = sesion.get(PartidaDocumento, partida_id)
        assert partida is not None
        assert partida.presentacion_solicitada == "Caja con 28 tabletas"


class DescubridorConConflictosAdicionales:
    modelo = "web-conflictos-adicionales"

    def buscar(self, _solicitud: SolicitudProveedor, *, terminos_adicionales=()):
        return (
            CandidatoWeb(
                proveedor="Farmacia Concentración",
                producto_exacto="Trayenta 10 mg 30 tab (Linagliptina)",
                url="https://concentracion.invalid/trayenta",
                precio_total=Decimal("800.00"),
                coincidencia_exacta=True,
            ),
            CandidatoWeb(
                proveedor="Farmacia Forma",
                producto_exacto="Trayenta 5 mg 30 cápsulas (Linagliptina)",
                url="https://forma.invalid/trayenta",
                precio_total=Decimal("810.00"),
                coincidencia_exacta=True,
            ),
        )


def test_conflicto_de_concentracion_o_forma_no_ofrece_alternativa(cliente):
    cotizacion_id, partida_id, _ = _preparar_producto(
        cliente,
        producto="LINAGLIPTINA",
        marca=None,
        concentracion="5 mg",
        forma_dispositivo="tabletas",
        presentacion="Caja con 28 tabletas",
    )
    cliente.app.state.descubridor_web = DescubridorConConflictosAdicionales()

    resultado = _buscar_web_desde_ui(cliente, cotizacion_id, partida_id)
    assert "Posible presentación comercial encontrada" not in resultado.text
    assert "presentacion-alternativa" not in resultado.text
    assert "Usar 30 tabletas para buscar" not in resultado.text


class DescubridorConPresentacionAmbigua:
    modelo = "web-presentacion-ambigua"

    def buscar(self, _solicitud: SolicitudProveedor, *, terminos_adicionales=()):
        return (
            CandidatoWeb(
                proveedor="Farmacia Ambigua",
                producto_exacto=(
                    "Trayenta 5 mg 30 tabletas o 60 tabletas (Linagliptina)"
                ),
                url="https://ambigua.invalid/trayenta",
                precio_total=Decimal("820.00"),
                coincidencia_exacta=True,
            ),
        )


def test_presentacion_ambigua_solo_permite_edicion_manual(cliente):
    cotizacion_id, partida_id, _ = _preparar_producto(
        cliente,
        producto="LINAGLIPTINA",
        marca=None,
        concentracion="5 mg",
        forma_dispositivo="tabletas",
        presentacion="Caja con 28 tabletas",
    )
    cliente.app.state.descubridor_web = DescubridorConPresentacionAmbigua()

    resultado = _buscar_web_desde_ui(cliente, cotizacion_id, partida_id)
    assert "Posible presentación comercial encontrada" not in resultado.text
    assert "Usar 30 tabletas para buscar" not in resultado.text
    assert "Editar preparación" in resultado.text

    with cliente.app.state.fabrica_sesiones() as sesion:
        descartado = sesion.scalar(select(CandidatoWebDescartado))
        assert descartado is not None
        candidato_id = descartado.id

    intento_forzado = cliente.post(
        (
            f"/cotizaciones/{cotizacion_id}/proveedores/{partida_id}"
            f"/presentacion-alternativa/{candidato_id}"
        ),
        data={"csrf_token": _csrf(resultado.text)},
    )
    assert intento_forzado.status_code == 409
    with cliente.app.state.fabrica_sesiones() as sesion:
        normalizacion = sesion.get(NormalizacionPartida, partida_id)
        partida = sesion.get(PartidaDocumento, partida_id)
        assert normalizacion is not None
        assert partida is not None
        assert normalizacion.presentacion == "Caja con 28 tabletas"
        assert partida.presentacion_solicitada == "Caja con 28 tabletas"
        assert list(sesion.scalars(select(ObservacionPrecio))) == []


class DescubridorAmantadinaFalso:
    modelo = "gemini-prueba"

    def __init__(self) -> None:
        self.llamadas: list[tuple[str, ...]] = []

    def buscar(self, solicitud: SolicitudProveedor, *, terminos_adicionales=()):
        self.llamadas.append(tuple(terminos_adicionales))
        assert solicitud.producto == "Amantadina"
        if not terminos_adicionales:
            return (
                CandidatoWeb(
                    proveedor="Farmacia Caja 20",
                    producto_exacto="Amantadina 100 mg tabletas caja con 20 tabletas",
                    url="https://ejemplo.invalid/amantadina-20",
                    precio_total=Decimal("110.00"),
                    coincidencia_exacta=True,
                ),
                CandidatoWeb(
                    proveedor="Farmacia 50 mg",
                    producto_exacto="Amantadina 50 mg tabletas caja con 30 tabletas",
                    url="https://ejemplo.invalid/amantadina-50",
                    precio_total=Decimal("90.00"),
                    coincidencia_exacta=True,
                ),
            )
        assert "tableta | tabletas | tab" in terminos_adicionales
        assert "100 mg | 0.1 g" in terminos_adicionales
        return (
            CandidatoWeb(
                proveedor="Farmacia Exacta Amantadina",
                producto_exacto="Amantadina 0.1 g tab caja con 30 tab",
                url="https://ejemplo.invalid/amantadina-30",
                precio_total=Decimal("120.00"),
                coincidencia_exacta=True,
            ),
        )


def test_amantadina_hace_un_solo_intento_ampliado_y_conserva_descartes(cliente):
    cotizacion_id, partida_id, usuario_id = _preparar_producto(
        cliente,
        producto="Amantadina",
        marca=None,
        concentracion="100 mg",
        forma_dispositivo="tabletas",
        presentacion="Caja con 30 tabletas de 100 mg",
    )
    descubridor = DescubridorAmantadinaFalso()

    with cliente.app.state.fabrica_sesiones() as sesion:
        resumen = ejecutar_descubrimiento_web(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_id,
            usuario_id=usuario_id,
            descubridor=descubridor,
        )

        assert resumen.intentos == 2
        assert resumen.candidatos == 3
        assert resumen.guardados == 1
        assert resumen.descartados == 2
        assert len(descubridor.llamadas) == 2
        observaciones = list(sesion.scalars(select(ObservacionPrecio)))
        assert len(observaciones) == 1
        assert observaciones[0].producto_observado == "Amantadina 0.1 g tab caja con 30 tab"

        descartados = list(
            sesion.scalars(
                select(CandidatoWebDescartado).order_by(
                    CandidatoWebDescartado.precio_observado.desc()
                )
            )
        )
        assert len(descartados) == 2
        assert "presentación distinta" in descartados[0].motivos
        assert "concentración distinta" in descartados[1].motivos
        assert all(resultado.intento_busqueda == 1 for resultado in descartados)


class DescubridorSiempreDescartado:
    modelo = "web-sin-exactos"

    def __init__(self) -> None:
        self.llamadas = 0

    def buscar(self, _solicitud: SolicitudProveedor, *, terminos_adicionales=()):
        self.llamadas += 1
        sufijo = "ampliada" if terminos_adicionales else "original"
        return (
            CandidatoWeb(
                proveedor=f"Farmacia {sufijo}",
                producto_exacto="Amantadina 100 mg tabletas caja con 20 tabletas",
                url=f"https://ejemplo.invalid/{sufijo}",
                precio_total=Decimal("80.00"),
                coincidencia_exacta=True,
            ),
        )


def test_descartados_no_crean_historico_y_la_busqueda_se_detiene_en_dos(cliente):
    cotizacion_id, partida_id, usuario_id = _preparar_producto(
        cliente,
        producto="Amantadina",
        marca=None,
        concentracion="100 mg",
        forma_dispositivo="tabletas",
        presentacion="Caja con 30 tabletas de 100 mg",
    )
    descubridor = DescubridorSiempreDescartado()

    with cliente.app.state.fabrica_sesiones() as sesion:
        resumen = ejecutar_descubrimiento_web(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_id,
            usuario_id=usuario_id,
            descubridor=descubridor,
        )

        assert descubridor.llamadas == 2
        assert resumen.intentos == 2
        assert resumen.guardados == 0
        assert resumen.descartados == 2
        assert list(sesion.scalars(select(ObservacionPrecio))) == []
        consulta = sesion.scalar(select(ConsultaWeb))
        assert consulta is not None
        assert consulta.criterios_busqueda["presentacion"] == (
            "Caja con 30 tabletas de 100 mg"
        )
        assert consulta.terminos_ampliados

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    assert pagina.status_code == 200
    assert "Ver resultados descartados (2)" in pagina.text
    assert "Se buscó:" in pagina.text
    assert "Se realizaron 2 búsqueda(s)." in pagina.text
    assert "tableta | tabletas | tab" in pagina.text
    assert "Estos resultados son sólo trazabilidad" in pagina.text


class RespuestasFalsas:
    def __init__(self) -> None:
        self.argumentos = None

    def parse(self, **argumentos):
        self.argumentos = argumentos
        resultado = ResultadoDescubrimientoWebRespuesta(
            candidatos=[
                CandidatoWebRespuesta(
                    proveedor="Farmacia Web",
                    producto_exacto="Lantus 100 U/mL vial 10 mL",
                    url="https://ejemplo.invalid/producto",
                    precio_total=999.0,
                    coincidencia_exacta=True,
                )
            ]
        )
        parte = SimpleNamespace(type="output_text", parsed=resultado)
        mensaje = SimpleNamespace(type="message", content=[parte])
        return SimpleNamespace(output=[mensaje])


class ClienteFalso:
    def __init__(self) -> None:
        self.responses = RespuestasFalsas()


def test_openai_web_search_no_almacena_y_solo_recibe_contexto_operativo():
    descubridor = DescubridorWebOpenAI(api_key="sk-prueba-no-real", modelo="gpt-5")
    cliente = ClienteFalso()
    descubridor._cliente = cliente

    candidatos = descubridor.buscar(
        SolicitudProveedor(
            partida_documento_id="partida-1",
            producto="LANTUS",
            marca="Lantus",
            concentracion="100 U/mL",
            forma_dispositivo="vial",
            presentacion="10 mL",
            codigo_postal="91000",
        )
    )

    assert len(candidatos) == 1
    assert str(candidatos[0].precio_total) == "999.0"
    argumentos = cliente.responses.argumentos
    assert argumentos is not None
    assert argumentos["store"] is False
    assert argumentos["tools"][0]["type"] == "web_search"
    assert argumentos["tools"][0]["user_location"]["country"] == "MX"
    assert argumentos["text_format"] is ResultadoDescubrimientoWebRespuesta
    assert "LANTUS" in argumentos["input"]
    assert "91000" in argumentos["input"]
    assert "paciente" not in argumentos["input"].casefold()


class ModelosGeminiFalsos:
    def __init__(self) -> None:
        self.argumentos = None

    def generate_content(self, **argumentos):
        self.argumentos = argumentos
        return SimpleNamespace(
            parsed=ResultadoDescubrimientoWebRespuesta(
                candidatos=[
                    CandidatoWebRespuesta(
                        proveedor="Farmacia Gemini",
                        producto_exacto="Amantadina 0.1 g tab caja con 30 tab",
                        url="https://ejemplo.invalid/gemini",
                        precio_total=101.0,
                        coincidencia_exacta=True,
                    )
                ]
            ),
            usage_metadata=None,
        )


def test_gemini_recibe_los_mismos_terminos_de_busqueda_ampliada():
    descubridor = DescubridorWebGemini(
        api_key="gemini-prueba-no-real",
        modelo="gemini-prueba",
    )
    modelos = ModelosGeminiFalsos()
    descubridor._cliente = SimpleNamespace(models=modelos)

    candidatos = descubridor.buscar(
        SolicitudProveedor(
            partida_documento_id="amantadina-1",
            producto="Amantadina",
            marca=None,
            concentracion="100 mg",
            forma_dispositivo="tabletas",
            presentacion="Caja con 30 tabletas de 100 mg",
            codigo_postal="91000",
        ),
        terminos_adicionales=("tableta | tabletas | tab", "100 mg | 0.1 g"),
    )

    assert len(candidatos) == 1
    assert modelos.argumentos is not None
    assert "segunda y última búsqueda" in modelos.argumentos["contents"]
    assert "tableta | tabletas | tab" in modelos.argumentos["contents"]
    assert modelos.argumentos["config"].response_schema is (
        ResultadoDescubrimientoWebRespuesta
    )


def _claves_json(valor) -> set[str]:
    if isinstance(valor, dict):
        claves = set(valor)
        for hijo in valor.values():
            claves.update(_claves_json(hijo))
        return claves
    if isinstance(valor, list):
        claves: set[str] = set()
        for hijo in valor:
            claves.update(_claves_json(hijo))
        return claves
    return set()


def test_schema_externo_no_usa_formatos_ni_restricciones_innecesarias():
    schema = ResultadoDescubrimientoWebRespuesta.model_json_schema()
    claves = _claves_json(schema)

    assert "format" not in claves
    assert "exclusiveMinimum" not in claves
    assert "maxItems" not in claves
    assert "pattern" not in claves
