# Greenery · Servicio Extractor

Microservicio HTTP **sin estado** que convierte un PDF o una imagen de lista de precios de
un vivero (*grower*) en filas estructuradas, guiado por un **perfil de extracción** que le
entrega quien lo llama.

Es una pieza del módulo de ingesta de catálogo de Greenary App. El contexto completo está
en `docs/01-contexto-y-alcance.md`. **Léelo antes de escribir código.**

---

## Reglas no negociables

Estas reglas *son* el servicio. Si una tarea parece pedir romper una, la tarea está mal
planteada: pregunta antes de implementarla.

1. **Cero IA.** Este servicio no llama a ningún modelo de lenguaje, nunca. No tiene
   credenciales de proveedores de IA ni dependencias de SDKs de IA. La inferencia de
   perfiles la hace el worker, con la evidencia que devuelve `POST /v1/sample`.
2. **Cero base de datos.** Sin Postgres, sin Mongo, sin ORM, sin conexión persistente a
   nada. Este servicio no sabe qué es un `sku_id` ni un `grower_id` — solo los transporta
   como opacos.
3. **Determinista.** La misma entrada con el mismo perfil produce una salida
   byte-idéntica. Prohibido: `random`, `datetime.now()` dentro de la extracción, iterar
   sobre un `set`, depender del orden del sistema de archivos, o del orden de un `dict`
   construido por concurrencia.
4. **Sin estado.** Nada persiste entre peticiones. Sin caché en disco, sin variables
   globales mutables. Cualquier instancia atiende cualquier petición.
5. **Nunca lanza excepción por una fila mala.** Una fila que no se puede parsear se
   devuelve con su `raw` intacto y uno o más `issues`. Solo falla la petición completa
   cuando el documento es ilegible o el perfil es inválido.
6. **El dinero es `Decimal`.** Nunca `float`, ni en el parseo, ni en el modelo, ni en la
   serialización (se emite como *string* en JSON).
7. **`None` no es `0`.** Ausente es `None` = «el documento no lo dice». `0` = «el documento
   dice cero». Colapsar ambos corrompe el catálogo aguas abajo. Esto vale sobre todo para
   `quantity`.
8. **`raw` siempre se conserva.** Cada fila devuelve el texto exacto que se leyó, además de
   lo parseado. Es la base de la auditoría y del emparejamiento posterior.
9. **Sin red durante la extracción.** La única salida de red permitida es descargar el
   documento desde la URL firmada, y ocurre antes de empezar. Los tests corren sin red.

---

## Stack

| Pieza | Elección | Nota |
|---|---|---|
| Lenguaje | Python 3.12 | |
| Dependencias | `uv` | Lockfile comprometido en el repo |
| API | FastAPI + Pydantic v2 | |
| Servidor | `uvicorn` con workers | |
| PDF (geometría) | `PyMuPDF` (fitz) | Palabras con bbox — el motor principal |
| PDF (tablas con líneas) | `pdfplumber` | Solo para la estrategia `ruling` |
| Imágenes | `Pillow` | |
| OCR | `pytesseract` + binario `tesseract` | Opcional, desactivado por defecto |
| Lint y formato | `ruff` | |
| Tipos | `mypy --strict` sobre `src/` | |
| Tests | `pytest` + `syrupy` (snapshots) + `hypothesis` | |

---

## Comandos

```bash
uv sync --all-extras              # instalar dependencias
uv run uvicorn extractor.api.app:app --reload --port 8080   # servidor de desarrollo

uv run pytest                     # toda la suite
uv run pytest -m golden           # solo el golden set
uv run pytest -m "not slow"       # rápido, para el bucle de desarrollo
uv run pytest --snapshot-update   # regenerar snapshots (revisar el diff SIEMPRE)

uv run ruff check . --fix
uv run ruff format .
uv run mypy src

# CLI de depuración — extrae sin levantar el servidor
uv run python -m extractor.cli extract --file tests/fixtures/acme/spring.pdf \
                                       --profile tests/fixtures/acme/profile.json
uv run python -m extractor.cli sample  --file tests/fixtures/acme/spring.pdf
```

El CLI no es un extra: es la herramienta con la que se depura un perfil que no encaja.
Debe existir desde el hito M1.

---

## Convenciones

- **Idioma.** La documentación y los comentarios van en español. **Todo identificador de
  código, clave de JSON, nombre de archivo y mensaje de log va en inglés.** No se mezclan.
- **Tipado.** `mypy --strict` pasa sin `# type: ignore` salvo en fronteras de librerías sin
  stubs, y ahí con un comentario que explique por qué.
- **Modelos.** Pydantic v2 para todo lo que cruza la frontera HTTP. Dataclasses o Pydantic
  para el dominio, pero el dominio **no importa nada de FastAPI**.
- **Errores.** Excepciones de dominio en `domain/errors.py`, traducidas a respuestas HTTP
  en una sola capa (`api/error_handlers.py`). El dominio no conoce códigos HTTP.
- **Logs.** JSON estructurado a stdout. **Nunca** se registra el contenido del documento ni
  texto de filas: solo identificadores, contadores y códigos. Un log con precios de un
  proveedor dentro es una fuga.
- **Commits.** Convencionales (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).

---

## Mapa de la documentación

| Archivo | Qué contiene |
|---|---|
| `docs/01-contexto-y-alcance.md` | Dónde encaja este servicio, qué hace y qué explícitamente no hace |
| `docs/02-contrato-api.md` | Endpoints, esquemas de petición y respuesta, códigos de error, autenticación, límites |
| `docs/03-perfil-de-extraccion.md` | Esquema completo del perfil + tres ejemplos reales |
| `docs/04-modelo-de-salida.md` | Esquema de fila, catálogo de `issues`, diagnósticos |
| `docs/05-motor-de-extraccion.md` | El algoritmo paso a paso, el fingerprint, las estrategias, OCR |
| `docs/06-arquitectura.md` | Estructura de carpetas, reglas de dependencia, cómo extender |
| `docs/07-pruebas.md` | Golden set, snapshots, determinismo, property tests |
| `docs/08-despliegue.md` | Dockerfile, Railway, variables de entorno, observabilidad |
| `docs/09-plan-de-implementacion.md` | Hitos ordenados con criterios de aceptación |

**Orden de trabajo: `docs/09` manda.** No empieces por donde te parezca; los hitos están
ordenados para que cada uno se pueda verificar antes del siguiente.
