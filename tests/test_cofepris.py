"""Regresiones del snapshot COFEPRIS y su uso limitado a identidad web."""

import re
from io import BytesIO

import pytest
from openpyxl import Workbook
from sqlalchemy import select

from triage.cotizaciones.modelos import Cotizacion
from triage.documentos.modelos import Documento, EstadoDocumento, PartidaDocumento
from triage.historico.modelos import ObservacionPrecio
from triage.normalizacion.modelos import NormalizacionPartida
from triage.proveedores.base import SolicitudProveedor
from triage.proveedores.cofepris_modelos import ImportacionCofepris, RegistroCofepris
from triage.proveedores.cofepris_servicio import (
    ErrorImportacionCofepris,
    importar_snapshot_cofepris,
    resolver_identidad_cofepris,
)
from triage.proveedores.descubrimiento_web import CandidatoWeb
from triage.proveedores.modelos import CandidatoWebDescartado
from triage.proveedores.servicio import ejecutar_descubrimiento_web
from triage.usuarios.modelos import Usuario

_COLUMNAS_REALES = (
    "Número de Registro",
    "Denominación Distintiva",
    "Fecha Expedición Vigencia",
    "Fecha Expedición Vigencia Prorroga",
    "Estado",
    "Forma Farmaceutica",
    "Indicaciones Terapéuticas",
    "Contra Indicaciones",
    "Vida Útil",
    "Fracción",
    "Denominacion Generica",
    "Vista Administración",
    "Tipo Medicamento",
    "Presentación",
    "Cantidad",
    "Sistema Orgánico",
    "Grupo Farmacológico",
    "Subgrupo Farmacológico",
    "Subgrupo QuÍmico",
    "Sustancia Química",
    "Titular",
    "Domicilio",
    "Fabricantes Medicamentos",
    "Fabricantes Farmacos",
    "Acondicionado Por",
    "Acondicionado Extranjero",
    "Distribuidores",
    "Unidad Farmaco Vigilancia",
    "Fecha Emisión",
)


def _registro(
    *,
    numero: str = "159M2011 SSA",
    distintiva: str = "TRAYENTA",
    generica: str = "LINAGLIPTINA",
    estado: str = "VIGENTE",
) -> dict[str, object]:
    return {
        "Número de Registro": numero,
        "Denominación Distintiva": distintiva,
        "Estado": estado,
        "Forma Farmaceutica": "TABLETA",
        "Fracción": "IV",
        "Denominacion Generica": generica,
        "Vista Administración": "ORAL",
        "Tipo Medicamento": "ALOPÁTICO",
        "Presentación": "CAJA",
        "Cantidad": "30 TABLETAS",
        "Sustancia Química": generica,
        "Titular": "TITULAR DE PRUEBA",
        "Fecha Emisión": "2026-01-10",
    }


def _xlsx(
    registros: list[dict[str, object]],
    *,
    hoja: str = "Registros_Medicamentos",
    columnas: tuple[str, ...] = _COLUMNAS_REALES,
) -> bytes:
    libro = Workbook()
    activa = libro.active
    activa.title = hoja
    activa.append(columnas)
    for registro in registros:
        activa.append([registro.get(columna) for columna in columnas])
    salida = BytesIO()
    libro.save(salida)
    libro.close()
    return salida.getvalue()


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


def _importar(cliente, registros: list[dict[str, object]]) -> ImportacionCofepris:
    with cliente.app.state.fabrica_sesiones() as sesion:
        return importar_snapshot_cofepris(
            sesion,
            usuario_id=_usuario_id(cliente),
            nombre_archivo="Visor_Registros_Medicamentos.xlsx",
            datos=_xlsx(registros),
        )


def _preparar_producto(
    cliente,
    *,
    producto: str = "LINAGLIPTINA",
    marca: str | None = None,
    concentracion: str = "5 mg",
    forma: str = "tabletas",
    presentacion: str = "30 tabletas",
) -> tuple[str, str, str]:
    with cliente.app.state.fabrica_sesiones() as sesion:
        usuario = sesion.scalar(select(Usuario))
        assert usuario is not None
        cotizacion = Cotizacion(
            referencia="COFEPRIS-PRUEBA",
            codigo_postal_consulta="91000",
        )
        sesion.add(cotizacion)
        sesion.flush()
        documento = Documento(
            cotizacion_id=cotizacion.id,
            nombre_original="cofepris.pdf",
            mime_type="application/pdf",
            tamano_bytes=10,
            sha256="c" * 64,
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
            forma_farmaceutica_dispositivo=forma,
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
                forma_dispositivo=forma,
                presentacion=presentacion,
                confirmada_por_usuario_id=usuario.id,
            )
        )
        sesion.commit()
        return cotizacion.id, partida.id, usuario.id


