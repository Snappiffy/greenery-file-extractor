# Plan maestro · Servicio Extractor

Especificación y plan de construcción del extractor de listas de precios de viveros
(*growers*) para Greenary App.

Documento único y autocontenido. **Este archivo manda** sobre cualquier otro del repo.

---

# 1 · Qué es el extractor

## 1.1 Definición

Un **microservicio HTTP sin estado** que recibe un documento (PDF o imagen) y un **perfil
de extracción**, y devuelve las filas de producto que contiene, con sus valores tipados y
un informe honesto de la calidad de la lectura.

## 1.2 Su función en una frase

> Convertir un documento con formato fijo en filas estructuradas, **de forma determinista
> y sin IA**, y decir con precisión qué no pudo leer.

Las dos mitades pesan lo mismo. Un extractor que lee bien el 90% y calla el 10% restante
es peor que uno que lee el 80% y lo dice, porque el primero corrompe el catálogo en
silencio y el segundo solo genera trabajo manual.

## 1.3 Por qué existe

Greenary compra a una decena de viveros. Cada uno manda su lista periódicamente, **cada
uno con un formato estricto que cambia una o dos veces al año**. Un formato estricto no
necesita un modelo de lenguaje que lo interprete: necesita un parser configurado.

El perfil es ese ajuste por grower. Vive en una tabla versionada, se corrige en minutos y
es auditable. Es el sustituto del *fine-tuning*.

## 1.4 Dónde encaja

```
  Worker (Bun)  ──POST /v1/extract──▶  EXTRACTOR  ──GET URL firmada──▶  Object storage
       ▲                                   │
       └────── filas + diagnósticos ───────┘
```

El **worker es el único cliente**. El extractor no llama a nadie salvo al object storage
para descargar el documento.

## 1.5 Fronteras

| Hace | No hace |
|---|---|
| Descargar el documento por URL firmada | Llamar a un LLM |
| Detectar el layout y calcular su huella | Emparejar contra el catálogo |
| Recortar celdas por geometría | Escribir en base de datos |
| Parsear precio, tamaño, cantidad, disponibilidad | Decidir si una fila se aplica |
| Reportar incidencias y diagnósticos | Guardar estado entre peticiones |
| Devolver evidencia de layout (`/v1/sample`) | Interpretar reglas de negocio |
| Parsear xlsx, xls o csv — **eso es del worker** | |

---

# 2 · Los cinco principios del diseño

Cada uno existe porque su ausencia produce un fallo concreto y caro.

1. **Determinismo absoluto.** Misma entrada y mismo perfil ⇒ misma salida, byte a byte.
   Sin `random`, sin `datetime.now()` en la lógica, sin iterar sobre `set`, sin depender
   del orden del sistema de archivos.

2. **El fallo nunca es silencioso.** Toda anomalía produce un `issue` con código y
   severidad. Si una fila salió rara y no hay issue, **es un bug del extractor**, no del
   documento.

3. **`raw` es sagrado.** Cada fila conserva el texto exacto que se leyó, además de lo
   parseado. Es la prueba documental y la base de la auditoría.

4. **Nada se adivina.** Si el documento es ambiguo, la respuesta correcta es un issue, no
   una heurística que acierte el 80% de las veces.

5. **Se construye contra documentos reales desde el día uno.** Un extractor validado solo
   con PDFs que él mismo genera aprueba su propio examen. Ver la puerta **P0**.

---

# 3 · Lo que debe ser capaz de hacer

Capacidades numeradas. Cada una tiene su prueba en §6.

## 3.1 Lectura del documento

- **A1** · Abrir un PDF nativo y extraer sus palabras con caja delimitadora (`x0, top, x1,
  bottom`), en orden determinista.
- **A2** · Abrir un PDF protegido con contraseña; rechazar sin ella con
  `DOCUMENT_UNREADABLE`, nunca con una traza.
- **A3** · Medir la densidad de texto y decidir si el documento es escaneado.
- **A4** · Enrutar a OCR según `options.ocr` = `never` | `auto` | `force`.
- **A5** · Abrir imágenes PNG, JPEG y TIFF vía OCR.
- **A6** · Respetar `document.pages` y `skip_pages_matching`.
- **A7** · Rechazar por encima de `MAX_PAGES` y `MAX_DOCUMENT_BYTES`, **cortando la
  descarga en curso**, no leyendo 2 GB y comprobando al final.
- **A8** · Descargar solo de hosts en la allowlist, sin seguir redirecciones, solo
  `https`, rechazando IPs privadas tras resolver el DNS.

## 3.2 Identidad del layout

- **B1** · Calcular una **huella del layout** sobre estructura, **nunca sobre datos**:
  tamaño de página, rotación, número y posición de columnas en cubos de 5 pt, y texto de
  cabecera normalizado **sin dígitos**.
