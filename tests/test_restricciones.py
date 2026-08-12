"""Pruebas del motor provisional de alertas de comercialización."""

from triage.lectores.esquemas import PartidaLeida
from triage.restricciones.servicio import evaluar_partida, normalizar_texto


def _partida(
    producto: str,
    *,
    marca: str | None = None,
    forma: str | None = None,
    presentacion: str | None = None,
) -> PartidaLeida:
    return PartidaLeida(
        producto_solicitado=producto,
        marca_solicitada=marca,
        forma_farmaceutica_dispositivo=forma,
        presentacion_solicitada=presentacion,
        cantidad=1,
        unidad_medida="caja",
    )


def test_normalizacion_es_solo_para_comparacion():
    assert normalizar_texto("ALBÚMINA humana 20%") == "albumina humana 20"


def test_midazolam_genera_alerta_en_cualquier_presentacion():
    alertas = evaluar_partida(_partida("Midazolam", forma="solución"))

    assert len(alertas) == 1
    assert alertas[0].regla_id == "R16"
    assert "todas sus presentaciones" in alertas[0].motivo


def test_buprenorfina_solo_alerta_en_presentaciones_citadas():
    parche = evaluar_partida(_partida("Buprenorfina", forma="parche"))
    tableta = evaluar_partida(_partida("Buprenorfina", forma="tabletas"))

    assert parche and parche[0].regla_id == "R01"
    assert tableta == ()


def test_tramadol_tableta_alerta_aunque_sea_combinado():
    alertas = evaluar_partida(
        _partida("Tramadol con paracetamol", presentacion="Caja con 20 tabletas")
    )

    assert alertas and alertas[0].regla_id == "R06"


def test_xeomeen_se_conserva_literal_sin_inventar_correccion():
    assert evaluar_partida(_partida("Xeomeen"))
    assert evaluar_partida(_partida("Xeomin")) == ()


def test_ejemplo_hemoderivado_genera_alerta_provisional():
    alertas = evaluar_partida(_partida("Albúmina humana"))

    assert alertas and alertas[0].regla_id == "R23"
    assert alertas[0].nota is not None
    assert "categoría completa requiere validación" in alertas[0].nota
