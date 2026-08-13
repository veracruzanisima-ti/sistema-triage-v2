# Checklist de liberación — v0.1-piloto-interno

## Objetivo
Congelar una versión estable para que el equipo pruebe el flujo existente mientras `main` continúa evolucionando hacia el producto final.

## Alcance del piloto
El recorrido esperado es:

`Cotización → carga → lectura → revisión humana → exclusiones → preparación de producto → histórico/consultas → decisión de precio`

El piloto no implica que las reglas fiscales, sanitarias o comerciales pendientes estén validadas ni que la cotización final oficial esté automatizada.

## Condiciones obligatorias antes del tag
- [ ] CI de `main` completamente verde.
- [ ] Deploy de Render correspondiente al commit candidato en estado Live.
- [ ] Inicio y cierre de sesión funcionan.
- [ ] Administrador puede crear una cuenta operativa ficticia y desactivarla.
- [ ] Usuario operativo no puede entrar a la administración de usuarios.
- [ ] Creación y persistencia de cotización validadas.
- [ ] Referencia administrativa automática/manual validada en navegador.
- [ ] Carga de PDF/foto y cola de varios archivos validadas.
- [ ] Error transitorio no destruye documentos ya procesados.
- [ ] Revisión humana persiste cantidades enteras y datos administrativos.
- [ ] Restricción provisional muestra alerta y nunca rechaza automáticamente.
- [ ] Exclusión y reintegración de partida persisten.
- [ ] Preparación de producto no modifica la solicitud revisada.
- [ ] Histórico conserva observaciones previas.
- [ ] Consulta de proveedores funciona en estado sin adaptadores y conserva trazabilidad cuando haya adaptadores de prueba.
- [ ] Selección de referencia estable/oportunidad de adquisición es reversible y trazable.
- [ ] Flujo end-to-end ficticio de CI pasa.

## Datos permitidos durante este piloto
- Documentos ficticios.
- Datos anonimizados que no permitan identificar pacientes o terceros.

No cargar documentos reales sensibles en el preview actual hasta contar con infraestructura, respaldos, retención y tratamiento de datos aprobados para ese uso.

## Evidencia mínima de la sesión con el equipo
Registrar como issues o notas de prueba:
- tarea que intentaban realizar;
- pantalla donde ocurrió el problema;
- comportamiento esperado;
- comportamiento observado;
- si bloquea trabajo o sólo genera confusión;
- captura sin datos sensibles cuando sea útil.

## Punto de guardado
Cuando todo lo anterior esté validado:
1. identificar el SHA exacto de `main`;
2. crear tag `v0.1-piloto-interno` sobre ese SHA;
3. crear GitHub Release con alcance, limitaciones conocidas y procedimiento de prueba;
4. fijar el entorno piloto a esa versión estable;
5. continuar desarrollo normal sobre `main`;
6. corregir fallos críticos del piloto con una versión `v0.1.x-piloto` cuando sea necesario.

## Reversión
Si el piloto falla después de liberar, volver el entorno piloto al tag estable anterior. No resolver una incidencia urgente desplegando automáticamente todo lo nuevo que exista en `main`.
