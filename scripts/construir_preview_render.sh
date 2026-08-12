#!/usr/bin/env bash
set -euo pipefail

# Render Free no ofrece pre-deploy command. Para este preview ejecutamos la
# migración una vez durante el build y dejamos el start libre de cambios de
# esquema. Las migraciones del preview deben mantenerse compatibles hacia atrás
# con la revisión anterior mientras Render completa el cambio de instancia.
pip install -e .
alembic upgrade head
