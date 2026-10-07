"""Sugerencias de catálogo separadas de la evidencia documental y la cotización."""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from triage.lectores.esquemas import PartidaLeida


class ProductoCatalogo(BaseModel):
    """Identidad explícita de una entrada; la fuente permite comprobarla."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    fuente: str
    nombre_comercial: str
    sustancia_activa: str
    concentracion: str
    forma_farmaceutica_dispositivo: str
    presentacion: str


class SugerenciaComercial(BaseModel):
    """Candidato verificable, nunca una sustitución clínica ni una referencia de precio."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    producto: ProductoCatalogo
    motivo: str = "Coincidencia exacta de identidad con el catálogo proporcionado"


def _clave(valor: str | None) -> str:
    return " ".join((valor or "").split()).casefold()


def sugerir_desde_catalogo(
    partida: PartidaLeida, catalogo: Sequence[ProductoCatalogo]
) -> list[SugerenciaComercial]:
    """No completa campos, no modifica la extracción y no consulta proveedores.

    Devuelve todos los candidatos exactos, sin inferir popularidad o equivalencia.
    Una identidad incompleta impide sugerir, pero nunca impide capturar la partida.
    """

    identidad = tuple(
        map(
            _clave,
            (
                partida.sustancia_activa,
                partida.concentracion,
                partida.forma_farmaceutica_dispositivo,
                partida.presentacion_solicitada,
            ),
        )
    )
    if not all(identidad):
        return []

    return [
        SugerenciaComercial(producto=producto)
        for producto in catalogo
        if _clave(producto.id)
        and _clave(producto.fuente)
        and _clave(producto.nombre_comercial)
        and identidad
        == tuple(
            map(
                _clave,
                (
                    producto.sustancia_activa,
                    producto.concentracion,
                    producto.forma_farmaceutica_dispositivo,
                    producto.presentacion,
                ),
            )
        )
        and (
            not partida.marca_solicitada
            or _clave(partida.marca_solicitada) == _clave(producto.nombre_comercial)
        )
    ]
