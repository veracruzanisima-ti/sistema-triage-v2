# Decisión 0003 — Acceso interno antes del despliegue público

## Estado

Aceptada para el MVP.

## Contexto

Triage será una aplicación de uso interno accesible desde Internet. Aunque todavía no procesa documentos reales, publicar el servicio sin control de acceso facilitaría que datos empresariales se expongan por error durante las pruebas.

## Decisión

- No habrá registro público de cuentas.
- Las contraseñas se almacenarán únicamente como hashes Argon2.
- La identidad del navegador se mantendrá mediante una sesión firmada.
- La cookie de sesión será `HttpOnly`, `SameSite=Lax` y `Secure` en producción.
- Los formularios que cambian información requerirán un token CSRF ligado a la sesión.
- Una base nueva podrá crear una única cuenta administrativa inicial mediante configuración segura del entorno.
- Una vez creada esa cuenta, el proceso de arranque no reemplazará contraseñas ni creará usuarios adicionales.
- La administración normal de integrantes se implementará después dentro de la aplicación.

## Motivos

1. Impedir que la futura URL de Triage quede abierta a personas externas.
2. Mantener una experiencia de acceso convencional para personas con distintos niveles de experiencia tecnológica.
3. Evitar depender todavía de un proveedor externo de identidad.
4. Conservar una ruta futura hacia SSO u otro proveedor sin mezclar autenticación con la lógica de cotización.

## Alcance

Esta etapa incluye acceso, cierre de sesión, protección CSRF y cuenta administrativa inicial.

No incluye recuperación de contraseña, MFA, SSO, roles complejos, administración visual de usuarios ni auditoría por usuario de cada campo modificado.

## Criterios de aceptación

- una persona sin sesión no puede abrir las cotizaciones;
- una cuenta válida puede iniciar sesión;
- un error de acceso no revela si falló el correo o la contraseña;
- cerrar sesión vuelve a bloquear las rutas internas;
- formularios sin token CSRF válido se rechazan;
- producción exige una clave de sesión propia;
- las migraciones crean la tabla de usuarios de forma reproducible.

## Riesgos

- todavía no existe recuperación de acceso;
- la cuenta inicial requiere un procedimiento operativo cuidadoso durante el primer despliegue;
- una sesión firmada puede revocarse únicamente desactivando al usuario o esperando su expiración;
- antes de usar información real deben completarse el despliegue HTTPS y las pruebas de seguridad básicas.

## Reversión

Antes del merge: cerrar el Pull Request.

Después del merge: revertir el cambio de aplicación. La eliminación de la tabla de usuarios sólo debe hacerse con respaldo y mediante la migración de reversión correspondiente.
