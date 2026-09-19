# 03 · El perfil de extracción

El perfil es **el sustituto del fine-tuning**. Todo lo que es particular de un grower vive
aquí: dónde están las columnas, cómo escribe los tamaños, qué palabras usa para decir que
algo está agotado, qué líneas hay que ignorar.

Lo guarda el worker en `plant_catalog.grower_ingest_profile`, versionado. Este servicio lo
recibe en cada petición y **no lo persiste**.

## Esquema completo

```jsonc
{
  "schema_version": 1,
  "profile_id": "0192f3a1-...",       // opaco; solo se devuelve en diagnósticos
  "grower_id": "0192e7b4-...",        // opaco
  "version": 3,                        // versión del perfil, para trazabilidad
  "layout_fingerprint": "sha256:9f2a...",   // null en el primer uso

  "document": {
    "kind": "pdf",                     // "pdf" | "image"
    "pages": "all",                    // "all" | "1-3" | [1,2,5]
    "skip_pages_matching": [           // regex; si la página 1 casa, se salta entera
      "^\\s*TERMS AND CONDITIONS",
      "^\\s*DELIVERY SCHEDULE"
    ],
    "password": null                   // PDFs protegidos; normalmente null
  },

  "table": {
    "strategy": "columns",             // "columns" | "ruling" | "regex"

    // --- solo para strategy = "columns" ---
    "column_boundaries": [52.0, 268.5, 372.0, 468.0, 540.0],
    "boundary_tolerance": 4.0,         // pts; margen para asignar una palabra a una columna

    // --- solo para strategy = "ruling" ---
    "ruling": { "vertical_strategy": "lines", "horizontal_strategy": "lines", "snap_tolerance": 3.0 },

    // --- solo para strategy = "regex" ---
    "line_pattern": "^(?P<plant_name>.+?)\\s{2,}(?P<size>\\d+\"?)\\s+\\$(?P<price>[\\d,.]+)$",

    // --- comunes ---
    "header_anchor": {                 // dónde empiezan los datos
      "text": "BOTANICAL NAME",
      "match": "contains",             // "contains" | "exact" | "regex"
      "on_every_page": true,           // la cabecera se repite en cada página
      "offset_lines": 1                // cuántas líneas saltar tras el ancla
    },
    "stop_patterns": [                 // al casar, se corta la página
      "^\\s*TOTAL\\b", "^\\s*SUBTOTAL\\b", "^Page \\d+ of \\d+"
    ],
    "row_tolerance": 2.5,              // pts; palabras dentro de este rango vertical = misma fila
    "multiline": {
      "enabled": true,
      "continuation_max_gap": 14.0,    // pts entre líneas para considerar continuación
      "join_with": " "
    }
  },

  "columns": [
    { "role": "plant_name",   "index": 0, "required": true  },
    { "role": "size",         "index": 1, "required": true  },
    { "role": "price",        "index": 2, "required": false },
    { "role": "quantity",     "index": 3, "required": false },
    { "role": "availability", "index": 4, "required": false },
    { "role": "grower_code",  "index": 5, "required": false },
    { "role": "notes",        "index": 6, "required": false }
  ],

  "parsing": {
    "price": {
      "strip": ["$", "USD", "ea", "/ea", "each"],
      "decimal_separator": ".",
      "thousands_separator": ",",
      "on_range": "min",               // "min" | "max" | "issue"  — para "40.00 - 55.00"
      "empty_means": "unknown",        // "unknown" | "zero"
      "max_reasonable": "10000.00"     // por encima → issue PRICE_IMPLAUSIBLE
    },
    "quantity": {
      "empty_means": "unknown",        // "unknown" | "zero"   ← ver regla 7 de CLAUDE.md
      "on_non_numeric": "issue"        // "issue" | "null"
    },
    "availability": {
      "true_values":  ["yes", "y", "available", "in stock", "avail", "x", "✓"],
      "false_values": ["no", "n", "sold out", "so", "unavailable", "none", "0"],
      "empty_means": "true",           // "true" | "false" | "unknown"
      "derive_from_quantity": false    // si true y no hay columna: qty>0 ⇒ disponible
    },
    "size": {
      "patterns": [
        { "regex": "(?P<v>\\d+(?:\\.\\d+)?)\\s*\"",        "unit": "in", "dimension": "pot_diameter" },
        { "regex": "(?P<v>\\d+(?:\\.\\d+)?)\\s*in\\b",     "unit": "in", "dimension": "pot_diameter" },
        { "regex": "#(?P<v>\\d+)",                          "unit": "gal","dimension": "pot_volume" },
        { "regex": "(?P<v>\\d+(?:\\.\\d+)?)\\s*gal\\b",    "unit": "gal","dimension": "pot_volume" },
        { "regex": "(?P<v>\\d+(?:\\.\\d+)?)\\s*(?:ft|')\\s*(?:HT|tall)", "unit": "ft", "dimension": "plant_height" }
      ],
      "on_multiple_matches": "issue",  // "issue" | "first"
      "on_no_match": "issue"           // "issue" | "null"
    },
    "text": {
      "collapse_whitespace": true,
      "trim": true,
      "normalize_unicode": "NFKC",
      "drop_soft_hyphens": true
    }
  },

  "filters": {
    "drop_rows_matching": {
      "plant_name": ["^$", "^NOTES?\\b", "^\\*+$", "^-+$"]
    },
    "drop_rows_where_all_empty": ["price", "quantity", "availability"],
    "min_plant_name_length": 3
  }
}
```

