from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]


def test_blueprint_preview_no_guarda_secretos_en_texto():
    configuracion = yaml.safe_load((RAIZ / "render.yaml").read_text(encoding="utf-8"))
    servicio = configuracion["services"][0]
    variables = {item["key"]: item for item in servicio["envVars"]}

    assert servicio["type"] == "web"
    assert servicio["runtime"] == "python"
    assert servicio["plan"] == "free"
    assert servicio["healthCheckPath"] == "/health"
    assert servicio["autoDeployTrigger"] == "checksPass"
    assert variables["APP_SECRET_KEY"]["generateValue"] is True

    for clave in (
        "BOOTSTRAP_ADMIN_EMAIL",
        "BOOTSTRAP_ADMIN_NAME",
        "BOOTSTRAP_ADMIN_PASSWORD",
    ):
        assert variables[clave]["sync"] is False
        assert "value" not in variables[clave]


def test_blueprint_conecta_postgres_sin_exponerlo_publicamente():
    configuracion = yaml.safe_load((RAIZ / "render.yaml").read_text(encoding="utf-8"))
    servicio = configuracion["services"][0]
    base = configuracion["databases"][0]
    variables = {item["key"]: item for item in servicio["envVars"]}

    assert base["plan"] == "free"
    assert base["ipAllowList"] == []
    assert variables["DATABASE_URL"]["fromDatabase"] == {
        "name": base["name"],
        "property": "connectionString",
    }


def test_preview_aplica_migraciones_antes_de_iniciar_servidor():
    script = (RAIZ / "scripts" / "iniciar_preview_render.sh").read_text(
        encoding="utf-8"
    )

    assert script.index("alembic upgrade head") < script.index("uvicorn triage.main:app")
