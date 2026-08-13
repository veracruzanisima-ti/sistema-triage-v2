# ADR 0011 — Histórico de precios append-only

## Estado
Aceptada como base del producto final.

## Objetivo
Conservar observaciones de precio reutilizables sin convertir una captura histórica en una decisión comercial automática.

## Decisión
- Cada precio observado crea una fila nueva en `observaciones_precio`.
- No existen rutas de edición ni eliminación de observaciones en esta etapa.
- La observación guarda una fotografía de la identidad preparada del producto: producto, marca, concentración, forma/dispositivo y presentación.
- Una clave SHA-256 determinista permite recuperar histórico sólo para la misma identidad exacta preparada; no resuelve equivalencias semánticas.
- El vínculo a la normalización origen es opcional y usa `ON DELETE SET NULL`; la observación conserva su fotografía aunque la solicitud que la originó cambie o sea retirada.
- Se guarda proveedor, precio antes de IVA, IVA observado, precio total, promoción, condiciones, disponibilidad, viabilidad de entrega, fuente, fecha y usuario capturante.
- Se requiere al menos precio antes de IVA o precio total.
- Triage no infiere IVA cuando la fuente no lo muestra.
- La clasificación `referencia estable` / `oportunidad de adquisición` no forma parte de la observación histórica; se decidirá en una capa posterior con contexto de la cotización.

## Alcance
Incluye persistencia, consulta por producto exacto y captura manual. No incluye búsqueda automática, scrapers, selección de proveedor, cálculo de precio de venta, importación masiva ni clasificación comercial.

## Criterios de aceptación
- dos capturas del mismo producto producen dos observaciones diferentes;
- una captura nueva no modifica la anterior;
- sólo productos preparados de partidas revisadas e incluidas aceptan observaciones;
- una observación puede registrar sólo precio total sin inventar base o IVA;
- promoción y entrega permanecen como hechos observados, no decisiones de compra;
- migración `20260813_0007` aplica y revierte en la cadena Alembic.

## Riesgos
- si una preparación cambia de identidad, el nuevo producto ya no recuperará automáticamente observaciones con la clave anterior; esto es preferible a mezclar presentaciones distintas;
- la captura manual puede contener errores humanos y deberá contrastarse con evidencia;
- una promoción histórica no demuestra que siga vigente;
- la fuente se conserva como texto en esta etapa, no como evidencia binaria permanente.

## Pruebas
Regresiones de elegibilidad, append-only, validación de precios, persistencia de promoción/entrega y ausencia de inferencia fiscal o clasificación comercial.

## Reversión
Respaldar la base si el histórico ya contiene observaciones. Revertir el PR y bajar `20260813_0007` a `20260812_0006`; el downgrade elimina sólo `observaciones_precio`.