## Roles de columna

| Rol | Tipo de salida | Obligatorio | Notas |
|---|---|---|---|
| `plant_name` | `str` | sí | Texto crudo. **Este servicio no lo descompone en planta/variedad** — eso es del worker |
| `size` | objeto `{magnitude, unit, dimension}` | sí | Ver abajo |
| `price` | `Decimal` como string, o `null` | no | |
| `quantity` | `int` o `null` | no | `null` ≠ `0` |
| `availability` | `bool` o `null` | no | |
| `grower_code` | `str` o `null` | no | El código del producto en el catálogo del grower. **Vale oro para el emparejamiento** |
| `notes` | `str` o `null` | no | Se transporta sin interpretar |

Restricciones que valida el servicio y que producen `400 INVALID_PROFILE`:

- Ningún `role` repetido.
- `plant_name` y `size` presentes y `required: true`.
- Con `strategy: "columns"`, cada `index` debe existir: `index < len(column_boundaries) - 1`.
- `column_boundaries` estrictamente creciente, mínimo 2 valores.
- Con `strategy: "regex"`, cada `role` declarado debe existir como grupo nombrado en
  `line_pattern`.
- Todo `regex` del perfil compila; si no, se nombra cuál falló.

## El tamaño: la parte que más falla

El campo `size` es el que más errores de emparejamiento causa aguas abajo, porque `10"`
puede ser diámetro de maceta o altura de planta según el grower, y una vez que el número se
pega al nombre ningún algoritmo de similitud acierta.

Por eso:

1. **El tamaño se separa del nombre siempre**, incluso si vienen en la misma columna. Si
   `plant_name` contiene un patrón de tamaño y la columna `size` viene vacía, se extrae de
   ahí y se emite el issue `SIZE_RECOVERED_FROM_NAME`.
2. **`dimension` es explícito y viene del perfil, no se adivina.** Los valores permitidos
   son `pot_diameter`, `pot_volume`, `plant_height`, `spread`.
3. **Si dos patrones casan con dimensiones distintas**, se emite `SIZE_AMBIGUOUS` y se
   devuelven las dos interpretaciones en el issue. No se elige por el orden de la lista
   salvo que el perfil diga `on_multiple_matches: "first"`.

Salida:

```json
{ "magnitude": "10.0", "unit": "in", "dimension": "pot_diameter", "raw": "10\"" }
```

