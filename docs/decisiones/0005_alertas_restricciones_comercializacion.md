# 0005 - Alertas provisionales de restricciones de comercialización

## Estado

Provisional. Pendiente de validación por el Responsable Sanitario.

## Objetivo

Advertir al equipo cuando una partida parece coincidir con una restricción interna de comercialización sin permitir que la aplicación tome por sí sola una decisión sanitaria o comercial.

## Fuente

Documento interno revisado: `PRODUCTOS QUE NO SE PUEDEN COMERCIALIZAR.docx`.

El archivo original no se incorpora al repositorio. La política derivada se identifica como `POL-COM-001`, versión `0.1-provisional`.

La fuente indica, con base en el aviso de funcionamiento y el giro del establecimiento, restricciones para:

- Buprenorfina: parches o inyectable.
- Xeomeen.
- Dysport.
- Metilfenidato: cualquier dosis.
- Clonazepam: tabletas y gotas.
- Tramadol: inyectable y tabletas, combinado o solo.
- Naltrexone o Naltrexona.
- Fentanilo.
- Alprazolam: cualquier gramaje.
- Lorazepam.
- Bromazepam.
- Flumazenil.
- Morfina.
- Sufentanilo.
- Nalbufina.
- Midazolam: todas sus presentaciones.
- Diazepam: inyectable y tabletas.
- Ergometrina.
- Efedrina.
- Medicamentos hemoderivados, citando como ejemplos inmunoglobulinas, factores de coagulación, fibrinógeno humano y albúmina humana.

## Decisión

Triage no bloqueará ni eliminará una partida por esta política.

El sistema normaliza temporalmente el texto únicamente para comparar mayúsculas, acentos y puntuación. Los datos originales permanecen sin modificación. Si encuentra una coincidencia con una regla provisional, muestra:

- `Posible rechazo - requiere revisión`;
- el motivo tomado de la política;
- identificador y versión de la regla;
- indicación de que la política está pendiente de validación del Responsable Sanitario.

La persona conserva la capacidad de corregir y guardar la partida.

## Lo que esta normalización no es

Este mecanismo no constituye todavía el catálogo maestro ni la normalización comercial completa de productos. No decide equivalencias entre marcas, principios activos, concentraciones, presentaciones o dispositivos y no se utilizará como identidad para precios históricos.

## Ambigüedades deliberadamente no resueltas

1. `Xeomeen` se conserva con la grafía exacta de la fuente. No se asume que corresponda a otro nombre comercial.
2. Cuando la fuente menciona una sustancia sin indicar presentación, el motor puede advertir por nombre, pero la interpretación sanitaria definitiva debe validarse.
3. Para hemoderivados, la fuente usa la expresión `medicamentos como` y proporciona ejemplos. El motor alerta por esos ejemplos; no intenta inferir automáticamente toda la categoría farmacológica.
4. No se agregan sinónimos farmacológicos, principios activos relacionados ni equivalencias que no estén expresadas en la fuente.

## Criterios de aceptación

- una coincidencia válida se destaca con color tenue y texto visible;
- la alerta explica el motivo y no sólo indica que una IA lo sugirió;
- guardar una partida alertada sigue siendo posible;
- reglas condicionadas por presentación sólo alertan en las presentaciones citadas;
- la grafía `Xeomeen` no se autocorrige;
- las alertas se recalculan al volver a renderizar la revisión;
- no se introduce una migración de base de datos;
- CI utiliza datos ficticios.

## Riesgos

- una coincidencia textual puede producir falsos positivos o falsos negativos;
- una descripción incompleta puede no contener la presentación necesaria para activar una regla;
- la política fuente puede cambiar o requerir interpretación sanitaria.

Por estas razones, la alerta es informativa y provisional.

## Validación pendiente

El Responsable Sanitario debe confirmar al menos:

- alcance por presentación de las sustancias donde la fuente no la especifica;
- grafía y alcance de `Xeomeen`;
- alcance completo de la categoría de hemoderivados;
- vigencia de la política respecto del aviso de funcionamiento actual.

## Reversión

Revertir este cambio elimina el motor y las alertas visuales. No requiere downgrade de base de datos porque no agrega tablas ni columnas.
