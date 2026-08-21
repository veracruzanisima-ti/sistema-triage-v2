"""Comprueba ida y vuelta de la migración del precio final manual."""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

RAIZ = Path(__file__).resolve().parents[1]
TABLA = "precios_venta_partida"


def _alembic(base_datos: Path, *argumentos: str) -> None:
    entorno = os.environ.copy()
    entorno["DATABASE_URL"] = f"sqlite+pysqlite:///{base_datos}"
    subprocess.run(
        [sys.executable, "-m", "alembic", *argumentos],
        cwd=RAIZ,
        env=entorno,
        check=True,
        capture_output=True,
        text=True,
    )


def _tabla_existe(base_datos: Path) -> bool:
    motor = create_engine(f"sqlite+pysqlite:///{base_datos}")
    try:
        return TABLA in inspect(motor).get_table_names()
    finally:
        motor.dispose()


def test_migracion_precio_venta_upgrade_downgrade_upgrade(tmp_path):
    base_datos = tmp_path / "precio_venta_migracion.sqlite3"

    _alembic(base_datos, "upgrade", "head")
    assert _tabla_existe(base_datos)

    _alembic(base_datos, "downgrade", "20260820_0016")
    assert not _tabla_existe(base_datos)

    _alembic(base_datos, "upgrade", "head")
    assert _tabla_existe(base_datos)
