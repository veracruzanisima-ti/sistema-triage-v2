"""Carga transaccional y consulta del snapshot normalizado de EdiNadro."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from triage.proveedores.nadro_edi import (
    ErrorFormatoNadro,
    parsear_linea_catalogo,
    parsear_linea_oferta,
)
from triage.proveedores.nadro_modelos import ArticuloNadro, ImportacionNadro, OfertaNadro

_MAX_CATALOGO_BYTES = 10 * 1024 * 1024
_MAX_OFERTAS_BYTES = 5 * 1024 * 1024


class ErrorImportacionNadro(ValueError):
    """Archivo NADRO inválido o inconsistente; el snapshot previo debe conservarse."""


def _nombre_archivo(nombre: str, esperado: str) -> str:
    limpio = Path(nombre or "").name.strip()
    if not limpio or not limpio.lower().endswith(".dat"):
        raise ErrorImportacionNadro(f"{esperado} debe ser un archivo .DAT")
    return limpio[:255]


def _lineas(datos: bytes, *, nombre: str, max_bytes: int) -> list[str]:
    if not datos:
        raise ErrorImportacionNadro(f"{nombre} está vacío")
    if len(datos) > max_bytes:
        raise ErrorImportacionNadro(f"{nombre} excede el tamaño permitido")
    try:
        texto = datos.decode("cp1252")
    except UnicodeDecodeError as error:
        raise ErrorImportacionNadro(f"{nombre} no usa una codificación esperada") from error
    return [linea for linea in texto.splitlines() if linea.strip()]


def importar_snapshot_nadro(
    sesion: Session,
    *,
    usuario_id: str,
    nombre_catalogo: str,
    datos_catalogo: bytes,
    nombre_ofertas: str,
    datos_ofertas: bytes,
) -> ImportacionNadro:
    """Reemplaza catálogo+ofertas en una sola transacción, o conserva el snapshot previo."""

    archivo_catalogo = _nombre_archivo(nombre_catalogo, "El catálogo NADRO")
    archivo_ofertas = _nombre_archivo(nombre_ofertas, "El archivo de ofertas NADRO")
    lineas_catalogo = _lineas(
        datos_catalogo,
        nombre=archivo_catalogo,
        max_bytes=_MAX_CATALOGO_BYTES,
    )
    lineas_ofertas = _lineas(
        datos_ofertas,
        nombre=archivo_ofertas,
        max_bytes=_MAX_OFERTAS_BYTES,
    )

    try:
        catalogo = tuple(parsear_linea_catalogo(linea) for linea in lineas_catalogo)
        ofertas = tuple(parsear_linea_oferta(linea) for linea in lineas_ofertas)
    except ErrorFormatoNadro as error:
        raise ErrorImportacionNadro(str(error)) from error

    if not catalogo:
        raise ErrorImportacionNadro("El catálogo NADRO no contiene artículos")

    codigos = [registro.codigo_nadro for registro in catalogo]
    if len(codigos) != len(set(codigos)):
        raise ErrorImportacionNadro("El catálogo NADRO contiene códigos duplicados")
    codigos_catalogo = set(codigos)
    ofertas_huerfanas = sorted(
        {oferta.codigo_nadro for oferta in ofertas if oferta.codigo_nadro not in codigos_catalogo}
    )
    if ofertas_huerfanas:
        raise ErrorImportacionNadro(
            "El archivo de ofertas contiene códigos que no existen en el catálogo actual"
        )

    importacion_id = str(uuid4())
    importacion = ImportacionNadro(
        id=importacion_id,
        cargada_por_usuario_id=usuario_id,
        archivo_catalogo=archivo_catalogo,
        sha256_catalogo=sha256(datos_catalogo).hexdigest(),
        articulos_cargados=len(catalogo),
        archivo_ofertas=archivo_ofertas,
        sha256_ofertas=sha256(datos_ofertas).hexdigest(),
        ofertas_cargadas=len(ofertas),
    )

    articulos = [
        {
            "codigo_nadro": registro.codigo_nadro,
            "importacion_id": importacion_id,
            "descripcion": registro.descripcion,
            "laboratorio": registro.laboratorio,
            "codigo_ean": registro.codigo_ean,
            "familia": registro.familia,
            "departamento": registro.departamento,
            "categoria": registro.categoria,
            "clave_ssa": registro.clave_ssa,
            "clasificacion_fiscal": registro.clasificacion_fiscal,
            "requiere_refrigeracion": registro.requiere_refrigeracion,
            "precio_publico_sin_iva": registro.precio_publico_sin_iva,
            "precio_venta_reportado": registro.precio_venta,
            "precio_farmacia_sin_iva": registro.precio_farmacia_sin_iva,
            "descuento_limitado_pct": registro.descuento_limitado_pct,
            "fecha_ultimo_movimiento": registro.fecha_ultimo_movimiento,
        }
        for registro in catalogo
    ]
    filas_oferta = [
        {
            "id": str(uuid4()),
            "importacion_id": importacion_id,
            "codigo_nadro": oferta.codigo_nadro,
            "descripcion": oferta.descripcion,
            "codigo_ean": oferta.codigo_ean,
            "precio_farmacia_sin_iva": oferta.precio_farmacia_sin_iva,
            "cantidad_con_cargo": oferta.cantidad_con_cargo,
            "descuento_primera_escala_pct": oferta.descuento_primera_escala_pct,
            "descuento_segunda_escala_pct": oferta.descuento_segunda_escala_pct,
            "cantidad_sin_cargo": oferta.cantidad_sin_cargo,
            "desde_piezas_primera_escala": oferta.desde_piezas_primera_escala,
            "desde_piezas_segunda_escala": oferta.desde_piezas_segunda_escala,
            "descuento_factura_pct": oferta.descuento_factura_pct,
        }
        for oferta in ofertas
    ]

    try:
        sesion.add(importacion)
        sesion.flush()
        sesion.execute(delete(OfertaNadro))
        sesion.execute(delete(ArticuloNadro))
        sesion.execute(insert(ArticuloNadro), articulos)
        if filas_oferta:
            sesion.execute(insert(OfertaNadro), filas_oferta)
        sesion.commit()
    except Exception:
        sesion.rollback()
        raise

    sesion.refresh(importacion)
    return importacion


def ultima_importacion_nadro(sesion: Session) -> ImportacionNadro | None:
    return sesion.scalar(
        select(ImportacionNadro).order_by(ImportacionNadro.cargada_en.desc()).limit(1)
    )


def hay_catalogo_nadro(sesion: Session) -> bool:
    return bool(sesion.scalar(select(func.count()).select_from(ArticuloNadro)))


def hay_ofertas_nadro(sesion: Session) -> bool:
    return bool(sesion.scalar(select(func.count()).select_from(OfertaNadro)))
