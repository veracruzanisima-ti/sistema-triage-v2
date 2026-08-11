# Sistema Triage V2

Nueva base del Sistema Triage de Veracruzanísima.

## Objetivo del MVP

Permitir que cualquier integrante autorizado del equipo pueda iniciar, continuar y terminar una cotización desde una interfaz web sencilla, conservando trazabilidad y evitando depender de una sesión local o de conocimientos técnicos.

El flujo objetivo inicial es:

`subir solicitud -> revisar datos -> guardar -> continuar después -> finalizar`

La búsqueda de proveedores, inteligencia comercial, histórico de precios, cálculo fiscal definitivo y generación de PDF se incorporarán por etapas.

## Principios

- simplicidad antes que sofisticación;
- una sola fuente de verdad persistente;
- la IA propone y una persona puede corregir;
- reglas fiscales, sanitarias y comerciales sensibles requieren validación humana o empresarial;
- Excel y PDF son salidas, no la base histórica del sistema;
- ninguna credencial real se guarda en GitHub;
- comentarios y documentación se mantienen en español siempre que sea razonable.

## Stack inicial

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

- mostrar un listado de cotizaciones;
- iniciar una cotización con referencia opcional;
- guardar la cotización fuera de la sesión del navegador;
- reabrirla después;
- cambiar explícitamente su estado entre `EN_PROCESO`, `PENDIENTE_REVISION` y `FINALIZADA`.

Todavía no procesa documentos reales, no integra OpenAI y no ejecuta decisiones fiscales o comerciales.

## Migraciones

Los cambios de estructura de la base se versionan con Alembic.

```bash
alembic upgrade head
```

No se debe usar `create_all()` para preparar una base de producción. Las pruebas sí lo utilizan sobre bases SQLite temporales y aisladas.

## Repositorio anterior

`sistema-triage` se conserva intacto como prototipo V1 y referencia de piezas reutilizables. La migración será selectiva; no se copiará código automáticamente.