`magnitude` va como string por la misma razón que el precio: es `Decimal`.

> ⚠️ El proyecto tiene la pregunta **P-01 abierta**: si en el catálogo de Greenary el
> tamaño es diámetro de maceta, altura, o ambos según el caso. Este servicio no la
> resuelve — la traslada con `dimension` explícito para que el worker pueda aplicar la
> regla correcta cuando se decida.

## Tres perfiles de ejemplo

Los tres deben existir como fixtures en `tests/fixtures/` desde el hito M3.

### A · Tabla alineada por espacios, sin líneas (`columns`)

El caso más común. Cabecera repetida en cada página, columnas alineadas a la izquierda.

```json
{
  "schema_version": 1, "version": 1,
  "document": { "kind": "pdf", "pages": "all" },
  "table": {
    "strategy": "columns",
    "column_boundaries": [52.0, 268.5, 372.0, 468.0, 540.0],
    "boundary_tolerance": 4.0,
    "header_anchor": { "text": "BOTANICAL NAME", "match": "contains", "on_every_page": true, "offset_lines": 1 },
    "stop_patterns": ["^\\s*TOTAL\\b", "^Page \\d+"],
    "row_tolerance": 2.5,
    "multiline": { "enabled": true, "continuation_max_gap": 14.0, "join_with": " " }
  },
  "columns": [
    { "role": "plant_name", "index": 0, "required": true },
    { "role": "size", "index": 1, "required": true },
    { "role": "price", "index": 2 },
    { "role": "quantity", "index": 3 }
  ]
}
```

### B · Tabla con líneas dibujadas (`ruling`)

Cuadrícula visible. `pdfplumber` recupera las celdas directamente y no hacen falta
`column_boundaries`.

```json
{
  "schema_version": 1, "version": 1,
  "document": { "kind": "pdf", "pages": "all", "skip_pages_matching": ["^\\s*TERMS"] },
  "table": {
    "strategy": "ruling",
    "ruling": { "vertical_strategy": "lines", "horizontal_strategy": "lines", "snap_tolerance": 3.0 },
    "header_anchor": { "text": "Item", "match": "exact", "on_every_page": true, "offset_lines": 0 },
    "stop_patterns": []
  },
  "columns": [
    { "role": "grower_code", "index": 0 },
    { "role": "plant_name", "index": 1, "required": true },
    { "role": "size", "index": 2, "required": true },
    { "role": "price", "index": 3 },
    { "role": "availability", "index": 4 }
  ]
}
```

### C · Catálogo en una línea por producto (`regex`)

Sin tabla: cada producto es una línea de texto con formato fijo. Ocurre en listas generadas
desde sistemas antiguos.

```json
{
  "schema_version": 1, "version": 1,
  "document": { "kind": "pdf", "pages": "all" },
  "table": {
    "strategy": "regex",
    "line_pattern": "^(?P<grower_code>[A-Z]{3}-\\d{4})\\s+(?P<plant_name>.+?)\\s+(?P<size>\\d+(?:\\.\\d+)?\"?)\\s+\\$(?P<price>[\\d,]+\\.\\d{2})\\s+(?P<quantity>\\d+|-)$",
    "header_anchor": null,
    "stop_patterns": ["^={3,}"]
  },
  "columns": [
    { "role": "grower_code", "index": 0 },
    { "role": "plant_name", "index": 1, "required": true },
    { "role": "size", "index": 2, "required": true },
    { "role": "price", "index": 3 },
    { "role": "quantity", "index": 4 }
  ]
}
```

Con `strategy: "regex"` el `index` de cada columna se ignora para el recorte (el grupo
nombrado manda), pero se conserva para que el orden de las claves en `raw` sea estable.

## Valores por defecto

Todo campo omitido toma el valor por defecto documentado arriba. El servicio **normaliza el
perfil al recibirlo** y devuelve el perfil efectivo en `diagnostics.effective_profile`
cuando `options.include_raw_words` es `true`, para que sea depurable qué defaults se
aplicaron.
