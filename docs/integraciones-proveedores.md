# Integraciones de proveedores: NADRO y FESA

## Objetivo

Integrar precios de NADRO y FESA al flujo normal de `Buscar precios` sin guardar credenciales en el repositorio, sin convertir una fuente en decisión comercial automática y conservando trazabilidad de cada consulta.

## NADRO

NADRO debe integrarse mediante los archivos/medios EdiNadro autorizados por el proveedor. No se implementará scraping autenticado de `i22.nadro.mx` como mecanismo productivo.

### Formatos confirmados con documentación descargada de EdiNadro

`MATERIAL.DAT` y `PRECIO.DAT` usan registros de ancho fijo de 101 caracteres y comparten layout. Incluyen:

- movimiento (alta, baja o cambio según archivo);
- código NADRO;
- familia, departamento y categoría;
- vigencia;
- clave de refrigeración (`0` sin refrigeración, `1` con refrigeración);
- clave SSA reportada por NADRO;
- clasificación fiscal reportada por NADRO (`2` grava IVA, `4` exento);
- descripción y laboratorio;
- precio público sin IVA;
- precio farmacia sin IVA;
- fecha de último movimiento;
- código EAN.

La propia especificación indica que estos archivos muestran movimientos de los últimos 30 días naturales desde la descarga. Por ello **no constituyen por sí solos una base completa de catálogo**.

`OFERTA.DAT` usa registros de ancho fijo de 115 caracteres e incluye:

- código NADRO y EAN de unidad/subempaque/empaque;
- descripción;
- precio farmacia sin IVA;
- cantidad con cargo;
- descuentos de primera y segunda escala;
- cantidad sin cargo;
- umbrales de piezas para cada escala;
- descuento en factura.

Las ofertas deben mantenerse separadas del precio estable. Triage puede mostrarlas como evidencia/oportunidad potencial, pero no debe reemplazar automáticamente la referencia estable usada para cotizar.

### Base completa pendiente

El portal ofrece `AutoIICX.dat` como **ABC de materiales extendido**. Antes de activar NADRO como proveedor completo se requiere descargar:

1. el documento de **Formato** de `AutoIICX.dat`;
2. un archivo real `AutoIICX.dat`;
3. archivos reales `MATERIAL.DAT`, `PRECIO.DAT` y `OFERTA.DAT` para validar el parser contra datos de producción.

Con ello el flujo objetivo será:

1. cargar una base completa `AutoIICX.dat`;
2. aplicar altas/cambios/bajas de `MATERIAL.DAT`;
3. aplicar cambios vigentes de `PRECIO.DAT`;
4. asociar `OFERTA.DAT` por código NADRO/EAN sin mezclarla con el precio estable;
5. buscar la identidad preparada contra la instantánea local;
6. aplicar el matcher conservador antes de crear una observación de precio.

La clave de refrigeración y la clasificación fiscal se conservarán como hechos reportados por NADRO. No sustituyen reglas sanitarias, fiscales o comerciales definidas por la empresa.

La disponibilidad en tiempo real no aparece en los tres layouts recibidos; deberá resolverse mediante otra fuente autorizada de NADRO si se requiere para compra inmediata.

## FESA

FESA se integra como adaptador opt-in. Puede consultar el catálogo público y, si existen credenciales completas configuradas en el entorno, intenta autenticarse antes de buscar. Las credenciales se leen exclusivamente desde secretos/variables de entorno y nunca se persisten en GitHub ni en la base de datos de Triage.

La automatización autenticada debe permanecer sujeta a que:

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
