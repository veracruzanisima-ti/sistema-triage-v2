"""Consulta directa del catálogo FESA, pública o con sesión autenticada opcional."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from triage.proveedores.base import ResultadoProveedor, SolicitudProveedor
from triage.proveedores.coincidencia_catalogo import (
    CandidatoCatalogo,
    seleccionar_candidato,
)

_BASE_URL = "https://www.farmaciasespecializadas.com"
_LOGIN_PATH = "/customer/account/login/"
_SEARCH_PATH = "/catalogsearch/result/"


class ErrorFesa(RuntimeError):
    """Fallo técnico del canal FESA sin exponer secretos."""


class AdaptadorFesa:
    """Consulta FESA y deja la decisión comercial fuera del adaptador."""

    nombre = "FESA"

    def __init__(
        self,
        *,
        usuario: str = "",
        password: str = "",
        timeout_seconds: float = 25.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._usuario = usuario.strip()
        self._password = password
        self._timeout = timeout_seconds
        self._transport = transport
        if bool(self._usuario) != bool(self._password):
            raise ValueError("FESA requiere usuario y contraseña juntos o ninguno")

    @property
    def autenticada(self) -> bool:
        return bool(self._usuario and self._password)

    def consultar(self, solicitud: SolicitudProveedor) -> ResultadoProveedor:
        """Busca una identidad preparada en FESA y devuelve sólo hechos observados."""

        consulta = _armar_consulta(solicitud)
        if not consulta:
            return ResultadoProveedor(
                encontrado=False,
                fuente=f"{_BASE_URL}{_SEARCH_PATH}",
            )

        try:
            with httpx.Client(
                base_url=_BASE_URL,
                follow_redirects=True,
                timeout=self._timeout,
                transport=self._transport,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
                    )
                },
            ) as cliente:
                if self.autenticada:
                    _iniciar_sesion(cliente, self._usuario, self._password)

                respuesta = cliente.get(_SEARCH_PATH, params={"q": consulta})
                respuesta.raise_for_status()
                productos = _extraer_productos(respuesta.text, str(respuesta.url))
        except (httpx.HTTPError, ValueError) as error:
            raise ErrorFesa("FESA no pudo completar la consulta.") from error

        candidatos = [
            CandidatoCatalogo(
                descripcion=producto.nombre,
                precio_observado=producto.precio,
                stock=producto.stock,
                fuente=producto.url,
            )
            for producto in productos
        ]
        seleccion = seleccionar_candidato(solicitud, candidatos)
        if seleccion is None:
            return ResultadoProveedor(
                encontrado=False,
                fuente=str(respuesta.url),
            )

        producto = next(
            item for item in productos if item.url == seleccion.candidato.fuente
        )
        return ResultadoProveedor(
            encontrado=True,
            fuente=producto.url,
            producto_exacto=producto.nombre,
            precio_total=producto.precio,
            es_promocion=producto.es_promocion,
            disponibilidad=producto.disponibilidad,
            entrega_viable=False if producto.stock == 0 else None,
        )


class _ProductoFesa:
    def __init__(
        self,
        *,
        nombre: str,
        precio: Decimal,
        url: str,
        stock: int | None,
        es_promocion: bool,
        disponibilidad: str | None,
    ) -> None:
        self.nombre = nombre
        self.precio = precio
        self.url = url
        self.stock = stock
        self.es_promocion = es_promocion
        self.disponibilidad = disponibilidad


def _armar_consulta(solicitud: SolicitudProveedor) -> str:
    partes = (
        solicitud.marca,
        solicitud.producto,
        solicitud.concentracion,
        solicitud.forma_dispositivo,
        solicitud.presentacion,
    )
    vistas: list[str] = []
    for parte in partes:
        limpio = " ".join(str(parte or "").split())
        if limpio and limpio.casefold() not in {valor.casefold() for valor in vistas}:
            vistas.append(limpio)
    return " ".join(vistas)


def _iniciar_sesion(cliente: httpx.Client, usuario: str, password: str) -> None:
    respuesta = cliente.get(_LOGIN_PATH)
    respuesta.raise_for_status()
    sopa = BeautifulSoup(respuesta.text, "html.parser")
    formulario = sopa.select_one("form.form-login") or sopa.find(
        "form", attrs={"action": re.compile("loginPost", re.I)}
    )
    if formulario is None:
        raise ErrorFesa("FESA cambió su formulario de acceso.")

    accion = formulario.get("action") or "/customer/account/loginPost/"
    datos: dict[str, str] = {}
    for entrada in formulario.select("input[name]"):
        nombre = entrada.get("name")
        if not nombre:
            continue
        datos[nombre] = str(entrada.get("value") or "")
    datos["login[username]"] = usuario
    datos["login[password]"] = password

    acceso = cliente.post(urljoin(str(respuesta.url), accion), data=datos)
    acceso.raise_for_status()
    sopa_acceso = BeautifulSoup(acceso.text, "html.parser")
    sigue_login = sopa_acceso.select_one("form.form-login") is not None
    if sigue_login and "customer/account/login" in str(acceso.url):
        raise ErrorFesa("FESA rechazó el inicio de sesión.")


def _extraer_productos(html: str, url_base: str) -> list[_ProductoFesa]:
    sopa = BeautifulSoup(html, "html.parser")
    bloques = sopa.select("li.product-item")
    if not bloques:
        bloques = sopa.select("div.product-item-info")

    productos: list[_ProductoFesa] = []
    urls_vistas: set[str] = set()
    for bloque in bloques:
        enlace = (
            bloque.select_one("a.product-item-link")
            or bloque.select_one(".product-item-name a")
            or bloque.select_one("a[href]")
        )
        if enlace is None:
            continue
        nombre = " ".join(enlace.get_text(" ", strip=True).split())
        href = enlace.get("href")
        if not nombre or not href:
            continue
        url = urljoin(url_base, href)
        if url in urls_vistas:
            continue

        precio = _extraer_precio(bloque)
        if precio is None or precio <= 0:
            continue

        texto = " ".join(bloque.get_text(" ", strip=True).split())
        texto_mayus = texto.upper()
        agotado = any(
            termino in texto_mayus
            for termino in ("TEMPORALMENTE AGOTADO", "AGOTADO", "NO DISPONIBLE")
        )
        disponible = "DISPONIBLE" in texto_mayus and not agotado
        promocion = bool(bloque.select_one(".special-price")) or any(
            termino in texto_mayus
            for termino in ("DESCUENTO", "MAS CALIDAD DE VIDA", "PROMOCION", "OFERTA")
        )
        disponibilidad = None
        stock: int | None = None
        if agotado:
            disponibilidad = "Agotado / no disponible"
            stock = 0
        elif disponible:
            disponibilidad = "Disponible"
            stock = 1

        productos.append(
            _ProductoFesa(
                nombre=nombre,
                precio=precio,
                url=url,
                stock=stock,
                es_promocion=promocion,
                disponibilidad=disponibilidad,
            )
        )
        urls_vistas.add(url)
    return productos


def _extraer_precio(bloque) -> Decimal | None:
    selectores = (
        ".special-price .price",
        ".price-final_price .price",
        ".price-box .price",
        ".price",
    )
    for selector in selectores:
        nodo = bloque.select_one(selector)
        if nodo is None:
            continue
        precio = _decimal_desde_texto(nodo.get_text(" ", strip=True))
        if precio is not None:
            return precio
    return _decimal_desde_texto(bloque.get_text(" ", strip=True))


def _decimal_desde_texto(texto: str) -> Decimal | None:
    coincidencia = re.search(r"\$\s*([0-9][0-9,.]*)", texto)
    if coincidencia is None:
        coincidencia = re.search(r"\b([0-9][0-9,]*\.[0-9]{2})\b", texto)
    if coincidencia is None:
        return None
    try:
        return Decimal(coincidencia.group(1).replace(",", ""))
    except InvalidOperation:
        return None