- **B2** · Ser **estable** ante lo que cambia en cada envío: precios, cantidades, número
  de filas, fecha del encabezado, año de temporada.
- **B3** · Ser **sensible** a lo que invalida el perfil: columna desplazada, columna que
  aparece o desaparece, cabecera distinta, página de otro tamaño.
- **B4** · Devolver **qué componente** cambió (`detail.changed`), no solo que cambió.
- **B5** · Detener la extracción con `409` cuando no coincide y
  `fail_on_fingerprint_mismatch` es `true`.
- **B6** · **Nunca declarar `matched: true` cuando no había huella previa contra la que
  comparar.** Ese caso se reporta como `matched: null` o `"unverified"`.

## 3.3 Recorte de celdas

Es la parte donde se rompen los extractores. Tres estrategias, un mismo contrato de
integridad.

- **C1** · Estrategia `columns`: asignar cada palabra a su columna según su `x0` y las
  `column_boundaries` del perfil.
- **C2** · Estrategia `ruling`: recuperar celdas de una tabla con líneas dibujadas.
- **C3** · Estrategia `regex`: una línea, un producto, por grupos nombrados.
- **C4** · **Conservar el texto.** La unión del texto de las celdas de una fila es igual al
  texto de la línea de origen. Ni se pierde ni se duplica ni una letra.
- **C5** · **Nunca partir una palabra entre dos celdas.** Una palabra pertenece a una
  celda y solo a una.
- **C6** · **Reportar el desbordamiento.** Cuando una palabra cruza un límite de columna,
  emitir `TEXT_CROSSES_BOUNDARY` — **en las tres estrategias, sin excepción**.
- **C7** · Detectar que el número de celdas no cuadra con los roles del perfil y emitir
  `ROW_COLUMN_COUNT_MISMATCH`, en vez de acomodar las celdas corridas.
- **C8** · Agrupar palabras en líneas por proximidad vertical con `row_tolerance`, usando
  media ponderada por ancho para que un superíndice no arrastre la línea.
- **C9** · Fusionar líneas de continuación cuando un nombre largo se parte en dos, según
  cinco condiciones: `multiline.enabled`, la celda de nombre tiene contenido, **todas** las
  celdas ancla están vacías, el hueco vertical es menor que
  `continuation_max_gap`, y la línea anterior existe y no fue descartada.

## 3.4 Parseo de valores

- **D1** · Precio como `Decimal`, **nunca `float`**, ni siquiera como paso intermedio.
  Gestiona símbolos, separadores de millar y decimal, rangos (`40.00 - 55.00`), y precios
  implausibles.
- **D2** · Tamaño con `dimension` **explícito del perfil** (`pot_diameter`, `pot_volume`,
  `plant_height`, `spread`). Si dos patrones casan con dimensiones distintas →
  `SIZE_AMBIGUOUS`, no se elige por orden.
- **D3** · Tamaño **siempre separado del nombre**, incluso si vienen en la misma celda.
- **D4** · `quantity` vacío ⇒ `None`, **nunca `0`**. `None` = «el documento no lo dice»;
  `0` = «dice cero».
- **D5** · Disponibilidad por **igualdad exacta** tras normalizar, nunca por `contains`:
  «no stock» no debe casar con «stock».
- **D6** · Ningún parser lanza excepción con ninguna cadena Unicode. Devuelven
  `(valor|None, [issues])`.

## 3.5 Honestidad del resultado

- **E1** · Cada fila devuelve **tres vistas separadas**: `raw` (el texto exacto), `text`
  (normalizado) y `parsed` (tipado).
- **E2** · Cada fila devuelve su `bbox`, para que la pantalla de revisión pueda señalar el
  sitio exacto del documento.
- **E3** · Toda anomalía produce un `issue` con `code`, `severity` (`error` | `warning` |
  `info`), `field` y `detail`.
- **E4** · Una fila con issues de severidad `error` **se devuelve igualmente**, con
  `parsed` parcialmente relleno. El extractor nunca decide por el worker.
- **E5** · **Toda fila descartada se registra con su motivo y su contenido.** Un
  `dropped_by_reason` agregado sin las filas hace imposible auditar por qué se fue el 27%
  de un documento.
- **E6** · Los diagnósticos agregados **cuadran** con la suma de las filas.
- **E7** · Cuando un issue supera un umbral de frecuencia (ej. `TEXT_CROSSES_BOUNDARY` en
  más del 2% de las filas), aparece además en `diagnostics.warnings` como señal de que el
  perfil está desfasado.

## 3.6 Evidencia de layout (`/v1/sample`)

