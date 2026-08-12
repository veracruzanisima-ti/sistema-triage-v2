#!/usr/bin/env bash
set -euo pipefail

# El arranque de una instancia no modifica el esquema de la base de datos.
# Render puede mantener temporalmente dos revisiones del servicio durante un
# deploy sin downtime; ejecutar Alembic aquí puede romper la instancia anterior
# si la base ya fue adelantada por la nueva revisión.
exec uvicorn triage.main:app --host 0.0.0.0 --port "${PORT:?Render debe definir PORT}"
