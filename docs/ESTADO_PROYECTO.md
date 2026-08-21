# Estado del proyecto · Sistema Triage V2

Última actualización: 2026-08-21 (America/Mexico_City).

## Fuente de verdad

- Repositorio: `veracruzanisima-ti/sistema-triage-v2`.
- Rama estable: `main`.
- Este documento resume el punto de reanudación; los PR e issues enlazados conservan el detalle y la evidencia.

## Estado operativo actual

El piloto end-to-end de #55 continúa activo. Durante la prueba con productos reales aparecieron problemas reproducibles de identidad, forma/dispositivo, disponibilidad y navegación. Se corrigieron como cambios separados, con pruebas y reversión, sin reutilizar reglas del V1.

### PR #69 · convergencia segura marca → genérico con COFEPRIS

Fusionado en `main` con commit `be772341f965f536e0ff30f06f37fe2b3d0a3766`. CI #159 verde.

- Corrige falsos descartes `producto distinto` cuando una marca tiene varios registros VIGENTES en COFEPRIS pero todos convergen inequívocamente en el mismo genérico solicitado.
- Casos del piloto relacionados: LANTUS → INSULINA GLARGINA y la misma familia de problema observada con FORXIGA/DAPOSAR y ZANIDIP/REMANSIL/EVIPRESS.
- No acepta similitud textual como equivalencia.
- Si las filas divergen en genéricos, contienen combinaciones o son duplicados equivalentes, mantiene el rechazo conservador.
- COFEPRIS sólo resuelve identidad marca → genérico; concentración, forma/dispositivo y presentación siguen dependiendo del matcher exacto.
- La evidencia puede mostrar varios registros vigentes convergentes sin afirmar que COFEPRIS validó una presentación comercial concreta.

### PR #70 · forma farmacéutica separada de envase/dispositivo

Fusionado en `main` con commit `a5e902792bf9d6021e3b5f614026c901c3389dec`. CI #161 verde.

- Un título que sólo dice `frasco ámpula` ya no se interpreta como una forma farmacéutica distinta de `solución inyectable`.
- Si falta la forma solicitada, queda como `faltan datos suficientes para comprobar coincidencia`.
- Una forma explícitamente incompatible, como `tabletas` frente a `solución inyectable`, sigue siendo rechazo real.
- Dispositivos explícitos incompatibles, como pluma frente a vial, siguen siendo rechazo.
- No se infiere solución, suspensión o polvo a partir del envase.

### PR #71 · disponibilidad confirmada antes de usar una referencia

Fusionado en `main` con commit `c3eeb0bf108435bcbf6336e19c9f0c279b97c872`. CI #165 verde.

Regla operativa confirmada durante el piloto:

- `entrega_viable=True`: una observación puede ser elegible como referencia estable si cumple las demás reglas.
- `entrega_viable=None`: `Disponibilidad por confirmar`; se conserva como evidencia y no se puede usar para cotizar.
- `entrega_viable=False`: `Sin disponibilidad`; se conserva como evidencia y no se puede usar para cotizar.
- La falta temporal de existencia **no** convierte automáticamente la partida en `NO_SE_COTIZA`.
- Si una persona contacta al proveedor y confirma existencia/entrega, registra una nueva observación append-only con fuente/evidencia; la observación web anterior no se modifica.
- Reutilización del mismo día y oportunidades de compra también exigen disponibilidad/entrega confirmada.
- Selecciones antiguas apoyadas en observaciones no confirmadas dejan de ser vigentes sin borrar historia.

### PR #72 · clasificación visual basada en evidencia

Fusionado en `main` con commit `50c8baf7c6f6c90c17b24f85daeba8de8511b6c4`. CI #170 verde.

La tarjeta de precio prioriza 1–3 señales principales para lectura rápida:

1. estado operativo: `Usado para cotizar`, `Cotizado hoy`, `Disponible`, `Sin disponibilidad` o `Por confirmar`;
2. identidad descriptiva cuando existe evidencia: `Marca comercial`, `Nombre genérico registrado`, `Nombre genérico visible` o `Marca propia declarada`;
3. `Oferta / promoción` cuando corresponde.

- `Marca comercial` requiere respaldo COFEPRIS con denominación distintiva diferente del genérico.
- `Nombre genérico visible` significa únicamente que el genérico preparado aparece explícitamente en la descripción de la fuente; no afirma intercambiabilidad.
- `Marca propia declarada` sólo se muestra cuando la propia fuente lo declara.
- COFEPRIS conserva visible su evidencia y la advertencia de que sólo confirma identidad sanitaria.
- No se muestra ni se infiere `Patente`.

### PR #73 y #74 · navegación contextual y resumen visual

- PR #73 fusionado con commit `4e61b584d9ac61f057695731675ba8fc7c87e9d4`. CI #172 verde.
- PR #74 fusionado con commit `7281129f6e3822587686e353beefdb56749ccbcb`. CI #174 verde.

Resultado UX:

- Proveedores recuerda la partida al revalidar, consultar una fuente o confirmar una presentación.
- `Usar para cotizar` conserva el avance de #61: va a la siguiente pendiente y sólo vuelve arriba cuando termina todas.
- Confirmar disponibilidad o registrar un precio manual abre la partida exacta y regresa al mismo medicamento.
- Revisión final conserva el foco tras validar o retirar fiscal, precio final o estado comercial.
- La partida activa recibe un resaltado azul suave que no representa un estado de negocio.
- Revisión consolidada resume con cinco señales: `Preparación`, `Referencias`, `Fiscal`, `Precio final` y `Alertas`; los conteos completos siguen disponibles bajo `Ver conteos detallados`.
- Preparación e Histórico ya tenían navegación dirigida por #63 y #71; la auditoría evitó rediseñar pantallas que ya comunicaban correctamente el siguiente paso.