- **F1** · Devolver líneas con coordenadas, candidatos de columna y líneas de tabla
  detectadas, para que el worker construya un perfil nuevo.
- **F2** · Calcular los candidatos de columna **determinísticamente**: histograma de `x0`
  de todas las palabras, en cubos de 3 pt, filtrando los que no alcancen el 15% de las
  líneas de la página.
- **F3** · Recomendar estrategia: si hay líneas verticales → `ruling`; si los candidatos
  son estables → `columns`; si no → `regex`.
- **F4** · No interpretar nada. El endpoint describe geometría; **poner nombre a los roles
  es trabajo del worker**.

## 3.7 Operación

- **G1** · Sin estado: nada persiste entre peticiones, ni en disco ni en variables
  globales.
- **G2** · Sin red durante la extracción. La única salida es la descarga inicial.
- **G3** · Semáforo de concurrencia; por encima, `503` con `Retry-After`.
- **G4** · Timeout de extracción efectivo; al superarlo, `504` y el proceso sigue sano.
- **G5** · Logs JSON estructurados **sin contenido del documento**: ni texto de filas, ni
  precios, ni nombres de planta, ni la URL firmada completa.
- **G6** · Métricas Prometheus.
- **G7** · CLI de depuración que extrae sin levantar el servidor.

---

# 4 · Contrato

## 4.1 Endpoints

| Método | Ruta | Para qué |
|---|---|---|
| `POST` | `/v1/extract` | Extraer filas aplicando un perfil |
| `POST` | `/v1/sample` | Devolver evidencia de layout |
| `GET` | `/health` | Liveness, sin dependencias |
| `GET` | `/ready` | Readiness: PyMuPDF carga, tesseract existe si procede |
| `GET` | `/v1/version` | `engine_version`, estrategias y tipos soportados |
| `GET` | `/metrics` | Prometheus |

Autenticación: `Authorization: Bearer <EXTRACTOR_SHARED_SECRET>`, comparado con
`secrets.compare_digest`. En Railway el servicio solo se publica en red privada.

## 4.2 Petición de extracción

```jsonc
{
  "document": {
    "url": "https://…firmada…",        // uno de los dos, nunca ambos
    "inline_base64": null,
    "content_type": "application/pdf",
    "filename": "spring-2026.pdf",
    "sha256": "ab12…"                   // opcional; si viene, se verifica
  },
  "profile": { /* §4.4 */ },
  "options": {
    "ocr": "auto",                      // never | auto | force
    "max_pages": 200,
    "include_bbox": true,
    "fail_on_fingerprint_mismatch": true
  }
}
```

Tipos soportados: `application/pdf`, `image/png`, `image/jpeg`, `image/tiff`.
**El tipo se toma de `content_type`, nunca de la extensión del nombre.**

## 4.3 Respuesta

```jsonc
{
  "engine_version": "1.0.0",
  "profile_version": 3,
  "layout": {
    "fingerprint": "sha256:9f2a…",
    "expected_fingerprint": "sha256:9f2a…",
    "matched": true,                    // null si no había huella previa
    "page_count": 6, "pages_processed": 6,
    "page_geometry": { "width": 612.0, "height": 792.0, "rotation": 0 }
  },
  "rows": [ /* §4.5 */ ],
  "dropped_rows": [ /* §4.6 — obligatorio */ ],
  "diagnostics": { /* §4.7 */ }
}
```

**`200` no significa «todo bien».** Significa «el documento se pudo leer». La calidad se
lee en `diagnostics` y en los `issues`.

### Errores

| HTTP | `code` |
|---|---|
| 400 | `INVALID_PROFILE` · `INVALID_REQUEST` |
| 401 | `UNAUTHORIZED` |
| 409 | `FINGERPRINT_MISMATCH` |
| 413 | `DOCUMENT_TOO_LARGE` |
| 415 | `UNSUPPORTED_CONTENT_TYPE` |
| 422 | `DOCUMENT_UNREADABLE` · `SHA256_MISMATCH` · `NO_ROWS_FOUND` |
| 502 | `SOURCE_FETCH_FAILED` |
| 503 | `CONCURRENCY_LIMIT` |
| 504 | `EXTRACTION_TIMEOUT` |

```jsonc
{ "error": { "code": "FINGERPRINT_MISMATCH", "message": "…",
  "detail": { "expected": "…", "actual": "…", "changed": ["boundaries"],
              "actual_components": { … } } } }
```

## 4.4 El perfil

