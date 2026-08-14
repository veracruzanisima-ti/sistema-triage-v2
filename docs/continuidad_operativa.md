# Continuidad operativa — Sistema Triage V2

Actualizado: 13 de agosto de 2026

Este documento conserva el contexto funcional que debe sobrevivir a cambios de chat, desarrollador o PR. No reemplaza los ADR técnicos existentes; resume el flujo operativo aprobado, las reglas que Triage puede sugerir y las decisiones que todavía no deben automatizarse como verdad absoluta.

## Estado de implementación

- PR #23 (`feat: simplificar flujo operativo de cotizaciones`) ya fue integrado a `main` con CI verde.
- PR #24 (`feat: cerrar flujo de precios a revisión`) ya fue integrado a `main` con CI verde.
- PR #25 (`feat: conservar contexto de código postal en precios`) ya fue integrado a `main` con CI verde.
- El recorrido visible ya puede avanzar por `Sube y analiza → Revisa → Confirma producto → Busca precio → Revisa cotización` sin obligar al usuario a recorrer pantallas técnicas.
- En `Buscar precios`, una observación no promocional puede marcarse como `Usar para cotizar`; se reutiliza la decisión append-only `REFERENCIA_ESTABLE` ya existente.
- Una promoción no puede convertirse en referencia estable, ni desde el flujo normal ni desde la vista avanzada. Las selecciones promocionales históricas dejan de considerarse vigentes sin borrar su trazabilidad.
- El CP habitual puede configurarse con `CODIGO_POSTAL_CONSULTA_DEFAULT`; cada cotización puede cambiarlo y cada observación nueva conserva el CP con el que fue obtenida. Las consultas automáticas no corren sin CP.
- Histórico, consultas, decisiones de precio, revisión consolidada y cambio manual de estado siguen disponibles bajo áreas secundarias; no se eliminaron datos ni rutas.
- El bloque actualmente en desarrollo (`agent/busqueda-precios-unificada`) agrega una sola acción `Buscar precios` que recorre todos los productos y adaptadores configurados. Un fallo aislado queda registrado y no detiene las demás fuentes. La consulta individual por proveedor permanece como herramienta secundaria.
- Todavía no están implementadas fuentes reales NADRO/FESA, sesiones autenticadas por fuente, cadena fría persistente, Excel final, sugerencia de recargo ni descubrimiento web automático.

## 1. Fuente de verdad del proyecto

- Repositorio actual: `veracruzanisima-ti/sistema-triage-v2`.
- V1 y los scrapers antiguos sólo se consideran referencia selectiva. No son la arquitectura vigente.
- El sistema es una herramienta interna de Veracruzanísima para acelerar cotizaciones sin eliminar la revisión humana.
- El equipo operativo actual es pequeño (aprox. tres personas al mismo nivel). Evitar roles, permisos o capas adicionales sin una necesidad real.
- Prioridades: simplicidad, trazabilidad, seguridad, reversión, pruebas y capacidad de entender de dónde salió cada dato.

## 2. Principio de interacción humana

Triage propone, busca, compara, calcula y conserva evidencia. Una persona hace un vistazo/revisión final y puede corregir la propuesta.

No se busca detener el flujo para pedir una validación formal en cada campo. La revisión humana ocurre como parte natural de la cotización.

Una corrección humana debe conservarse cuando sea útil para analizar tendencias futuras, pero una corrección aislada no se convierte automáticamente en regla del sistema.

## 3. Flujo operativo visible aprobado

El usuario normal debe sentir un recorrido lineal:

`Inicia cotización → Sube y analiza → Revisa → Confirma producto → Busca precio → Revisa cotización → Finaliza`

La interfaz debe mostrar una acción primaria clara para continuar. El usuario no debe necesitar comprender la arquitectura interna ni decidir entre varias herramientas técnicas para avanzar.

### Herramientas secundarias

Histórico, fuentes, intentos de consulta, decisiones internas de precio y trazabilidad deben conservarse, pero presentarse en un área secundaria como `Análisis y trazabilidad`.

No eliminar estos módulos: son valiosos para auditoría y aprendizaje. Sólo dejar de presentarlos como pasos paralelos obligatorios.

## 4. Solicitud y producto a cotizar

Reglas operativas actuales:

1. Si la solicitud exige explícitamente una marca, intentar respetar esa marca.
2. Si no se solicita una marca explícita, priorizar una marca comercial/reconocida que cumpla el producto solicitado; después considerar patente/originador y otras alternativas adecuadas.
3. Intentar respetar exactamente concentración, forma/dispositivo y presentación solicitada.
4. Si la presentación exacta no existe o no está disponible, la cotización debe mostrar la presentación real encontrada y dejar visible la diferencia.
5. La solicitud revisada se conserva sin modificar. La identidad usada para buscar precios es una preparación operativa separada.

