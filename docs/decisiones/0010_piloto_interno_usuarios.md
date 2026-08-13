# ADR 0010 — Gestión mínima de usuarios para piloto interno

## Estado
Aceptada para piloto interno.

## Objetivo
Permitir compartir Triage con integrantes de Veracruzanísima sin abrir registro público ni depender de cambios manuales en la base de datos.

## Decisión
- Sólo una cuenta administradora puede crear, activar, desactivar o restablecer contraseñas de otras cuentas.
- Las cuentas creadas desde la interfaz son operativas y no administradoras.
- No existe registro público.
- Cada persona puede cambiar su propia contraseña verificando primero la contraseña actual.
- Un administrador no puede desactivar su propia cuenta desde la interfaz.
- Una cuenta desactivada pierde acceso en la siguiente petición porque la sesión valida nuevamente que el usuario siga activo.
- Las contraseñas se reciben únicamente por formularios HTTPS y se almacenan como hash Argon2; no se muestran ni se registran después.
- La interfaz del piloto advierte que todavía no deben cargarse documentos sensibles reales.

## Alcance
Incluye administración mínima de cuentas, cambio de contraseña propio y onboarding del piloto. No incluye invitaciones por correo, recuperación automática, MFA, SSO, roles granulares ni auditoría avanzada de identidad.

## Criterios de aceptación
- un administrador puede crear una cuenta operativa;
- un usuario operativo recibe 403 al intentar administrar cuentas;
- un administrador no puede desactivarse a sí mismo;
- desactivar una cuenta invalida su acceso en la siguiente solicitud;
- cambiar contraseña exige conocer la actual;
- la lista de cotizaciones muestra guía y advertencia de entorno piloto;
- no hay cambios de esquema ni migraciones.

## Riesgos
- la contraseña temporal debe compartirse por un canal interno seguro;
- no se fuerza todavía el cambio de contraseña en el primer acceso;
- no existe recuperación automática si una persona olvida su contraseña; un administrador debe restablecerla;
- una cuenta administradora comprometida conserva capacidad de restablecer cuentas, por lo que no debe compartirse.

## Pruebas
Pruebas web de creación de cuentas, autorización administrativa, auto-desactivación, pérdida de acceso al desactivar, cambio de contraseña y presencia del onboarding.

## Reversión
Revertir el PR. No hay migraciones ni datos nuevos obligatorios; las cuentas creadas siguen siendo compatibles con el modelo de usuarios previo.
