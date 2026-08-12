# ADR 0007 — Migraciones de Render fuera del arranque de instancia

## Estado

Adoptado para el preview gratuito.

## Contexto

El preview ejecutaba `alembic upgrade head` dentro de `scripts/iniciar_preview_render.sh` antes de arrancar Uvicorn.

Durante el despliegue de la migración `20260812_0004`, PostgreSQL quedó actualizado a esa revisión mientras Render todavía podía mantener o reiniciar una instancia de la revisión anterior. Esa instancia anterior no conocía `20260812_0004`; al ejecutar Alembic durante su propio arranque falló con `Can't locate revision identified by '20260812_0004'` y nunca alcanzó a iniciar el servidor web.

Render realiza despliegues sin downtime levantando la versión nueva antes de retirar la anterior. Por ello, el arranque de cada instancia no debe utilizarse como una fase de migración compartida.

## Decisión

Para el servicio Free de preview:

- `scripts/construir_preview_render.sh` instala el proyecto y ejecuta `alembic upgrade head`;
- `scripts/iniciar_preview_render.sh` únicamente arranca Uvicorn;
- `render.yaml` usa esos scripts como `buildCommand` y `startCommand` respectivamente;
- las migraciones del preview deben ser compatibles hacia atrás con al menos la revisión inmediatamente anterior mientras Render completa el cambio de instancia.

En un entorno de producción con una instancia de pago se prefiere un `preDeployCommand` dedicado para migraciones y un procedimiento explícito de respaldo/reversión.

## Consecuencias

### Positivas

- un reinicio o despertar de una instancia no vuelve a ejecutar Alembic;
- una instancia anterior puede arrancar aunque la base ya incluya columnas aditivas de la revisión nueva;
- el servidor web queda separado de los cambios de esquema;
- el fallo de una instancia no crea un bucle de migraciones durante cada reinicio.

### Límites

- en el plan Free la migración sigue ocurriendo antes de confirmar que la nueva instancia está saludable;
- por eso las migraciones deben mantenerse aditivas y compatibles hacia atrás en este preview;
- cambios destructivos o incompatibles requieren un procedimiento de despliegue diferente y respaldo previo.

## Criterios de aceptación

- el start del preview no contiene `alembic upgrade`;
- el build del preview ejecuta `alembic upgrade head`;
- CI valida la sintaxis de ambos scripts y la cadena completa de migraciones;
- el deploy puede arrancar cuando PostgreSQL ya está en `20260812_0004`.

## Reversión

Revertir el cambio de configuración y scripts. No se requiere downgrade de base de datos porque este ADR no modifica el esquema.
