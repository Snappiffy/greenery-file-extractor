# 02 · Contrato de API

Todos los endpoints bajo `/v1`. `Content-Type: application/json` salvo donde se indique.

## Autenticación

Cabecera `Authorization: Bearer <EXTRACTOR_SHARED_SECRET>` en todo endpoint salvo
`/health`. La comparación se hace con `secrets.compare_digest` (tiempo constante), nunca
con `==`.

En Railway el servicio se publica **solo en la red privada**; el secreto compartido es la
segunda capa, no la única.

---

## `POST /v1/extract`

Extrae filas de un documento aplicando un perfil.

### Petición

```jsonc
{
  "document": {
    // exactamente uno de "url" o "inline_base64"
    "url": "https://r2.example.com/raw/ab12...?X-Amz-Signature=...",
    "inline_base64": null,
    "content_type": "application/pdf",     // ver tabla de tipos soportados
    "filename": "spring-availability-2026.pdf",  // solo para logs y diagnósticos
    "sha256": "ab12cd34..."                // opcional; si viene, se verifica tras descargar
  },
  "profile": { /* ver docs/03-perfil-de-extraccion.md */ },
  "options": {
    "ocr": "auto",                          // "never" | "auto" | "force"   (def. "auto")
    "max_pages": 200,                       // def. 200
    "include_bbox": true,                   // def. true
    "include_raw_words": false,             // def. false — solo para depuración, pesa mucho
    "fail_on_fingerprint_mismatch": true    // def. true
  }
}
```

**Tipos soportados** (`content_type`):

| MIME | Extensión | Motor |
|---|---|---|
| `application/pdf` | `.pdf` | PyMuPDF; `pdfplumber` si la estrategia es `ruling` |
| `image/png` | `.png` | Pillow → OCR |
| `image/jpeg` | `.jpg` | Pillow → OCR |
| `image/tiff` | `.tif` | Pillow → OCR |

Cualquier otro tipo devuelve `415 UNSUPPORTED_CONTENT_TYPE`. **No** se infiere el tipo por
la extensión del nombre de archivo: manda `content_type`.

### Respuesta `200 OK`

```jsonc
{
  "engine_version": "1.0.0",
  "profile_version": 3,
  "layout": {
    "fingerprint": "sha256:9f2a...",
    "expected_fingerprint": "sha256:9f2a...",
    "matched": true,
    "page_count": 6,
    "pages_processed": 6,
    "page_geometry": { "width": 612.0, "height": 792.0, "rotation": 0 }
  },
  "rows": [ /* ver docs/04-modelo-de-salida.md */ ],
  "diagnostics": {
    "rows_extracted": 187,
    "rows_dropped": 12,
    "rows_with_errors": 3,
    "rows_with_warnings": 14,
    "issues_by_code": { "PRICE_UNPARSEABLE": 3, "SIZE_UNRECOGNIZED": 11 },
    "dropped_by_reason": { "matched_stop_pattern": 4, "empty_row": 8 },
    "ocr_used": false,
    "ocr_mean_confidence": null,
    "strategy_used": "columns",
    "duration_ms": 1842,
    "warnings": ["page 5 has 2 words crossing a column boundary"]
  }
}
```

**`200` no significa «todo bien».** Significa «el documento se pudo leer». La calidad se
lee en `diagnostics` y en los `issues` de cada fila. Es el worker quien decide si esa
calidad basta, aplicando su guarda de completitud.

### Errores

| HTTP | `code` | Cuándo |
|---|---|---|
| 400 | `INVALID_PROFILE` | El perfil no valida contra el esquema, o es incoherente (p. ej. dos columnas con el mismo `role`) |
| 400 | `INVALID_REQUEST` | Faltan campos, o vienen `url` e `inline_base64` a la vez |
| 401 | `UNAUTHORIZED` | Secreto ausente o incorrecto |
| 409 | `FINGERPRINT_MISMATCH` | El layout no coincide y `fail_on_fingerprint_mismatch` es `true` |
| 413 | `DOCUMENT_TOO_LARGE` | Supera `MAX_DOCUMENT_BYTES` o `max_pages` |
| 415 | `UNSUPPORTED_CONTENT_TYPE` | Tipo no soportado |
| 422 | `DOCUMENT_UNREADABLE` | PDF corrupto, cifrado sin contraseña, o cero páginas |
| 422 | `SHA256_MISMATCH` | Se mandó `sha256` y no coincide con lo descargado |
| 422 | `NO_ROWS_FOUND` | El documento se leyó pero el perfil no produjo ninguna fila. Casi siempre es perfil desactualizado |
| 502 | `SOURCE_FETCH_FAILED` | La URL firmada falló, expiró o dio no-2xx |
| 504 | `EXTRACTION_TIMEOUT` | Superó `EXTRACTION_TIMEOUT_SECONDS` |

