from decimal import Decimal

import httpx
import pytest
from pydantic import ValidationError

from triage.config import Configuracion
from triage.proveedores.base import SolicitudProveedor
from triage.proveedores.fesa import AdaptadorFesa


def _solicitud_lantus() -> SolicitudProveedor:
    return SolicitudProveedor(
        partida_documento_id="partida-1",
        producto="Insulina glargina",
        marca="LANTUS",
        concentracion="100 UI/mL",
        forma_dispositivo="Solución inyectable - vial",
        presentacion="Frasco vial de 10 mL",
        codigo_postal="91193",
    )


def _html_resultados() -> str:
    return """
    <html><body>
      <ol class="products list items product-items">
        <li class="product-item">
          <a class="product-item-link" href="/lantus-solostar.html">
            LANTUS SOLOSTAR 100UI AMP CAJ C/5X3ML
          </a>
          <span class="price">$2,341.62</span>
        </li>
        <li class="product-item">
          <a class="product-item-link" href="/lantus-vial.html">
            LANTUS 100 UI/ml 1 FAM C/10 ml
          </a>
          <span class="price">$2,306.01</span>
        </li>
      </ol>
    </body></html>
    """


def test_fesa_elige_presentacion_exacta_sin_confundir_solostar():
    def responder(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/catalogsearch/result/"
        return httpx.Response(200, text=_html_resultados())

    adaptador = AdaptadorFesa(transport=httpx.MockTransport(responder))

    resultado = adaptador.consultar(_solicitud_lantus())

    assert resultado.encontrado is True
    assert resultado.producto_exacto == "LANTUS 100 UI/ml 1 FAM C/10 ml"
    assert resultado.precio_total == Decimal("2306.01")
    assert resultado.fuente.endswith("/lantus-vial.html")


def test_fesa_prefiere_precio_promocional_visible_y_lo_marca():
    html = """
    <li class="product-item">
      <a class="product-item-link" href="/lantus-vial.html">
        LANTUS 100 UI/ml 1 FAM C/10 ml
      </a>
      <span class="old-price"><span class="price">$2,306.01</span></span>
      <span class="special-price"><span class="price">$1,900.00</span></span>
      <span>MAS CALIDAD DE VIDA · Descuento</span>
    </li>
    """

    adaptador = AdaptadorFesa(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, text=html))
    )

    resultado = adaptador.consultar(_solicitud_lantus())

    assert resultado.encontrado is True
    assert resultado.precio_total == Decimal("1900.00")
    assert resultado.es_promocion is True


def test_fesa_no_usa_producto_agotado_como_precio_utilizable():
    html = """
    <li class="product-item">
      <a class="product-item-link" href="/lantus-vial.html">
        LANTUS 100 UI/ml 1 FAM C/10 ml
      </a>
      <span class="price">$2,306.01</span>
      <span>Temporalmente agotado</span>
    </li>
    """
    adaptador = AdaptadorFesa(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, text=html))
    )

    resultado = adaptador.consultar(_solicitud_lantus())

    assert resultado.encontrado is False


def test_fesa_autenticada_inicia_sesion_antes_de_buscar():
    pasos: list[str] = []

    def responder(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/customer/account/login/":
            pasos.append("login-get")
            return httpx.Response(
                200,
                text="""
                <form class="form-login" action="/customer/account/loginPost/">
                  <input name="form_key" value="abc123">
                </form>
                """,
            )
        if request.url.path == "/customer/account/loginPost/":
            pasos.append("login-post")
            assert b"login%5Busername%5D=usuario%40example.com" in request.content
            return httpx.Response(200, text="<html><body>Mi cuenta</body></html>")
        if request.url.path == "/catalogsearch/result/":
            pasos.append("buscar")
            return httpx.Response(200, text=_html_resultados())
        raise AssertionError(f"Ruta inesperada: {request.url.path}")

    adaptador = AdaptadorFesa(
        usuario="usuario@example.com",
        password="password-ficticio",
        transport=httpx.MockTransport(responder),
    )

    resultado = adaptador.consultar(_solicitud_lantus())

    assert resultado.encontrado is True
    assert pasos == ["login-get", "login-post", "buscar"]


def test_configuracion_fesa_acepta_publica_y_exige_par_completo_de_credenciales():
    publica = Configuracion(fesa_habilitada=True)
    assert publica.fesa_habilitada is True
    assert publica.fesa_autenticada is False

    autenticada = Configuracion(
        fesa_habilitada=True,
        fesa_usuario="usuario@example.com",
        fesa_password="password-ficticio",
    )
    assert autenticada.fesa_autenticada is True

    with pytest.raises(ValidationError):
        Configuracion(fesa_usuario="usuario@example.com")
