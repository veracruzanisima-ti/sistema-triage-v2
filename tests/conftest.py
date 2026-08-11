"""Fixtures compartidas para probar la aplicación sin servicios externos."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from triage.base_datos import Base
from triage.config import Configuracion
from triage.main import crear_app


@pytest.fixture()
def cliente(tmp_path) -> Iterator[TestClient]:
    """Entrega una app aislada con SQLite sólo para la duración de la prueba."""

    ruta_db = tmp_path / "triage_prueba.sqlite3"
    configuracion = Configuracion(
        app_env="test",
        database_url=f"sqlite+pysqlite:///{ruta_db}",
    )
    aplicacion = crear_app(configuracion)
    Base.metadata.create_all(bind=aplicacion.state.motor)

    with TestClient(aplicacion) as cliente_prueba:
        yield cliente_prueba

    aplicacion.state.motor.dispose()
