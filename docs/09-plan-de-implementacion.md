# 09 · Plan de implementación

Ocho hitos ordenados. **Cada uno se cierra cuando sus criterios de aceptación pasan en
verde**, y no se empieza el siguiente antes. El orden no es arbitrario: cada hito deja algo
verificable sobre lo que se apoya el que sigue.

Para un agente de codificación: trabaja un hito por sesión o por pull request. No mezcles.

---

## M0 · Andamiaje

**Objetivo:** un repo que arranca, se testea y se despliega, sin lógica todavía.

- `pyproject.toml` con `uv`, Python 3.12, dependencias de runtime y de desarrollo separadas
  en extras.
- `ruff` (lint + formato) y `mypy --strict` sobre `src/` configurados en `pyproject.toml`.
- `src/extractor/config.py` con `Settings` (pydantic-settings) leyendo todas las variables
  de `docs/08`. **Único punto del código que lee `os.environ`.**
- `src/extractor/api/app.py` con `create_app()`, `/health`, `/ready` y `/v1/version`.
- Autenticación bearer con `secrets.compare_digest`.
- Logging JSON estructurado con `request_id`.
- `Dockerfile` (el de `docs/08`), `.dockerignore`, `.env.example`.
- GitHub Actions con lint, tipos y tests.
- `tests/test_layering.py` — ya, desde el primer día, aunque solo haya dos capas.
- `tests/conftest.py` con el fixture `no_network` autouse.

**Aceptación**

- [ ] `uv sync && uv run pytest && uv run ruff check . && uv run mypy src` en verde
- [ ] `docker build -t extractor . && docker run -p 8080:8080 extractor` responde `200` en `/health`
- [ ] `/v1/extract` sin bearer devuelve `401`; con bearer correcto devuelve `501` (aún no implementado)
- [ ] CI en verde

---

## M1 · Dominio y parsers

**Objetivo:** toda la lógica pura, sin tocar un solo PDF. Es la parte que más errores
produce en producción y la más barata de testear aquí.

- `domain/models.py`: `Word`, `Line`, `Cell`, `Row`, `Size`, `Issue`, `Diagnostics`.
- `domain/issues.py`: enum `IssueCode` con **todos** los códigos de la tabla de `docs/04`,
  y `Severity`.
- `domain/profile.py`: el modelo completo de `docs/03`, con la validación semántica
  (roles no repetidos, `plant_name` y `size` presentes, índices dentro de rango, regex que
  compilan, `column_boundaries` creciente).
- `domain/parsing/`: `text`, `price`, `size`, `quantity`, `availability`, exactamente con
  los algoritmos de `docs/05` § Paso 13.
- `domain/errors.py`.
- `cli.py` con el subcomando `parse` para probar un parser desde la terminal.

**Aceptación**

- [ ] Cobertura de `domain/` ≥ 95%
- [ ] Property tests con `hypothesis`: ningún parser lanza excepción con ninguna cadena
- [ ] Test explícito: `parse_quantity("")` devuelve `None`, **nunca** `0`, con la configuración por defecto
- [ ] Test explícito: `parse_price` nunca usa `float` — verificado porque el resultado es `Decimal` y `Decimal("0.1") + Decimal("0.2") == Decimal("0.3")`
- [ ] Un perfil con dos columnas del mismo `role` lanza el error de dominio correspondiente
- [ ] `mypy --strict` sin `type: ignore` en `domain/`

---

## M2 · Lectura de PDF y fingerprint

**Objetivo:** abrir un PDF y describirlo. Todavía sin extraer filas.

- `adapters/readers/base.py`: protocolo `DocumentReader -> list[Page[Word]]`.
- `adapters/readers/pymupdf_reader.py`: palabras con bbox, orden determinista
  `(round(top,1), round(x0,1), text)`.
- `engine/lines.py`: agrupado en líneas con `row_tolerance` y media ponderada por ancho.
- `domain/fingerprint.py`: componentes, hash y comparación con `changed`, exactamente como
  en `docs/05` § Paso 6.
- Detección de `is_scanned` y `text_density`.

**Aceptación**

- [ ] Sobre un fixture, el fingerprint es idéntico en 10 ejecuciones
- [ ] Dos versiones del mismo documento con precios y fechas distintas dan **el mismo** fingerprint
- [ ] Una versión con una columna desplazada 30 pt da un fingerprint **distinto**, y `changed == ["boundaries"]`
- [ ] Un PDF cifrado sin contraseña produce `DOCUMENT_UNREADABLE`, no una traza

---

## M3 · `POST /v1/extract` con estrategia `columns`

**Objetivo:** el camino principal completo, de punta a punta. Es el hito que hace útil el
servicio.

- `engine/strategies/columns.py` con los casos especiales de `docs/05` § Paso 10
  (palabra a caballo, fuera de rango, columna vacía).
- `engine/header.py`, `engine/filters.py`.
- `engine/merge.py` (fusión multilínea, las cinco condiciones).
- `application/extract_document.py`.
- `adapters/fetch/http_fetcher.py` **con las cinco mitigaciones de SSRF de `docs/08`**.
- `api/schemas.py`, `api/routes.py`, `api/error_handlers.py` con todos los códigos de error
  de `docs/02`.
- Primeros tres fixtures del golden set: una página, varias páginas, nombres multilínea.

**Aceptación**

