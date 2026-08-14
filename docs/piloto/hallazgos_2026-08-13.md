# Hallazgos de prueba manual del piloto - 13 de agosto de 2026

Este documento complementa `docs/continuidad_operativa.md` y deja evidencia de la prueba manual realizada por Raúl para que un chat o PR posterior pueda retomar el trabajo sin reconstruir la sesión.

## Estado al iniciar la prueba

`main` ya incluía los PR #23 a #28 con CI verde: flujo operativo simplificado, selección de referencia estable desde Buscar precios, CP contextual, búsqueda unificada, descubrimiento web opcional y reutilización diaria de precios.

El objetivo de la sesión era realizar una cotización ficticia de principio a fin antes de cerrar formalmente `v0.1-piloto-interno`.

## Incidente de acceso al preview

El dominio `sistema-triage-v2-preview.onrender.com` mostró primero Cloudflare 525 y después 520 desde el Wi-Fi del equipo.

Evidencia observada:

- Render mostraba el servicio `Live`.
- Los logs internos repetían `GET /health ... 200 OK`.
- Un restart de la instancia terminó correctamente y la app siguió sana.
- `/health` funcionó desde datos móviles.
- La misma computadora funcionó al conectarse al hotspot del celular.
- En el Wi-Fi habitual siguió fallando hasta cambiar DNS IPv4 del equipo a `1.1.1.1` y `1.0.0.1`.
- Después del cambio DNS, el preview funcionó normalmente.

Conclusión operativa: el incidente no fue una regresión de Triage ni de Render; fue un problema de resolución/ruta DNS de la red local. Ante un caso similar, comprobar primero `/health` por otra red antes de cambiar código o base de datos.

## Documentos ficticios utilizados

Se generaron dos solicitudes ficticias para cubrir varios casos con pocos archivos:

1. solicitud estructurada con medicamentos normales, marca explícita, productos repetidos y reglas provisionales de restricción;
2. continuación tipo escaneo con numeración avanzada, más productos repetidos y señales de posible fragmento.

No contienen datos reales sensibles.

## Hallazgo 1 - regreso desde precio manual

### Problema observado

Desde `Buscar precios`, cuando no existen adaptadores automáticos configurados, la acción `Registrar precio manual` envía a `Histórico de precios`. Después de capturar la observación, el botón de regreso llevaba a la pantalla general de la cotización y se perdía el punto de trabajo anterior.

### Comportamiento aprobado

Si Histórico se abrió desde Buscar precios:

- conservar ese origen de forma explícita;
- después de guardar una observación seguir conservándolo;
- mostrar `Volver a buscar precios` y regresar a `/proveedores`;
- no aceptar URLs arbitrarias como destino de regreso.

Si Histórico se abre directamente desde análisis/trazabilidad, conserva el comportamiento normal de volver a la cotización.

### Implementación en curso

Rama: `agent/cerrar-hallazgos-piloto-ux-web`.

Se usa un valor interno permitido `volver=proveedores`; no se implementa un open redirect genérico.

## Hallazgo 2 - búsqueda web devuelve BadRequestError

### Problema observado

La acción `Buscar más opciones en web` mostró:

`La búsqueda web no pudo completarse (BadRequestError)`

La lectura documental con la misma infraestructura OpenAI sí funcionaba.

### Diagnóstico

El descubridor web estaba enviando directamente a Structured Outputs un modelo Pydantic de dominio con tipos/restricciones como `Decimal`, `HttpUrl`, `gt=0` y `max_length`. Esa complejidad no es necesaria en el contrato externo y aumenta el riesgo de producir JSON Schema incompatible con el subconjunto soportado por Structured Outputs.

### Cambio aplicado

- Mantener `CandidatoWeb` como modelo interno fuerte.
- Crear un DTO externo deliberadamente simple: strings, número opcional, booleanos y nullables.
- Limitar a máximo cinco candidatos en código local, no en el JSON Schema externo.
- Convertir y validar URL/precio después de recibir la respuesta.
- Conservar la segunda validación local de identidad de producto antes de persistir una observación.
- Si OpenAI vuelve a fallar, el usuario ve un mensaje accionable y genérico; los logs guardan únicamente tipo/status/code/param/request-id, sin API key ni datos personales.

Este cambio debe validarse primero con CI y después con una búsqueda web manual en preview.

## Hallazgo 3 - separación visual de partidas

### Problema observado

En la revisión de documentos con muchas partidas, la separación basada sólo en una línea horizontal era correcta pero costaba escanear visualmente dónde terminaba una partida y comenzaba la siguiente.

### Cambio aprobado

Las partidas normales detectadas reciben un contenedor muy sutil:

- fondo apenas contrastante;
- borde fino;
- barra lateral gris discreta;
- espacio entre partidas.

Las partidas con posible restricción y las excluidas mantienen sus tratamientos visuales especiales. No se introducen colores fuertes para cada renglón.

## Estado de cierre del piloto

Estos tres puntos se consideran hallazgos de UX/integración del piloto. No cambian reglas fiscales, sanitarias ni comerciales y no requieren migración de datos.

Antes de declarar cerrado formalmente el piloto:

1. CI de este bloque debe quedar verde;
2. desplegar el commit resultante en preview;
3. Raúl debe repetir sólo los tres checks manuales: regreso desde precio manual, una búsqueda web y legibilidad de varias partidas;
4. si pasan, continuar con el checklist de tag/release `v0.1-piloto-interno`.
