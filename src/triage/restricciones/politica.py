"""Política provisional derivada de una fuente interna pendiente de validación sanitaria."""

from dataclasses import dataclass

POLITICA_ID = "POL-COM-001"
POLITICA_VERSION = "0.1-provisional"
ESTADO_VALIDACION = "PENDIENTE_VALIDACION_RESPONSABLE_SANITARIO"
FUENTE_INTERNA = "PRODUCTOS QUE NO SE PUEDEN COMERCIALIZAR.docx"


@dataclass(frozen=True)
class ReglaRestriccion:
    """Una coincidencia textual que sólo genera una alerta; nunca bloquea la partida."""

    id: str
    descripcion: str
    terminos: tuple[str, ...]
    condiciones_presentacion: tuple[str, ...] = ()
    nota: str | None = None


REGLAS: tuple[ReglaRestriccion, ...] = (
    ReglaRestriccion(
        id="R01",
        descripcion="Buprenorfina (parches o inyectable).",
        terminos=("buprenorfina",),
        condiciones_presentacion=("parche", "parches", "inyectable", "inyectables"),
    ),
    ReglaRestriccion(
        id="R02",
        descripcion="Xeomeen.",
        terminos=("xeomeen",),
        nota="Se conserva exactamente la grafía de la fuente; no se corrige automáticamente.",
    ),
    ReglaRestriccion(id="R03", descripcion="Dysport.", terminos=("dysport",)),
    ReglaRestriccion(
        id="R04",
        descripcion="Metilfenidato (en cualquier dosis).",
        terminos=("metilfenidato",),
    ),
    ReglaRestriccion(
        id="R05",
        descripcion="Clonazepam (tabletas y gotas).",
        terminos=("clonazepam",),
        condiciones_presentacion=("tableta", "tabletas", "gota", "gotas"),
    ),
    ReglaRestriccion(
        id="R06",
        descripcion="Tramadol (inyectable y tabletas, combinado o solo).",
        terminos=("tramadol",),
        condiciones_presentacion=("inyectable", "inyectables", "tableta", "tabletas"),
    ),
    ReglaRestriccion(
        id="R07",
        descripcion="Naltrexone o Naltrexona.",
        terminos=("naltrexone", "naltrexona"),
    ),
    ReglaRestriccion(id="R08", descripcion="Fentanilo.", terminos=("fentanilo",)),
    ReglaRestriccion(
        id="R09",
        descripcion="Alprazolam (de cualquier gramaje).",
        terminos=("alprazolam",),
    ),
    ReglaRestriccion(id="R10", descripcion="Lorazepam.", terminos=("lorazepam",)),
    ReglaRestriccion(id="R11", descripcion="Bromazepam.", terminos=("bromazepam",)),
    ReglaRestriccion(id="R12", descripcion="Flumazenil.", terminos=("flumazenil",)),
    ReglaRestriccion(id="R13", descripcion="Morfina.", terminos=("morfina",)),
    ReglaRestriccion(id="R14", descripcion="Sufentanilo.", terminos=("sufentanilo",)),
    ReglaRestriccion(id="R15", descripcion="Nalbufina.", terminos=("nalbufina",)),
    ReglaRestriccion(
        id="R16",
        descripcion="Midazolam (en todas sus presentaciones).",
        terminos=("midazolam",),
    ),
    ReglaRestriccion(
        id="R17",
        descripcion="Diazepam (inyectable y tabletas).",
        terminos=("diazepam",),
        condiciones_presentacion=("inyectable", "inyectables", "tableta", "tabletas"),
    ),
    ReglaRestriccion(id="R18", descripcion="Ergometrina.", terminos=("ergometrina",)),
    ReglaRestriccion(id="R19", descripcion="Efedrina.", terminos=("efedrina",)),
    ReglaRestriccion(
        id="R20",
        descripcion="Inmunoglobulinas, citadas como ejemplo de medicamento hemoderivado.",
        terminos=("inmunoglobulina", "inmunoglobulinas"),
        nota="La fuente usa 'medicamentos como'; la categoría completa requiere validación.",
    ),
    ReglaRestriccion(
        id="R21",
        descripcion="Factores de coagulación, citados como ejemplo de medicamento hemoderivado.",
        terminos=("factor de coagulacion", "factores de coagulacion"),
        nota="La fuente usa 'medicamentos como'; la categoría completa requiere validación.",
    ),
    ReglaRestriccion(
        id="R22",
        descripcion="Fibrinógeno humano, citado como ejemplo de medicamento hemoderivado.",
        terminos=("fibrinogeno humano",),
        nota="La fuente usa 'medicamentos como'; la categoría completa requiere validación.",
    ),
    ReglaRestriccion(
        id="R23",
        descripcion="Albúmina humana, citada como ejemplo de medicamento hemoderivado.",
        terminos=("albumina humana",),
        nota="La fuente usa 'medicamentos como'; la categoría completa requiere validación.",
    ),
)