Estas reglas son recomendaciones operativas y seguirán refinándose con cotizaciones reales aprobadas.

## 5. Posibles restricciones de comercialización

Existe una lista/regla provisional de productos que actualmente la empresa puede no ser capaz de comercializar.

Triage puede detectar una posible restricción y avisar incluso si el equipo no la había identificado previamente.

La interfaz debe comunicarlo como:

`Posible restricción de comercialización — requiere revisión`

Triage no rechaza automáticamente la partida. La persona puede investigar, excluirla o continuar según corresponda.

## 6. Precios: separar cotización y abastecimiento

### Precio de referencia para cotizar

Para construir la cotización se busca el precio estable más barato disponible y comparable.

Un precio estable es, provisionalmente, un precio vigente que no depende explícitamente de una promoción temporal y que razonablemente puede volver a encontrarse al momento de surtir.

Un precio normal de una cuenta empresarial autenticada puede considerarse estable si no está marcado como promoción.

### Oportunidad de compra

Para surtir una adjudicación se vuelve a consultar el mercado y puede usarse el precio real más barato disponible en ese momento, incluyendo promociones u ofertas.

Por tanto:

`precio para cotizar != precio final de compra`

Una oferta puede registrarse como oportunidad de adquisición sin utilizarse como referencia estable de la cotización.

El sistema no compra automáticamente ni modifica inventario por detectar una oportunidad. Sólo la señala para evaluación humana.

## 7. Contexto de cada consulta de precio

Los precios pueden cambiar por ubicación, sesión, disponibilidad y momento de consulta. La evidencia interna de Triage debe poder conservar, cuando aplique:

- proveedor/fuente;
- producto exacto observado;
- precio;
- código postal utilizado;
- fecha/hora;
- disponibilidad;
- promoción sí/no;
- condiciones relevantes de la promoción;
- información disponible de entrega.

Estas referencias sirven para double check dentro de Triage y no deben saturar el Excel final.

### Código postal y sesión

- Mantener un código postal habitual configurable para las consultas.
- Permitir cambiarlo para una cotización excepcional.
- El CP operativo actual se guarda en la cotización; cada observación de precio conserva el CP usado en el momento en que se obtuvo.
- Los intentos de proveedor conservan el CP dentro de `criterios_busqueda`, evitando duplicar otra columna de base de datos.
- El CP habitual se configura con `CODIGO_POSTAL_CONSULTA_DEFAULT`; no existe una tabla de configuración empresarial sólo para este dato.
- Mientras el sistema opere con ubicaciones mexicanas, el CP aceptado es de exactamente 5 dígitos.
- Una consulta automática a proveedor no debe ejecutarse sin CP; una cotización existente sí puede mantenerse temporalmente sin él.
- Cambiar el CP de una cotización sólo afecta consultas nuevas; nunca reescribe observaciones históricas.
- Cuando una fuente cambia precio/disponibilidad al iniciar sesión, consultar preferentemente con la sesión real autorizada de la empresa.
- Reutilizar sesiones mientras sigan vigentes; pedir intervención sólo cuando caduquen o exista MFA/CAPTCHA.
- Credenciales, cookies y estados autenticados nunca deben guardarse en GitHub ni hardcodearse.

## 8. Estrategia para proveedores y fuentes

No construir un mega-scraper universal.

Usar un motor híbrido:

1. adaptadores de proveedores conocidos y recurrentes;
2. integraciones estructuradas/archivos/APIs antes que scraping cuando existan;
3. automatización autenticada cuando el portal lo requiera y esté autorizada;
4. búsqueda web para descubrir proveedores desconocidos;
5. una fuente nueva se considera candidata y conserva evidencia;
6. si una fuente nueva demuestra utilidad recurrente, entonces construir un adaptador dedicado.

El objetivo es descubrir opciones que el equipo no conocía sin mantener decenas de scrapers innecesarios.

### Orquestación de consultas

La interfaz normal debe ofrecer una sola acción `Buscar precios` que recorra todos los productos preparados y todos los adaptadores configurados. Por ahora la ejecución es secuencial para mantener comportamiento simple, predecible y trazable.

Un error operativo de una fuente se registra en su intento y no debe detener las demás consultas. Errores de configuración del sistema sí deben hacerse visibles en vez de ocultarse.

La consulta individual por proveedor se conserva como herramienta secundaria para diagnóstico, reintentos o casos excepcionales.

## 9. Cadena fría

Triage debe investigar y conservar si el producto requiere cadena fría para evitar repetir la misma investigación en futuras cotizaciones.

