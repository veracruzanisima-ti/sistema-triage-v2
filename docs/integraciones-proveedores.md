# Integraciones de proveedores: NADRO y FESA

## Objetivo

Integrar precios de NADRO y FESA al flujo normal de `Buscar precios` sin guardar credenciales en el repositorio, sin convertir una fuente en decisión comercial automática y conservando trazabilidad de cada consulta.

## NADRO

NADRO debe integrarse mediante los archivos/medios EdiNadro autorizados por el proveedor. El portal publica materiales, cambios de precio, ofertas, facturación, volumetría y descontinuados con actualización diaria.

No se implementará scraping autenticado de `i22.nadro.mx` como mecanismo productivo. Para construir el importador hace falta un archivo real de ejemplo de los contenidos EdiNadro que usa Veracruzanísima, sin credenciales.

Flujo objetivo:

1. Descargar/sincronizar contenido EdiNadro por un medio permitido por NADRO.
2. Importar el catálogo/precios a una instantánea local trazable.
3. Buscar la identidad preparada contra esa instantánea.
4. Conservar precio, disponibilidad/oferta cuando estén presentes, fecha del archivo y fuente.
5. Aplicar el matcher conservador de Triage antes de crear una observación de precio.

## FESA

FESA se integrará como adaptador autenticado opt-in. Las credenciales se leerán exclusivamente desde secretos/variables de entorno y nunca se persistirán en GitHub ni en la base de datos de Triage.

La automatización debe permanecer deshabilitada hasta que:

- exista una cuenta autorizada para el uso operativo;
- la contraseña comprometida en el prototipo legado haya sido rotada;
- las credenciales nuevas estén configuradas en el entorno;
- se haya validado que el portal no requiere CAPTCHA/MFA no automatizable y que el uso está permitido para la cuenta.

Si aparece CAPTCHA o MFA, Triage no intentará evadirlo. Se requerirá renovación/asistencia humana de sesión o un mecanismo autorizado por FESA.

## Reglas comunes

- Un adaptador sólo devuelve hechos observados; no elige qué comprar ni qué cotizar.
- Los precios se validan con la identidad exacta preparada antes de guardarse.
- Un fallo de NADRO/FESA no debe impedir que otras fuentes continúen.
- Cada intento debe quedar en `consultas_proveedor`.
- Secretos y estados de autenticación nunca se versionan.
- Promoción no equivale automáticamente a oportunidad de compra.
