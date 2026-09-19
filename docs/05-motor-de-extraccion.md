# 05 · El motor de extracción

## El pipeline, paso a paso

```
1. fetch          descargar (URL firmada) o decodificar (base64) → bytes
2. verify         comprobar sha256 si vino; comprobar tamaño y tipo
3. open           abrir con PyMuPDF; detectar cifrado, páginas, geometría
4. decide_ocr     ¿hay capa de texto? → texto nativo o OCR
5. read_words     por página: lista de palabras con (text, x0, top, x1, bottom)
6. fingerprint    calcular el hash del layout y compararlo con el del perfil
7. select_pages   aplicar document.pages y skip_pages_matching
8. locate_header  encontrar el ancla en cada página; recortar lo anterior
9. group_lines    agrupar palabras en líneas por proximidad vertical
10. cut_columns   aplicar la estrategia → celdas por fila
11. merge_rows    fusionar líneas de continuación (nombres largos)
12. filter_rows   aplicar stop_patterns y filters
13. parse         precio, tamaño, cantidad, disponibilidad → valores tipados
14. emit          construir las filas y los diagnósticos
```

Cada paso es una función pura sobre la salida del anterior. Eso es lo que hace que se pueda
testear con snapshots paso a paso, y es lo que hay que preservar al extender.

---

## Paso 4 · Decisión de OCR

```
texto_nativo = suma de caracteres extraídos de las primeras 3 páginas
area_paginas = suma de área de esas páginas en pulgadas²
densidad     = texto_nativo / area_paginas

options.ocr = "never"  → siempre texto nativo; si densidad == 0 → 422 DOCUMENT_UNREADABLE
options.ocr = "force"  → siempre OCR
options.ocr = "auto"   → OCR si densidad < OCR_DENSITY_THRESHOLD (def. 5.0 car/pulg²)
```

Una imagen (`image/*`) siempre va por OCR, sea cual sea la opción.

Cuando se usa OCR, cada palabra lleva su confianza y la fila hereda la media. Por debajo de
`OCR_MIN_CONFIDENCE` (def. 70) se emite `OCR_LOW_CONFIDENCE`.

**El OCR está desactivado por defecto en producción** (`OCR_ENABLED=false`): añade
`tesseract` a la imagen, multiplica el tiempo por ~20 y las listas de los growers actuales
son PDFs nativos. Se activa cuando aparezca un escaneado real.

---

## Paso 6 · El fingerprint del layout

Es la pieza que convierte «la IA interpretó mal» en «el documento cambió y el sistema se
detuvo». Tiene que cumplir dos propiedades opuestas:

- **Estable** ante lo que cambia en cada envío: precios, cantidades, número de filas, qué
  plantas hay, la fecha del encabezado.
- **Sensible** a lo que invalida el perfil: que se mueva una columna, que aparezca o
  desaparezca una, que cambie el texto de la cabecera, que cambie el tamaño de página.

Por eso **se calcula sobre la estructura, nunca sobre los datos**.

### Algoritmo

```
componentes = [
  "page_size:"   + f"{ancho:.0f}x{alto:.0f}"          # página 1, redondeado a entero
  "rotation:"    + str(rotacion)
  "columns:"     + str(len(column_candidates))
  "boundaries:"  + ",".join(f"{round(x/5)*5}" for x in column_candidates)   # cubos de 5 pt
  "header:"      + normalizar(texto_linea_cabecera)
  "strategy:"    + estrategia_detectada
]
fingerprint = "sha256:" + sha256("\n".join(componentes)).hexdigest()[:32]
```

Donde `normalizar(s)`:

```
1. NFKC
2. minúsculas
3. eliminar todos los dígitos          ← "SPRING 2026" y "SPRING 2027" dan lo mismo
4. eliminar todo lo que no sea [a-z ]
5. colapsar espacios, trim
```

Eliminar los dígitos es lo que hace que la fecha del encabezado, el número de página y el
año de la temporada no disparen un falso positivo. Los cubos de 5 puntos absorben el ruido
sub-píxel de distintas versiones del generador de PDF.

La línea de cabecera es la que localiza `header_anchor` en la página 1. Si el perfil no
tiene `header_anchor` (estrategia `regex`), se usa la primera línea con 3 o más palabras.

