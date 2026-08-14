from triage.config import Configuracion
from triage.main import crear_app


def test_modelos_especificos_heredan_openai_model():
    configuracion = Configuracion(
        app_env="test",
        openai_model="gpt-5-base",
    )

    assert configuracion.modelo_openai_lector == "gpt-5-base"
    assert configuracion.modelo_openai_web == "gpt-5-base"


def test_modelos_especificos_pueden_separarse():
    configuracion = Configuracion(
        app_env="test",
        openai_model="gpt-5-base",
        openai_model_lector="gpt-5-lector",
        openai_model_web="gpt-5-web",
    )

    assert configuracion.modelo_openai_lector == "gpt-5-lector"
    assert configuracion.modelo_openai_web == "gpt-5-web"


def test_app_conecta_cada_adaptador_con_su_modelo(tmp_path):
    ruta_db = tmp_path / "modelos_openai.sqlite3"
    configuracion = Configuracion(
        app_env="test",
        database_url=f"sqlite+pysqlite:///{ruta_db}",
        openai_api_key="sk-prueba-no-real",
        openai_model="gpt-5-base",
        openai_model_lector="gpt-5-lector",
        openai_model_web="gpt-5-web",
    )

    aplicacion = crear_app(configuracion)

    assert aplicacion.state.lector_documentos.modelo == "gpt-5-lector"
    assert aplicacion.state.descubridor_web.modelo == "gpt-5-web"
    aplicacion.state.motor.dispose()