Cuerpo de error, siempre igual:

```jsonc
{
  "error": {
    "code": "FINGERPRINT_MISMATCH",
    "message": "El layout del documento no coincide con el perfil v3.",
    "detail": {
      "expected": "sha256:9f2a...",
      "actual": "sha256:71bd...",
      "changed": ["column_count", "header_text"],
      "hint": "Llama a POST /v1/sample para reconstruir el perfil."
    }
  }
}
```

`detail.changed` es importante: dice **qué** cambió del layout, no solo que cambió. Se
calcula comparando los componentes del fingerprint uno a uno (ver `docs/05`).

---

## `POST /v1/sample`

Devuelve evidencia del layout para que el worker construya o repare un perfil. **Este
endpoint no interpreta nada**: describe geometría.

### Petición

```jsonc
{
  "document": { /* igual que en /v1/extract */ },
  "options": {
    "pages": [1, 2],          // def. [1] — casi siempre basta la primera
    "max_lines_per_page": 120,
    "ocr": "auto"
  }
}
```

### Respuesta `200 OK`

```jsonc
{
  "engine_version": "1.0.0",
  "fingerprint": "sha256:9f2a...",
  "page_count": 6,
  "page_geometry": { "width": 612.0, "height": 792.0, "rotation": 0 },
  "is_scanned": false,
  "text_density": 0.87,
  "recommended_strategy": "columns",
  "pages": [
    {
      "number": 1,
      "lines": [
        { "top": 72.0, "x0": 52.1, "x1": 402.3, "text": "ACME NURSERY — SPRING 2026" },
        { "top": 118.4, "x0": 52.0, "x1": 540.0, "text": "BOTANICAL NAME        SIZE    PRICE   QTY" }
      ],
      "column_candidates": [
        { "x": 52.0, "support": 143, "sample": ["Ficus lyrata", "Monstera deliciosa"] },
        { "x": 268.5, "support": 139, "sample": ["10\"", "14\""] },
        { "x": 372.0, "support": 141, "sample": ["$42.50", "$68.00"] },
        { "x": 468.0, "support": 96,  "sample": ["12", "4"] }
      ],
      "ruling_lines": { "vertical": [], "horizontal": [110.0, 130.0] }
    }
  ]
}
```

`column_candidates` se calcula **determinísticamente**: histograma de las coordenadas `x0`
de todas las palabras de la página, agrupadas en cubos de 3 puntos, ordenado por posición,
filtrando los cubos cuyo `support` (número de palabras alineadas) esté por debajo del 15%
de las líneas de la página.

Esto importa: **el LLM del worker no tiene que encontrar la geometría, solo poner nombre a
los roles.** Es un problema mucho más fácil y mucho más difícil de equivocar.

---

## `GET /health`

Liveness. Sin autenticación, sin dependencias. `200 {"status":"ok"}` siempre que el proceso
responda.

## `GET /ready`

Readiness. Verifica que PyMuPDF importa y, si `OCR_ENABLED`, que el binario `tesseract`
existe y responde a `--version`.

```jsonc
{ "status": "ready", "checks": { "pymupdf": "ok", "tesseract": "ok" }, "engine_version": "1.0.0" }
```

Devuelve `503` con el mismo cuerpo y `"status": "degraded"` si algún check falla.

## `GET /v1/version`

```jsonc
{
  "engine_version": "1.0.0",
  "profile_schema_version": 1,
  "supported_strategies": ["columns", "ruling", "regex"],
  "supported_content_types": ["application/pdf", "image/png", "image/jpeg", "image/tiff"]
}
```

El worker lo consulta al arrancar y registra `engine_version` en cada `update_run`. Sin eso
no se puede saber con qué versión del motor se extrajo una corrida vieja.

---

## Límites

| Límite | Valor por defecto | Variable |
|---|---|---|
| Tamaño de cuerpo | 50 MB | `MAX_REQUEST_BYTES` |
| Tamaño de documento | 50 MB | `MAX_DOCUMENT_BYTES` |
| Páginas | 200 | `MAX_PAGES` |
| Timeout de extracción | 120 s | `EXTRACTION_TIMEOUT_SECONDS` |
| Timeout de descarga | 30 s | `FETCH_TIMEOUT_SECONDS` |
| Peticiones concurrentes por instancia | 4 | `MAX_CONCURRENCY` |

`MAX_CONCURRENCY` se aplica con un semáforo: la extracción es CPU-intensiva y saturar el
proceso degrada a todos por igual. Por encima del límite se responde `503` con
`Retry-After`, y el worker reintenta con backoff (pg-boss ya lo hace).

## Idempotencia

`/v1/extract` y `/v1/sample` son funciones puras del par (documento, perfil). No hay claves
de idempotencia ni hace falta: reintentar es seguro y produce el mismo resultado.
