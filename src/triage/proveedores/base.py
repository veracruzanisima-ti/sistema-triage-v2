"""Contrato neutral para consultar productos sin acoplar Triage a un proveedor."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class SolicitudProveedor:
    """Identidad preparada que un adaptador puede usar para buscar un producto."""

    partida_documento_id: str
    producto: str | None
    marca: str | None
    concentracion: str | None
    forma_dispositivo: str | None
    presentacion: str | None
    codigo_postal: str | None = None


@dataclass(frozen=True)
class ResultadoProveedor:
    """Hechos observados por un proveedor; no representa una decisión de compra."""

    encontrado: bool
    fuente: str
    producto_exacto: str | None = None
    precio_antes_iva: Decimal | None = None
    iva_porcentaje: Decimal | None = None
    precio_total: Decimal | None = None
    es_promocion: bool = False
    condiciones_promocion: str | None = None
    disponibilidad: str | None = None
    entrega_viable: bool | None = None


class ProveedorProducto(Protocol):
    """Interfaz mínima que deberán implementar NADRO, FESA u otros canales."""

    @property
    def nombre(self) -> str:
        """Nombre estable y entendible del canal consultado."""

    def consultar(self, solicitud: SolicitudProveedor) -> ResultadoProveedor:
        """Busca una identidad preparada y devuelve únicamente hechos observados."""
