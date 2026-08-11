# Preview de Triage V2 en Render

## Objetivo

Publicar una URL temporal para probar la experiencia de uso de Triage V2 desde distintos navegadores y equipos antes de conectar documentos, proveedores o información real.

## Regla de seguridad

**Este preview sólo admite datos ficticios o de prueba.**

El plan gratuito de Render es útil para validar el producto, pero su base PostgreSQL temporal no ofrece las garantías de respaldo y permanencia que necesitaremos para operación empresarial. La transición a un entorno con respaldo será una decisión separada antes de usar datos reales.

## Infraestructura

El archivo `render.yaml` define:

- un servicio web FastAPI;
- una base PostgreSQL temporal;
- conexión privada entre ambos;
- generación automática de la clave usada para firmar sesiones;
- solicitud interactiva de los datos del primer administrador durante la creación del Blueprint;
- health check en `/health`;
- despliegue automático únicamente cuando las comprobaciones de GitHub pasan.

## Migraciones

El preview ejecuta `alembic upgrade head` antes de iniciar Uvicorn.

Esto es deliberadamente una solución de **preview de una sola instancia**. En producción las migraciones deberán ejecutarse como una etapa de despliegue separada para evitar carreras entre instancias.

## Primera publicación

1. Entrar al panel de Render.
2. Elegir `New` y después `Blueprint`.
3. Conectar el repositorio privado `veracruzanisima-ti/sistema-triage-v2`.
4. Mantener `render.yaml` como archivo Blueprint.
5. Revisar los dos recursos que Render propone crear.
6. Completar los tres valores solicitados para la cuenta administrativa inicial.
7. Desplegar el Blueprint.
8. Esperar a que la base y el servicio web terminen de aprovisionarse.
9. Abrir la URL `onrender.com` creada por Render y comprobar el acceso.

## Prueba inicial esperada

Con información ficticia:

1. iniciar sesión;
2. crear una cotización de prueba;
3. cerrar sesión;
4. volver a entrar;
5. comprobar que la cotización continúa en el listado;
6. abrirla y cambiar su estado;
7. repetir desde otro navegador o equipo.

## Limitaciones aceptadas del preview

- puede existir demora al abrir la aplicación después de un periodo sin uso;
- la base gratuita es temporal;
- no existe garantía de respaldo;
- todavía no hay recuperación de contraseña;
- todavía no hay gestión visual de usuarios;
- no deben cargarse documentos ni datos sensibles reales.

## Reversión

El código puede revertirse cerrando o revirtiendo el PR de despliegue. Los recursos creados en Render se eliminan por separado desde el panel; quitar `render.yaml` del repositorio no destruye automáticamente recursos existentes.
