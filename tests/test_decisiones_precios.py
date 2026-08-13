from triage.historico.decisiones_modelos import RolDecisionPrecio


def test_roles_de_decision_son_explicitos():
    assert RolDecisionPrecio.REFERENCIA_ESTABLE.value == "REFERENCIA_ESTABLE"
    assert RolDecisionPrecio.OPORTUNIDAD_ADQUISICION.value == "OPORTUNIDAD_ADQUISICION"