- [ ] Los tres fixtures pasan contra su `.expected.json` revisado a mano
- [ ] `test_determinism` pasa
- [ ] Los cinco tests de SSRF pasan
- [ ] Una fila con precio ilegible se devuelve con `raw` intacto, `parsed.price = null` y el issue — la petición sigue siendo `200`
- [ ] Todos los códigos de error de `docs/02` tienen un test que los provoca
- [ ] Los `null` se serializan explícitamente y los `Decimal` como string

---

## M4 · `POST /v1/sample`

**Objetivo:** que el worker pueda construir un perfil para un grower nuevo.

- `application/sample_document.py`.
- Histograma de `x0` en cubos de 3 pt, filtrado por `support ≥ 15%` de las líneas.
- `ruling_lines` vía `pdfplumber`.
- `recommended_strategy` con la heurística: si hay líneas verticales → `ruling`; si los
  candidatos de columna tienen `support` alto y estable → `columns`; si no → `regex`.
- Muestras de texto por columna candidata (máximo 3, las tres primeras filas de datos).

**Aceptación**

- [ ] Sobre los tres fixtures de M3, los `column_candidates` coinciden con los
      `column_boundaries` de su perfil dentro de ±4 pt
- [ ] `recommended_strategy` acierta en los tres
- [ ] La respuesta no supera 200 KB con `max_lines_per_page = 120`

---

## M5 · Estrategias `ruling` y `regex`

- `engine/strategies/ruling.py` sobre `pdfplumber.extract_tables()`.
- `engine/strategies/regex.py` con grupos nombrados.
- Validación de perfil específica de cada una.
- Dos fixtures nuevos, uno por estrategia.

**Aceptación**

- [ ] Los dos fixtures nuevos pasan
- [ ] Un perfil `regex` cuyo `line_pattern` no declara un grupo para un `role` declarado da `400 INVALID_PROFILE` con el nombre del rol que falta
- [ ] `GET /v1/version` lista las tres estrategias

---

## M6 · Fingerprint como guarda operativa

**Objetivo:** que un cambio de plantilla se detenga en vez de extraerse mal. Es la razón de
ser del fingerprint y merece su propio hito.

- `fail_on_fingerprint_mismatch` aplicado en el caso de uso.
- `409` con `detail.changed` y `detail.actual_components`.
- Detección de `TEXT_CROSSES_BOUNDARY` agregada y añadida a `diagnostics.warnings` cuando
  supera el 2% de las filas.
- Métrica `extractor_fingerprint_mismatch_total`.

**Aceptación**

- [ ] Fixture de layout cambiado → `409` con `changed` correcto
- [ ] Con `fail_on_fingerprint_mismatch: false` la misma petición devuelve `200` y
      `layout.matched = false`
- [ ] Un fixture con `column_boundaries` deliberadamente desfasados 20 pt produce el
      warning agregado

---

## M7 · OCR

- `adapters/ocr/tesseract.py` y `adapters/readers/image_reader.py`.
- Decisión `never` / `auto` / `force` según `docs/05` § Paso 4.
- Confianza por palabra y por fila, `OCR_LOW_CONFIDENCE`.
- Build arg `WITH_OCR` en el Dockerfile.

**Aceptación**

- [ ] Un PDF escaneado produce filas con `ocr_used: true` y confianza media reportada
- [ ] Con `ocr: "never"`, ese mismo PDF da `422 DOCUMENT_UNREADABLE`
- [ ] La imagen sin `WITH_OCR` arranca y `/ready` devuelve `degraded` si `OCR_ENABLED=true`
- [ ] Los tests `ocr` se saltan limpiamente si no hay binario

---

## M8 · Producción

- Métricas Prometheus completas.
- Semáforo `MAX_CONCURRENCY` con `503` y `Retry-After`.
- Timeout de extracción efectivo (no solo configurado).
- Test de fuga de logs: recorre lo emitido durante el golden set y falla si aparece
  cualquier cadena de un fixture.
- Despliegue en Railway con red privada, y el worker apuntando al hostname interno.
- `README.md` con el quickstart real, ya verificado.

**Aceptación**

- [ ] `/metrics` expone las seis métricas de `docs/08`
- [ ] Con `MAX_CONCURRENCY=1`, dos peticiones simultáneas → la segunda da `503` con `Retry-After`
- [ ] Un documento que excede el timeout da `504`, y el proceso sigue sano después
- [ ] El test de fuga de logs pasa
- [ ] El worker en staging completa una corrida real de punta a punta

---

## Fuera de alcance de esta versión

Documentado aquí para que no se cuele:

- Cualquier llamada a un modelo de lenguaje.
- Parseo de xlsx, xls o csv — va en el worker.
- Emparejamiento contra el catálogo.
- Persistencia de perfiles, documentos o resultados.
- Caché de extracciones.
- Interfaz de usuario.

## Dependencias externas de este plan

| Bloqueo | Quién | Necesario para |
|---|---|---|
| Documentos reales de 3 growers, anonimizados | Greenary / Manuel | M3 |
| Un documento con layout cambiado del mismo grower | Greenary / Manuel | M6 |
| Un escaneado real, si existe | Greenary / Manuel | M7 (si no aparece, M7 se pospone) |
| Bucket R2/S3 de staging con URLs firmadas | Infra | M3 |
| Decisión de P-01 (dimensión del tamaño) | Cliente | No bloquea este servicio: se transporta como `dimension` explícito. Bloquea al worker |
