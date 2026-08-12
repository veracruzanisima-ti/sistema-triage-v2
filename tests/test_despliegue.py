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
        "OPENAI_API_KEY",
        "BOOTSTRAP_ADMIN_EMAIL",
        "BOOTSTRAP_ADMIN_NAME",
        "BOOTSTRAP_ADMIN_PASSWORD",
    ):
        assert variables[clave]["sync"] is False
        assert "value" not in variables[clave]

    assert variables["OPENAI_MODEL"]["value"] == "gpt-5"
    assert int(variables["MAX_DOCUMENTO_BYTES"]["value"]) > 0


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


def test_preview_separa_migraciones_del_arranque_de_instancia():
    configuracion = yaml.safe_load((RAIZ / "render.yaml").read_text(encoding="utf-8"))
    servicio = configuracion["services"][0]
    build = (RAIZ / "scripts" / "construir_preview_render.sh").read_text(
        encoding="utf-8"
    )
    start = (RAIZ / "scripts" / "iniciar_preview_render.sh").read_text(
        encoding="utf-8"
    )

    assert servicio["buildCommand"] == "bash scripts/construir_preview_render.sh"
    assert servicio["startCommand"] == "bash scripts/iniciar_preview_render.sh"
    assert "alembic upgrade head" in build
    assert "uvicorn triage.main:app" not in build
    assert "alembic upgrade head" not in start
    assert "uvicorn triage.main:app" in start