```jsonc
{
  "schema_version": 1, "version": 3,
  "layout_fingerprint": "sha256:…",          // null en el primer uso

  "document": { "kind": "pdf", "pages": "all", "skip_pages_matching": ["^\\s*TERMS"] },

  "table": {
    "strategy": "columns",                    // columns | ruling | regex
    "column_boundaries": [52.0, 268.5, 372.0, 468.0, 540.0],
    "boundary_tolerance": 4.0,
    "ruling": { "vertical_strategy": "lines", "horizontal_strategy": "lines",
                "snap_tolerance": 3.0 },
    "line_pattern": "^(?P<plant_name>.+?)\\s{2,}(?P<size>\\d+\"?)\\s+\\$(?P<price>[\\d,.]+)$",
    "header_anchor": { "text": "BOTANICAL NAME", "match": "contains",
                       "on_every_page": true, "offset_lines": 1 },
    "stop_patterns": ["^\\s*TOTAL\\b", "^Page \\d+"],
    "row_tolerance": 2.5,
    "multiline": { "enabled": true, "continuation_max_gap": 14.0, "join_with": " " }
  },

  "columns": [
    { "role": "plant_name",   "index": 0, "required": true },
    { "role": "size",         "index": 1, "required": true },
    { "role": "price",        "index": 2 },
    { "role": "quantity",     "index": 3 },
    { "role": "availability", "index": 4 },
    { "role": "grower_code",  "index": 5 },
    { "role": "notes",        "index": 6 }
  ],

  "parsing": {
    "price": { "strip": ["$", "USD"], "decimal_separator": ".",
               "thousands_separator": ",", "on_range": "min",
               "empty_means": "unknown", "max_reasonable": "10000.00" },
    "quantity": { "empty_means": "unknown", "on_non_numeric": "issue" },
    "availability": { "true_values": ["yes","available","in stock"],
                      "false_values": ["no","sold out"],
                      "empty_means": "true", "derive_from_quantity": false },
    "size": {
      "patterns": [
        { "regex": "(?P<v>\\d+(?:\\.\\d+)?)\\s*\"", "unit": "in",  "dimension": "pot_diameter" },
        { "regex": "#(?P<v>\\d+)",                   "unit": "gal", "dimension": "pot_volume" }
      ],
      "on_multiple_matches": "issue", "on_no_match": "issue"
    },
    "text": { "collapse_whitespace": true, "trim": true, "normalize_unicode": "NFKC" }
  },

  "filters": {
    "drop_rows_matching": { "plant_name": ["^$", "^NOTES?\\b"] },
    "drop_rows_where_all_empty": ["price", "quantity", "availability"],
    "min_plant_name_length": 3
  }
}
```

Validaciones que devuelven `400 INVALID_PROFILE`, nombrando el campo:

- Ningún `role` repetido.
- `plant_name` y `size` presentes y `required: true`.
- `column_boundaries` estrictamente creciente, mínimo 2 valores.
- Con `columns`, cada `index < len(column_boundaries) - 1`.
- Con `regex`, cada `role` declarado existe como grupo nombrado en `line_pattern`.
- Todos los regex compilan; si no, se dice **cuál**.

## 4.5 La fila

```jsonc
{
  "row_index": 42, "page": 2, "source_lines": [310, 311],
  "raw":  { "plant_name": "Ficus  lyrata   'Bambino'", "size": "10\"",
            "price": "$42.50", "quantity": "12", "availability": "" },
  "text": { "plant_name": "Ficus lyrata 'Bambino'", "…": "…" },
  "parsed": {
    "plant_name": "Ficus lyrata 'Bambino'",
    "size": { "magnitude": "10.0", "unit": "in",
              "dimension": "pot_diameter", "raw": "10\"" },
    "price": "42.50",            // string decimal, NUNCA número JSON
    "quantity": 12,              // int o null
    "availability": true,        // bool o null
    "grower_code": null, "notes": null
  },
  "issues": [ { "code": "…", "severity": "warning", "field": "…", "detail": "…" } ],
  "bbox": { "page": 2, "x0": 52.1, "top": 310.4, "x1": 540.0, "bottom": 322.9 }
}
```

## 4.6 Las filas descartadas

**Obligatorio.** Sin esto no se puede auditar un descarte masivo.

```jsonc
{ "row_index": 7, "page": 1, "reason": "matched_stop_pattern",
  "raw": { "plant_name": "TOTAL", "price": "1,240.00" },
  "bbox": { … } }
```

## 4.7 Diagnósticos

```jsonc
{
  "rows_extracted": 187, "rows_dropped": 12,
  "rows_with_errors": 3, "rows_with_warnings": 14,
  "issues_by_code": { "PRICE_UNPARSEABLE": 3 },
  "dropped_by_reason": { "matched_stop_pattern": 4, "empty_row": 8 },
  "pages_processed": 6, "pages_skipped": [7],
  "ocr_used": false, "ocr_mean_confidence": null,
  "strategy_used": "columns", "duration_ms": 1842,
  "warnings": ["14 palabras cruzan un límite de columna (7.5%) — revisar column_boundaries"]
}
```

