# Estado del proyecto · Sistema Triage V2

Última actualización: 2026-08-21 (America/Mexico_City).

## Fuente de verdad

- Repositorio: `veracruzanisima-ti/sistema-triage-v2`.
- Rama estable: `main`.
- Este documento resume el punto de reanudación; los PR e issues enlazados conservan el detalle y la evidencia.

## Último hito completado

PR #52, **“feat(dif): agrega exportador Excel v1 como borrador no emitible”**, fusionado en `main`.

- Commit de fusión: `d598f729b63a150e653c3cc7b636019253c34836`.
- El exportador DIF consume el modelo consolidado y no contiene reglas propias de margen ni fiscal.
- Conserva `NO SE COTIZA` con `—` en importes.
- Exige preparación completa, referencia estable y tratamiento fiscal validado antes de generar el archivo.
- Neutraliza texto que Excel podría interpretar como fórmula.
- Quedó deliberadamente como borrador mientras faltaba una decisión trazable de precio final de venta.
- GitHub Actions #136 aprobó estilo, migraciones y pruebas del exportador.

Hitos inmediatamente anteriores:

- PR #50, **“fix: acepta conteo exacto aunque la ficha omita Caja”**, fusionado en `main` con commit `0fc4854ae02962af254ba6d656c56e545d04129a`. Corrige falsos negativos como `Dapagliflozina 10 mg 28 Tabs` sin relajar concentración ni cantidad; GitHub Actions #137 quedó verde.
- PR #47, motor fiscal validable por capas, fusionado en `main` con commit base posterior `dbc1e29c719331acbd4f315ecb5c4c50fb6d5cec`. Separa sugerencia de validación humana, distingue tasa 0 de exención y conserva cálculos unitario s/IVA → subtotal → IVA → total.
- PR #45, estado comercial `COTIZABLE` / `NO_SE_COTIZA` append-only y reversible.

## Siguiente objetivo

Issue #51, **“Precio final de venta: validación comercial antes de emitir DIF”**.

La referencia estable sigue siendo evidencia de adquisición y no debe convertirse silenciosamente en precio de venta. V2 no contiene una regla aprobada de utilidad o margen y no se reutilizará ninguna regla del V1.

Ruta provisional segura para el prototipo:

1. Capturar manualmente por partida el **precio unitario final sin IVA**.
2. Exigir una fuente o criterio comercial explícito y conservar usuario y fecha.
3. Guardar decisiones como eventos append-only; retirar un precio agrega un evento pendiente en lugar de borrar historia.
4. Invalidar automáticamente la decisión vigente si cambia la identidad exacta normalizada del producto.
5. Aplicar el tratamiento fiscal ya validado sobre ese precio final para calcular subtotal, IVA y total.
6. Considerar emitible el DIF sólo cuando cada partida `COTIZABLE` tenga referencia estable, validación fiscal, precio final validado y cálculo final; `NO_SE_COTIZA` permanece con `—`.
7. Mantener fuera de alcance cualquier porcentaje automático de utilidad hasta que Dirección / Comercial lo apruebe y versione.

## Decisiones confirmadas

- Una partida que Veracruzanísima no pueda comercializar permanece en la cotización y en el Excel con el resultado `NO SE COTIZA`.
- En la salida DIF, una partida no cotizable muestra `—` en precio unitario sin IVA, subtotal, IVA y total.
- COFEPRIS no decide qué controlados puede comercializar la empresa.
- La IA no inventa tasas, tratamientos fiscales, márgenes, restricciones sanitarias ni reglas comerciales.
- La referencia estable es evidencia de mercado/adquisición, no precio final de venta.
- El precio final manual es una decisión comercial explícita y trazable, no una regla automática.
- Se implementa primero DIF con un núcleo desacoplado; futuros formatos deben ser exportadores independientes.

## Validaciones externas pendientes

- Responsable Sanitario: regla empresarial sobre productos controlados o restringidos que Veracruzanísima no puede comercializar.
- Contabilidad: matriz de tasas y tratamientos fiscales productivos, con versión y vigencia.
- Dirección / Comercial: si en el futuro se desea automatizar precio de venta, definir y aprobar la política de margen/utilidad, alcance, excepciones, vigencia y responsables.

Hasta contar con esas validaciones, el sistema puede proponer, capturar y conservar decisiones humanas, pero no debe convertir supuestos en reglas productivas.

## Diseño fiscal y comercial reservado

- El estado comercial de una partida se mantiene separado de sus importes y de su tratamiento fiscal.
- Las validaciones fiscales son append-only y ligadas a identidad exacta; los cambios de identidad invalidan su uso actual sin borrar historia.
- La futura matriz fiscal tendrá versión, vigencia, fuente y validación explícita de Contabilidad.
- El precio final de venta se conserva separado de la referencia estable de adquisición.
- Una futura regla de margen deberá ser versionada y no recalcular silenciosamente cotizaciones anteriores.
- El exportador DIF consume resultados internos ya calculados; no contiene tasas, márgenes ni decisiones propias.

## Protocolo para reanudar

1. Leer `AGENTS.md`, este documento y `README.md`.
2. Verificar `main`, PR abiertos, issues y GitHub Actions.
3. Confirmar que el estado documentado coincide con GitHub.
4. Continuar el siguiente objetivo sin usar automáticamente artefactos del V1.
5. Actualizar este archivo cuando se fusione el siguiente hito o cambie la decisión.

Prompt mínimo recomendado:

> Retoma Sistema Triage V2 desde GitHub. Usa `veracruzanisima-ti/sistema-triage-v2` como fuente de verdad; lee `AGENTS.md` y `docs/ESTADO_PROYECTO.md`, verifica `main`, PR, issues y CI antes de cambiar código. Continúa el siguiente objetivo documentado con hechos vs. supuestos, seguridad, trazabilidad, pruebas, reversión y simplicidad. No uses el V1 ni archivos antiguos salvo instrucción explícita.
