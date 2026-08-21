"""Deriva disponibilidad operativa sin reescribir la evidencia original."""

import re
import unicodedata


_PATRONES_NEGATIVOS = (
    r"\bagotad[oa]s?\b",
    r"\bsin existencias?\b",
    r"\bsin stock\b",
    r"\bfuera de stock\b",
    r"\bno disponible\b",
)

_PATRONES_AMBIGUOS = (
    r"\b(?:consulta|consultar|confirma|confirmar|ver|revisar|pregunta|preguntar)\s+(?:la\s+)?disponibilidad\b",
    r"\bsujeto a disponibilidad\b",
    r"\bdisponibilidad por confirmar\b",
    r"\bcodigo postal\b.*\b(?:ver|consultar)\b.*\bdisponibilidad\b",
    r"\b(?:ingresa|ingresar|captura|capturar)\b.*\bcodigo postal\b",
)

_PATRONES_POSITIVOS = (
    r"\b\d+\s+(?:unidades?\s+|piezas?\s+|cajas?\s+)?disponibles?\b",
    r"\ben existencia\b",
    r"\bhay existencias?\b",
    r"\bstock disponible\b",
    r"\b(?:agregar|anadir)\s+al carrito\b",
    r"\bdisponible\b",
)


def _normalizar_texto(valor: str | None) -> str:
    if not valor:
        return ""
    normalizado = unicodedata.normalize("NFKD", valor)
    sin_acentos = "".join(
        caracter for caracter in normalizado if not unicodedata.combining(caracter)
    )
    return " ".join(sin_acentos.casefold().split())


def resolver_disponibilidad_operativa(
    *,
    entrega_viable: bool | None,
    disponibilidad: str | None,
) -> bool | None:
    """Combina el booleano externo con señales textuales inequívocas y conservadoras."""

    texto = _normalizar_texto(disponibilidad)
    if texto and any(re.search(patron, texto) for patron in _PATRONES_NEGATIVOS):
        return False

    if entrega_viable is not None:
        return entrega_viable

    if not texto:
        return None

    if any(re.search(patron, texto) for patron in _PATRONES_AMBIGUOS):
        return None

    if any(re.search(patron, texto) for patron in _PATRONES_POSITIVOS):
        return True

    return None