## 4.8 Catálogo de `issues`

| Código | Severidad | Cuándo |
|---|---|---|
| `REQUIRED_COLUMN_EMPTY` | error | Columna con `required: true` vacía |
| `ROW_COLUMN_COUNT_MISMATCH` | error | El recuento de celdas no cuadra con el perfil |
| `LINE_PATTERN_NO_MATCH` | error | `regex`: la línea no casó |
| `PRICE_UNPARSEABLE` | error | Texto en la columna de precio que no es número |
| `PRICE_NEGATIVE` | error | |
| `PRICE_IMPLAUSIBLE` | warning | Supera `max_reasonable` |
| `PRICE_RANGE` | warning | Rango resuelto según `on_range` |
| `SIZE_UNRECOGNIZED` | error | Ningún patrón casó |
| `SIZE_AMBIGUOUS` | error | Dos patrones con `dimension` distinta |
| `SIZE_RECOVERED_FROM_NAME` | warning | El tamaño se extrajo del nombre |
| `QUANTITY_UNPARSEABLE` | warning | |
| `AVAILABILITY_UNKNOWN_TOKEN` | warning | |
| `AVAILABILITY_EMPTY_DEFAULTED` | info | Se aplicó `empty_means` |
| **`TEXT_CROSSES_BOUNDARY`** | **warning** | Una palabra cae a caballo de dos columnas |
| `MULTILINE_JOINED` | info | La fila se compuso uniendo 2+ líneas |
| `OCR_LOW_CONFIDENCE` | warning | |
| `ROW_LIKELY_HEADER` / `ROW_LIKELY_TOTAL` | info | Descartada por parecerlo |

---

# 5 · Las cuatro invariantes

Son **propiedades**, no fixtures: se verifican sobre cualquier documento, sintético o
real. Son lo que convierte un fallo silencioso en uno ruidoso.

## I1 · Conservación de texto

```
normalizar(concat(celdas_de_la_fila)) == normalizar(texto_de_la_línea_origen)
```

Si falla, el recorte perdió o duplicó texto. **Es la invariante más importante del
servicio.**

## I2 · Integridad de palabra

Ninguna palabra devuelta por el lector aparece partida entre dos celdas. Cada palabra está
íntegra en exactamente una celda.

> Esta invariante es la que impide el fallo típico: `Sansevieria Boncellensis` partido en
> `Sans Bonce` + `llensis`, con el sobrante cayendo en la columna del precio y
> desplazando todas las demás una posición.

## I3 · Coherencia de forma

El número de celdas de cada fila es el que declara el perfil. Si sobra o falta una, es un
problema de layout y se reporta como tal — **nunca se acomodan las celdas corridas**.

## I4 · Cuadre de diagnósticos

```
rows_extracted        == len(rows)
rows_dropped          == len(dropped_rows) == sum(dropped_by_reason.values())
sum(issues_by_code)   == total de issues en las filas
```

Un diagnóstico que no cuadra con sus filas es peor que no tenerlo, porque se usa para
decidir.

---

# 6 · Las pruebas que debe pasar

Siete niveles. Los marcados 🔴 son **puertas bloqueantes**: no se avanza sin ellas.

## 🔴 P0 · Puerta de entrada — documentos reales

**Antes de escribir una línea del motor de extracción.**

- [ ] Al menos **tres documentos reales de tres growers distintos**, anonimizados
      (precios sustituidos por valores del **mismo formato y longitud**, para no alterar
      el ancho de columna).
- [ ] Al menos uno con **nombres largos que desbordan su columna**.
- [ ] Al menos uno **multipágina con cabecera repetida**.
- [ ] Un cuarto documento: **el mismo grower con el layout cambiado**, para probar la
      huella.
- [ ] `tests/fixtures/real/<grower>/NOTES.md` explicando qué tiene de particular cada uno.

> **Sin esta puerta no se construye.** Un extractor validado solo con PDFs que él mismo
> genera aprueba su propio examen y falla el día uno en producción.

Los fixtures sintéticos se permiten **solo** para tests unitarios de funciones puras.
Nunca como golden set.

## P1 · Unidad — funciones puras

- [ ] Precio: símbolos, separadores, rangos, negativos, implausibles, vacío.
- [ ] Precio: round-trip `Decimal` → texto → `Decimal`.
- [ ] **Precio nunca pasa por `float`** — verificable porque `0.1 + 0.2 == 0.3` en `Decimal`.
- [ ] Tamaño: un patrón, varios con misma dimensión, varios con distinta, ninguno.
- [ ] Tamaño recuperado del nombre cuando la celda viene vacía.
- [ ] **`parse_quantity("")` devuelve `None`, nunca `0`.**
- [ ] Disponibilidad: igualdad exacta; «no stock» **no** casa con «stock».
- [ ] Normalización de texto es idempotente: `norm(norm(x)) == norm(x)`.
- [ ] Validación de perfil: rol repetido, índice fuera de rango, boundaries no crecientes,
      regex que no compila, grupo nombrado ausente — **cada uno nombra el campo**.

