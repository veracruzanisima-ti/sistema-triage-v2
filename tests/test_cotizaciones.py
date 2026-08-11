from fastapi.testclient import TestClient

from triage.base_datos import Base
from triage.config import Configuracion
from triage.main import crear_app


def test_crear_cotizacion_la_guarda_y_la_muestra(cliente):
    respuesta = cliente.post(
        "/cotizaciones",
        data={"referencia": "  DAIS/SSMA/944/2026  "},
    )

    assert respuesta.status_code == 200
    assert "DAIS/SSMA/944/2026" in respuesta.text
    assert "En Proceso" in respuesta.text

    listado = cliente.get("/cotizaciones")
    assert "DAIS/SSMA/944/2026" in listado.text


def test_cotizacion_puede_finalizarse_explictamente(cliente):
    creada = cliente.post(
        "/cotizaciones",
        data={"referencia": "CASC 388/08/2026"},
    )
    cotizacion_id = creada.url.path.rsplit("/", 1)[-1]

    respuesta = cliente.post(
        f"/cotizaciones/{cotizacion_id}/estado",
        data={"estado": "FINALIZADA"},
    )

    assert respuesta.status_code == 200
    assert "Finalizada" in respuesta.text


def test_cotizacion_sobrevive_a_otra_instancia_de_la_app(tmp_path):
    ruta_db = tmp_path / "triage_compartida.sqlite3"
    configuracion = Configuracion(
        app_env="test",
        database_url=f"sqlite+pysqlite:///{ruta_db}",
    )

    app_primera = crear_app(configuracion)
    Base.metadata.create_all(bind=app_primera.state.motor)
    with TestClient(app_primera) as primera_sesion:
        primera_sesion.post(
            "/cotizaciones",
            data={"referencia": "DAIS/SSMA/951/2026"},
        )
    app_primera.state.motor.dispose()

    app_segunda = crear_app(configuracion)
    with TestClient(app_segunda) as segunda_sesion:
        respuesta = segunda_sesion.get("/cotizaciones")
    app_segunda.state.motor.dispose()

    assert respuesta.status_code == 200
    assert "DAIS/SSMA/951/2026" in respuesta.text


def test_produccion_rechaza_sqlite_local():
    try:
        Configuracion(
            app_env="production",
            database_url="sqlite+pysqlite:///./no_permitida.sqlite3",
        )
    except ValueError as error:
        assert "base de datos compartida" in str(error)
    else:
        raise AssertionError("producción no debe aceptar SQLite local")
