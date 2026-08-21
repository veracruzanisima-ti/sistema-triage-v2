# Instrucciones para agentes · Sistema Triage V2

## Fuente de verdad y alcance

- La única fuente de verdad del código es `veracruzanisima-ti/sistema-triage-v2`.
- No reutilices automáticamente el repositorio V1, scripts adjuntos antiguos ni archivos de otros chats.
- Antes de proponer o modificar código, revisa `README.md`, `docs/ESTADO_PROYECTO.md`, la rama `main`, los PR abiertos y los issues relacionados.
- Distingue en tus reportes hechos verificados, supuestos y decisiones pendientes de validación humana.

## Criterio técnico

- Prioriza seguridad, trazabilidad, pruebas, reversión y simplicidad.
- Prefiere cambios pequeños y explícitos; evita sobreingeniería, dependencias innecesarias y cambios silenciosos.
- Toda modificación de esquema debe usar Alembic con `upgrade` y `downgrade` verificables.
- No mezcles resultados distintos en un mismo PR cuando puedan revisarse y revertirse por separado.
- Ejecuta `ruff check .`, `pytest` y las validaciones de migraciones aplicables antes de considerar listo un PR.
- No guardes credenciales, archivos oficiales completos ni datos sensibles en GitHub.
- Mantén código, documentación operativa y mensajes para el equipo en español cuando sea razonable.

## Límites del dominio

- La IA propone; las decisiones sensibles deben quedar trazables y ser corregibles por una persona.
- COFEPRIS aporta evidencia de identidad sanitaria. No autoriza sustituciones clínicas, comerciales ni fiscales.
- No marques automáticamente una partida como `NO SE COTIZA` sólo por ser un producto controlado.
- Una restricción comercial debe conservar motivo, fuente o regla, responsable de validación y fecha cuando aplique.
- Las reglas fiscales deben estar separadas del cálculo, versionadas y validadas por Contabilidad.
- Una cotización con validación fiscal pendiente no debe considerarse emitible.
- Los exportadores por cliente, empezando por DIF, deben renderizar el modelo interno sin duplicar la lógica central.

## Continuidad

- Actualiza `docs/ESTADO_PROYECTO.md` cuando se fusione un hito o cambie el siguiente paso.
- Los PR e issues de GitHub conservan el detalle técnico y la discusión; el archivo de estado sólo resume lo necesario para reanudar.
- Al comenzar un chat nuevo, reconstruye primero el estado desde GitHub y no dependas de la memoria de conversaciones anteriores.

## Code Review Rules

- Señala cualquier ruta que permita que COFEPRIS o una IA eviten validaciones exactas ya existentes.
- Señala reglas fiscales, sanitarias o comerciales codificadas sin fuente, versión o validación humana explícita.
- Señala partidas eliminadas por no ser cotizables: deben permanecer visibles y trazables.
- Señala cálculos o exportadores que oculten estados pendientes o acoplen un formato de cliente al núcleo.
