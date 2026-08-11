# Decisión 0002 — Persistencia compartida de cotizaciones

## Estado

Aceptada para el MVP.

## Contexto

El prototipo V1 utilizó estado de sesión y persistencia local. El flujo real requiere que una persona pueda iniciar una cotización y otra pueda retomarla desde otra sesión o equipo. Además, el histórico comercial y documental futuro debe sobrevivir al cierre del navegador y a los reinicios del servidor.

## Decisión

- SQLAlchemy 2.x será la capa de acceso relacional.
- Alembic versionará los cambios del esquema.
- PostgreSQL será la base de datos de producción.
- SQLite se permitirá únicamente para desarrollo local y pruebas automáticas.
- El código de dominio no dependerá directamente de Supabase, Render, Neon u otro proveedor de PostgreSQL.
- `DATABASE_URL` será la frontera de configuración entre la aplicación y el servicio de base de datos.
- Un despliegue con `APP_ENV=production` debe fallar si intenta usar SQLite.

## Motivos

1. El equipo necesita una fuente de verdad compartida.
2. PostgreSQL permite crecer hacia usuarios, documentos, auditoría, histórico de precios y concurrencia sin cambiar el modelo de persistencia.
3. Mantener una conexión SQL estándar reduce dependencia de un proveedor de nube concreto.
4. Alembic permite revisar, aplicar y revertir cambios de esquema de forma trazable.

## Alcance de esta etapa

La primera tabla sólo representa una cotización como unidad de trabajo con:

- identificador interno;
- referencia opcional;
- estado;
- fecha de creación;
- fecha de última modificación.

No se guardan todavía documentos, medicamentos, pacientes, precios, reglas fiscales ni información de proveedores.

## Criterios de aceptación

- crear una cotización desde la interfaz;
- verla en el listado después de guardarla;
- cambiar su estado manualmente;
- abrir una nueva instancia de la aplicación sobre la misma base y seguir viendo la cotización;
- poder construir el esquema desde cero mediante `alembic upgrade head`;
- CI valida estilo, migración y pruebas.

## Riesgos

- todavía no hay autenticación, por lo que no existe autoría individual de cambios;
- todavía no hay bloqueo optimista para dos personas editando simultáneamente la misma cotización;
- SQLite no reproduce todas las diferencias de PostgreSQL y sólo se usa como herramienta de desarrollo;
- el proveedor de PostgreSQL en nube aún está pendiente de selección/configuración operativa.

## Pruebas

Se cubren creación, listado, cambio de estado, reapertura con una segunda instancia y rechazo de SQLite en producción.

## Reversión

Antes del merge: cerrar el PR.

Después del merge: revertir el commit del PR y ejecutar el `downgrade` de Alembic sólo si la migración ya fue aplicada a una base no productiva. En producción cualquier reversión de esquema deberá respaldar primero la información.