## Hitos base del flujo DIF

### PR #54 · precio final manual y DIF emitible

Fusionado en `main` con commit `d2585246d04fbc3d2f6d6e0d441934a27608d2e4`.

- La referencia estable de adquisición no se usa como precio final de venta.
- Cada partida `COTIZABLE` puede recibir un precio unitario final sin IVA capturado manualmente con fuente o criterio comercial, usuario y fecha.
- La decisión es append-only y reversible; cambiar la identidad exacta invalida su uso actual sin borrar historia.
- DIF sólo se genera cuando cada partida cotizable tiene referencia estable, validación fiscal, precio final validado y cálculo final.
- `NO_SE_COTIZA` permanece visible con `—` en importes.
- No existe una regla automática de margen/utilidad y no se reutilizó ninguna regla del V1.
- Migración `20260821_0017` reversible. CI #144 verde.

### Hitos inmediatamente anteriores

- PR #48: indicadores visibles y trazabilidad COFEPRIS; revalidado contra el `main` posterior a #54, CI #146 verde.
- PR #50: corrige `Dapagliflozina 10 mg 28 Tabs` frente a `Caja con 28 tabletas` sin relajar concentración ni cantidad. CI #137 verde.
- PR #52: Exportador DIF v1 desacoplado, conservación de `NO SE COTIZA`, trazabilidad y protección ante fórmulas de Excel. CI #136 verde.
- PR #47: motor fiscal explicable por capas, validación humana append-only y separación entre tasa 0 y exención.
- PR #45: estado comercial `COTIZABLE` / `NO_SE_COTIZA` append-only y reversible.
- PR #42: snapshot e identidad conservadora con COFEPRIS.

## Siguiente objetivo

Issue #55, **“Piloto end-to-end: validar una cotización DIF real en Triage V2”**.

Continuar con la misma solicitud real después de desplegar el `main` actual:

`cargar/reabrir -> revisar lectura -> normalizar -> consultar precios -> validar identidad/evidencia -> confirmar disponibilidad -> elegir referencia estable -> decidir COTIZABLE/NO SE COTIZA -> validar tratamiento fiscal -> capturar precio final autorizado -> revisar rubros -> exportar DIF`

Objetivos restantes del piloto:

1. Repetir los casos que antes fallaron por marca/genérico y comprobarlos contra el snapshot COFEPRIS realmente cargado en producción.
2. Confirmar visualmente los estados `Disponible`, `Por confirmar` y `Sin disponibilidad` con proveedores reales.
3. Verificar el recorrido completo sin volver manualmente al inicio de listas largas.
4. Comparar el Excel generado con el formato operativo esperado por DIF.
5. Registrar cualquier nueva diferencia reproducible como issue separado antes de modificar código.
6. Medir de forma aproximada el tiempo desde carga hasta exportación.

Issue #43 permanece abierto hasta completar esta validación operativa del flujo DIF.

## Decisiones confirmadas

- Una partida que Veracruzanísima no pueda comercializar permanece en la cotización y en el Excel con el resultado `NO SE COTIZA`.
- La falta de existencia web o entrega por confirmar es un estado operativo temporal y **no** equivale a `NO_SE_COTIZA`.
- Una referencia estable requiere disponibilidad/entrega confirmada además de las validaciones de identidad y precio aplicables.
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
- **Dirección / Compras / Jurídico o responsable definido:** Issue #68. Definir qué significa operativamente `patente` / `original` para Veracruzanísima y qué fuente autoritativa vigente será aceptada. Hasta entonces Triage no etiqueta `Patente` como hecho ni lo infiere por marca, laboratorio, precio o reconocimiento comercial.

Hasta contar con esas validaciones, el sistema puede proponer, capturar y conservar decisiones humanas, pero no debe convertir supuestos en reglas productivas.

## Diseño fiscal y comercial reservado

- El estado comercial de una partida se mantiene separado de sus importes, disponibilidad y tratamiento fiscal.
- Las validaciones fiscales son append-only y ligadas a identidad exacta; los cambios de identidad invalidan su uso actual sin borrar historia.
- La futura matriz fiscal tendrá versión, vigencia, fuente y validación explícita de Contabilidad.
- El precio final de venta se conserva separado de la referencia estable de adquisición.
- Una futura regla de margen deberá ser versionada y no recalcular silenciosamente cotizaciones anteriores.
- El exportador DIF consume resultados internos ya calculados; no contiene tasas, márgenes ni decisiones propias.

## Protocolo para reanudar

1. Leer `AGENTS.md`, este documento y `README.md`.
2. Verificar `main`, PR abiertos, issues y GitHub Actions.
3. Confirmar que el estado documentado coincide con GitHub.
4. Continuar el piloto #55 sin usar automáticamente artefactos del V1.
5. Mantener `Patente` sin automatizar hasta resolver #68 con fuente y validación empresarial.
6. Actualizar este archivo cuando se fusione el siguiente hito o cambie una decisión.

Prompt mínimo recomendado:

> Retoma Sistema Triage V2 desde GitHub. Usa `veracruzanisima-ti/sistema-triage-v2` como fuente de verdad; lee `AGENTS.md` y `docs/ESTADO_PROYECTO.md`, verifica `main`, PR, issues y CI antes de cambiar código. Continúa el piloto #55 con hechos vs. supuestos, seguridad, trazabilidad, pruebas, reversión y simplicidad. No uses el V1 ni archivos antiguos salvo instrucción explícita.