### Comparación y `detail.changed`

No basta con decir que el fingerprint cambió. Se comparan los componentes **uno a uno** y
se devuelve la lista de los que difieren, con los nombres `page_size`, `rotation`,
`column_count`, `boundaries`, `header_text`, `strategy`.

Para eso hay que guardar los componentes, no solo el hash. El perfil trae el hash; el
servicio recalcula los componentes del documento actual y, cuando hay `mismatch`, devuelve
los componentes actuales en `detail.actual_components` para que el worker se los pueda
enseñar a la persona o al LLM que va a reparar el perfil.

### Qué NO entra en el fingerprint

Número de páginas (una lista puede tener 4 páginas en marzo y 9 en mayo), número de filas,
cualquier texto de una fila de datos, la fecha, el nombre del archivo.

---

## Paso 9 · Agrupar palabras en líneas

PyMuPDF devuelve palabras sueltas con su bbox. Para agruparlas:

```
ordenar palabras por (top, x0)
para cada palabra:
    si |palabra.top - linea_actual.top| <= table.row_tolerance:
        añadir a linea_actual, actualizar su top como media ponderada por ancho
    si no:
        cerrar linea_actual, abrir una nueva
```

La media ponderada por ancho evita que una palabra en superíndice (una nota al pie, un
asterisco) arrastre la línea entera.

`row_tolerance` por defecto 2.5 pt. Para documentos con interlineado apretado puede bajar a
1.5; por encima de 4 empiezan a fusionarse filas distintas.

---

## Paso 10 · Las tres estrategias

### `columns` — recorte por coordenada x

La principal. `column_boundaries` define N+1 fronteras para N columnas. Cada palabra se
asigna a la columna cuyo intervalo `[b[i] - tol, b[i+1] + tol)` contiene su `x0`.

Casos especiales que hay que manejar:

- **Palabra a caballo de dos columnas** (`x0 < b[i+1] <= x1`): se asigna a la columna de
  su `x0` y se emite `TEXT_CROSSES_BOUNDARY`. No se parte la palabra.
- **Palabra antes de la primera frontera o después de la última**: se asigna a la primera
  o la última columna respectivamente, y se emite `TEXT_CROSSES_BOUNDARY`.
- **Columna vacía**: celda `""`, no `null`. `null` se reserva para «no existe esa columna».
- **Texto centrado o alineado a la derecha**: las fronteras se definen sobre `x0`, así que
  una columna numérica alineada a la derecha necesita que la frontera izquierda esté antes
  del número más largo posible. Esto es un problema del perfil, no del motor, pero conviene
  documentarlo en el mensaje del issue.

### `ruling` — celdas de una tabla con líneas dibujadas

Delegar en `pdfplumber.extract_tables()` con las `table_settings` del perfil. Devuelve una
matriz de celdas. Se mapea directamente a los `index` de las columnas.

Es más fiable que `columns` **cuando hay líneas de verdad**. Cuando la cuadrícula es
simulada con caracteres o con sombreado de fondo, `pdfplumber` no ve nada y hay que usar
`columns`. Por eso `/v1/sample` devuelve `ruling_lines`: si están vacías, la estrategia
recomendada es `columns`.

### `regex` — una línea, un producto

Se aplica `line_pattern` al texto de cada línea ya agrupada. Los grupos nombrados producen
las celdas. Una línea que no casa emite `LINE_PATTERN_NO_MATCH` y se devuelve con su `raw`.

Regla: el patrón se compila **una vez** al validar el perfil, con `re.VERBOSE` desactivado
y sin flags implícitas, para que el comportamiento sea el mismo en cualquier máquina.

---

## Paso 11 · Fusión de filas multilínea

Este es el detalle que más filas salva en listas de plantas reales, donde
`Dracaena marginata 'Colorama' Character Specimen` no cabe en la columna y el generador de
PDF lo parte en dos líneas.

Una línea es **continuación** de la anterior si se cumple todo:

1. `multiline.enabled` es `true`.
2. La celda `plant_name` tiene contenido.
3. **Todas** las celdas «ancla» están vacías. Las anclas son, por orden de preferencia:
   `price`, luego `size`, luego `grower_code`. Se usa la primera que exista en el perfil.
