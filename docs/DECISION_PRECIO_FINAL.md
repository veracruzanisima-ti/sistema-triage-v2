# Precio final de venta manual · decisión provisional

## Objetivo

Permitir que el prototipo genere importes finales sin inventar una regla de margen o utilidad.

## Alcance

- Precio unitario final sin IVA capturado por una persona por partida.
- Fuente o criterio comercial obligatorio.
- Usuario, fecha y observación conservados como trazabilidad.
- Eventos append-only: retirar un precio no borra el anterior.
- La decisión queda ligada a la identidad exacta normalizada del producto.
- El cálculo fiscal final usa únicamente el tratamiento fiscal ya validado.
- DIF se bloquea mientras falte precio final o validación fiscal en una partida cotizable.

## Fuera de alcance

- Porcentajes automáticos de utilidad o margen.
- Heredar reglas del V1.
- Inferir precio final desde la referencia estable.
- Convertir evidencia de proveedor en una autorización comercial.

## Criterios de aceptación

- Un precio cero o negativo se rechaza.
- Una captura sin fuente o criterio comercial se rechaza.
- `NO_SE_COTIZA` no admite una nueva captura de precio final.
- Cambiar la identidad normalizada invalida el precio vigente sin borrar su historial.
- Retirar el precio agrega un evento `PENDIENTE`.
- El DIF usa el precio final validado, no la referencia de compra.
- El exportador conserva `NO SE COTIZA` con `—` en importes.

## Riesgos

- La autorización comercial sigue siendo humana; el sistema sólo conserva la decisión.
- Si Dirección define más adelante una regla de margen, deberá versionarse y no reescribir cotizaciones históricas.
- La matriz fiscal productiva sigue requiriendo validación de Contabilidad.

## Pruebas

- Servicio append-only y reversión.
- Validación de precio y fuente.
- Invalidación por cambio de identidad.
- Bloqueo cuando la partida es `NO_SE_COTIZA`.
- DIF bloqueado sin precio final.
- DIF calculado desde un precio final deliberadamente distinto a la referencia estable.
- Migración 0017 de ida y vuelta mediante CI.

## Reversión

1. Revertir el PR elimina rutas, UI y cálculo final.
2. Downgrade de Alembic 0017 elimina `precios_finales_venta_partida`.
3. Las tablas y decisiones anteriores del sistema no se modifican.
4. El DIF vuelve al estado previo de borrador no emitible basado en referencia provisional.
