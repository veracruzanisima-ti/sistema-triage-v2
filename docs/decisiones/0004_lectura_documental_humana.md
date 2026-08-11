# ADR 0004 — Lectura documental con revisión humana

## Estado

Propuesta implementada en rama; requiere CI y prueba de preview antes de considerarse aceptada.

## Objetivo

Permitir que una persona suba una fotografía o PDF, obtenga una extracción estructurada y corrija el resultado antes de que Triage utilice esos datos en etapas comerciales posteriores.

## Decisión

- OpenAI será el lector principal inicial mediante Responses API y salida estructurada.
- El lector está detrás del contrato `LectorDocumento`; la aplicación no depende directamente de un único proveedor.
- La lectura sólo extrae datos administrativos necesarios y partidas.
- No se extraen deliberadamente nombre del paciente, CURP, diagnóstico, domicilio particular, firmas ni otros datos clínicos que no sean necesarios para cotizar.
- La IA no busca precios, proveedores, IVA, clasificación sanitaria, sustitutos ni marcas no escritas en la fuente.
- La aplicación no decide que un archivo sea continuación de otro. Sólo puede indicar que, visto aisladamente, parece un fragmento y explicar señales visibles.
- La relación entre archivos será una decisión humana en una etapa posterior.
- En este hito el archivo original se procesa en memoria y no se conserva en PostgreSQL ni en el repositorio. Sólo se guardan metadatos, SHA-256 y la extracción revisable.
- `store=False` se usa en la petición de Responses API, pero esto no sustituye una validación empresarial de privacidad y retención antes de procesar documentación sensible real.

## Alcance

1. Subir un archivo PDF, JPG, PNG o WEBP.
2. Limitar tamaño de entrada.
3. Calcular SHA-256.
4. Interpretar el archivo mediante un lector inyectable.
5. Guardar metadatos y partidas extraídas.
6. Mostrar una pantalla de revisión editable.
7. Permitir corregir datos administrativos y partidas.
8. Guardar qué usuario realizó la revisión.

## Fuera de alcance

- almacenamiento permanente del archivo original;
- asociación de continuaciones;
- deduplicación visual;
- normalización comercial;
- búsqueda de proveedores;
- histórico de precios;
- IVA, margen o cálculos de cotización;
- Excel o PDF final;
- procesamiento asíncrono de grandes lotes.

## Criterios de aceptación

- un archivo permitido puede subirse desde una cotización;
- CI no realiza llamadas reales a OpenAI;
- la lectura produce campos estructurados y partidas;
- una persona puede corregir lo leído y guardar la revisión;
- el archivo original no queda escrito en GitHub ni en la base;
- un formato no permitido se rechaza antes de llamar al lector;
- un fallo del lector queda registrado como error controlado;
- ninguna sugerencia de fragmento une documentos automáticamente;
- la migración Alembic crea y revierte las tablas documentales;
- todas las pruebas existentes continúan pasando.

## Riesgos

- la calidad del lector debe medirse con casos reales anonimizados o autorizados;
- una petición de lectura puede tardar varios segundos;
- el preview gratuito no es un entorno autorizado para documentos sensibles reales;
- sin almacenamiento de evidencia todavía no puede hacerse una comparación visual posterior desde Triage;
- la política empresarial de tratamiento de documentos y datos personales sigue pendiente de validación antes de producción.

## Pruebas

Las pruebas usan un lector falso determinista. Se valida carga, tipos permitidos, visualización de lectura, corrección humana y persistencia sin consumir API.

## Reversión

Antes del merge, cerrar el PR. Después del merge, revertir el commit del PR. Si la migración `20260811_0003` ya fue aplicada a una base compartida, respaldar la base antes de ejecutar un downgrade porque elimina documentos y partidas creados por esta versión.