class _DescubridorTrayenta:
    modelo = "web-cofepris-prueba"

    def __init__(
        self,
        producto_observado: str = "TRAYENTA 5 mg 30 tabletas",
        *,
        coincidencia_exacta: bool = True,
    ) -> None:
        self.producto_observado = producto_observado
        self.coincidencia_exacta = coincidencia_exacta

    def buscar(self, _solicitud: SolicitudProveedor, *, terminos_adicionales=()):
        return (
            CandidatoWeb(
                proveedor="Farmacia COFEPRIS",
                producto_exacto=self.producto_observado,
                url="https://ejemplo.invalid/trayenta",
                precio_total=850,
                coincidencia_exacta=self.coincidencia_exacta,
            ),
        )


def test_importacion_valida_normaliza_y_no_persiste_el_xlsx(cliente, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    importacion = _importar(
        cliente,
        [
            _registro(),
            _registro(
                numero="200M2020 SSA",
                distintiva="PRODUCTO CANCELADO",
                generica="OTRO PRINCIPIO",
                estado="CANCELADO",
            ),
        ],
    )

    assert importacion.registros_cargados == 2
    assert importacion.registros_vigentes == 1
    assert importacion.registros_sin_identidad_util == 0
    assert importacion.numeros_registro_duplicados == 0
    assert importacion.archivo == "Visor_Registros_Medicamentos.xlsx"
    assert len(importacion.sha256) == 64
    with cliente.app.state.fabrica_sesiones() as sesion:
        trayenta = sesion.scalar(
            select(RegistroCofepris).where(
                RegistroCofepris.numero_registro == "159M2011 SSA"
            )
        )
        assert trayenta is not None
        assert trayenta.denominacion_distintiva_normalizada == "TRAYENTA"
        assert trayenta.componentes_genericos_normalizados == ["LINAGLIPTINA"]
        assert trayenta.fraccion_sanitaria == "IV"
        assert not hasattr(sesion.get(ImportacionCofepris, importacion.id), "contenido")
    assert list(tmp_path.glob("*.xlsx")) == []


@pytest.mark.parametrize(
    ("datos", "mensaje"),
    [
        (_xlsx([_registro()], hoja="Otra_hoja"), "Registros_Medicamentos"),
        (
            _xlsx(
                [_registro()],
                columnas=tuple(
                    columna
                    for columna in _COLUMNAS_REALES
                    if columna != "Denominacion Generica"
                ),
            ),
            "Denominacion Generica",
        ),
        (_xlsx([_registro(generica="")]), "Denominacion Generica"),
    ],
    ids=(
        "hoja-incorrecta",
        "columna-faltante",
        "dato-obligatorio-vacio",
    ),
)
def test_importacion_rechaza_hoja_columnas_y_dato_obligatorio_vacio(
    cliente,
    datos,
    mensaje,
):
    with cliente.app.state.fabrica_sesiones() as sesion:
        with pytest.raises(ErrorImportacionCofepris, match=mensaje):
            importar_snapshot_cofepris(
                sesion,
                usuario_id=_usuario_id(cliente),
                nombre_archivo="catalogo.xlsx",
                datos=datos,
            )


def test_importacion_conserva_filas_imperfectas_y_duplicados_sin_resolverlos(cliente):
    importacion = _importar(
        cliente,
        [
            _registro(numero="DUP-1"),
            _registro(numero="DUP-1"),
            _registro(numero="SIN-MARCA", distintiva="."),
            _registro(numero="SIN-GENERICA", distintiva="INCOMPLETO", generica="/ / /"),
        ],
    )

    assert importacion.registros_cargados == 4
    assert importacion.registros_vigentes == 4
    assert importacion.registros_sin_identidad_util == 2
    assert importacion.numeros_registro_duplicados == 1
    with cliente.app.state.fabrica_sesiones() as sesion:
        registros = list(sesion.scalars(select(RegistroCofepris)))
        assert len(registros) == 4
        assert sum(registro.numero_registro == "DUP-1" for registro in registros) == 2
        assert (
            resolver_identidad_cofepris(
                sesion,
                producto_solicitado="LINAGLIPTINA",
                producto_observado="TRAYENTA 5 mg 30 tabletas",
            )
            is None
        )
        assert (
            resolver_identidad_cofepris(
                sesion,
                producto_solicitado="LINAGLIPTINA",
                producto_observado="INCOMPLETO 5 mg 30 tabletas",
            )
            is None
        )


def test_archivo_invalido_conserva_snapshot_anterior(cliente):
    anterior = _importar(cliente, [_registro()])
    with cliente.app.state.fabrica_sesiones() as sesion:
        with pytest.raises(ErrorImportacionCofepris):
            importar_snapshot_cofepris(
                sesion,
                usuario_id=_usuario_id(cliente),
                nombre_archivo="catalogo.xlsx",
                datos=_xlsx([]),
            )
        assert (
            sesion.scalar(
                select(RegistroCofepris).where(
                    RegistroCofepris.numero_registro == "159M2011 SSA"
                )
            )
            is not None
        )
        importaciones = list(sesion.scalars(select(ImportacionCofepris)))
        assert [importacion.id for importacion in importaciones] == [anterior.id]


@pytest.mark.parametrize("estado", ["CANCELADO", "REVOCADO"])
def test_solo_registro_vigente_resuelve_identidad(cliente, estado):
    _importar(cliente, [_registro(estado=estado)])
    with cliente.app.state.fabrica_sesiones() as sesion:
        assert (
            resolver_identidad_cofepris(
                sesion,
                producto_solicitado="LINAGLIPTINA",
                producto_observado="TRAYENTA 5 mg 30 tabletas",
            )
            is None
        )


def test_medicamento_combinado_y_marca_ambigua_no_resuelven(cliente):
    _importar(
        cliente,
        [
            _registro(
                numero="COMBO-1",
                distintiva="JARDIANZ DPP",
                generica="EMPAGLIFLOZINA / LINAGLIPTINA",
            ),
            _registro(numero="AMB-1", distintiva="TRAYENTA"),
            _registro(numero="AMB-2", distintiva="TRAYENTA"),
        ],
    )
    with cliente.app.state.fabrica_sesiones() as sesion:
        assert (
            resolver_identidad_cofepris(
                sesion,
                producto_solicitado="LINAGLIPTINA",
                producto_observado="JARDIANZ DPP 10 mg / 5 mg 30 tabletas",
            )
            is None
        )
        assert (
            resolver_identidad_cofepris(
                sesion,
                producto_solicitado="LINAGLIPTINA",
                producto_observado="TRAYENTA 5 mg 30 tabletas",
            )
            is None
        )


def test_trayenta_vigente_crea_observacion_con_evidencia_y_la_muestra(cliente):
    importacion = _importar(cliente, [_registro()])
    cotizacion_id, partida_id, usuario_id = _preparar_producto(cliente)

    with cliente.app.state.fabrica_sesiones() as sesion:
        resumen = ejecutar_descubrimiento_web(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_id,
            usuario_id=usuario_id,
            descubridor=_DescubridorTrayenta(),
        )
        assert resumen.guardados == 1
        assert resumen.descartados == 0
        observacion = sesion.scalar(select(ObservacionPrecio))
        assert observacion is not None
        assert observacion.evidencia_identidad == {
            "fuente": "COFEPRIS",
            "numero_registro": "159M2011 SSA",
            "denominacion_distintiva": "TRAYENTA",
            "denominacion_generica": "LINAGLIPTINA",
            "estado": "VIGENTE",
            "importacion_id": importacion.id,
            "sha256_importacion": importacion.sha256,
        }

    pagina = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    assert pagina.status_code == 200
    assert "COFEPRIS verificado" in pagina.text
    assert "Identidad verificada con COFEPRIS · Registro 159M2011 SSA" in pagina.text
    assert "TRAYENTA" in pagina.text
    assert "LINAGLIPTINA" in pagina.text
    assert "sólo confirma identidad sanitaria" in pagina.text


def test_pantalla_de_precios_muestra_si_cofepris_esta_activo(cliente):
    cotizacion_id, _, _ = _preparar_producto(cliente)

    sin_catalogo = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    assert sin_catalogo.status_code == 200
    assert "COFEPRIS no cargado" in sin_catalogo.text
    assert "Las marcas comerciales no pueden validarse contra su genérico" in (
        sin_catalogo.text
    )
    assert "Cargar COFEPRIS" in sin_catalogo.text

    _importar(cliente, [_registro()])
    con_catalogo = cliente.get(f"/cotizaciones/{cotizacion_id}/proveedores")
    assert con_catalogo.status_code == 200
    assert "COFEPRIS activo" in con_catalogo.text
    assert "Equivalencias de identidad disponibles" in con_catalogo.text
    assert "1 registros vigentes" in con_catalogo.text
    assert "1 registros totales" in con_catalogo.text
    assert "Actualizar COFEPRIS" in con_catalogo.text


def test_trayenta_no_exacta_sigue_descartada_aunque_cofepris_resuelva(cliente):
    _importar(cliente, [_registro()])
    cotizacion_id, partida_id, usuario_id = _preparar_producto(cliente)

    with cliente.app.state.fabrica_sesiones() as sesion:
        resumen = ejecutar_descubrimiento_web(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_id,
            usuario_id=usuario_id,
            descubridor=_DescubridorTrayenta(coincidencia_exacta=False),
        )
        assert resumen.guardados == 0
        assert sesion.scalar(select(ObservacionPrecio)) is None
        descartados = list(sesion.scalars(select(CandidatoWebDescartado)))
        assert descartados
        assert all(
            "faltan datos suficientes para comprobar coincidencia" in descartado.motivos
            for descartado in descartados
        )


@pytest.mark.parametrize(
    ("producto_observado", "motivo_esperado"),
    [
        ("TRAYENTA 10 mg 30 tabletas", "concentración distinta"),
        ("TRAYENTA 5 mg 20 tabletas", "presentación distinta"),
        ("TRAYENTA 5 mg 30 cápsulas", "forma o dispositivo distinto"),
    ],
)
def test_cofepris_no_relaja_concentracion_presentacion_ni_forma(
    cliente,
    producto_observado,
    motivo_esperado,
):
    _importar(cliente, [_registro()])
    cotizacion_id, partida_id, usuario_id = _preparar_producto(cliente)
    with cliente.app.state.fabrica_sesiones() as sesion:
        resumen = ejecutar_descubrimiento_web(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_id,
            usuario_id=usuario_id,
            descubridor=_DescubridorTrayenta(producto_observado),
        )
        assert resumen.guardados == 0
        assert sesion.scalar(select(ObservacionPrecio)) is None
        descartados = list(sesion.scalars(select(CandidatoWebDescartado)))
        assert descartados
        assert motivo_esperado in descartados[0].motivos


def test_marca_solicitada_no_puede_sustituirse_con_cofepris(cliente):
    _importar(cliente, [_registro()])
    cotizacion_id, partida_id, usuario_id = _preparar_producto(cliente, marca="JANUVIA")
    with cliente.app.state.fabrica_sesiones() as sesion:
        resumen = ejecutar_descubrimiento_web(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_id,
            usuario_id=usuario_id,
            descubridor=_DescubridorTrayenta(),
        )
        assert resumen.guardados == 0
        assert sesion.scalar(select(ObservacionPrecio)) is None
        descartado = sesion.scalar(select(CandidatoWebDescartado))
        assert descartado is not None
        assert "marca distinta" in descartado.motivos


def test_sin_snapshot_conserva_el_rechazo_anterior(cliente):
    cotizacion_id, partida_id, usuario_id = _preparar_producto(cliente)
    with cliente.app.state.fabrica_sesiones() as sesion:
        resumen = ejecutar_descubrimiento_web(
            sesion,
            cotizacion_id=cotizacion_id,
            partida_documento_id=partida_id,
            usuario_id=usuario_id,
            descubridor=_DescubridorTrayenta(),
        )
        assert resumen.guardados == 0
        assert sesion.scalar(select(ObservacionPrecio)) is None
        descartado = sesion.scalar(select(CandidatoWebDescartado))
        assert descartado is not None
        assert "producto distinto" in descartado.motivos


def test_pantalla_importa_y_resume_snapshot(cliente):
    pantalla = cliente.get("/proveedores/cofepris/actualizar")
    assert pantalla.status_code == 200
    assert "Aún no hay catálogo COFEPRIS cargado" in pantalla.text
    respuesta = cliente.post(
        "/proveedores/cofepris/actualizar",
        data={"csrf_token": _csrf(pantalla.text)},
        files={
            "catalogo": (
                "Visor_Registros_Medicamentos.xlsx",
                _xlsx([_registro()]),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        follow_redirects=True,
    )
    assert respuesta.status_code == 200
    assert "Catálogo COFEPRIS actualizado correctamente" in respuesta.text
    assert "1 registros vigentes · 1 registros totales" in respuesta.text
