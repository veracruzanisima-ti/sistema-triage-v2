"""Selección temporal de motores de IA para comparar precisión y consumo en el piloto."""

from dataclasses import dataclass

from fastapi import Request

_CLAVE_LECTOR_SESION = "modelo_ia_lector"
_CLAVE_WEB_SESION = "modelo_ia_web"


@dataclass(frozen=True)
class OpcionModeloIA:
    clave: str
    etiqueta: str
    descripcion: str
    disponible: bool
    seleccionada: bool


_CATALOGO = (
    (
        "openai:gpt-5",
        "GPT-5",
        "Control actual. Úsalo para comparar precisión con los candidatos económicos.",
    ),
    (
        "openai:gpt-5.4-mini",
        "GPT-5.4 mini",
        "Candidato OpenAI más económico para lectura y búsquedas bien definidas.",
    ),
    (
        "gemini:gemini-3.6-flash",
        "Gemini 3.6 Flash",
        "Candidato Gemini para lectura multimodal y búsqueda con Google Search.",
    ),
)


def _registro(request: Request, tipo: str) -> dict[str, object]:
    nombre = "lectores_ia" if tipo == "lector" else "descubridores_ia"
    return getattr(request.app.state, nombre, {})


def _clave_default(request: Request, tipo: str) -> str:
    nombre = "clave_lector_default" if tipo == "lector" else "clave_web_default"
    return getattr(request.app.state, nombre, "")


def clave_activa(request: Request, tipo: str) -> str:
    """Devuelve la selección de la sesión sólo si sigue disponible en este despliegue."""

    registro = _registro(request, tipo)
    sesion_clave = _CLAVE_LECTOR_SESION if tipo == "lector" else _CLAVE_WEB_SESION
    elegida = str(request.session.get(sesion_clave) or "")
    if elegida in registro:
        return elegida
    predeterminada = _clave_default(request, tipo)
    if predeterminada in registro:
        return predeterminada
    return next(iter(registro), "")


def opciones_modelo(request: Request, tipo: str) -> tuple[OpcionModeloIA, ...]:
    """Lista el catálogo estable sin revelar secretos ni contenido de variables de entorno."""

    registro = _registro(request, tipo)
    activa = clave_activa(request, tipo)
    opciones: list[OpcionModeloIA] = []
    claves_catalogo = {clave for clave, _, _ in _CATALOGO}
    for clave, etiqueta, descripcion in _CATALOGO:
        opciones.append(
            OpcionModeloIA(
                clave=clave,
                etiqueta=etiqueta,
                descripcion=descripcion,
                disponible=clave in registro,
                seleccionada=clave == activa,
            )
        )

    for clave in registro:
        if clave in claves_catalogo or clave.startswith("inyectado:"):
            continue
        proveedor, _, modelo = clave.partition(":")
        opciones.append(
            OpcionModeloIA(
                clave=clave,
                etiqueta=f"{proveedor.title()} · {modelo or clave}",
                descripcion="Modelo adicional configurado por variable de entorno.",
                disponible=True,
                seleccionada=clave == activa,
            )
        )
    return tuple(opciones)


def seleccionar_modelos(request: Request, *, lector: str, web: str) -> None:
    """Guarda una selección por navegador; no modifica configuración global ni secretos."""

    if lector not in _registro(request, "lector"):
        raise ValueError("El modelo elegido para lectura no está disponible en este entorno.")
    if web not in _registro(request, "web"):
        raise ValueError("El modelo elegido para búsqueda web no está disponible en este entorno.")
    request.session[_CLAVE_LECTOR_SESION] = lector
    request.session[_CLAVE_WEB_SESION] = web


def obtener_lector_documentos(request: Request):
    """Resuelve el lector de esta sesión conservando compatibilidad con pruebas existentes."""

    registro = _registro(request, "lector")
    clave = clave_activa(request, "lector")
    return registro.get(clave) or getattr(request.app.state, "lector_documentos", None)


def obtener_descubridor_web(request: Request):
    """Resuelve el buscador web de esta sesión conservando compatibilidad con inyección de tests."""

    registro = _registro(request, "web")
    clave = clave_activa(request, "web")
    return registro.get(clave) or getattr(request.app.state, "descubridor_web", None)
