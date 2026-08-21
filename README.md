# Sistema Triage V2

Base operativa del Sistema Triage de Veracruzanísima.

## Objetivo del MVP

Permitir que cualquier integrante autorizado del equipo pueda iniciar, continuar y terminar una cotización desde una interfaz web sencilla, conservando trazabilidad y evitando depender de una sesión local o de conocimientos técnicos.

El flujo operativo actual es:

`cargar solicitud -> revisar lectura -> normalizar -> consultar precios -> validar decisiones -> revisar importes -> exportar DIF`

## Principios

- simplicidad antes que sofisticación;
- una sola fuente de verdad persistente;
- la IA propone y una persona puede corregir;
- reglas fiscales, sanitarias y comerciales sensibles requieren validación humana o empresarial;
- Excel y futuros PDF son salidas, no la base histórica del sistema;
- ninguna credencial real se guarda en GitHub;
- comentarios y documentación se mantienen en español siempre que sea razonable.

## Stack

- Python 3.12+
- FastAPI
- Jinja2
- HTMX, sólo cuando aporte una interacción concreta
- SQLAlchemy 2.x
- Alembic
- PostgreSQL en producción
- SQLite únicamente para desarrollo y pruebas
- pytest
- Docker
- GitHub Actions

## Ejecución local

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env       # Windows: copy .env.example .env
alembic upgrade head
uvicorn triage.main:app --reload
```

Abrir `http://127.0.0.1:8000`.

El `.env.example` usa SQLite para que el desarrollo local sea sencillo. Un despliegue con `APP_ENV=production` rechaza SQLite y exige una base compartida mediante `DATABASE_URL`.

## Estado actual

La aplicación ya puede:

- autenticar usuarios internos y conservar cotizaciones en una base compartida;
- iniciar, pausar, reabrir y cambiar el estado de una cotización;
- cargar documentos y conservar lectura/revisión humana de sus partidas;
- preparar una identidad normalizada sin modificar la solicitud original;
- consultar proveedores configurados, descubrimiento web y evidencia histórica de precios;
- importar snapshots de NADRO y COFEPRIS con trazabilidad;
- usar COFEPRIS de forma conservadora para respaldar identidad, sin convertirlo en decisión clínica, comercial o fiscal;
- mostrar resultados web descartados y la causa de rechazo sin convertirlos en referencias cotizables;
- conservar decisiones humanas de referencia estable y oportunidad de adquisición;
- mantener partidas `COTIZABLE` / `NO_SE_COTIZA` como eventos reversibles y trazables;
- proponer tratamiento fiscal por capas, mostrar conflictos y exigir validación humana explícita;
- calcular precio unitario s/IVA, subtotal, IVA y total;
- capturar un precio final unitario sin IVA de forma manual, trazable y separada de la referencia de adquisición;
- impedir que una partida cotizable sea emitible mientras falte referencia estable, validación fiscal o precio final;
- exportar un Excel DIF desde el modelo consolidado, conservando `NO SE COTIZA` con `—` en importes;
- neutralizar texto controlado por usuarios que Excel pudiera interpretar como fórmula.

El siguiente paso no es añadir más automatización: es ejecutar el piloto end-to-end de #55 con una solicitud real y registrar las diferencias reproducibles.

## Límites deliberados

Triage V2 todavía **no debe**:

- fijar una matriz fiscal productiva sin validación y versionado de Contabilidad;
- decidir automáticamente qué productos controlados puede comercializar Veracruzanísima sin regla validada por el Responsable Sanitario;
- inventar o heredar una política de margen/utilidad para precio de venta;
- aceptar una marca comercial como equivalente sólo por similitud textual;
- convertir sugerencias de IA o COFEPRIS en decisiones sensibles automáticas;
- copiar automáticamente reglas o código del V1.

## Migraciones

Los cambios de estructura de la base se versionan con Alembic.

```bash
alembic upgrade head
```

No se debe usar `create_all()` para preparar una base de producción. Las pruebas sí lo utilizan sobre bases SQLite temporales y aisladas.

## Continuidad del proyecto

Antes de continuar desarrollo, leer:

1. `AGENTS.md`;
2. `docs/ESTADO_PROYECTO.md`;
3. los PR e issues abiertos de GitHub;
4. el estado de GitHub Actions.

`docs/ESTADO_PROYECTO.md` indica el siguiente objetivo operativo y los límites de negocio pendientes de validación.

## Repositorio anterior

`sistema-triage` se conserva intacto como prototipo V1. Sólo puede consultarse o reutilizarse de forma selectiva cuando exista una decisión explícita; no es fuente de verdad para V2.
