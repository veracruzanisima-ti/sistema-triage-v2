# ADR 0008 — Referencia administrativa de la cotización

## Estado

Propuesto para el MVP de preview.

## Contexto

Una cotización puede crearse antes de conocer su memorándum. Después, un documento leído y revisado por una persona puede aportar esa referencia. La lista de cotizaciones no debe quedarse permanentemente como `Sin referencia identificada` si ya existe evidencia revisada.

También pueden existir documentos con referencias distintas dentro de la misma cotización. Triage no conoce por sí solo cuál identifica administrativamente la unidad de trabajo y no debe adivinarlo.

## Decisión

La cotización conserva:

- `referencia`: identificador administrativo visible;
- `referencia_fijada_manual`: indica si una persona decidió explícitamente ese valor.

La sincronización automática usa únicamente documentos con estado `REVISADO`.

- cero referencias revisadas distintas: la referencia automática queda vacía;
- exactamente una: se copia a la cotización;
- más de una: la referencia automática queda vacía y la interfaz pide una decisión humana;
- si `referencia_fijada_manual = true`, ninguna revisión documental puede sobrescribirla.

Una persona puede volver a `detección automática`; en ese momento Triage aplica nuevamente las reglas anteriores.

Las referencias existentes antes de esta migración se consideran manuales porque el producto todavía no tenía sincronización automática. Para cotizaciones existentes sin referencia, la migración completa el valor sólo cuando ya existe exactamente un memorándum distinto en documentos revisados.

## Interfaz

- la lista muestra la referencia sincronizada cuando existe;
- cada tarjeta permite ir directamente a `Añadir referencia` o `Editar referencia`;
- el detalle permite fijarla manualmente;
- si hay conflicto, muestra las referencias revisadas disponibles sin seleccionar una por cuenta propia;
- una referencia manual muestra claramente que Triage no la reemplazará;
- el usuario puede volver al modo automático.

Los códigos técnicos de políticas de comercialización permanecen disponibles dentro de `Ver detalle de la regla`, pero el motivo normal de una partida excluida se guarda y muestra en lenguaje humano.

## Criterios de aceptación

- un documento sólo `ANALIZADO` no modifica la referencia de la cotización;
- al guardar su revisión, una referencia única se refleja en la cotización y en el listado;
- una referencia manual no se sobrescribe después;
- dos referencias revisadas distintas generan conflicto y Triage no elige una;
- una persona puede resolver el conflicto seleccionando una referencia;
- puede volver a detección automática;
- eliminar o corregir un documento revisado resincroniza la referencia automática;
- referencias previas a la migración se conservan como manuales;
- motivos de exclusión antiguos con prefijo técnico dejan visible únicamente el motivo entendible.

## Riesgos

- dos textos que representan el mismo memorándum pero tienen diferencias reales de escritura pueden verse como referencias distintas; por ahora sólo se normalizan espacios, no se adivinan equivalencias;
- una referencia fijada manualmente puede quedar desactualizada respecto a los documentos, pero esa decisión explícita tiene prioridad y puede revertirse;
- el backfill de la migración sólo actúa en casos inequívocos.

## Reversión

Revertir el PR asociado y bajar la migración `20260812_0005` a `20260812_0004`.

El downgrade elimina `referencia_fijada_manual`, pero conserva el texto actual de `referencia`; no intenta reconstruir si ese texto provenía de una persona o de un documento. En una base compartida debe realizarse respaldo antes del downgrade.