## P2 · Propiedad — con Hypothesis

- [ ] **Ningún parser lanza excepción con ninguna cadena Unicode.**
- [ ] Cualquier `Decimal` positivo formateado con los separadores del perfil se parsea de
      vuelta al mismo valor.
- [ ] La cadena vacía nunca produce `0` en cantidad.
- [ ] Si un patrón de tamaño casa, `magnitude > 0`.

## P3 · Geometría y huella

- [ ] Huella **idéntica en 10 ejecuciones** sobre el mismo documento.
- [ ] Mismo layout con **precios y fechas distintas** → **misma** huella.
- [ ] Columna desplazada 30 pt → huella **distinta**, `changed == ["boundaries"]`.
- [ ] Cabecera con otro texto → `changed == ["header_text"]`.
- [ ] Página de otro tamaño → `changed == ["page_size"]`.
- [ ] **Sin huella previa, `matched` no es `true`.**
- [ ] PDF cifrado sin contraseña → `DOCUMENT_UNREADABLE`, sin traza.
- [ ] PDF de cero páginas → `DOCUMENT_UNREADABLE`.

## 🔴 P4 · Integridad de celdas

**La puerta donde se juega la calidad del servicio.** Las cuatro invariantes, en las tres
estrategias, sobre los documentos reales de P0.

- [ ] **I1** conservación de texto.
- [ ] **I2** integridad de palabra.
- [ ] **I3** coherencia de forma.
- [ ] **I4** cuadre de diagnósticos.
- [ ] `TEXT_CROSSES_BOUNDARY` se emite en `columns`, `ruling` **y** `regex`.
- [ ] `ROW_COLUMN_COUNT_MISMATCH` se emite cuando el recuento no cuadra.
- [ ] **Caso de regresión obligatorio:** un nombre largo en una celda estrecha produce
      `TEXT_CROSSES_BOUNDARY` **y no corrompe las columnas siguientes**.
- [ ] Palabra antes de la primera frontera o después de la última → se asigna a la primera
      o la última, con issue.
- [ ] Columna vacía produce `""`, no `null` (`null` se reserva para «no existe esa columna»).
- [ ] Cuando `TEXT_CROSSES_BOUNDARY` supera el 2% de las filas, aparece en
      `diagnostics.warnings`.
- [ ] Fusión multilínea: se fusiona lo que debe, y **no** se fusiona una fila con precio
      legítimamente vacío pero con tamaño.

## 🔴 P5 · Golden set real

- [ ] Los tres documentos de P0 con su `.expected.json` **revisado fila por fila contra el
      PDF**.
- [ ] Los `.expected.json` están **congelados**, con su `sha256` verificado por un test: si
      el PDF cambia, la suite falla y obliga a revisar la expectativa.
- [ ] **Los fixtures no se regeneran en tiempo de test.** El generador, si existe, es un
      script manual en `scripts/`.
- [ ] Determinismo: dos extracciones del mismo fixture producen JSON byte-idéntico
      (excluyendo `duration_ms`).

> Un `.expected.json` generado y no revisado **no es un golden set: es un test que
> certifica el bug actual.** Es el error más caro de este plan.

## P6 · Contrato HTTP

- [ ] Cada código de error de §4.3 tiene un test que lo provoca.
- [ ] `409` incluye `changed` y `actual_components`.
- [ ] Con `fail_on_fingerprint_mismatch: false`, la misma petición da `200` con
      `matched: false`.
- [ ] Sin bearer → `401`; con bearer incorrecto → `401`.
- [ ] Documento con 0 filas → `NO_ROWS_FOUND`, **no** un `200` con lista vacía.
- [ ] Los `Decimal` se serializan como **string**; los `null` se emiten explícitamente.
- [ ] `/v1/sample`: los candidatos de columna coinciden con las `column_boundaries` del
      perfil dentro de ±4 pt; `recommended_strategy` acierta en los tres reales.
- [ ] `/ready` devuelve `degraded` si `OCR_ENABLED` y falta el binario.

## P7 · Robustez y SSRF

- [ ] Host fuera de la allowlist → rechazado.
- [ ] Redirección → no se sigue.
- [ ] Esquema `http` → rechazado.
- [ ] IP privada tras resolver DNS (`169.254.169.254`, `10/8`, `127/8`) → rechazada.
- [ ] Tamaño excedido → **se corta la descarga**, no se lee entero.
- [ ] PDF corrupto → error tipado.
- [ ] Documento de 200 páginas dentro del presupuesto de tiempo.

