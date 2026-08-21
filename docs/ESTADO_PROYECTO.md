# Estado del proyecto · Sistema Triage V2

Última actualización: 2026-08-21 (America/Mexico_City).

## Fuente de verdad

- Repositorio: `veracruzanisima-ti/sistema-triage-v2`.
- Rama estable: `main`.
- Este documento resume el punto de reanudación; los PR e issues enlazados conservan el detalle y la evidencia.

## Estado operativo actual

El piloto end-to-end de #55 continúa activo. Durante la prueba con productos reales aparecieron problemas reproducibles de identidad, forma/dispositivo, disponibilidad, navegación, verificabilidad documental por terceros y lectura de trazabilidad histórica. Se corrigieron como cambios separados, con pruebas y reversión, sin reutilizar reglas del V1.

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

### PR #71 y #85 · disponibilidad antes de usar una referencia

- PR #71 fusionado con commit `c3eeb0bf108435bcbf6336e19c9f0c279b97c872`. CI #165 verde.
- PR #85 fusionado con commit `0fda5bac808672bdb2ec0894cb5b1618b328c8f1`. CI #192 verde, 234 pruebas. Issue #80 cerrado.

Regla operativa vigente después del hallazgo real `100 disponibles` + `entrega_viable=null`:

- `entrega_viable=True`: una observación puede ser elegible como referencia estable si cumple las demás reglas.
- `entrega_viable=False`: `Sin disponibilidad`; se conserva como evidencia y no se puede usar para cotizar.
- `entrega_viable=None` en observaciones MANUAL/ADAPTADOR permanece `Por confirmar`; Triage no infiere decisiones desde texto libre humano.
- `entrega_viable=None` en observaciones WEB se combina con el texto de disponibilidad ya persistido para obtener una **disponibilidad operativa derivada**, sin reescribir la evidencia original.
- Señales WEB positivas inequívocas como `100 disponibles`, `en existencia` o `Disponible (Agregar al carrito)` permiten tratar la opción como disponible.
- Señales negativas como `agotado`, `sin existencias` o `no disponible` mantienen el bloqueo aunque otra señal sea contradictoria.
- Frases ambiguas o condicionadas como `consulta disponibilidad`, `sujeto a disponibilidad`, `ingresa un código postal...`, `falta confirmar` o `pendiente de confirmar` permanecen pendientes.
- Los resultados WEB ya persistidos se recalculan al mostrarse/seleccionarse; no requieren migración ni repetir la búsqueda.
- La falta temporal de existencia **no** convierte automáticamente la partida en `NO_SE_COTIZA`.
- Si una fuente indica falta de existencia y después una persona contacta al proveedor, la confirmación se registra como una nueva observación append-only con fuente/evidencia; la observación web anterior no se modifica.
- Reutilización del mismo día y oportunidades de compra usan la misma disponibilidad operativa.
- Promociones siguen sin poder usarse como referencia estable aunque tengan disponibilidad.

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

### PR #77 · conservación privada del documento original

Fusionado en `main` con commit `dd93e7d55492a195d019b171ebc79d7e1f6f4e0f`. CI #179 verde. Migración `20260821_0018`.

- Las nuevas cargas conservan el archivo original en PostgreSQL **antes** de invocar al lector.
- La ruta de lectura del original requiere sesión y responde con `Cache-Control: private, no-store`.
- PDF e imágenes admitidas pueden revisarse desde la pantalla del documento; también existe `Abrir original`.
- Si el lector falla, el documento no queda bloqueado: una persona puede contrastar el original y capturar manualmente los datos/partidas antes de `Guardar revisión`.
- Los documentos creados antes de esta migración no recuperan el archivo automáticamente; muestran `Original no disponible` y requieren nueva carga si se necesita comprobación visual.
- Para el prototipo se conserva en la base compartida y aplica el límite existente de 15 MB por archivo. Si el volumen crece, debe migrarse a almacenamiento de objetos conservando hash, acceso privado y trazabilidad.
- El archivo sólo se sirve dentro de la cotización a la que pertenece; no se expone como URL pública reutilizable.

### PR #78 · paleta semántica suave y CTA de disponibilidad