4. El hueco vertical con la línea anterior es menor que `multiline.continuation_max_gap`.
5. La línea anterior existe y no fue descartada por un filtro.

Entonces se une: `anterior.plant_name + join_with + actual.plant_name`, se extiende el
`bbox`, se añade el índice de línea a `source_lines`, y se emite `MULTILINE_JOINED`.

Contraejemplo que hay que **no** fusionar: una fila cuyo precio está vacío porque el grower
no lo publicó, pero que sí tiene tamaño. La condición 3 exige *todas* las anclas vacías
justamente para eso, y por eso el orden de preferencia pone `price` primero solo si existe
más de un ancla.

---

## Paso 13 · Los parsers

Viven en `domain/parsing/` y son funciones puras `str -> (valor, [issues])`. Ninguna lanza
excepción. Se testean con `hypothesis` además de con casos concretos.

### Precio

```
1. NFKC, trim
2. si vacío → (None, [] o issue según empty_means)
3. quitar cada literal de parsing.price.strip (case-insensitive)
4. detectar rango: dos números separados por "-", "–", "to", "/"
      → resolver según on_range, emitir PRICE_RANGE
5. quitar thousands_separator; sustituir decimal_separator por "."
6. Decimal(texto). Si falla → (None, [PRICE_UNPARSEABLE])
7. si < 0 → (valor, [PRICE_NEGATIVE]);  si > max_reasonable → (valor, [PRICE_IMPLAUSIBLE])
8. cuantizar a 2 decimales con ROUND_HALF_UP
```

Nunca `float()`. Ni siquiera como paso intermedio.

### Tamaño

```
1. texto = celda size; si vacía y plant_name tiene patrón → usar ese, emitir SIZE_RECOVERED_FROM_NAME
2. aplicar TODOS los patterns del perfil, recoger todas las coincidencias
3. 0 coincidencias → según on_no_match
4. 1 coincidencia   → devolver
5. >1 con la misma (unit, dimension) → devolver la primera, sin issue
6. >1 con distinta dimension → según on_multiple_matches
      "issue" → (None, [SIZE_AMBIGUOUS con las lecturas en detail])
      "first" → la primera de la lista del perfil
```

El grupo `v` del regex es la magnitud. `unit` y `dimension` los pone el perfil, no el
regex: eso es deliberado, porque es la información que el documento no lleva.

### Cantidad

```
vacío → None  (o 0 si empty_means == "zero" — pero NUNCA por defecto)
"-", "N/A", "TBD", "call" → None + QUANTITY_UNPARSEABLE (warning)
numérico → int, quitando separadores de millar
negativo → None + QUANTITY_UNPARSEABLE
```

### Disponibilidad

```
1. normalizar: NFKC, minúsculas, trim, colapsar espacios
2. si vacío → empty_means ("true" | "false" | "unknown") + AVAILABILITY_EMPTY_DEFAULTED
3. si está en true_values  → True
4. si está en false_values → False
5. si no → None + AVAILABILITY_UNKNOWN_TOKEN, con el token en detail
6. si no hay columna availability y derive_from_quantity: quantity is not None and quantity > 0
```

La comparación con `true_values`/`false_values` es por igualdad exacta tras normalizar, no
por `contains`: «no stock» no debe casar con «stock».

---

## Determinismo: cómo no romperlo

| Riesgo | Regla |
|---|---|
| Orden de palabras | Ordenar siempre por `(round(top, 1), round(x0, 1), text)`. El tercer criterio desempata palabras exactamente superpuestas |
| `set` / `dict` | Nunca iterar un `set`. Los `dict` de Python preservan inserción: construirlos siempre en el mismo orden |
| Coma flotante | Redondear coordenadas a 1 decimal **antes** de comparar o agrupar |
| Concurrencia | Ninguna paralelización dentro de una petición. Una petición, un hilo |
| Tiempo | `duration_ms` es el único campo con reloj, y está excluido de los snapshots |
| Versión de librería | PyMuPDF puede cambiar la extracción entre versiones. Pinear la versión exacta en `uv.lock` y subir `engine_version` cuando se actualice |

El test `test_determinism.py` extrae dos veces cada fixture del golden set y compara el
JSON serializado byte a byte, con `duration_ms` excluido. Si falla, hay estado oculto.
