# 10 · Verificación y endurecimiento del extractor

Plan de trabajo tras la primera implementación. **No reemplaza a `docs/01`…`docs/09`**: los
completa con lo que la realidad enseñó.

Fecha: 28 sep 2026 · Estado de la suite: **160 tests en verde, 1 saltado**

---

## 0 · El problema, en una frase

> La suite está verde y el extractor falla con documentos reales, porque **todos los
> fixtures los genera el propio repo**.

Los cinco casos golden (`acme-single`, `acme-multipage`, `acme-multiline`, `acme-ruling`,
`acme-regex`) los construye `tests/fixtures/golden/_generate.py` con PyMuPDF, a partir de
cinco filas inventadas:

```python
ROWS = [
    ("Ficus lyrata", '10"', "$42.50", "12"),
    ("Monstera deliciosa", '14"', "$68.00", "4"),
    …
]
```

Son nombres cortos, precios limpios y columnas perfectamente alineadas **porque el
generador las dibuja así**. El extractor se está examinando de un temario que él mismo
escribió.

Peor: `tests/golden/test_golden.py` **importa `_generate` y regenera los PDF en cada
ejecución**. El input ni siquiera está congelado, así que puede derivar con la versión de
PyMuPDF sin que nadie lo note.

---

## 1 · El fallo real

En la raíz del repo hay dos archivos sin versionar —`tmp_bj_profile.json` y
`tmp_ruling_extract_full.json`— que son una extracción real de **B&J Nurseries (Apopka)**,
5 páginas, estrategia `ruling`. Eso es lo más valioso del repo ahora mismo y está fuera de
la suite.

Sus diagnósticos:

| Métrica | Valor | Lectura |
|---|---|---|
| `rows_extracted` | 227 | |
| `rows_dropped` | **85** | 27% del documento descartado |
| ├ `empty_row` | 65 | |
| └ `matched_drop_pattern` | 20 | |
| `rows_with_errors` | **20** | 8.8% de lo extraído |
| `PRICE_UNPARSEABLE` | 20 | |
| `QUANTITY_UNPARSEABLE` | 5 | |
| `TEXT_CROSSES_BOUNDARY` | **0** | ⬅ el dato importante |
| `warnings` | `[]` | ⬅ y este |

### Las 20 filas rotas son el mismo bug

```jsonc
{ "size": "6\"",   "plant_name": "Sans Bonce",  "price": "llensis",        "quantity": "", "notes": "5"  }
{ "size": "4\"",   "plant_name": "Sans Fernw",  "price": "ood",            "quantity": "", "notes": "4"  }
{ "size": "4\"",   "plant_name": "Sans Mikad",  "price": "o",              "quantity": "", "notes": "4"  }
{ "size": "2.5\"", "plant_name": "Sans Icicle", "price": "Mikado",         "quantity": "", "notes": "17" }
{ "size": "8\"",   "plant_name": "Sans Dishga", "price": "rdens (Bowls)",  "quantity": "", "notes": "2"  }
```

`Sans Boncellensis` se partió en `Sans Bonce` + `llensis`. **El nombre desborda su celda y
el sobrante cae en la columna del precio.** Y como el sobrante ocupa una celda, **todo lo
demás se desplaza una posición a la derecha**: la cantidad acaba en `notes`.

Confirmado en 19 de las 20 filas: `quantity` vacío y `notes` numérico.

### Las tres conclusiones que importan

1. **No es un problema de parseo.** El parser de precio hace lo correcto al rechazar
   `"llensis"`. El error ocurrió antes, en el recorte de celdas.

2. **El fallo es silencioso.** Cero `TEXT_CROSSES_BOUNDARY`, cero `warnings`. El
   mecanismo de detección que `docs/04` y `docs/05` exigen **no está operando en la
   estrategia `ruling`**. Un documento que se lee mal y no se queja es exactamente lo que
   este rediseño existía para eliminar.

3. **El fingerprint no protegió nada.** `expected_fingerprint: null` y `matched: true`: sin
   perfil previo no hay nada contra qué comparar, así que la primera extracción de un
   grower nunca está protegida — que es justo cuando más se equivoca.

### Y un dato que hay que explicar, no asumir

**85 filas descartadas de 312.** Puede ser correcto (cabeceras de sección, líneas en
blanco, totales) o puede ser producto en la basura. Hoy no hay forma de saberlo, porque
`dropped_by_reason` da el motivo agregado pero **no guarda qué se descartó**. Sin eso,
nadie puede auditar el 27% de un documento.

---

## 2 · Qué es el extractor

### Su función

