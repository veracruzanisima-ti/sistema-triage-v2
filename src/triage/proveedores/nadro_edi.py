"""Parser de los archivos EdiNadro documentados por NADRO.

Los formatos MATERIAL.DAT y PRECIO.DAT usan registros de ancho fijo de 101
caracteres. OFERTA.DAT usa registros de 115 caracteres. Este módulo conserva
los hechos publicados por NADRO sin convertir clasificación fiscal, cadena fría
o promociones en decisiones automáticas de Triage.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path


class ErrorFormatoNadro(ValueError):
    """Indica que un registro EDI no cumple el ancho/formato documentado."""


@dataclass(frozen=True)
class RegistroMaterialNadro:
    movimiento: str
    codigo_nadro: str
    familia: str
    departamento: str
    categoria: str
    vigencia: str
    refrigeracion: str
    clave_ssa: str
    clasificacion_fiscal: str
    descripcion: str
    laboratorio: str
    precio_publico_sin_iva: Decimal
    precio_farmacia_sin_iva: Decimal
    pece_1989: str
    fecha_ultimo_movimiento: str
    codigo_ean: str

    @property
    def vigente(self) -> bool | None:
        if self.vigencia == "1":
            return True
        if self.vigencia == "0":
            return False
        return None

    @property
    def requiere_refrigeracion(self) -> bool | None:
        if self.refrigeracion == "1":
            return True
        if self.refrigeracion == "0":
            return False
        return None


@dataclass(frozen=True)
class RegistroOfertaNadro:
    codigo_nadro: str
    codigo_ean: str
    codigo_ean_subempaque: str
    codigo_ean_empaque: str
    clave_ssa: str
    descripcion: str
    precio_farmacia_sin_iva: Decimal
    cantidad_con_cargo: int
    descuento_primera_escala_pct: Decimal
    descuento_segunda_escala_pct: Decimal
    cantidad_sin_cargo: int
    desde_piezas_primera_escala: int
    desde_piezas_segunda_escala: int
    descuento_factura_pct: Decimal


_ANCHO_MATERIAL = 101
_ANCHO_OFERTA = 115


def parsear_linea_material(linea: str) -> RegistroMaterialNadro:
    """Interpreta una línea MATERIAL.DAT según el formato oficial recibido."""

    texto = _normalizar_linea(linea, _ANCHO_MATERIAL, "MATERIAL.DAT")
    return RegistroMaterialNadro(
        movimiento=_campo(texto, 1, 1),
        codigo_nadro=_campo(texto, 2, 9),
        familia=_campo(texto, 10, 10),
        departamento=_campo(texto, 11, 11),
        categoria=_campo(texto, 12, 12),
        vigencia=_campo(texto, 14, 14),
        refrigeracion=_campo(texto, 15, 15),
        clave_ssa=_campo(texto, 16, 16),
        clasificacion_fiscal=_campo(texto, 17, 17),
        descripcion=_campo(texto, 18, 52, limpiar=True),
        laboratorio=_campo(texto, 53, 62, limpiar=True),
        precio_publico_sin_iva=_decimal_con_dos_decimales(_campo(texto, 63, 71)),
        precio_farmacia_sin_iva=_decimal_con_dos_decimales(_campo(texto, 72, 80)),
        pece_1989=_campo(texto, 81, 81),
        fecha_ultimo_movimiento=_campo(texto, 82, 87),
        codigo_ean=_campo(texto, 88, 101),
    )


def parsear_linea_precio(linea: str) -> RegistroMaterialNadro:
    """PRECIO.DAT comparte exactamente el layout documentado de MATERIAL.DAT."""

    return parsear_linea_material(linea)


def parsear_linea_oferta(linea: str) -> RegistroOfertaNadro:
    """Interpreta una línea OFERTA.DAT según el formato oficial recibido."""

    texto = _normalizar_linea(linea, _ANCHO_OFERTA, "OFERTA.DAT")
    return RegistroOfertaNadro(
        codigo_nadro=_campo(texto, 1, 8),
        codigo_ean=_campo(texto, 9, 22),
        codigo_ean_subempaque=_campo(texto, 23, 36),
        codigo_ean_empaque=_campo(texto, 37, 50),
        clave_ssa=_campo(texto, 51, 51),
        descripcion=_campo(texto, 52, 86, limpiar=True),
        precio_farmacia_sin_iva=_decimal_con_dos_decimales(_campo(texto, 87, 95)),
        cantidad_con_cargo=_entero(_campo(texto, 96, 98)),
        descuento_primera_escala_pct=_decimal_entero(_campo(texto, 99, 101)),
        descuento_segunda_escala_pct=_decimal_entero(_campo(texto, 102, 104)),
        cantidad_sin_cargo=_entero(_campo(texto, 105, 106)),
        desde_piezas_primera_escala=_entero(_campo(texto, 107, 108)),
        desde_piezas_segunda_escala=_entero(_campo(texto, 109, 110)),
        descuento_factura_pct=_decimal_con_dos_decimales(_campo(texto, 111, 115)),
    )


def leer_materiales(ruta: str | Path) -> tuple[RegistroMaterialNadro, ...]:
    return tuple(parsear_linea_material(linea) for linea in _leer_lineas(ruta))


def leer_cambios_precio(ruta: str | Path) -> tuple[RegistroMaterialNadro, ...]:
    return tuple(parsear_linea_precio(linea) for linea in _leer_lineas(ruta))


def leer_ofertas(ruta: str | Path) -> tuple[RegistroOfertaNadro, ...]:
    return tuple(parsear_linea_oferta(linea) for linea in _leer_lineas(ruta))


def aplicar_movimientos(
    base: dict[str, RegistroMaterialNadro],
    movimientos: tuple[RegistroMaterialNadro, ...],
) -> dict[str, RegistroMaterialNadro]:
    """Aplica altas/cambios/bajas sobre una base ya existente sin inventar un catálogo inicial."""

    resultado = dict(base)
    for registro in movimientos:
        if registro.movimiento == "B":
            resultado.pop(registro.codigo_nadro, None)
        elif registro.movimiento in {"A", "C"}:
            resultado[registro.codigo_nadro] = registro
        else:
            raise ErrorFormatoNadro(
                f"movimiento NADRO no reconocido para {registro.codigo_nadro}: "
                f"{registro.movimiento!r}"
            )
    return resultado


def agrupar_ofertas_por_codigo(
    ofertas: tuple[RegistroOfertaNadro, ...],
) -> dict[str, tuple[RegistroOfertaNadro, ...]]:
    acumuladas: dict[str, list[RegistroOfertaNadro]] = {}
    for oferta in ofertas:
        acumuladas.setdefault(oferta.codigo_nadro, []).append(oferta)
    return {codigo: tuple(valores) for codigo, valores in acumuladas.items()}


def _leer_lineas(ruta: str | Path) -> list[str]:
    datos = Path(ruta).read_bytes()
    texto = datos.decode("cp1252")
    return [linea for linea in texto.splitlines() if linea.strip()]


def _normalizar_linea(linea: str, ancho: int, nombre: str) -> str:
    texto = linea.rstrip("\r\n")
    if len(texto) != ancho:
        raise ErrorFormatoNadro(
            f"{nombre} esperaba {ancho} caracteres y recibió {len(texto)}"
        )
    return texto


def _campo(texto: str, desde: int, hasta: int, *, limpiar: bool = False) -> str:
    valor = texto[desde - 1 : hasta]
    return valor.strip() if limpiar else valor


def _decimal_con_dos_decimales(valor: str) -> Decimal:
    limpio = valor.strip().replace(",", "")
    if not limpio:
        return Decimal("0")
    try:
        if "." in limpio:
            return Decimal(limpio)
        if limpio.isdigit():
            return Decimal(limpio) / Decimal("100")
        return Decimal(limpio)
    except InvalidOperation as error:
        raise ErrorFormatoNadro(f"importe NADRO inválido: {valor!r}") from error


def _decimal_entero(valor: str) -> Decimal:
    limpio = valor.strip()
    if not limpio:
        return Decimal("0")
    try:
        return Decimal(limpio)
    except InvalidOperation as error:
        raise ErrorFormatoNadro(f"porcentaje NADRO inválido: {valor!r}") from error


def _entero(valor: str) -> int:
    limpio = valor.strip()
    if not limpio:
        return 0
    try:
        return int(limpio)
    except ValueError as error:
        raise ErrorFormatoNadro(f"entero NADRO inválido: {valor!r}") from error