## P8 · Operación

- [ ] `MAX_CONCURRENCY=1` + dos peticiones simultáneas → la segunda `503` con `Retry-After`.
- [ ] Documento que excede el timeout → `504`, y el proceso sigue sano después.
- [ ] `/metrics` expone las seis métricas.
- [ ] **Test de fuga:** ninguna cadena de un fixture aparece en los logs emitidos durante
      el golden set.
- [ ] Los tests corren **sin red** (fixture global que bloquea `socket.connect`).
- [ ] La imagen Docker arranca como usuario no-root y `/health` responde.
- [ ] Test de capas: `domain` no importa `fitz`, `pdfplumber`, `fastapi` ni `httpx`.

---

# 7 · Criterios de aceptación

Medidos sobre el **golden set real**, no el sintético.

| Métrica | Umbral |
|---|---|
| Filas con issue de severidad `error` | **≤ 1%** |
| **Filas anómalas sin issue (fallo silencioso)** | **0** |
| Palabras partidas entre celdas | **0** |
| Filas descartadas sin contenido registrado | **0** |
| Invariantes I1–I4 | **todas, en las tres estrategias** |
| Determinismo | byte a byte |
| Cobertura de `domain/` | ≥ 95% |
| Duración p95, documento de 5 páginas | < 3 s |

La segunda fila es la que define «funciona». Un 5% de precios ilegibles es tolerable si el
sistema lo dice; **un solo fallo silencioso no lo es**.

---

# 8 · Plan de construcción

Ocho hitos. Uno por pull request.

| Hito | Contenido | Puerta de salida |
|---|---|---|
| **H0** | Conseguir y anonimizar los documentos reales. Andamiaje: `uv`, `ruff`, `mypy --strict`, `pytest`, Dockerfile, CI, test de capas, fixture sin-red | 🔴 **P0** |
| **H1** | Dominio puro: modelos, issues, perfil + validación, los cuatro parsers, CLI de depuración | P1, P2 |
| **H2** | Lector PyMuPDF con bbox, agrupado en líneas, huella del layout | P3 |
| **H3** | Estrategia `columns` + **las cuatro invariantes desde el primer commit** | 🔴 **P4** (parcial) |
| **H4** | `POST /v1/extract` completo, fetcher con SSRF, errores, filas descartadas con contenido | P6, P7 |
| **H5** | Estrategias `ruling` y `regex` — **cada una con sus invariantes** | 🔴 **P4** (completa) |
| **H6** | Golden set real congelado con expected revisados a mano | 🔴 **P5** |
| **H7** | `/v1/sample`, OCR, métricas, concurrencia, timeout, test de fuga, despliegue | P8 |

## Reglas de orden

1. **H0 no se salta.** Si no hay documentos reales, no se empieza. Es preferible esperar
   una semana a los archivos que construir un mes contra PDFs inventados.
2. **Las invariantes se implementan con la primera estrategia (H3), no al final.** Añadirlas
   después obliga a reescribir el recorte.
3. **`ruling` y `regex` no se implementan en el mismo commit.** Son dos mecanismos con dos
   defectos posiblemente distintos.
4. **Ninguna estrategia se da por terminada sin sus cuatro invariantes en verde.**

---

# 9 · Lo que NO hay que hacer

- ❌ **Generar los fixtures golden con el propio repo.** Es el error que invalida todo lo
  demás.
- ❌ **Regenerar fixtures en tiempo de test.** El input tiene que estar congelado.
- ❌ **Crear un `.expected.json` sin revisarlo fila por fila contra el documento.**
- ❌ **Añadir heurísticas que recompongan nombres partidos adivinando.** El recorte se
  arregla en la geometría.
- ❌ **Relajar un parser para que bajen los errores.** El problema sigue ahí, ahora
  invisible.
- ❌ **Llamar a un LLM.** Ni para inferir perfiles: eso es del worker, con la evidencia de
  `/v1/sample`.
- ❌ **Tocar base de datos.** El servicio no sabe qué es un `sku_id`.
- ❌ **Declarar `matched: true` sin huella previa contra la que comparar.**
- ❌ **Devolver `200` con lista vacía** cuando el perfil no produjo filas.
- ❌ **Registrar contenido del documento en los logs.**

---

# 10 · Stack y convenciones

