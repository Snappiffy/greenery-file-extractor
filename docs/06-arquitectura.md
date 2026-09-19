# 06 · Arquitectura y estructura

Mismo principio que el backend de Greenary (hexagonal), adaptado a Python y a un servicio
mucho más pequeño: **el dominio no sabe que existe HTTP ni PyMuPDF**.

## Estructura de carpetas

```
extractor/
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── uv.lock
├── Dockerfile
├── .dockerignore
├── .env.example
├── docs/
├── src/extractor/
│   ├── __init__.py
│   ├── config.py                  # Settings (pydantic-settings), única lectura de env
│   ├── cli.py                     # CLI de depuración
│   │
│   ├── domain/                    # PURO. Sin I/O, sin frameworks, sin librerías de PDF
│   │   ├── models.py              # Word, Line, Cell, Row, Size, Issue, Diagnostics
│   │   ├── profile.py             # Profile y sus submodelos + validación semántica
│   │   ├── issues.py              # IssueCode (enum), Severity, constructores
│   │   ├── errors.py              # ExtractorError y subclases de dominio
│   │   ├── fingerprint.py         # cálculo y comparación de componentes
│   │   └── parsing/
│   │       ├── text.py            # normalización
│   │       ├── price.py
│   │       ├── size.py
│   │       ├── quantity.py
│   │       └── availability.py
│   │
│   ├── engine/                    # la extracción. Depende de domain, NO de api
│   │   ├── lines.py               # agrupar palabras en líneas
│   │   ├── header.py              # localizar el ancla
│   │   ├── merge.py               # fusión multilínea
│   │   ├── filters.py             # stop_patterns y filters
│   │   └── strategies/
│   │       ├── base.py            # protocolo Strategy
│   │       ├── columns.py
│   │       ├── ruling.py
│   │       └── regex.py
│   │
│   ├── application/               # casos de uso. Orquestan, no implementan
│   │   ├── extract_document.py
│   │   └── sample_document.py
│   │
│   ├── adapters/                  # todo lo que toca el mundo exterior
│   │   ├── readers/
│   │   │   ├── base.py            # protocolo DocumentReader -> list[Page[Word]]
│   │   │   ├── pymupdf_reader.py
│   │   │   ├── pdfplumber_reader.py
│   │   │   └── image_reader.py
│   │   ├── ocr/
│   │   │   ├── base.py            # protocolo OcrEngine
│   │   │   └── tesseract.py
│   │   └── fetch/
│   │       └── http_fetcher.py    # descarga por URL firmada, con timeout y límite
│   │
│   └── api/
│       ├── app.py                 # create_app(), middlewares, routers
│       ├── routes.py
│       ├── schemas.py             # DTOs de petición y respuesta
│       ├── auth.py                # bearer con compare_digest
│       ├── error_handlers.py      # dominio -> HTTP. ÚNICO sitio que conoce códigos HTTP
│       └── logging.py             # logging JSON estructurado
│
└── tests/
    ├── conftest.py
    ├── unit/
    ├── integration/
    ├── golden/
    └── fixtures/
```

## Reglas de dependencia

```
domain     ←  engine  ←  application  ←  api
                              ↑
                          adapters
```

- `domain` no importa **nada** de las otras capas, ni `fastapi`, ni `fitz`, ni `pdfplumber`,
  ni `httpx`. Solo stdlib y `pydantic`.
- `engine` importa `domain`. No importa `fitz` directamente: recibe `list[Page[Word]]`, que
  es un modelo de dominio. Así se puede testear sin un PDF.
- `adapters` importa `domain` y traduce el mundo exterior a modelos de dominio.
- `application` orquesta: recibe puertos (protocolos) por parámetro, no los construye.
- `api` es la única capa que conoce HTTP, códigos de estado y FastAPI.

**Esto se verifica automáticamente**, no se confía en la disciplina: `tests/test_layering.py`
recorre los imports de cada módulo con `ast` y falla si alguno viola la regla. Es 40 líneas
y evita que la arquitectura se erosione en el tercer sprint.

## Inyección de dependencias

Sin contenedor de DI. El caso de uso recibe sus puertos como argumentos:

```python
# application/extract_document.py
def extract_document(
    *,
    request: ExtractRequest,
    fetcher: Fetcher,
    reader_for: Callable[[ContentType], DocumentReader],
    ocr: OcrEngine | None,
    clock: Clock,
) -> ExtractResult: ...
```

`api/routes.py` los construye desde `config.Settings`. Los tests los sustituyen por dobles.
`clock` está ahí precisamente para que `duration_ms` no obligue a llamar a `time` dentro
del dominio.

## Cómo extender

### Añadir una estrategia

1. Crear `engine/strategies/<nombre>.py` implementando el protocolo `Strategy`:
   `cut(lines: list[Line], profile: Profile) -> list[list[Cell]]`.
2. Registrarla en el mapa de `engine/strategies/__init__.py`.
3. Añadir su bloque de configuración a `domain/profile.py` y documentarlo en `docs/03`.
4. Añadirla a `supported_strategies` en `GET /v1/version`.
5. Un fixture en el golden set. **Sin fixture no se mergea.**

### Añadir un parser de campo

1. `domain/parsing/<campo>.py`, firma `(text: str, cfg: <Campo>Config) -> tuple[T | None, list[Issue]]`.
2. Nuevos códigos en `domain/issues.py` y en la tabla de `docs/04`.
3. Tests unitarios + property test con `hypothesis`.

### Añadir un formato de documento

1. Un reader en `adapters/readers/` que produzca `list[Page[Word]]`.
2. Registrarlo por MIME.
3. Actualizar la tabla de tipos soportados en `docs/02` y en `GET /v1/version`.

Si el formato es tabular (xlsx, csv), **no**: eso va en el worker. Ver `docs/01`.

## Concurrencia

FastAPI con `uvicorn`. Los endpoints de extracción son `def` (síncronos), no `async def`:
el trabajo es CPU puro y ponerlo en la corrutina bloquearía el loop. FastAPI los ejecuta en
el threadpool, y un semáforo de `MAX_CONCURRENCY` limita cuántos corren a la vez.

Solo `http_fetcher` es asíncrono, porque ahí sí hay espera de red.

Estado global mutable: ninguno. El único estado de proceso son los `Settings` y los regex
compilados de un perfil, que viven lo que dura la petición.