> Convertir un documento de lista de precios en filas estructuradas, aplicando un perfil
> declarativo, **de forma determinista y sin IA**, y reportar con honestidad la calidad de
> la lectura.

### Sus fronteras

| Hace | No hace |
|---|---|
| Descargar el documento por URL firmada | Llamar a un LLM |
| Detectar layout y calcular su fingerprint | Emparejar contra el catálogo |
| Recortar celdas por geometría | Escribir en base de datos |
| Parsear precio, tamaño, cantidad, disponibilidad | Decidir si una fila se aplica |
| Reportar incidencias y diagnósticos | Guardar estado entre peticiones |
| Devolver evidencia de layout (`/v1/sample`) | Interpretar el negocio |

### El contrato conceptual

> Entra un documento y un perfil. Sale una lista de filas y **un juicio honesto sobre la
> calidad de la lectura**.

La segunda mitad de esa frase es la que falló.

---

## 3 · Lo que debe ser capaz de hacer

Lista de capacidades verificables. Cada una tiene su puerta en §5.

### A · Lectura del documento

- **A1** Abrir PDF nativo y extraer palabras con bbox, en orden determinista.
- **A2** Abrir PDF cifrado con contraseña; rechazar con `DOCUMENT_UNREADABLE` sin contraseña.
- **A3** Detectar documento escaneado (`text_density`) y enrutar a OCR según `options.ocr`.
- **A4** Abrir imágenes (PNG, JPEG, TIFF) vía OCR.
- **A5** Respetar `document.pages` y `skip_pages_matching`.
- **A6** Rechazar documentos por encima de `MAX_PAGES` y `MAX_DOCUMENT_BYTES`.

### B · Identidad del layout

- **B1** Calcular el fingerprint sobre **estructura, no datos**: estable ante cambios de
  precio, fecha y número de filas.
- **B2** Cambiar el fingerprint si se mueve una columna, aparece o desaparece una, cambia
  el texto de cabecera o el tamaño de página.
- **B3** Devolver **qué componente** cambió (`detail.changed`), no solo que cambió.
- **B4** Detener la extracción con `409` cuando no coincide y
  `fail_on_fingerprint_mismatch` es `true`.

### C · Recorte de celdas — ⬅ **donde está el fallo**

- **C1** Estrategia `columns`: asignar cada palabra a su columna por `x0`.
- **C2** Estrategia `ruling`: recuperar celdas de una tabla con líneas dibujadas.
- **C3** Estrategia `regex`: una línea, un producto, por grupos nombrados.
- **C4** **Conservar el texto**: la unión del texto de las celdas de una fila debe ser
  igual al texto de la línea de origen. Ni se pierde ni se duplica.
- **C5** **Nunca partir una palabra entre dos celdas.** Una palabra pertenece a una celda
  y solo a una.
- **C6** Detectar y **reportar** cuando una palabra cruza un límite, en **las tres
  estrategias**.
- **C7** Detectar cuando el número de celdas no cuadra con los roles del perfil y emitir
  `ROW_COLUMN_COUNT_MISMATCH`.
- **C8** Fusionar líneas de continuación según las cinco condiciones de `docs/05`.

### D · Parseo

- **D1** Precio como `Decimal`, nunca `float`; rangos, símbolos, separadores.
- **D2** Tamaño con `dimension` explícito del perfil; ambigüedad → issue.
- **D3** `quantity` vacío → `None`, **nunca `0`**.
- **D4** Disponibilidad por igualdad exacta tras normalizar.
- **D5** Ningún parser lanza excepción con ninguna cadena.

### E · Honestidad del resultado

- **E1** Cada fila devuelve `raw`, `text` y `parsed` separados.
- **E2** Toda anomalía produce un `issue` con código y severidad.
- **E3** **Ninguna fila anómala pasa sin issue.** Silencio = correcto.
- **E4** Toda fila descartada queda registrada con su motivo **y su contenido**.
- **E5** Los diagnósticos agregados cuadran con la suma de las filas.
- **E6** `bbox` por fila para que la revisión pueda señalar el sitio exacto.

### F · Operación

- **F1** Determinista: misma entrada, misma salida byte a byte.
- **F2** Sin estado, sin red durante la extracción (salvo la descarga inicial).
- **F3** Las cinco mitigaciones de SSRF de `docs/08`.
- **F4** Semáforo de concurrencia, timeout efectivo, apagado limpio.
- **F5** Logs sin contenido del documento.
- **F6** Métricas Prometheus.

---

## 4 · Las cuatro invariantes nuevas

Son propiedades, no fixtures. Se verifican sobre **cualquier** documento, sintético o real,
y son lo que convierte un fallo silencioso en uno ruidoso.

