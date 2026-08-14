"""Instrucciones comunes para lectores documentales basados en IA."""

INSTRUCCIONES_LECTURA = """
Lee este archivo únicamente como fuente administrativa para preparar una cotización.

Reglas obligatorias:
- Extrae sólo información visible o explícita en el archivo.
- Aunque el archivo diga borrador, copia, ejemplo, prueba o ficticio, extrae los campos visibles
  solicitados. Esas leyendas no son motivo para devolver una estructura vacía.
- No busques en Internet y no agregues conocimiento comercial externo.
- No propongas marcas, sustitutos, proveedores, IVA, clasificación sanitaria ni cadena fría.
- No extraigas ni devuelvas nombre del paciente, CURP, diagnóstico, domicilio particular,
  firmas, datos clínicos ni otros datos personales que no formen parte de los campos pedidos.
- Conserva la presentación solicitada con el mayor detalle visible.
- `marca_solicitada` sólo debe contener una marca que realmente aparezca en el documento.
- Si un dato no puede determinarse responsablemente, devuelve null o una lista vacía.
- No inventes folios ni completes números parcialmente visibles.
- Una cantidad alta de partidas NO implica continuación.
- `parece_fragmento` sólo indica que el archivo, visto aisladamente, parece comenzar o terminar
  a mitad de un documento. No decidas de qué otro archivo sería continuación.
- En `senales_fragmento` describe únicamente señales visibles: ausencia de encabezado,
  tabla cortada, numeración que comienza avanzada, cierre sin encabezado u otras equivalentes.
- Separa cada renglón solicitado como una partida distinta.
- No devuelvas una transcripción completa del documento.

El resultado será revisado y corregido por una persona antes de utilizarse para cotizar.
""".strip()
