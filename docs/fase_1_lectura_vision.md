# Fase 1: lectura estructurada de imágenes

El lector OpenAI usa Responses API con Vision (`input_image`, detalle alto),
`store=False` y `text_format=LecturaDocumento`. PDF mantiene `input_file`.
El prompt versionado completo está en `src/triage/lectores/instrucciones.py`.
Se envía como instrucciones de la petición, separado del documento.

Gemini comparte el mismo esquema y prompt mediante `system_instruction` y
`response_schema`. También valida archivos y maneja rechazos, límites de tokens y
JSON inválido con errores controlados. Para usarlo mientras OpenAI está pausado,
configura `GEMINI_API_KEY` de forma segura y `GEMINI_MODEL_LECTOR` con un modelo
habilitado en tu cuenta. Si no hay clave OpenAI, Gemini se usa como lector disponible;
si hay ambas claves, selecciónalo en la pantalla existente de modelos IA.
No se comprueba aquí la disponibilidad real del modelo configurado.

## Evidencia y propuestas

Cada partida distingue:

- `texto_original`: texto visible del medicamento, excluyendo datos personales.
- `producto_solicitado`: nombre tal como aparece, compatible con la captura existente.
- `nombre_normalizado`: propuesta ortográfica inequívoca, sin sustituir la identidad.
- `sustancia_activa`: sólo lo explícitamente visible, sin deducir un genérico de una marca.
- Concentración, forma/dispositivo, presentación, cantidad y unidad: lo visible;
  datos ilegibles o ausentes son `null`. La cantidad no acepta fracciones, texto ni booleanos.
- `advertencias`: avisos informativos por documento y por partida.

La migración `20261006_0019` añade `documentos.extraccion_original` (JSON nullable).
Conserva la lectura automática completa incluso si después se corrige o excluye una
partida. Los documentos anteriores quedan con `null`; no se reinterpreta su evidencia.
El downgrade elimina esta evidencia nueva, pero conserva documentos y archivos originales.

El formulario Jinja existente muestra evidencia y avisos en un panel informativo,
sin requerir confirmaciones adicionales. La revisión, navegación y validaciones
de negocio existentes siguen vigentes. El nombre normalizado no reemplaza el original
ni se aplica automáticamente a la normalización posterior.

## Sugerencia comercial separada

`triage.lectores.catalogo.sugerir_desde_catalogo(partida, catalogo)` recibe entradas
`ProductoCatalogo` de una fuente proporcionada por el llamador y devuelve
`SugerenciaComercial` con fuente e identificador verificables.

Exige coincidencia de sustancia activa, concentración, forma/dispositivo y presentación;
sólo limpia espacios y mayúsculas/minúsculas. Si se solicitó una marca, también debe
coincidir. Datos incompletos o un catálogo vacío producen una lista vacía y no bloquean
la captura. No modifica la partida, infiere dosis, elige por popularidad, asigna precios
ni autoriza sustituciones clínicas. La fuente e identidad deben comprobarse en el catálogo.

Es una función de backend independiente: en esta fase no se conecta automáticamente
a NADRO/COFEPRIS, a la consulta de proveedores ni a nuevas pantallas. No se inventa
un catálogo comercial ni se añade una búsqueda externa durante la extracción.

## Errores y límites verificados

Archivos vacíos o formatos no admitidos fallan antes de consumir la API. Timeout
(80 segundos por petición, un reintento), errores del proveedor, rechazos, respuestas
incompletas o estructura inválida producen `ErrorLecturaDocumento` sin incluir contenido
ni credenciales en el mensaje. El flujo existente conserva el archivo original y permite
captura manual. Los logs del lector contienen sólo modelo y métricas de tokens.

Las pruebas usan respuestas de API, archivos y catálogo ficticios; no evalúan la precisión
real de OCR ni consumen OpenAI/Gemini. La validación Pydantic garantiza estructura,
pero no demuestra que una predicción coincida con la imagen: la evidencia y la revisión
humana siguen disponibles.

Validaciones: `ruff check .`, `pytest -q`, sintaxis de scripts de preview y migración
`upgrade → downgrade → upgrade` sobre SQLite aislado. PostgreSQL no se probó en esta fase.
`alembic check` detecta divergencias preexistentes en `main` (tabla de precios finales,
índices comerciales y unicidad del correo); la nueva columna no añade divergencias.
