# ADR 0009: separar solicitud revisada de la preparación para búsqueda

## Estado
Aceptada para el MVP.

## Objetivo
Preparar cada partida para histórico de precios y proveedores sin alterar lo que realmente solicitó el documento ni introducir equivalencias no confirmadas.

## Decisión
La solicitud revisada permanece en `partidas_documento`. Se crea una relación uno a uno opcional en `normalizaciones_partida` con una copia operativa confirmada por una persona.

Sólo son normalizables las partidas que cumplen simultáneamente:

- pertenecen a un documento con estado `REVISADO`;
- siguen incluidas en la cotización.

La propuesta inicial copia los campos revisados y aplica únicamente limpieza tipográfica inequívoca, como espacios redundantes y escritura de `mL`. No infiere marcas, dispositivos, liberación, presentaciones equivalentes ni sustituciones terapéuticas.

## Regla operativa
`solicitud revisada != datos para buscar`.

Los campos de búsqueda pueden corregirse para encontrar el producto correcto, pero la evidencia de lo solicitado permanece intacta. Los proveedores e histórico deberán consumir la preparación confirmada, no modificar la extracción documental.

## Motivo
La coincidencia comercial exige distinguir variantes que pueden compartir nombre o principio activo. Un cambio automático de `vial` a `SoloStar`, de liberación inmediata a prolongada o de una presentación a otra podría generar una cotización incorrecta.

## Alcance de esta versión
- persistencia de una copia operativa por partida;
- pantalla de preparación en bloque;
- propuesta conservadora desde la revisión humana;
- contador de partidas preparadas;
- exclusión automática de partidas descartadas o documentos aún no revisados.

No incluye:

- catálogo maestro de productos;
- equivalencias entre marcas o genéricos;
- búsqueda en proveedores;
- histórico de precios;
- reglas fiscales;
- decisiones sanitarias adicionales.

## Riesgos
- si una revisión documental sustituye una partida, su normalización puede desaparecer por `ON DELETE CASCADE`; esto es intencional porque la evidencia cambió y debe prepararse nuevamente;
- la normalización manual puede contener errores humanos; antes de cotizar deberá seguir existiendo revisión final;
- dos textos equivalentes pueden permanecer distintos hasta que exista un catálogo o estrategia de matching explícita.

## Pruebas
- documentos sólo analizados no habilitan preparación;
- partidas excluidas no se preparan;
- guardar preparación no modifica la solicitud revisada;
- la propuesta no cambia dispositivo ni inventa marca;
- la migración debe aplicar y revertir dentro de la cadena Alembic.

## Reversión
Revertir el PR y bajar `20260812_0006` a `20260812_0005`. El downgrade elimina únicamente `normalizaciones_partida`; no elimina documentos, partidas revisadas ni cotizaciones.