Fusionado en `main` con commit `a1756e1e4ed940d8255a6f3b8f5015d9dca61326`. CI #184 verde.

Se normalizó el significado visual sin depender únicamente del color:

- verde suave: confirmado, disponible, seleccionado o listo;
- ámbar suave: pendiente o por confirmar;
- azul suave: identidad/evidencia informativa;
- violeta suave: oferta o promoción;
- rosa/rojo suave: sin disponibilidad, bloqueado, `NO SE COTIZA` o atención fuerte;
- gris: neutral o contexto sin decisión.

La misma semántica se reutiliza en Proveedores, Histórico y Revisión final; el texto siempre permanece visible y no se colorean botones o fondos por decoración.

Ajuste de CTA confirmado durante el piloto:

- disponibilidad operativa `False`: se muestra `Confirmar con proveedor`, porque la fuente indicó falta de existencia/no viabilidad y una confirmación humana posterior puede cambiar el estado mediante una nueva observación trazable;
- disponibilidad operativa `None`: se muestra `Por confirmar`, pero sin el CTA de contacto repetitivo;
- disponibilidad operativa `True`: se muestra `Disponible` y tampoco necesita ese CTA;
- la disponibilidad operativa puede provenir del booleano explícito o, sólo para origen WEB, de evidencia textual inequívoca conforme a #85.

### PR #88 · confirmación humana de una fuente web pendiente

Fusionado en `main` con commit `a8fdf3b6b8ac477316b66d7d31c8be80bcf28a02`. CI #196 verde.

- Una observación WEB `Por confirmar`, no promocional, puede mostrar `Verifiqué fuente · usar para cotizar`.
- El clic representa una afirmación humana explícita de que la persona abrió la fuente y comprobó que el precio sigue visible y que existe disponibilidad/entrega para comprar.
- La observación WEB original permanece intacta; se crea una nueva observación MANUAL append-only con usuario, fecha y vínculo de evidencia a la observación revisada.
- La confirmación manual se usa como `REFERENCIA_ESTABLE` y conserva el avance a la siguiente partida pendiente.
- El envío es idempotente para evitar duplicados por doble clic.
- No aplica a promociones ni a resultados explícitamente `Sin disponibilidad`; estos últimos mantienen el flujo de confirmación con proveedor.

### PR #90 · excepción comercial de surtimiento NADRO

Fusionado en `main` con commit `807d8cf1ad0f77465b46ea36eb720b5f849f81af`. CI #200 verde. Issue #89 cerrado.

Regla comercial confirmada por Veracruzanísima durante el piloto:

- Si el catálogo EdiNadro contiene la identidad exacta y un precio estable válido, la falta de existencia inmediata **no bloquea la cotización**, porque NADRO puede surtir el producto bajo pedido.
- Esta excepción aplica sólo al adaptador estable `NADRO`; no se hereda a WEB, FESA ni otros proveedores.
- `entrega_viable=True` en ese adaptador representa **viabilidad de surtimiento**, no existencia física inmediata.
- La UI distingue el caso con `Surtible por NADRO` y explica que EdiNadro no informa stock en tiempo real.
- El precio estable NADRO puede mostrar `Usar para cotizar` si cumple las demás validaciones.
- `NADRO oferta` conserva la información de surtimiento, pero sigue bloqueada como referencia estable por ser promoción.
- El código postal pertenece al contrato común de consulta, pero el adaptador EdiNadro actual no lo usa para elegir artículo ni precio.

### PR #92 · motivos históricos vs. evaluación actual de descartes web

Fusionado en `main` con commit `a03db83221596573b4cf95dd2d18e806b5ef2b27`. CI #203 verde. Issue #91 cerrado.

- Los motivos de un `CandidatoWebDescartado` siguen siendo evidencia inmutable de la búsqueda original.
- La lista ahora los etiqueta como `Motivo registrado en esa búsqueda` en vez de presentarlos como una conclusión necesariamente vigente.
- Cada descarte puede abrir `Evaluar con reglas actuales`, una vista autenticada de sólo lectura.
- La reevaluación usa la preparación vigente, el matcher local actual y el snapshot COFEPRIS actual cuando corresponde.
- Si una marca antes rechazada hoy puede resolverse al genérico, el motivo actual puede diferir del histórico sin reescribir la evidencia anterior.
- Caso cubierto: `Forxiga 10 mg | Dapagliflozina | Tableta` deja de ser `producto distinto` con reglas actuales si la identidad es comprobable, pero sigue incompleto si no demuestra el conteo solicitado de 28 tabletas.
- Un resultado que hoy aparece `Compatible hoy` **no recupera automáticamente el precio**: debe volver a buscarse/revalidarse porque precio y disponibilidad pueden haber cambiado.

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

