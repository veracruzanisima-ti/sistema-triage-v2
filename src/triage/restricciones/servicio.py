"""Evaluación determinista de alertas provisionales de comercialización."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol

from triage.restricciones.politica import (
    ESTADO_VALIDACION,
    POLITICA_ID,
    POLITICA_VERSION,
    REGLAS,
)


class PartidaEvaluable(Protocol):
    """Campos mínimos disponibles tanto antes como después de la revisión humana."""

    producto_solicitado: str | None
    marca_solicitada: str | None
    concentracion: str | None
    forma_farmaceutica_dispositivo: str | None
    presentacion_solicitada: str | None
    unidad_medida: str | None


@dataclass(frozen=True)
class AlertaRestriccion:
    """Advertencia informativa; no representa un rechazo automático."""

    regla_id: str
    motivo: str
    politica_id: str = POLITICA_ID
    politica_version: str = POLITICA_VERSION
    estado_validacion: str = ESTADO_VALIDACION
    nota: str | None = None


_CARACTERES_NO_ALFANUMERICOS = re.compile(r"[^a-z0-9]+")


def normalizar_texto(*valores: object | None) -> str:
    """Normaliza texto sólo para comparación; nunca reemplaza los datos originales."""

    texto = " ".join(str(valor) for valor in valores if valor is not None).lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
    texto = _CARACTERES_NO_ALFANUMERICOS.sub(" ", texto)
    return " ".join(texto.split())


def _contiene_termino(texto_normalizado: str, termino: str) -> bool:
    termino_normalizado = normalizar_texto(termino)
    if not termino_normalizado:
        return False
    return f" {termino_normalizado} " in f" {texto_normalizado} "


def evaluar_partida(partida: PartidaEvaluable) -> tuple[AlertaRestriccion, ...]:
    """Devuelve posibles restricciones aplicables sin modificar ni bloquear la partida."""

    texto = normalizar_texto(
        partida.producto_solicitado,
        partida.marca_solicitada,
        partida.concentracion,
        partida.forma_farmaceutica_dispositivo,
        partida.presentacion_solicitada,
        partida.unidad_medida,
    )
    if not texto:
        return ()

    alertas: list[AlertaRestriccion] = []
    for regla in REGLAS:
        if not any(_contiene_termino(texto, termino) for termino in regla.terminos):
            continue
        if regla.condiciones_presentacion and not any(
            _contiene_termino(texto, condicion)
            for condicion in regla.condiciones_presentacion
        ):
            continue
        alertas.append(
            AlertaRestriccion(
                regla_id=regla.id,
                motivo=regla.descripcion,
                nota=regla.nota,
            )
        )
    return tuple(alertas)
