# 08 · Despliegue

Railway, junto al resto del stack de Greenary. El servicio se publica **solo en la red
privada**: el worker lo alcanza por su hostname interno y no hay dominio público.

## Variables de entorno

| Variable | Requerida | Def. | Qué hace |
|---|---|---|---|
| `EXTRACTOR_SHARED_SECRET` | sí | — | Bearer que el worker envía. Mínimo 32 caracteres |
| `LOG_LEVEL` | no | `INFO` | |
| `ENVIRONMENT` | no | `production` | `development` \| `staging` \| `production` |
| `MAX_REQUEST_BYTES` | no | `52428800` | 50 MB |
| `MAX_DOCUMENT_BYTES` | no | `52428800` | |
| `MAX_PAGES` | no | `200` | |
| `MAX_CONCURRENCY` | no | `4` | Semáforo de extracciones simultáneas |
| `EXTRACTION_TIMEOUT_SECONDS` | no | `120` | |
| `FETCH_TIMEOUT_SECONDS` | no | `30` | |
| `FETCH_ALLOWED_HOSTS` | sí | — | Lista separada por comas. **Ver SSRF abajo** |
| `OCR_ENABLED` | no | `false` | |
| `OCR_DENSITY_THRESHOLD` | no | `5.0` | Caracteres por pulgada² para decidir OCR en `auto` |
| `OCR_MIN_CONFIDENCE` | no | `70` | |
| `TESSERACT_CMD` | no | `tesseract` | |
| `UVICORN_WORKERS` | no | `2` | |

`.env.example` debe existir en el repo con todas, sin valores reales.

## SSRF: el riesgo real de este servicio

El servicio descarga una URL que le pasa el cliente. Si esa URL no se valida, cualquiera
que llegue al endpoint puede hacer que el servicio consulte `http://169.254.169.254/` (los
metadatos de la nube) o cualquier servicio interno.

Mitigación, obligatoria antes del primer despliegue:

1. **Allowlist de hosts** (`FETCH_ALLOWED_HOSTS`). Solo el dominio del bucket. Se compara
   el host **tras** resolver redirecciones, no antes.
2. **Sin seguir redirecciones** (`follow_redirects=False`). Una URL firmada de R2 o S3 no
   redirige.
3. **Solo `https`**.
4. **Rechazar IPs privadas y de loopback** tras resolver el DNS: `10/8`, `172.16/12`,
   `192.168/16`, `127/8`, `169.254/16`, `::1`, `fc00::/7`.
5. **Límite de tamaño durante la descarga**, no después: cortar el stream al superar
   `MAX_DOCUMENT_BYTES` en vez de leer 2 GB en memoria y comprobar al final.

Hay un test por cada uno de estos cinco puntos en `tests/unit/adapters/test_fetch_ssrf.py`.

## Dockerfile

```dockerfile
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# Dependencias del sistema. tesseract solo si OCR_ENABLED
ARG WITH_OCR=false
RUN apt-get update && apt-get install -y --no-install-recommends \
      libgl1 libglib2.0-0 \
 && if [ "$WITH_OCR" = "true" ]; then \
      apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng; \
    fi \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Capa de dependencias, cacheable
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=3).status==200 else 1)"

CMD ["uv", "run", "uvicorn", "extractor.api.app:app", \
     "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
```

Notas que importan:

- **Usuario no root.** El servicio procesa archivos que vienen de fuera; correr como root
  es regalar el contenedor ante un fallo de PyMuPDF.
- **`--frozen`.** El build falla si `uv.lock` no está sincronizado con `pyproject.toml`.
  Reproducibilidad no negociable: la versión exacta de PyMuPDF afecta a la extracción.
- **`WITH_OCR` como build arg.** Sin tesseract la imagen pesa menos de la mitad. Se
  construye con OCR solo cuando `OCR_ENABLED=true`.
- **Sin `--reload` ni volúmenes** en producción.

## Dimensionado

El consumo es CPU y memoria transitoria. Regla práctica: **cada extracción concurrente
necesita ~250 MB** para un PDF de 200 páginas, más el documento en memoria.

| Perfil | vCPU | RAM | `UVICORN_WORKERS` | `MAX_CONCURRENCY` |
|---|---|---|---|---|
| Arranque | 1 | 1 GB | 2 | 2 |
| Normal | 2 | 2 GB | 2 | 4 |
| Con OCR | 4 | 4 GB | 2 | 2 |

Con OCR la concurrencia **baja**, no sube: tesseract satura el CPU y lanzar cuatro a la vez
solo alarga la latencia de todos.

Escalar horizontalmente (más réplicas) antes que verticalmente: el servicio es sin estado y
esa es su ventaja.

## Observabilidad

### Logs

JSON estructurado a stdout, un objeto por línea:

```json
{"ts":"2026-09-19T14:22:01.482Z","level":"info","event":"extract.completed",
 "request_id":"01JF...","grower_id":"0192e7b4-...","profile_version":3,
 "content_type":"application/pdf","pages":6,"rows_extracted":187,
 "rows_with_errors":3,"strategy":"columns","ocr_used":false,"duration_ms":1842}
```

**Nunca se registra:** el contenido del documento, el texto de una fila, un precio, un
nombre de planta, la URL firmada completa (solo su host y el hash del path), ni el
`EXTRACTOR_SHARED_SECRET`. Hay un test que recorre los logs emitidos durante el golden set
y falla si aparece cualquier cadena de un fixture.

`request_id` se acepta de la cabecera `X-Request-Id` si viene y se genera si no. El worker
lo propaga desde el `update_run`, y así una corrida se puede seguir de punta a punta.

### Métricas

Prometheus en `/metrics` (solo red privada):

| Métrica | Tipo | Etiquetas |
|---|---|---|
| `extractor_requests_total` | counter | `endpoint`, `status` |
| `extractor_duration_seconds` | histogram | `endpoint`, `strategy`, `ocr` |
| `extractor_rows_extracted` | histogram | `strategy` |
| `extractor_issues_total` | counter | `code`, `severity` |
| `extractor_fingerprint_mismatch_total` | counter | — |
| `extractor_concurrency_rejected_total` | counter | — |

`extractor_fingerprint_mismatch_total` merece una alerta: si sube, un grower cambió su
plantilla y hay corridas detenidas esperando un perfil nuevo.

### Alertas mínimas

| Condición | Significa |
|---|---|
| `fingerprint_mismatch` > 0 en 1 h | Cambio de plantilla; hay que reparar un perfil |
| p95 de `duration_seconds` > 30 s | Documentos más grandes, o OCR activándose sin querer |
| `concurrency_rejected` > 0 sostenido | Faltan réplicas |
| `/ready` en `degraded` > 2 min | Falta tesseract o PyMuPDF no carga |

## Versionado

`engine_version` sigue semver y vive en `src/extractor/__init__.py`.

- **Patch** — corrección que no cambia ninguna salida.
- **Minor** — funcionalidad nueva (una estrategia, un formato) que no cambia la salida de
  los perfiles existentes.
- **Major** — **cualquier cambio que altere la salida de un golden existente**, incluida
  una subida de versión de PyMuPDF que mueva coordenadas.

Esa tercera regla es la que importa: el worker guarda `engine_version` en cada
`update_run`, y sin ella no se puede explicar por qué una corrida de marzo y una de
septiembre leyeron el mismo documento distinto.