`cargar/reabrir -> revisar original/lectura -> normalizar -> consultar precios -> validar identidad/evidencia -> validar disponibilidad o surtimiento -> elegir referencia estable -> decidir COTIZABLE/NO SE COTIZA -> validar tratamiento fiscal -> capturar precio final autorizado -> revisar rubros -> exportar DIF`

Objetivos restantes del piloto:

1. Reabrir Dapagliflozina y usar `Evaluar con reglas actuales` sobre FORXIGA/DAPOSAR antiguos; si hoy son compatibles, repetir/revalidar la fuente antes de cotizar.
2. Confirmar en una partida NADRO que una identidad exacta con precio estable aparece como `Surtible por NADRO`, permite `Usar para cotizar` y no se presenta como stock físico inmediato.
3. Reabrir el caso real de Linagliptina/Farmatodo y confirmar que `100 disponibles (texto en página)` aparece `Disponible` y ofrece `Usar para cotizar` sin repetir la búsqueda.
4. Probar una fuente WEB `Por confirmar`: abrir la fuente, usar `Verifiqué fuente · usar para cotizar` y comprobar que la evidencia automática anterior permanece intacta.
5. Confirmar que el CP mostrado por Triage coincide con el contexto del sitio web cuando se comparen precio y disponibilidad; si difiere, tratarlo como contexto distinto y no como contradicción del mismo dato.
6. Confirmar que frases ambiguas siguen como `Por confirmar`, las faltas de existencia siguen como `Sin disponibilidad` y `Confirmar con proveedor` aparece sólo en este último caso.
7. Comprobar que disponibilidad, identidad y promoción se distinguen por color suave y texto sin saturar la pantalla.
8. Cargar un documento nuevo y verificar que un segundo usuario pueda abrir el original, contrastar la lectura y completar manualmente un caso de lector incompleto/error.
9. Verificar el recorrido completo sin volver manualmente al inicio de listas largas.
10. Comparar el Excel generado con el formato operativo esperado por DIF.
11. Registrar cualquier nueva diferencia reproducible como issue separado antes de modificar código.
12. Medir de forma aproximada el tiempo desde carga hasta exportación.

Issue #43 permanece abierto hasta completar esta validación operativa del flujo DIF.

## Decisiones confirmadas

- Una partida que Veracruzanísima no pueda comercializar permanece en la cotización y en el Excel con el resultado `NO SE COTIZA`.
- La falta de existencia web o una disponibilidad realmente ambigua es un estado operativo temporal y **no** equivale a `NO_SE_COTIZA`.
- Una referencia estable requiere disponibilidad operativa positiva además de las validaciones de identidad y precio aplicables, excepto la regla comercial explícita de surtimiento NADRO descrita abajo.
- En origen WEB, una señal textual inequívoca de existencia puede satisfacer la disponibilidad operativa aunque el booleano externo haya llegado nulo; la evidencia cruda no se modifica.
- En una fuente WEB pendiente, una persona puede confirmar explícitamente precio visible + disponibilidad/entrega después de abrir la fuente; Triage registra una nueva observación manual append-only y conserva intacta la automática.
- En origen MANUAL/ADAPTADOR no se infiere disponibilidad desde texto libre cuando el booleano está nulo.
- **Excepción NADRO confirmada por Veracruzanísima:** identidad exacta + precio estable del catálogo EdiNadro puede cotizarse como `Surtible por NADRO` aunque no exista stock en tiempo real; esto expresa capacidad de suministro bajo pedido, no inventario físico.
- El CTA `Confirmar con proveedor` se reserva para una observación marcada sin disponibilidad/no viable; no se muestra de forma general para toda observación pendiente o disponible.
- Una promoción no puede usarse como referencia estable aunque tenga disponibilidad; se conserva como evidencia/oportunidad.
- Los motivos de descartes web son evidencia histórica y no se reescriben cuando cambian las reglas. Una evaluación actual favorable no reutiliza automáticamente el precio antiguo.
- El código postal puede cambiar el contexto de precio/disponibilidad de una fuente WEB y queda persistido con la observación; el adaptador EdiNadro actual no usa el CP para decidir artículo/precio.
- En la salida DIF, una partida no cotizable muestra `—` en precio unitario sin IVA, subtotal, IVA y total.
- COFEPRIS aporta evidencia de identidad sanitaria; no decide sustituciones clínicas, comerciales ni fiscales.
- La IA no inventa tasas, tratamientos fiscales, márgenes, restricciones sanitarias ni reglas comerciales.
- La referencia estable es evidencia de mercado/adquisición, no precio final de venta.
- El precio final manual es una decisión comercial explícita y trazable, no una regla automática.
- Una cotización con tratamiento fiscal pendiente o precio final pendiente no es emitible.
- Los exportadores consumen el modelo interno; futuros formatos deben permanecer separados del núcleo.
- Para documentos nuevos, el original debe permanecer disponible a usuarios autenticados para permitir revisión posterior por una persona distinta de quien cargó el archivo.

