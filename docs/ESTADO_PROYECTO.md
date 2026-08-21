# Estado del proyecto · Sistema Triage V2

Última actualización: 2026-08-21 (America/Mexico_City).

## Fuente de verdad

- Repositorio: `veracruzanisima-ti/sistema-triage-v2`.
- Rama estable: `main`.
- Este documento resume el punto de reanudación; los PR e issues enlazados conservan el detalle y la evidencia.

## Últimos hitos completados

### PR #54 · precio final manual y DIF emitible

Fusionado en `main` con commit `d2585246d04fbc3d2f6d6e0d441934a27608d2e4`.

- La referencia estable de adquisición ya no se usa como si fuera precio final de venta.
- Cada partida `COTIZABLE` puede recibir un precio unitario final sin IVA capturado manualmente con fuente o criterio comercial, usuario y fecha.
- La decisión es append-only y reversible; cambiar la identidad exacta invalida su uso actual sin borrar historia.
- El cálculo final aplica únicamente el tratamiento fiscal ya validado al precio final comercial.
- DIF sólo se genera cuando cada partida cotizable tiene referencia estable, validación fiscal, precio final validado y cálculo final.
- `NO_SE_COTIZA` permanece visible con `—` en importes.
- No existe una regla automática de margen/utilidad y no se reutilizó ninguna regla del V1.
- Migración `20260821_0017` reversible.
- GitHub Actions #144: estilo, scripts, migraciones y suite completa aprobados.

### PR #48 · indicadores visibles COFEPRIS

Fusionado en `main` con commit `5a7ae55904fcca859115c94032411580832fcfd3`.

- La pantalla de proveedores indica claramente `COFEPRIS activo` o `COFEPRIS no cargado`.
- Muestra registros vigentes/totales, archivo y fecha de carga cuando existe snapshot.
- Las observaciones respaldadas por COFEPRIS muestran distintivo, registro, genérico y estado.
- La interfaz recuerda que COFEPRIS sólo aporta evidencia de identidad sanitaria; no decide sustituciones clínicas, comerciales ni fiscales.
- No modifica matcher, esquema ni datos.
- La rama fue revalidada explícitamente contra el `main` posterior a #54; GitHub Actions #146 quedó verde.

### Hitos inmediatamente anteriores

- PR #50, `0fc4854ae02962af254ba6d656c56e545d04129a`: corrige falsos negativos como `Dapagliflozina 10 mg 28 Tabs` frente a `Caja con 28 tabletas`, sin relajar concentración ni cantidad. CI #137 verde.
- PR #52, `d598f729b63a150e653c3cc7b636019253c34836`: Exportador DIF v1 desacoplado, conservación de `NO SE COTIZA`, trazabilidad y protección ante fórmulas de Excel. CI #136 verde.
- PR #47: motor fiscal explicable por capas, validación humana append-only y separación entre tasa 0 y exención.
- PR #45: estado comercial `COTIZABLE` / `NO_SE_COTIZA` append-only y reversible.
- PR #42: snapshot e identidad conservadora con COFEPRIS.

## Siguiente objetivo

Issue #55, **“Piloto end-to-end: validar una cotización DIF real en Triage V2”**.

Antes de agregar más automatización, validar una solicitud real mediante el flujo completo:

`cargar documento -> revisar lectura -> normalizar -> consultar precios -> validar identidad/evidencia -> elegir referencia estable -> decidir COTIZABLE/NO SE COTIZA -> validar tratamiento fiscal -> capturar precio final autorizado -> revisar rubros -> exportar DIF`

Objetivos del piloto:

1. Confirmar que una cotización puede iniciarse, pausarse y retomarse sin depender de una sesión local.
2. Verificar con datos reales el matcher corregido, incluyendo abreviaturas de presentación como `Tabs`.
3. Confirmar que COFEPRIS hace visible cuándo existe respaldo de identidad y cuándo no.
4. Validar que los bloqueos por referencia, fiscal o precio final sean comprensibles para una persona operadora.
5. Comparar el Excel generado con el formato operativo esperado por DIF.
6. Registrar cada diferencia reproducible como issue separado antes de modificar código.
7. Medir de forma aproximada el tiempo desde carga hasta exportación.

Issue #43 permanece abierto hasta completar esta validación operativa del flujo DIF.

## Decisiones confirmadas

- Una partida que Veracruzanísima no pueda comercializar permanece en la cotización y en el Excel con el resultado `NO SE COTIZA`.
- En la salida DIF, una partida no cotizable muestra `—` en precio unitario sin IVA, subtotal, IVA y total.
- COFEPRIS aporta evidencia de identidad sanitaria; no decide sustituciones clínicas, comerciales ni fiscales.
- La IA no inventa tasas, tratamientos fiscales, márgenes, restricciones sanitarias ni reglas comerciales.
- La referencia estable es evidencia de mercado/adquisición, no precio final de venta.
- El precio final manual es una decisión comercial explícita y trazable, no una regla automática.
- Una cotización con tratamiento fiscal pendiente o precio final pendiente no es emitible.
- Los exportadores consumen el modelo interno; futuros formatos deben permanecer separados del núcleo.

## Validaciones externas pendientes

- **Responsable Sanitario:** regla empresarial sobre productos controlados o restringidos que Veracruzanísima no puede comercializar.
- **Contabilidad:** matriz de tasas y tratamientos fiscales productivos, con versión y vigencia.
- **Dirección / Comercial:** si en el futuro se desea automatizar precio de venta, definir y aprobar política de margen/utilidad, alcance, excepciones, vigencia y responsables.

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
