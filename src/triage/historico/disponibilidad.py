"""Deriva disponibilidad operativa sin reescribir la evidencia original."""

_TRANSLITERACION = str.maketrans("áéíóúüñ", "aeiouun")

_SENALES_NEGATIVAS = (
    "agotado",
    "agotada",
    "agotados",
    "agotadas",
    "sin existencia",
    "sin existencias",
    "sin stock",
    "fuera de stock",
    "no disponible",
)

_SENALES_AMBIGUAS = (
    "consulta disponibilidad",
    "consultar disponibilidad",
    "confirma disponibilidad",
    "confirmar disponibilidad",
    "ver disponibilidad",
    "revisar disponibilidad",
    "pregunta disponibilidad",
    "preguntar disponibilidad",
    "sujeto a disponibilidad",
    "disponibilidad por confirmar",
    "falta confirmar",
    "pendiente de confirmar",
    "codigo postal para ver disponibilidad",
    "codigo postal para consultar disponibilidad",
    "ingresa un codigo postal",
    "ingresar un codigo postal",
    "captura un codigo postal",
    "capturar un codigo postal",
)

_SENALES_POSITIVAS = (
    "disponible",
    "en existencia",
    "hay existencia",
    "hay existencias",
    "stock disponible",
    "agregar al carrito",
    "anadir al carrito",
)


def _normalizar_texto(valor: str | None) -> str:
    if not valor:
        return ""
    return " ".join(valor.casefold().translate(_TRANSLITERACION).split())


def resolver_disponibilidad_operativa(
    *,
    entrega_viable: bool | None,
    disponibilidad: str | None,
) -> bool | None:
    """Combina el booleano externo con señales textuales inequívocas y conservadoras."""

    texto = _normalizar_texto(disponibilidad)
    if texto and any(senal in texto for senal in _SENALES_NEGATIVAS):
        return False

    if entrega_viable is not None:
        return entrega_viable

    if not texto:
        return None

    if any(senal in texto for senal in _SENALES_AMBIGUAS):
        return None

    if any(senal in texto for senal in _SENALES_POSITIVAS):
        return True

    return None