### I1 · Conservación de texto

```
normalizar(concat(celdas_de_la_fila)) == normalizar(texto_de_la_linea_origen)
```

Si falla, se perdió o se duplicó texto en el recorte. **Esta invariante habría atrapado el
bug de `Sans Boncellensis` en el primer intento.** Es la más importante del documento.

### I2 · Integridad de palabra

Ninguna palabra del documento aparece partida entre dos celdas. Se comprueba contra la
lista de palabras que devolvió el reader: cada palabra debe estar íntegra en exactamente
una celda.

### I3 · Coherencia de forma

El número de celdas de cada fila es el que declara el perfil. Si una fila produce más o
menos, es un problema de layout y se reporta como tal, no se acomoda en silencio.

### I4 · Cuadre de diagnósticos

```
rows_extracted == len(rows)
sum(issues_by_code.values()) == número total de issues en las filas
sum(dropped_by_reason.values()) == rows_dropped
```

Un diagnóstico que no cuadra con sus filas es peor que no tenerlo: se usa para decidir.

---

## 5 · Las siete puertas de calidad

Cada puerta es un conjunto de pruebas que debe pasar antes de avanzar. **Ninguna se salta.**

### G0 · Higiene de la suite

*Objetivo: que los tests puedan fallar.*

- [ ] Los fixtures golden **dejan de regenerarse** en cada ejecución. `_generate.py` pasa a
      ser un script manual (`scripts/`), y los PDF quedan congelados en el repo.
- [ ] Un test verifica el `sha256` de cada PDF golden: si cambia, falla y obliga a
      revisar el `.expected.json`.
- [ ] `tmp_bj_profile.json` y `tmp_ruling_extract_full.json` salen de la raíz: el perfil
      va al golden set, la salida se descarta.
- [ ] `.gitignore` cubre `tmp_*`, `.coverage`, `.hypothesis`, cachés.

### G1 · Parsers puros

*Ya cubierto en gran medida. Confirmar:*

- [ ] Property test: ningún parser lanza con ninguna cadena Unicode.
- [ ] `parse_quantity("")` → `None`, nunca `0`.
- [ ] Round-trip de precio: `Decimal` → texto con los separadores del perfil → `Decimal`.
- [ ] Cobertura de `domain/` ≥ 95%.

### G2 · Geometría y fingerprint

- [ ] Fingerprint idéntico en 10 ejecuciones.
- [ ] Mismo layout con precios y fechas distintas → **mismo** fingerprint.
- [ ] Columna desplazada 30 pt → fingerprint **distinto**, `changed == ["boundaries"]`.
- [ ] Documento sin `expected_fingerprint` → la respuesta lo indica explícitamente, y el
      campo `matched` **no** dice `true` (hoy miente: no comparó nada).

### G3 · Integridad de celdas — 🔴 **la puerta que faltaba**

*Aquí se cierra el fallo real. Las cuatro invariantes de §4, en las tres estrategias.*

- [ ] **I1** conservación de texto — property test sobre los 5 golden + el documento real
- [ ] **I2** integridad de palabra
- [ ] **I3** coherencia de forma
- [ ] **I4** cuadre de diagnósticos
- [ ] `TEXT_CROSSES_BOUNDARY` se emite en `columns` **y en `ruling`** (hoy solo existe en
      una, si acaso)
- [ ] `ROW_COLUMN_COUNT_MISMATCH` se emite cuando el recuento no cuadra
- [ ] Un nombre que desborda su celda produce **issue**, no corrupción silenciosa
- [ ] Caso de regresión explícito: `Sans Boncellensis` en una celda estrecha
- [ ] Cuando `TEXT_CROSSES_BOUNDARY` supera el 2% de las filas, aparece en
      `diagnostics.warnings` (hoy `warnings` viene vacío con 20 filas rotas)

### G4 · Golden set real

*Sin esto, nada de lo anterior demuestra que funcione.*

- [ ] **Mínimo 3 growers reales**, 1 documento cada uno, anonimizados.
- [ ] B&J Nurseries con sus 5 páginas y su perfil, **como caso golden**.
- [ ] Cada `.expected.json` **revisado fila por fila contra el PDF**. Un expected generado
      y no revisado certifica el bug actual.
- [ ] `NOTES.md` por fixture diciendo qué tiene de particular.
- [ ] Cobertura de casos: nombres largos que desbordan · celdas de precio legítimamente
      vacías · cantidades como `-` o `N/A` · dos unidades de tamaño en el mismo documento ·
      cabecera repetida entre páginas · página de términos que hay que saltar · layout
      cambiado del mismo grower · escaneado.

