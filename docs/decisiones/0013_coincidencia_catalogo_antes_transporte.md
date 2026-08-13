# ADR 0013 — Coincidencia de catálogo antes del transporte real

## Estado
Aceptada para preparar la primera integración B2B.

## Objetivo
Separar la validación de identidad de producto del navegador, autenticación y extracción de un portal externo.

## Decisión
- La coincidencia trabaja únicamente con la identidad preparada por una persona.
- Una marca explícita se usa como término preferente de búsqueda y debe aparecer en el candidato.
- Una forma o dispositivo explícito debe coincidir; no se considera equivalente otro dispositivo.
- Masa, volumen y unidades simples se convierten a bases comparables para detectar diferencias visibles de concentración o presentación.
- Precio no positivo y stock cero descartan una tarjeta.
- No se conserva la sustitución fonética `Y -> I` del código legado porque puede crear falsos positivos.
- Si dos candidatos obtienen el mismo mejor puntaje, el motor no elige uno arbitrariamente.
- `precio_observado` no se etiqueta todavía como precio antes de IVA ni precio total. Esa semántica debe validarse contra el portal real antes de persistirla fiscalmente.
- Este PR no instala Playwright, no inicia sesión y no incluye credenciales.

## Alcance
Motor puro de coincidencia y pruebas. El transporte del primer proveedor se conectará después mediante el contrato neutral ya existente.

## Criterios de aceptación
- 1 L y 1000 mL se consideran la misma medida;
- una presentación de 10 mL no coincide con 3 mL;
- una forma/dispositivo explícita distinta se rechaza;
- la marca explícita tiene prioridad como término de búsqueda;
- un empate no se resuelve automáticamente;
- el cambio no requiere migración ni afecta Render.

## Riesgos
- El texto real del catálogo puede omitir datos que el documento sí especifica; en ese caso el comportamiento conservador puede producir falsos negativos, preferibles inicialmente a cotizar una presentación incorrecta.
- Las reglas se ajustarán con evidencia real del portal, no con supuestos.

## Pruebas
Pruebas unitarias con candidatos ficticios; no se contacta ningún proveedor externo.

## Reversión
Revertir el PR. No existen cambios de base de datos ni secretos asociados.
