# greenery-extractor

Microservicio HTTP sin estado que convierte PDFs e imágenes de listas de precios de viveros
en filas estructuradas, guiado por un perfil de extracción por proveedor.

Parte del módulo de ingesta de catálogo de **Greenary App**. Construido por
**Snappiffy**.

```
documento (PDF/imagen) + perfil  →  [ extractor ]  →  filas + diagnósticos
```

- **No** llama a ningún modelo de lenguaje.
- **No** toca ninguna base de datos.
- Es determinista: la misma entrada produce la misma salida, byte a byte.

## Quickstart

```bash
uv sync --all-extras
cp .env.example .env
# Obligatorio: EXTRACTOR_SHARED_SECRET (>=32 chars) y FETCH_ALLOWED_HOSTS
uv run uvicorn extractor.api.app:app --reload --port 8080
```

Comprobar liveness y el contrato:

```bash
curl -s http://localhost:8080/health
curl -s -H "Authorization: Bearer $EXTRACTOR_SHARED_SECRET" http://localhost:8080/v1/version
curl -s http://localhost:8080/metrics | head
```

Extraer un fixture golden sin HTTP:

```bash
uv run python -m extractor.cli extract \
  --file tests/fixtures/golden/acme-single/catalog.pdf \
  --profile tests/fixtures/golden/acme-single/profile.json
```

Muestrear layout (`POST /v1/sample` vía CLI):

```bash
uv run python -m extractor.cli sample \
  --file tests/fixtures/golden/acme-single/catalog.pdf
```

Colección Bruno (HTTP local): `greenery-extractor/` con environment `local`.

### Tests

```bash
uv run pytest -m "not slow"
uv run ruff check . && uv run mypy src
```

## Despliegue

- Imagen: `Dockerfile` (build arg `WITH_OCR=true` solo si hace falta tesseract).
- Railway: `railway.toml` — publicar **solo en red privada**; el worker apunta al hostname
  interno (ver `docs/08-despliegue.md`).
- Observabilidad: logs JSON a stdout; Prometheus en `/metrics`.

## Documentación

Empieza por **[`CLAUDE.md`](CLAUDE.md)** — reglas del servicio, comandos y convenciones.
El plan de trabajo está en [`docs/09-plan-de-implementacion.md`](docs/09-plan-de-implementacion.md).

| | |
|---|---|
| [01 · Contexto y alcance](docs/01-contexto-y-alcance.md) | Dónde encaja, qué hace y qué no |
| [02 · Contrato de API](docs/02-contrato-api.md) | Endpoints, esquemas, errores, límites |
| [03 · Perfil de extracción](docs/03-perfil-de-extraccion.md) | El esquema completo, con ejemplos |
| [04 · Modelo de salida](docs/04-modelo-de-salida.md) | Filas, issues, diagnósticos |
| [05 · Motor de extracción](docs/05-motor-de-extraccion.md) | El algoritmo, el fingerprint, las estrategias |
| [06 · Arquitectura](docs/06-arquitectura.md) | Carpetas, capas, cómo extender |
| [07 · Pruebas](docs/07-pruebas.md) | Golden set, determinismo, property tests |
| [08 · Despliegue](docs/08-despliegue.md) | Docker, Railway, SSRF, observabilidad |
| [09 · Plan de implementación](docs/09-plan-de-implementacion.md) | Ocho hitos con criterios de aceptación |

## Licencia

Propiedad de Snappiffy. Uso interno del proyecto Greenary App.
