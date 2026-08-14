from decimal import Decimal

from sqlalchemy import select

from triage.cotizaciones.modelos import Cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.historico.decisiones_modelos import RolDecisionPrecio
from triage.historico.decisiones_servicio import registrar_decision_precio
from triage.historico.servicio import crear_observacion_precio
from triage.normalizacion.modelos import NormalizacionPartida
from triage.usuarios.modelos import Usuario


def _crear_caso(cliente) -> str:
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario))
        assert usuario is not None

        cotizacion = Cotizacion(
            referencia="PRECIOS-COMPACTOS",
            codigo_postal_consulta="91193",
        )
        sesion.add(cotizacion)
        sesion.flush()

        documento = Documento(
            cotizacion_id=cotizacion.id,
            nombre_original="precios.pdf",
            mime_type="application/pdf",
            tamano_bytes=10,
            sha256="f" * 64,
            estado=EstadoDocumento.REVISADO.value,
        )
        sesion.add(documento)
        sesion.flush()

        partida = PartidaDocumento(
            documento_id=documento.id,
            orden=1,
            producto_solicitado="Insulina glargina",
            incluida_cotizacion=True,
        )
        sesion.add(partida)
        sesion.flush()

        sesion.add(
            NormalizacionPartida(
                partida_documento_id=partida.id,
                producto="Insulina glargina",
                marca="LANTUS",
                concentracion="100 UI/mL",
                forma_dispositivo="solución inyectable - vial",
                presentacion="Frasco vial de 10 mL",
                confirmada_por_usuario_id=usuario.id,
            )
        )
        sesion.commit()

        def precio(
            proveedor: str,
            total: str,
            *,
            promocion: bool = False,
        ):
            return crear_observacion_precio(
                sesion,
                cotizacion_id=cotizacion.id,
                partida_documento_id=partida.id,
                usuario_id=usuario.id,
                proveedor=proveedor,
                fuente=f"https://ejemplo.invalid/{proveedor.casefold().replace(' ', '-')}",
                precio_antes_iva=None,
                iva_porcentaje=None,
                precio_total=Decimal(total),
                es_promocion=promocion,
                condiciones_promocion="Oferta" if promocion else None,
                disponibilidad="Disponible",
                entrega_viable=True,
                codigo_postal="91193",
                producto_observado="Lantus 100 UI/mL frasco ámpula 10 mL",
            )

        referencia = precio("Curitek", "1733.00")
        precio("Farmatodo", "2660.50")
        precio("Farmacias Guadalajara", "2113.68", promocion=True)
        precio("Proveedor oportunidad", "1500.00", promocion=True)

        registrar_decision_precio(
            sesion,
            cotizacion_id=cotizacion.id,
            partida_id=partida.id,
            usuario_id=usuario.id,
            rol=RolDecisionPrecio.REFERENCIA_ESTABLE,
            observacion_id=referencia.id,
        )
        return cotizacion.id


def test_referencia_queda_visible_y_alternativas_plegadas_y_ordenadas(cliente):
    cotizacion_id = _crear_caso(cliente)

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")

    assert pagina.status_code == 200
    assert "Precio usado para cotizar" in pagina.text
    assert "Mostrar otras opciones (3)" in pagina.text
    assert "Este producto ya se cotizó hoy." not in pagina.text

    posicion_resumen = pagina.text.index("Mostrar otras opciones (3)")
    posicion_barata = pagina.text.index("Proveedor oportunidad", posicion_resumen)
    posicion_guadalajara = pagina.text.index("Farmacias Guadalajara", posicion_resumen)
    posicion_farmatodo = pagina.text.index("Farmatodo", posicion_resumen)
    assert posicion_barata < posicion_guadalajara < posicion_farmatodo

    assert pagina.text.count("Oportunidad de compra.") == 1
    assert "13.4% debajo de la referencia actual" in pagina.text
    assert "Farmacias Guadalajara" in pagina.text
    assert "Oferta / promoción" in pagina.text
