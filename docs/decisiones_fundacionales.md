# Decisiones fundacionales de Triage V2

Fecha: 2026-08-10
Estado: vigente para el arranque del MVP; sujeto a revisión mediante PR.

## Objetivo

Construir una aplicación sencilla y compartida para que cualquier integrante autorizado de Veracruzanísima pueda iniciar, continuar y terminar una cotización sin depender de una computadora específica ni de conocimientos técnicos avanzados.

## Alcance de esta base

Incluye únicamente:

- servicio web FastAPI;
- interfaz HTML inicial;
- configuración por entorno;
- pruebas automáticas;
- Dockerfile;
- integración continua;
- documentación de decisiones.

No incluye todavía:

- lectura documental con OpenAI;
- almacenamiento PostgreSQL/Supabase;
- autenticación;
- proveedores o scrapers;
- cálculos fiscales o comerciales;
- Excel o PDF final.

## Decisiones

### Python se conserva

Python sigue siendo el lenguaje principal porque concentra bien el procesamiento documental, automatización de proveedores, generación de archivos, análisis de datos y backend web.

### FastAPI sustituye a Streamlit en V2

Streamlit se conserva en V1. Para V2 se prefiere FastAPI con HTML renderizado porque el producto necesita persistencia multiusuario, estados durables, flujos que una persona inicia y otra continúa, y una separación clara entre interfaz y reglas.

### Interfaz deliberadamente sencilla

La información necesaria se muestra por defecto. Historial, fuentes, razonamientos y análisis avanzados se ofrecerán bajo vistas o botones secundarios para no saturar a usuarios con menor familiaridad tecnológica.

### Base de datos como fuente de verdad

Excel y PDF serán artefactos de salida. El historial operativo y comercial debe vivir en una base compartida. PostgreSQL es la opción prevista; la decisión de proveedor de infraestructura se validará antes de integrar datos reales.

### Lector documental intercambiable

OpenAI será el candidato principal para el primer lector documental. Se diseñará una interfaz que permita incorporar Gemini u otro proveedor en el futuro sin reescribir el flujo de negocio.

### Historial de precios inmutable

Un precio nuevo no sustituirá observaciones anteriores. Cada consulta relevante conservará fecha, producto, presentación, proveedor, precio, promoción y evidencia para permitir revalidación y análisis histórico.

### Duplicados y continuaciones

El sistema podrá detectar archivos idénticos y sugerir posibles reenvíos, fotografías del mismo memorándum o continuaciones. Una coincidencia probabilística nunca debe unir o excluir documentos automáticamente.

### Fiscal y sanitario separados

La categoría sanitaria y el tratamiento de IVA serán conceptos independientes. Las reglas fiscales no validadas no se declararán como definitivas en código.

## Riesgos conocidos

- aún faltan reglas empresariales y fiscales por validar;
- los scrapers B2B pueden requerir infraestructura distinta al servidor web;
- el histórico real contiene excepciones que seguirán apareciendo;
- la simplicidad de interfaz debe protegerse a medida que crezcan funciones.

## Pruebas esperadas para esta etapa

- `/health` responde correctamente;
- la portada carga como HTML;
- CI ejecuta pruebas y lint en cada PR.

## Reversión

Cerrar el PR sin fusionar elimina todo impacto sobre `main`. El repositorio V1 permanece intacto como respaldo y referencia.