En el Excel final sólo se necesita una columna simple:

`Cadena fría: Sí / No`

No agregar al Excel procesos de aprobación, referencias técnicas ni detalle de conservación salvo que exista una necesidad operativa futura.

La interfaz puede mostrar avisos logísticos adicionales para cadena fría, por ejemplo transporte o tiempo de entrega, sin ensuciar el entregable de cotización.

## 10. Recargo comercial

El recargo no es fijo.

La experiencia validada muestra que puede variar aproximadamente entre 15% y 30% según factores como:

- costo unitario;
- costo total de la partida;
- cantidad/volumen;
- impacto del precio final sobre probabilidad de adjudicación.

Triage debe sugerir un porcentaje explicable dentro de ese rango y dejarlo editable. La persona puede aceptarlo o ajustarlo ligeramente.

No fijar todavía umbrales rígidos derivados de una sola cotización. Acumular casos aprobados y observar tendencias antes de formalizar reglas.

Guardar, cuando sea útil, `recargo sugerido` y `recargo finalmente usado` para aprender de las correcciones.

## 11. Excel final

El Excel aprobado por el equipo es el entregable de cálculo, no el expediente de auditoría.

Debe ser deliberadamente limpio. Campos esperados, sujetos a refinamiento:

`Partida | Producto | Marca | Presentación | Cantidad | Unidad | Cadena fría | Precio proveedor s/IVA | IVA proveedor % | IVA proveedor $ | Costo unitario c/IVA | Costo partida | Recargo % | Precio venta s/IVA | IVA venta % | IVA venta $ | Precio venta c/IVA | Total partida`

### Regla esencial

Todo valor derivado debe generarse con fórmulas Excel, no escribirse como resultado fijo.

Ejemplo conceptual:

- IVA unitario = precio base × tasa IVA;
- costo unitario con IVA = precio base + IVA unitario;
- costo de partida = costo unitario × cantidad;
- precio de venta s/IVA = costo base × (1 + recargo);
- IVA de venta = precio venta × tasa IVA;
- total = precio + IVA.

Esto permite editar entradas, seguir referencias de celda y encontrar errores de cálculo rápidamente.

Las tasas fiscales no deben inventarse; deben permanecer como entradas visibles/validadas por el proceso contable correspondiente.

### Qué NO debe saturar el Excel

Mantener en Triage, no en el Excel final:

- URLs/fuentes;
- histórico;
- CP de consulta;
- fecha/hora de búsqueda;
- disponibilidad;
- promociones;
- razonamiento de selección;
- intentos de proveedor;
- decisiones internas de referencia/oportunidad.

## 12. Excel curado como retroalimentación

El archivo de ejemplo terminado en `OK` fue la cotización validada manualmente por el equipo. El archivo anterior fue una propuesta generada durante el análisis.

En el `OK`, la hoja `Cotizacion` representa la versión final revisada. Las hojas auxiliares como `Control` conservaron parte de decisiones anteriores porque el equipo hizo las correcciones finales directamente en `Cotizacion`.

Futuros Excel aprobados pueden alimentar aprendizaje operacional:

`solicitud → propuesta Triage → cotización aprobada`

Detectar diferencias como:

- marca propuesta vs. marca aprobada;
- recargo sugerido vs. usado;
- presentación propuesta vs. aprobada;
- precio/fuente propuesta vs. decisión final.

No aplicar aprendizaje automático que cambie reglas silenciosamente. Acumular ejemplos, detectar tendencias y convertir patrones repetidos en mejores sugerencias o reglas explícitamente aceptadas.

## 13. Próximos bloques recomendados

Orden recomendado a partir de este documento:

1. completar y validar la búsqueda unificada sobre adaptadores configurados;
2. integrar la primera fuente real mediante la vía estructurada más estable disponible;
3. incorporar manejo de sesiones autenticadas por fuente sin guardar secretos en GitHub;
4. incorporar descubrimiento web de proveedores nuevos;
5. persistir y reutilizar `Cadena fría: Sí/No` para productos conocidos;
6. generar Excel limpio con fórmulas;
7. incorporar sugerencia explicable de recargo 15–30%;
8. acumular Excel aprobados y correcciones para detectar tendencias.

## 14. Límites actuales

No asumir todavía como resueltas:

- tasas fiscales por tipo de producto;
- reglas sanitarias específicas;
- duración futura de promociones;
- equivalencias farmacéuticas no confirmadas;
- compra automática;
- inventario automático;
- modelos de aprendizaje automático que cambien decisiones sin revisión.

Cuando una regla nueva sea dudosa, preferir una sugerencia visible y reversible antes que automatizar una decisión irreversible.
