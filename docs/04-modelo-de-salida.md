# 04 · Modelo de salida

## La fila

```jsonc
{
  "row_index": 42,                  // correlativo dentro del documento, empieza en 0
  "page": 2,
  "source_lines": [310, 311],       // índices de línea del documento, para auditoría

  "raw": {                          // texto EXACTO leído, por rol. Nunca se normaliza aquí
    "plant_name": "Ficus  lyrata   'Bambino'",
    "size": "10\"",
    "price": "$42.50",
    "quantity": "12",
    "availability": ""
  },

  "text": {                         // igual que raw, tras parsing.text (trim, colapso, NFKC)
    "plant_name": "Ficus lyrata 'Bambino'",
    "size": "10\"",
    "price": "$42.50",
    "quantity": "12",
    "availability": ""
  },

  "parsed": {
    "plant_name": "Ficus lyrata 'Bambino'",
    "size": { "magnitude": "10.0", "unit": "in", "dimension": "pot_diameter", "raw": "10\"" },
    "price": "42.50",               // string decimal, NUNCA número JSON
    "quantity": 12,                 // int o null
    "availability": true,           // bool o null
    "grower_code": null,
    "notes": null
  },

  "issues": [
    { "code": "AVAILABILITY_EMPTY_DEFAULTED", "severity": "warning",
      "field": "availability", "detail": "columna vacía; perfil dice empty_means=true" }
  ],

  "bbox": { "page": 2, "x0": 52.1, "top": 310.4, "x1": 540.0, "bottom": 322.9 }
}
```

### Por qué `raw`, `text` y `parsed` son tres cosas

- **`raw`** es la prueba. Si mañana alguien discute un precio, esto es lo que decía el
  documento. No se toca jamás.
- **`text`** es lo normalizado, que es contra lo que el worker empareja (`grower_alias`
  guarda su `normalized_key` a partir de aquí).
- **`parsed`** son los valores tipados que van a la base de datos.

Un pipeline que solo devuelve `parsed` no se puede auditar, y auditar es la mitad del
problema que este rediseño ataca.

### `bbox`

El rectángulo que ocupa la fila en la página. Permite que la UI de revisión resalte la
línea exacta del PDF cuando una persona tiene que resolver un `unmatched`. Sin esto,
revisar 20 filas dudosas significa buscarlas a mano en un PDF de 6 páginas.

Se omite si `options.include_bbox` es `false`.

---

## Catálogo de `issues`

`severity` decide qué puede hacer el worker con la fila:

- **`error`** — la fila no es utilizable tal cual; va a revisión manual.
- **`warning`** — la fila es utilizable, pero conviene mirarla.
- **`info`** — se aplicó una regla del perfil que conviene saber; no requiere nada.

| Código | Severidad | Significado |
|---|---|---|
| `REQUIRED_COLUMN_EMPTY` | error | Una columna con `required: true` vino vacía |
| `ROW_COLUMN_COUNT_MISMATCH` | error | La fila produjo un número de celdas distinto al del perfil |
| `LINE_PATTERN_NO_MATCH` | error | Estrategia `regex`: la línea no casó con `line_pattern` |
| `PRICE_UNPARSEABLE` | error | Hay texto en la columna de precio pero no es un número tras aplicar `strip` |
| `PRICE_NEGATIVE` | error | Precio negativo |
| `PRICE_IMPLAUSIBLE` | warning | Supera `max_reasonable` |
| `PRICE_RANGE` | warning | Se leyó un rango («40.00 - 55.00»); se resolvió según `on_range` |
| `SIZE_UNRECOGNIZED` | error | Ningún patrón de `parsing.size.patterns` casó |
| `SIZE_AMBIGUOUS` | error | Dos o más patrones casaron con `dimension` distinta. El `detail` trae las dos lecturas |
| `SIZE_RECOVERED_FROM_NAME` | warning | La columna `size` estaba vacía y el tamaño se extrajo de `plant_name` |
| `QUANTITY_UNPARSEABLE` | warning | Texto no numérico en cantidad; resultado según `on_non_numeric` |
| `AVAILABILITY_UNKNOWN_TOKEN` | warning | El texto no está en `true_values` ni en `false_values` |
| `AVAILABILITY_EMPTY_DEFAULTED` | info | Columna vacía; se aplicó `empty_means` |
| `TEXT_CROSSES_BOUNDARY` | warning | Una palabra cae a caballo de dos columnas. Señal fuerte de que `column_boundaries` está desfasado |
| `MULTILINE_JOINED` | info | La fila se compuso uniendo 2+ líneas |
| `OCR_LOW_CONFIDENCE` | warning | Confianza media de OCR de la fila por debajo de `OCR_MIN_CONFIDENCE` |
| `ROW_LIKELY_HEADER` | info | La fila parece una cabecera repetida; se descartó |
| `ROW_LIKELY_TOTAL` | info | La fila parece un total; se descartó |

Regla: **una fila con al menos un issue de severidad `error` sigue devolviéndose**, con
`parsed` parcialmente relleno (los campos que sí se pudieron leer) y los que no, en `null`.
El servicio nunca decide por el worker.

### Umbral y guarda

`TEXT_CROSSES_BOUNDARY` merece atención especial: si aparece en más del 2% de las filas, el
perfil está desfasado aunque el fingerprint haya coincidido, porque el fingerprint se
calcula con tolerancia. El servicio lo añade a `diagnostics.warnings` con el conteo, y el
worker debería tratarlo como señal de revisar el perfil.

---

## Diagnósticos

```jsonc
{
  "rows_extracted": 187,           // filas devueltas en "rows"
  "rows_dropped": 12,              // descartadas por filters o stop_patterns
  "rows_with_errors": 3,
  "rows_with_warnings": 14,
  "issues_by_code": { "PRICE_UNPARSEABLE": 3, "SIZE_UNRECOGNIZED": 11 },
  "dropped_by_reason": { "matched_stop_pattern": 4, "empty_row": 6, "min_name_length": 2 },
  "pages_processed": 6,
  "pages_skipped": [7],
  "ocr_used": false,
  "ocr_mean_confidence": null,
  "strategy_used": "columns",
  "duration_ms": 1842,
  "warnings": [
    "14 palabras cruzan un límite de columna (7.5% de las filas) — revisar column_boundaries"
  ]
}
```

**`rows_extracted` es el denominador de la guarda de completitud del worker.** Si el worker
calcula `unmatched / rows_extracted > 5%`, omite la reconciliación de bajas de
disponibilidad. Por eso este número tiene que ser honesto: cuenta filas devueltas, no filas
«buenas».

## Serialización

- Todo `Decimal` se emite como **string** (`"42.50"`), nunca como número JSON. Un
  `float64` no representa `0.1` y los precios acaban con céntimos fantasma.
- Los `null` se emiten explícitamente; no se omiten claves. El consumidor es TypeScript con
  Zod y un campo ausente no es lo mismo que un campo nulo.
- El orden de las claves es estable (el del modelo Pydantic), porque el determinismo se
  verifica comparando bytes.
- Las coordenadas van en **puntos PostScript** (1/72 pulgada), con origen arriba-izquierda,
  redondeadas a un decimal.
