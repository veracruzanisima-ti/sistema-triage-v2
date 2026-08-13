# ADR 0014 — Decisiones de precio trazables

## Estado
Aceptada para separar evidencia de decisión comercial.

## Objetivo
Permitir que una persona elija qué observación usa como referencia estable y cuál considera oportunidad de adquisición, sin modificar el histórico.

## Decisión
- Las observaciones de precio siguen siendo append-only y no reciben un rol permanente.
- Seleccionar, cambiar o retirar una evidencia crea un evento nuevo en `decisiones_precio`.
- La interfaz considera vigente el último evento de cada rol para la identidad actual del producto.
- Si la normalización cambia, una decisión asociada a otra `clave_producto` no reaparece como vigente.
- Se permite usar la misma observación para ambos roles; la diferencia es el propósito de la decisión, no la fuente.
- Las promociones y una entrega registrada como no viable generan advertencias, no bloqueos automáticos.
- No se elige automáticamente el precio menor.

## Roles
- **Referencia estable:** evidencia elegida por una persona como base para construir la cotización.
- **Oportunidad de adquisición:** evidencia que puede ser útil al momento de surtir y debe revalidarse si depende de promoción, stock, condiciones o entrega.

## Criterios de aceptación
- cambiar una selección no borra la decisión anterior;
- retirar una selección crea otro evento y deja el rol sin evidencia vigente;
- no se puede seleccionar una observación de otra identidad de producto;
- cambiar la identidad preparada invalida visualmente decisiones anteriores;
- la migración `20260813_0009` aplica después de `0008`.

## Riesgos
La tabla crecerá con cada decisión, pero el volumen esperado del equipo pequeño es bajo y la trazabilidad compensa el costo. Si después se necesita auditoría formal, estos eventos ya ofrecen una base clara.

## Reversión
Revertir el PR y bajar `20260813_0009` a `20260813_0008`. El histórico de precios no se modifica.
