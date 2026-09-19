# 07 · Pruebas

La calidad de este servicio no se mide en cobertura, se mide en **si el golden set pasa**.
Todo lo demás lo sostiene.

## Las cinco capas

| Capa | Qué prueba | Dónde |
|---|---|---|
| Unitaria | Los parsers puros, con casos concretos | `tests/unit/parsing/` |
| Propiedad | Los parsers, con `hypothesis` | `tests/unit/parsing/test_properties.py` |
| Motor | Estrategias y agrupado, con palabras sintéticas (sin PDF) | `tests/unit/engine/` |
| Golden | Documentos reales → salida esperada completa | `tests/golden/` |
| Integración | La API entera con un doble de fetcher | `tests/integration/` |

## El golden set

Es el activo más valioso del repo. Estructura:

```
tests/fixtures/<grower_slug>/
├── profile.json              # el perfil con el que se extrae
├── 2026-03-spring.pdf        # el documento
├── 2026-03-spring.expected.json    # la salida completa esperada
└── NOTES.md                  # qué tiene de particular este caso
```

`NOTES.md` no es opcional. Un fixture sin explicación de por qué existe deja de mantenerse
en cuanto quien lo añadió se va del proyecto. Una línea basta: «nombres largos que se
parten en dos líneas», «columna de cantidad con guiones en vez de vacíos».

### Cobertura mínima antes de considerar el servicio terminado

Al menos un fixture por cada uno de estos casos:

- [ ] Tabla alineada por espacios, una página (`columns`)
- [ ] Tabla alineada por espacios, varias páginas con cabecera repetida
- [ ] Tabla con líneas dibujadas (`ruling`)
- [ ] Línea por producto (`regex`)
- [ ] Nombres que se parten en dos líneas (fusión multilínea)
- [ ] Columna de precio con celdas vacías legítimas
- [ ] Cantidades expresadas como `-` y como `N/A`
- [ ] Tamaños en dos unidades distintas en el mismo documento (`10"` y `#5`)
- [ ] Un documento cuyo layout cambió → debe dar `FINGERPRINT_MISMATCH`
- [ ] Un PDF escaneado → ruta OCR
- [ ] Un documento con página de términos y condiciones que hay que saltar

### Cómo se genera un `.expected.json`

```bash
uv run python -m extractor.cli extract \
  --file tests/fixtures/acme/2026-03-spring.pdf \
  --profile tests/fixtures/acme/profile.json \
  --out tests/fixtures/acme/2026-03-spring.expected.json
```

**Y luego se revisa a mano, fila por fila, contra el PDF.** Un `.expected.json` generado y
no revisado no es un golden set: es un test que certifica el bug actual. Esto no es
negociable y hay que decirlo en la revisión de código.

### Anonimización

Los documentos reales llevan precios de proveedores. Antes de comprometer un fixture al
repo:

- Sustituir el nombre del grower por uno ficticio en el nombre de la carpeta.
- Multiplicar todos los precios por un factor arbitrario, o sustituirlos por valores
  inventados con el **mismo formato y la misma longitud** (esto último importa: cambiar
  `$1,250.00` por `$9.99` altera el ancho de columna y el fixture deja de probar lo que
  probaba).
- Si un documento no se puede anonimizar sin destruir el caso, dejarlo fuera del repo y
  referenciarlo desde `tests/fixtures/EXTERNAL.md` con instrucciones para obtenerlo.

## Las tres pruebas que no pueden faltar

### Determinismo

```python
# tests/golden/test_determinism.py
@pytest.mark.parametrize("fixture", all_fixtures())
def test_extraction_is_byte_identical_across_runs(fixture):
    a = run_extraction(fixture)
    b = run_extraction(fixture)
    assert canonical_json(a) == canonical_json(b)  # excluye duration_ms
```

Si falla, hay estado oculto, iteración sobre un `set`, o una dependencia del reloj.

### Estanqueidad de red

```python
# tests/conftest.py
@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def deny(*a, **k):
        raise AssertionError("un test intentó abrir una conexión de red")

    monkeypatch.setattr(socket.socket, "connect", deny)
```

Aplicado a toda la suite. El fetcher se sustituye siempre por un doble que lee de disco.
Esto además documenta la regla 9 de `CLAUDE.md` de forma ejecutable.

### Capas

```python
# tests/test_layering.py
```
Recorre los imports de cada módulo con `ast` y falla si `domain` importa de `engine`,
`adapters` o `api`, o si `engine` importa `fitz`, `pdfplumber` o `fastapi`.

## Property tests de los parsers

Con `hypothesis`, las invariantes que importan:

```
precio:      cualquier Decimal positivo con 2 decimales, formateado con los separadores
             del perfil, se parsea de vuelta al mismo Decimal
precio:      ninguna cadena, sea cual sea, hace que el parser lance una excepción
cantidad:    "" nunca produce 0        ← la regla que más caro sale romper
tamaño:      si un patrón casa, magnitude > 0
texto:       normalizar es idempotente: norm(norm(x)) == norm(x)
```

La segunda y la tercera son las que justifican todo el esfuerzo de `hypothesis`.

## Marcadores

```toml
[tool.pytest.ini_options]
markers = [
  "golden: usa fixtures de documentos reales",
  "slow: tarda más de un segundo",
  "ocr: requiere el binario tesseract",
]
```

`uv run pytest -m "not slow and not ocr"` es el bucle de desarrollo. CI corre todo.

## CI

GitHub Actions, en cada push:

```
uv sync --all-extras
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest --cov=src/extractor --cov-report=term-missing
```

El job instala `tesseract-ocr` para que los tests marcados `ocr` corran. Cobertura mínima
90% sobre `domain/` (es puro, no hay excusa) y 75% global.