## Validaciones externas pendientes

- **Responsable Sanitario:** regla empresarial sobre productos controlados o restringidos que Veracruzanísima no puede comercializar.
- **Contabilidad:** matriz de tasas y tratamientos fiscales productivos, con versión y vigencia.
- **Dirección / Comercial:** si en el futuro se desea automatizar precio de venta, definir y aprobar política de margen/utilidad, alcance, excepciones, vigencia y responsables.
- **Dirección / Compras / Jurídico o responsable definido:** Issue #68. Definir qué significa operativamente `patente` / `original` para Veracruzanísima y qué fuente autoritativa vigente será aceptada. Hasta entonces Triage no etiqueta `Patente` como hecho ni lo infiere por marca, laboratorio, precio o reconocimiento comercial.

Hasta contar con esas validaciones, el sistema puede proponer, capturar y conservar decisiones humanas, pero no debe convertir supuestos en reglas productivas.

## Diseño fiscal, comercial y documental reservado

- El estado comercial de una partida se mantiene separado de sus importes, disponibilidad y tratamiento fiscal.
- Las validaciones fiscales son append-only y ligadas a identidad exacta; los cambios de identidad invalidan su uso actual sin borrar historia.
- La futura matriz fiscal tendrá versión, vigencia, fuente y validación explícita de Contabilidad.
- El precio final de venta se conserva separado de la referencia estable de adquisición.
- Una futura regla de margen deberá ser versionada y no recalcular silenciosamente cotizaciones anteriores.
- El exportador DIF consume resultados internos ya calculados; no contiene tasas, márgenes ni decisiones propias.
- El original documental se conserva como evidencia para revisión humana; no sustituye la revisión ni convierte una lectura automática en dato aprobado.
- El almacenamiento en PostgreSQL es una decisión proporcional al piloto actual, no una arquitectura definitiva para alto volumen.

## Protocolo para reanudar

1. Leer `AGENTS.md`, este documento y `README.md`.
2. Verificar `main`, PR abiertos, issues y GitHub Actions.
3. Confirmar que el estado documentado coincide con GitHub.
4. Continuar el piloto #55 sin usar automáticamente artefactos del V1.
5. Mantener `Patente` sin automatizar hasta resolver #68 con fuente y validación empresarial.
6. Actualizar este archivo cuando se fusione el siguiente hito o cambie una decisión.

Prompt mínimo recomendado:

> Retoma Sistema Triage V2 desde GitHub. Usa `veracruzanisima-ti/sistema-triage-v2` como fuente de verdad; lee `AGENTS.md` y `docs/ESTADO_PROYECTO.md`, verifica `main`, PR, issues y CI antes de cambiar código. Continúa el piloto #55 con hechos vs. supuestos, seguridad, trazabilidad, pruebas, reversión y simplicidad. No uses el V1 ni archivos antiguos salvo instrucción explícita.
