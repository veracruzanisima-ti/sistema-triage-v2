"""Contrato pequeño para no acoplar Triage a un proveedor de IA."""

from typing import Protocol

from triage.lectores.esquemas import LecturaDocumento


class ErrorLecturaDocumento(RuntimeError):
    """Fallo controlado al interpretar un documento."""


class LectorDocumento(Protocol):
    """Convierte bytes de un documento en información revisable."""

    modelo: str

    def leer(
        self,
        *,
        contenido: bytes,
        mime_type: str,
        nombre_archivo: str,
    ) -> LecturaDocumento:
        """Interpreta un único archivo sin aplicar reglas comerciales."""
        ...
