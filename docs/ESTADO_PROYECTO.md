# Estado del proyecto · Sistema Triage V2

Última actualización: 2026-08-20 (America/Mexico_City).

## Fuente de verdad

- Repositorio: `veracruzanisima-ti/sistema-triage-v2`.
- Rama estable: `main`.
- Este documento resume el punto de reanudación; los PR e issues enlazados conservan el detalle y la evidencia.

## Último hito completado

PR #42, **“feat: integra identidad de medicamentos con COFEPRIS”**, fusionado en `main`.

- Commit de fusión: `7c3cfce61f8f99cd5fc37470fea2c34976e3cd7e`.
- El catálogo oficial se importa como snapshot local con bitácora, hash y reemplazo transaccional.
- COFEPRIS sólo resuelve identidad de forma conservadora; no relaja marca, concentración, forma, presentación ni la señal `coincidencia_exacta`.
- Las filas oficiales imperfectas y los números de registro repetidos se conservan por trazabilidad, pero no permiten resolver identidades ambiguas o incompletas.
- Validación del archivo oficial: 14,858 registros totales, 10,032 vigentes, 812 sin identidad útil y 1 número de registro repetido.
- GitHub Actions validó estilo, migraciones y 158 pruebas.
- No se incorporó el XLSX oficial al repositorio.

## Siguiente objetivo

Issue #43, **“Cotización DIF: partidas NO SE COTIZA y desglose de importes”**.

Orden de implementación acordado:

1. Modelar el estado comercial `COTIZABLE` / `NO_SE_COTIZA` sin eliminar partidas.
2. Conservar motivo, evidencia, regla o fuente, responsable de validación y fecha cuando aplique.
3. Separar reglas fiscales versionadas de los cálculos y exigir validación explícita de Contabilidad.
4. Calcular precio unitario sin IVA, subtotal, IVA y total únicamente con reglas válidas.
5. Impedir que una cotización fiscalmente pendiente se considere emitible.
6. Crear el exportador DIF v1 sobre el modelo interno.
7. Agregar futuros formatos como exportadores independientes, sin modificar el núcleo.

## Decisiones confirmadas

- Una partida que Veracruzanísima no pueda comercializar permanece en la cotización y en el Excel con el resultado `NO SE COTIZA`.
- En la salida DIF, una partida no cotizable muestra `—` en precio unitario sin IVA, subtotal, IVA y total, y muestra claramente `NO SE COTIZA`.
- COFEPRIS no decide qué controlados puede comercializar la empresa.
- La IA no inventa tasas, tratamientos fiscales ni restricciones sanitarias o comerciales.
- Se implementa primero DIF con un núcleo desacoplado; no se construye todavía un diseñador universal de formatos.

## Validaciones externas pendientes

- Responsable Sanitario: regla empresarial sobre productos controlados o restringidos que Veracruzanísima no puede comercializar.
- Contabilidad: matriz de tasas y tratamientos fiscales productivos, con versión y vigencia.

Hasta contar con esas validaciones, el sistema puede modelar estados pendientes y captura manual trazable, pero no debe convertir supuestos en reglas productivas.

## Protocolo para reanudar

1. Leer `AGENTS.md`, este documento y `README.md`.
2. Verificar `main`, PR abiertos, issues y GitHub Actions.
3. Confirmar que el estado documentado coincide con GitHub.
4. Continuar el siguiente objetivo sin usar automáticamente artefactos del V1.
5. Actualizar este archivo cuando se fusione el siguiente hito o cambie la decisión.

Prompt mínimo recomendado:

> Retoma Sistema Triage V2 desde GitHub. Usa `veracruzanisima-ti/sistema-triage-v2` como fuente de verdad; lee `AGENTS.md` y `docs/ESTADO_PROYECTO.md`, verifica `main`, PR, issues y CI antes de cambiar código. Continúa el siguiente objetivo documentado con hechos vs. supuestos, seguridad, trazabilidad, pruebas, reversión y simplicidad. No uses el V1 ni archivos antiguos salvo instrucción explícita.
