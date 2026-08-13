# ADR 0012 — Consulta neutral y trazable de proveedores

## Estado
Aceptada como base para integrar NADRO, FESA y otros canales.

## Objetivo
Permitir consultas de precio y disponibilidad actuales sin acoplar la aplicación a un scraper concreto ni convertir una coincidencia externa en una decisión automática de compra.

## Decisión
- Los proveedores implementan un contrato neutral `ProveedorProducto`.
- La solicitud usa exclusivamente la identidad de producto ya preparada por una persona.
- Cada intento crea una fila en `consultas_proveedor`, incluso cuando termina en no encontrado o error.
- Una consulta exitosa crea además una nueva `ObservacionPrecio`; nunca modifica observaciones previas.
- Triage no compara ni declara un ganador en esta capa.
- Los errores persistidos son mensajes sanitizados; no se almacenan excepciones crudas que puedan contener secretos o datos internos del portal.
- Los adaptadores se inyectan en la aplicación. Un entorno sin adaptadores sigue funcionando y permite captura manual en el histórico.
- Playwright, credenciales y particularidades de NADRO/FESA quedan fuera de este PR.

## Alcance
Incluye contrato, trazabilidad persistente, orquestación síncrona MVP, interfaz web y pruebas con proveedores falsos. No incluye automatización real de portales, ejecución en segundo plano, selección de proveedor ni cálculo de precio de venta.

## Criterios de aceptación
- sólo una partida revisada, incluida y preparada puede consultarse;
- cada intento conserva proveedor, criterios, estado y hora;
- una coincidencia válida genera exactamente una observación histórica nueva;
- un no encontrado no genera precio histórico;
- un error queda registrado sin guardar el texto crudo de la excepción;
- un entorno sin proveedores automáticos mantiene operativo el resto de Triage;
- migración `20260813_0008` aplica y revierte después de `20260813_0007`.

## Riesgos
- la consulta es síncrona; un proveedor lento puede ocupar una petición web y deberá migrarse a trabajo asíncrono si el tiempo real lo exige;
- un adaptador defectuoso puede reportar una coincidencia incorrecta, por lo que la observación sigue siendo evidencia a revisar y no una decisión;
- una consulta que quede `INICIADA` después de una caída indica un intento interrumpido y no debe interpretarse como disponibilidad.

## Pruebas
Proveedor falso exitoso, no encontrado y con error; vínculo a histórico; validación de elegibilidad y ausencia de filtrado de excepciones crudas.

## Reversión
Revertir el PR y bajar `20260813_0008` a `20260813_0007`. El downgrade elimina sólo la trazabilidad de consultas; las observaciones históricas ya creadas permanecen.
