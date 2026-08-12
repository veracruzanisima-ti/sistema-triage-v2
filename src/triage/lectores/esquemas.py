"""Esquemas neutrales que cualquier lector documental debe producir."""

from pydantic import BaseModel, ConfigDict, Field


class PartidaLeida(BaseModel):
    """Una partida observada en la solicitud, sin decisiones comerciales añadidas."""

    model_config = ConfigDict(extra="forbid")

    producto_solicitado: str | None = None
    marca_solicitada: str | None = None
    concentracion: str | None = None
    forma_farmaceutica_dispositivo: str | None = None
    presentacion_solicitada: str | None = None
    cantidad: int | None = Field(default=None, ge=0)
    unidad_medida: str | None = None


class LecturaDocumento(BaseModel):
    """Datos administrativos y partidas que una persona debe revisar."""

    model_config = ConfigDict(extra="forbid")

    tipo_documento: str | None = None
    memorandum: str | None = None
    folios: list[str] = Field(default_factory=list)
    fecha_documento: str | None = None
    municipio: str | None = None
    parece_fragmento: bool = False
    senales_fragmento: list[str] = Field(default_factory=list)
    partidas: list[PartidaLeida] = Field(default_factory=list)
