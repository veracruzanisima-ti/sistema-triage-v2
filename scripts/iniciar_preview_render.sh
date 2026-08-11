#!/usr/bin/env bash
set -euo pipefail

# En el plan gratuito no usamos pre-deploy. Para este preview de una sola
# instancia, aplicar migraciones al arrancar es aceptable y mantiene el esquema
# sincronizado. Producción tendrá un procedimiento de migración separado.
alembic upgrade head

exec uvicorn triage.main:app --host 0.0.0.0 --port "${PORT:?Render debe definir PORT}"
