# ADR 0006 — Robustez de cola y exclusión reversible de partidas

## Estado

Propuesto para el MVP de preview.

## Contexto

Durante una lectura real del preview, Render devolvió temporalmente un `502 Bad Gateway`. La cola actual procesa archivos secuencialmente, pero ante una falla de red marca el elemento como error y continúa con todos los siguientes. En una carga de 20–30 archivos, una interrupción breve podría producir numerosos errores que no representan fallos reales de los documentos.

También se confirmó que una partida puede ser correctamente extraída y, después de revisión humana, decidirse que no debe formar parte de la cotización. Borrarla sería incorrecto porque el producto sí fue solicitado.

## Decisión

### 1. Reintentos idempotentes de la cola

Cada elemento agregado a la cola recibe en el navegador una `clave_idempotencia` aleatoria. La misma clave se reutiliza durante los reintentos del mismo archivo.

El servidor conserva esa clave junto al documento y aplica unicidad dentro de cada cotización. Si vuelve a recibir la misma clave y el mismo contenido:

- reutiliza el documento ya creado;
- si ya terminó el análisis, devuelve el resultado existente;
- si quedó únicamente como `RECIBIDO`, vuelve a intentar el procesamiento usando los bytes enviados en el reintento;
- no crea una segunda tarjeta documental.

Si una clave se intenta reutilizar para contenido distinto, la petición se rechaza.

### 2. Pausa ante indisponibilidad temporal

La interfaz considera transitorios `502`, `503`, `504` y fallos de comunicación.

Para el mismo elemento realiza hasta tres intentos con esperas progresivas. Si el servicio sigue sin responder:

- el elemento queda `Pausado`;
- se detiene el procesamiento de la cola;
- los documentos ya terminados permanecen `Listo`;
- los siguientes permanecen pendientes;
- el usuario puede usar `Reintentar pendientes` cuando el servicio vuelva.

Una respuesta funcional del lector que indique error de documento no se trata como indisponibilidad de infraestructura y puede continuar con el siguiente archivo.

### 3. Exclusión reversible de una partida

`PartidaDocumento` conserva dos datos:

- `incluida_cotizacion`: si la partida debe continuar hacia la cotización;
- `motivo_exclusion`: motivo visible de la decisión, cuando corresponda.

Una alerta de posible restricción no excluye automáticamente nada. El revisor puede pulsar `Excluir de cotización`, confirmar la acción y guardar la revisión. La partida:

- sigue existiendo como parte de la solicitud original;
- se muestra compacta como excluida;
- puede reintegrarse;
- no debe formar parte de la futura salida de cotización mientras siga excluida.

La revisión del documento continúa registrando quién aprobó la versión completa. No se introduce por ahora una bitácora separada por cada cambio de inclusión.

## Códigos de política en la interfaz

Identificadores como `POL-COM-001 · R16 · 0.1-provisional` sirven para trazabilidad técnica. La pantalla normal muestra el motivo y deja el código dentro de `Ver detalle de la regla` para no saturar al usuario.

## Garantías y límites

La clave de idempotencia evita duplicar el registro documental cuando el navegador reintenta la misma operación.

No se garantiza ejecución exactamente una vez del proveedor externo en todos los escenarios posibles de concurrencia o caída entre la respuesta de OpenAI y el commit local. Implementar esa garantía requeriría una arquitectura de trabajos durables/cola externa que no se justifica todavía para el MVP.

La cola actual vive en la pestaña del navegador. Si el usuario recarga o cierra la página antes de terminar, el navegador no puede conservar automáticamente los archivos locales seleccionados. Una bandeja durable de cargas sería una etapa posterior.

## Criterios de aceptación

- reintentar el mismo elemento no crea un segundo documento;
- una clave no puede identificar dos contenidos distintos;
- fallas `502/503/504` o de red reintentan el mismo elemento;
- después de agotar reintentos, la cola se pausa y no convierte los elementos restantes en errores;
- una partida restringida puede excluirse sin borrarse;
- la exclusión persiste tras guardar y recargar;
- la partida puede reintegrarse;
- una partida excluida mantiene su información original y motivo;
- migraciones y pruebas automáticas pasan en CI.

## Riesgos

- un reinicio en un punto muy específico podría ocasionar una segunda llamada al proveedor externo aunque el registro documental no se duplique;
- las claves viven asociadas al elemento de la cola del navegador y no son identificadores de negocio;
- si se elimina mediante la función explícita de eliminar documento, también desaparecen sus partidas y decisiones, coherente con el caso de un archivo subido por error;
- el futuro generador de Excel/PDF deberá filtrar explícitamente `incluida_cotizacion = true`.

## Reversión

Revertir el PR asociado.

La migración `20260812_0004` puede bajarse a `20260811_0003`, pero elimina las claves de idempotencia y las decisiones de inclusión/exclusión ya guardadas. En una base compartida con datos operativos debe realizarse respaldo antes del downgrade.