### G5 · Robustez

- [ ] PDF corrupto, cifrado, de cero páginas → error tipado, nunca traza.
- [ ] Documento con 0 filas → `NO_ROWS_FOUND`, no un `200` con lista vacía.
- [ ] Perfil inválido → `400` nombrando el campo.
- [ ] Regex del perfil que no compila → `400` diciendo cuál.
- [ ] Documento de 200 páginas dentro del presupuesto de tiempo.
- [ ] Las cinco pruebas de SSRF.

### G6 · Operación

- [ ] Determinismo byte a byte sobre **todo** el golden set, real incluido.
- [ ] Sin red en la suite (el fixture `no_network` ya existe: verificar que cubre todo).
- [ ] `/metrics` expone las seis métricas.
- [ ] `MAX_CONCURRENCY=1` + dos peticiones → `503` con `Retry-After`.
- [ ] Timeout → `504` y el proceso sigue sano.
- [ ] Test de fuga: ninguna cadena de un fixture aparece en los logs.
- [ ] Imagen Docker arranca como no-root y `/health` responde.

---

## 6 · Criterios de aceptación medibles

Sobre el golden set **real**, no el sintético:

| Métrica | Umbral | Hoy (B&J) |
|---|---|---|
| Filas con issue de severidad `error` | **≤ 1%** | 8.8% ❌ |
| Filas anómalas sin issue (fallo silencioso) | **0** | 20 ❌ |
| `TEXT_CROSSES_BOUNDARY` sin reportar | **0** | 20 ❌ |
| Filas descartadas sin contenido registrado | **0** | 85 ❌ |
| Invariantes I1–I4 | **todas** | sin verificar ❌ |
| Determinismo | byte a byte | ✅ |
| Duración p95, 5 páginas | < 3 s | 0.68 s ✅ |

La primera fila es la que define «funciona»: **menos del 1% de filas con error, y cero
fallos silenciosos**. Un 8.8% de precios ilegibles es tolerable si el sistema lo dice; lo
que no es tolerable es que 20 filas se corrompan y el informe venga vacío.

---

## 7 · Fases

### F1 · Congelar y ver (G0)
Dejar la suite en condiciones de fallar. Sin esto, cualquier arreglo es a ciegas.
**Salida:** fixtures congelados con su hash; `tmp_*` fuera de la raíz.

### F2 · Instrumentar (G3, parte de detección)
Implementar I1–I4 y hacer que `TEXT_CROSSES_BOUNDARY` y `ROW_COLUMN_COUNT_MISMATCH` se
emitan en las tres estrategias. **Todavía sin arreglar el recorte.**
**Salida:** el documento de B&J produce 20+ issues de cruce de límite y la suite falla
ruidosamente donde antes callaba.

> Esta fase **empeora** los números a propósito. Ese es el objetivo: hacer visible lo que
> ya estaba roto antes de tocarlo.

### F3 · Arreglar el recorte (G3, parte de corrección)
Corregir la asignación de celdas en `ruling` para que una palabra no se parta y no
desplace las columnas siguientes. Revisar si `columns` tiene el mismo defecto.
**Salida:** las 20 filas de B&J se leen correctamente, o quedan marcadas con issue si el
documento es genuinamente ambiguo.

### F4 · Golden set real (G4)
Incorporar los 3 growers reales con sus expected revisados a mano.
**Salida:** la suite mide comportamiento real.

### F5 · Explicar los descartes (E4)
Registrar qué se descartó, no solo cuántas. Revisar las 85 de B&J una por una.
**Salida:** cada descarte es auditable; se sabe si el 27% era basura o producto.

### F6 · Robustez y operación (G5, G6)
**Salida:** listo para que el worker dependa de él.

---

## 8 · Lo que NO hay que hacer

- **No ajustar los umbrales** para que los números cuadren. Si el 8.8% baja porque se
  relajó el parser de precio, el problema sigue ahí y ahora invisible.
- **No añadir heurísticas** que «recompongan» nombres partidos adivinando. El recorte se
  arregla en la geometría; adivinar es volver al punto de partida.
- **No generar `.expected.json` sin revisarlo.** Es el error más caro de este plan: crea
  un test que certifica el bug.
- **No tocar `columns` y `ruling` en el mismo commit.** Son dos estrategias con dos
  defectos posiblemente distintos.
- **No seguir con el worker hasta cerrar G3 y G4.** El worker construye su emparejamiento
  sobre lo que el extractor devuelve; con celdas desplazadas, aprende aliases equivocados
  — y un alias equivocado con `hit_count` alto se propaga a todas las corridas futuras.
