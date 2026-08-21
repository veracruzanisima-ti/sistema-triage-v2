"""Regresiones para no confundir forma farmacéutica con envase o dispositivo."""

from decimal import Decimal

from triage.proveedores.base import SolicitudProveedor
from triage.proveedores.coincidencia_catalogo import CandidatoCatalogo, evaluar_candidato


def _solicitud(forma: str, presentacion: str | None = None) -> SolicitudProveedor:
    return SolicitudProveedor(
        partida_documento_id="partida",
        producto="INSULINA GLARGINA",
        marca=None,
        concentracion="100 U/mL",
        forma_dispositivo=forma,
        presentacion=presentacion,
    )


def _candidato(descripcion: str) -> CandidatoCatalogo:
    return CandidatoCatalogo(
        descripcion=descripcion,
        precio_observado=Decimal("393"),
        stock=None,
        fuente="https://ejemplo.invalid/insulina",
    )


def test_vial_sin_forma_explicita_es_evidencia_insuficiente_no_forma_distinta():
    evaluacion = evaluar_candidato(
        _solicitud("Solución inyectable"),
        _candidato("Insulina Glargina 100 UI frasco ámpula 10 mL"),
    )

    assert evaluacion.coincide is False
    assert "forma o dispositivo distinto" not in evaluacion.motivos
    assert "faltan datos suficientes para comprobar coincidencia" in evaluacion.motivos


def test_tableta_es_forma_explicita_incompatible_con_solucion_inyectable():
    evaluacion = evaluar_candidato(
        _solicitud("Solución inyectable"),
        _candidato("Insulina Glargina 100 UI/mL tabletas"),
    )

    assert evaluacion.coincide is False
    assert "forma o dispositivo distinto" in evaluacion.motivos


def test_solucion_inyectable_explicita_con_ampula_puede_coincidir():
    evaluacion = evaluar_candidato(
        _solicitud("Solución inyectable", "10 mL"),
        _candidato("Insulina Glargina 100 UI/mL Solución Inyectable Ámpula 10 mL"),
    )

    assert evaluacion.coincide is True
    assert evaluacion.motivos == ()


def test_dispositivos_explicitos_incompatibles_siguen_rechazados():
    evaluacion = evaluar_candidato(
        _solicitud("Solución inyectable pluma"),
        _candidato("Insulina Glargina 100 UI/mL Solución Inyectable Vial 10 mL"),
    )

    assert evaluacion.coincide is False
    assert "forma o dispositivo distinto" in evaluacion.motivos
