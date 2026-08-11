"""Punto de entrada de Triage V2."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
plantillas = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(
    title="Sistema Triage V2",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
)


@app.get("/health", tags=["operación"])
def healthcheck() -> dict[str, str]:
    """Permite al despliegue verificar que el proceso está disponible."""

    return {"estado": "ok"}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def inicio(request: Request):
    """Muestra una portada mínima y comprensible para cualquier integrante."""

    return plantillas.TemplateResponse(
        request=request,
        name="inicio.html",
        context={"titulo": "Sistema Triage"},
    )