| Pieza | Elección |
|---|---|
| Lenguaje | Python 3.12 |
| Dependencias | `uv`, lockfile comprometido, versiones **exactas** |
| API | FastAPI + Pydantic v2 |
| PDF (geometría) | PyMuPDF — motor principal |
| PDF (tablas con líneas) | `pdfplumber` — solo estrategia `ruling` |
| OCR | `pytesseract`, **desactivado por defecto** |
| Lint y formato | `ruff` |
| Tipos | `mypy --strict` sobre `src/` |
| Tests | `pytest` + `hypothesis` |
| Despliegue | Railway, red privada, usuario no-root |

**Capas:** `domain` ← `engine` ← `application` ← `api`, con `adapters` colgando de
`domain`. `domain` solo importa stdlib y `pydantic`. Verificado por test, no por
disciplina.

**Idioma:** documentación y comentarios en español; **todo identificador, clave de JSON,
nombre de archivo y mensaje de log en inglés.**

**Versionado:** `engine_version` en semver. Sube a **major** cualquier cambio que altere
la salida de un golden existente — incluida una actualización de PyMuPDF que mueva
coordenadas.

---

# 11 · Modo validación (`dry_run`) — perfiles automáticos

Añadido tras la decisión de eliminar el paso manual de aprobación de perfiles en el caso
común. El razonamiento completo está en el documento de proyecto
`claude/decision-perfiles-automaticos.md`.

## 11.1 El problema que resuelve

Que un cambio de plantilla de un grower bloquee una corrida hasta que alguien mire una
pantalla es fricción injustificada, y ocurre en momentos impredecibles (~10–20 veces al
año entre todos los growers).

**Pero regenerar el perfil en cada petición se muerde la cola:** si el perfil se infiere
del mismo documento que se va a extraer, encaja por construcción, y el fingerprint pierde
su única función — decir «este documento no se parece al que aprendí». Es el mismo error
que una suite que genera sus propios fixtures.

## 11.2 La solución: el extractor aporta la evidencia, no el veredicto

El worker decide si promueve un perfil candidato. El extractor le da los números con los
que decidir. Para eso necesita **una capacidad nueva**:

- **H1** · `options.dry_run: true` en `POST /v1/extract`. La extracción se ejecuta
  completa y se devuelve un **informe de validación**, con las filas **omitidas** de la
  respuesta salvo que se pidan.
- **H2** · El informe incluye todo lo que el worker necesita para puntuar, sin tener que
  recorrer las filas él mismo.
- **H3** · `dry_run` no cambia el comportamiento del motor: **la misma extracción produce
  los mismos números con `dry_run` activo o no**. Es una opción de respuesta, no de
  proceso.

### Bloque `validation` en la respuesta

```jsonc
{
  "validation": {
    "invariants": {
      "text_conservation": true,        // I1
      "word_integrity": true,           // I2
      "shape_coherence": true,          // I3
      "diagnostics_balance": true       // I4
    },
    "rows_total": 227,
    "error_rate": 0.008,                // filas con issue severity=error / rows_extracted
    "cross_boundary_rate": 0.004,       // TEXT_CROSSES_BOUNDARY / rows_extracted
    "column_mismatch_count": 0,
    "split_word_count": 0,
    "empty_required_rate": 0.012,
    "drop_rate": 0.27,                  // rows_dropped / (extracted + dropped)
    "distinct_sizes": 6,
    "distinct_names": 219
  }
}
```

`error_rate`, `cross_boundary_rate` y `split_word_count` son los tres números que deciden
si un perfil candidato es utilizable. El resto es contexto para el informe humano cuando
la validación falla.

> **El extractor no puntúa ni aprueba.** No conoce el catálogo, así que no puede evaluar el
> criterio más fuerte (cuántas filas emparejan contra lo que ya se sabe del grower). Eso es
> del worker. El extractor solo mide lo que puede medir con el documento delante.

## 11.3 Pruebas adicionales

Se añaden a **P4** y **P6**:

- [ ] `dry_run: true` y `dry_run: false` sobre el mismo documento y perfil producen
      **idénticos** `diagnostics` y `validation`.
- [ ] Con `dry_run: true`, `rows` viene vacío por defecto y presente con
      `include_rows: true`.
- [ ] Las cuatro invariantes del bloque `validation` coinciden con lo que reportan los
      issues de las filas (no son dos cálculos distintos).
- [ ] Un documento con una palabra partida da `word_integrity: false` **y**
      `split_word_count > 0`.
- [ ] `error_rate` y `cross_boundary_rate` cuadran con `issues_by_code` (extensión de I4).

## 11.4 Lo que el extractor sigue sin hacer

- ❌ Inferir el perfil. Sigue siendo del worker, con la evidencia de `/v1/sample`.
- ❌ Decidir si un perfil se promueve.
- ❌ Guardar perfiles.
- ❌ Comparar un perfil candidato con el anterior — no conoce el anterior.
