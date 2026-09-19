"""Genera la collection Bruno OpenCollection v1 (uso interno, una vez)."""

from __future__ import annotations

import base64
import json
import textwrap
from pathlib import Path

ROOT = Path("greenery-extractor/collections/v1")
GOLDEN = Path("tests/fixtures/golden")


def b64(name: str) -> str:
    return base64.b64encode((GOLDEN / name / "catalog.pdf").read_bytes()).decode("ascii")


def profile(name: str) -> dict:
    return json.loads((GOLDEN / name / "profile.json").read_text(encoding="utf-8"))


def write_folder(path: Path, name: str, seq: int, docs: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    indented = "\n".join(f"  {line}" if line else "" for line in docs.splitlines())
    (path / "folder.yml").write_text(
        f"info:\n  name: {name}\n  type: folder\n  seq: {seq}\n\ndocs: |-\n{indented}\n",
        encoding="utf-8",
    )


def write_request(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def extract_body(pdf_var: str, profile_obj: dict) -> str:
    doc = {
        "document": {
            "content_type": "application/pdf",
            "inline_base64": f"__PDF__{pdf_var}__",
            "filename": "catalog.pdf",
        },
        "profile": profile_obj,
        "options": {
            "ocr": "auto",
            "max_pages": 200,
            "include_bbox": True,
            "include_raw_words": False,
            "fail_on_fingerprint_mismatch": False,
        },
    }
    raw = json.dumps(doc, ensure_ascii=False, indent=2)
    return raw.replace(f'"__PDF__{pdf_var}__"', '"{{' + pdf_var + '}}"')


def dump_env(single: str, multi: str, mline: str) -> None:
    variables = [
        (
            "baseUrl",
            "http://localhost:8080",
            False,
            "Base URL del extractor en local (uvicorn --port 8080)",
        ),
        (
            "sharedSecret",
            "test-secret-with-at-least-32-characters",
            True,
            "Debe coincidir con EXTRACTOR_SHARED_SECRET del .env (min. 32 chars)",
        ),
        (
            "pdfBase64",
            "",
            False,
            "Opcional: pega aqui el base64 de TU PDF para sample/extract custom",
        ),
        (
            "lastFingerprint",
            "",
            False,
            "Se rellena automaticamente tras Sample · acme-single (after-response)",
        ),
        (
            "acmeSinglePdfBase64",
            single,
            False,
            "Fixture tests/fixtures/golden/acme-single/catalog.pdf",
        ),
        (
            "acmeMultipagePdfBase64",
            multi,
            False,
            "Fixture tests/fixtures/golden/acme-multipage/catalog.pdf",
        ),
        (
            "acmeMultilinePdfBase64",
            mline,
            False,
            "Fixture tests/fixtures/golden/acme-multiline/catalog.pdf",
        ),
    ]
    lines = ["name: local", "variables:"]
    for name, value, secret, desc in variables:
        lines.append(f"  - name: {name}")
        lines.append(f"    value: {json.dumps(value)}")
        lines.append("    enabled: true")
        lines.append(f"    secret: {'true' if secret else 'false'}")
        lines.append(f"    description: {json.dumps(desc)}")
    (ROOT / "environments").mkdir(parents=True, exist_ok=True)
    (ROOT / "environments" / "local.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)

    (ROOT / "opencollection.yml").write_text(
        textwrap.dedent(
            """\
            opencollection: 1.0.0

            info:
              name: v1
              summary: greenery-extractor HTTP API — health, sample y extract
              version: "1.0.0"
              authors:
                - name: Snappiffy

            bundled: false

            extensions:
              bruno:
                ignore:
                  - node_modules
                  - .git
                defaultEnvironment: local

            request:
              headers:
                - name: Content-Type
                  value: application/json
                  description: Todos los POST usan JSON (no multipart)
                - name: Accept
                  value: application/json
              auth:
                type: bearer
                token: "{{sharedSecret}}"

            docs: |-
              # greenery-extractor · collection v1

              Microservicio **sin estado** que convierte PDF (e imagenes) de listas de precios
              en filas estructuradas, guiado por un **perfil de extraccion**.

              ## Como usar esta collection

              1. Abre el workspace `greenery-extractor` en Bruno.
              2. Selecciona el environment **local**.
              3. Pon en `sharedSecret` el mismo valor que `EXTRACTOR_SHARED_SECRET` de tu `.env`
                 (minimo 32 caracteres).
              4. Arranca el servicio:

                 ```bash
                 uv run uvicorn extractor.api.app:app --reload --port 8080
                 ```

              5. Ejecuta en orden: **ops → sample → extract**. Los requests de **errors**
                 provocan fallos a proposito para validar el contrato.

              ## Autenticacion

              Cabecera `Authorization: Bearer <EXTRACTOR_SHARED_SECRET>` en **todo** endpoint
              excepto `GET /health`. La collection hereda Bearer desde el nivel raiz
              (`{{sharedSecret}}`). `health` anula auth con `type: none`.

              ## Flujo recomendado con un PDF nuevo

              1. `POST /v1/sample` → mirar `column_candidates`, `recommended_strategy`, `fingerprint`.
              2. Armar / ajustar un `profile` (boundaries ≈ candidatos ±4 pt).
              3. `POST /v1/extract` con `fail_on_fingerprint_mismatch: false` al principio.
              4. Revisar `rows`, `issues` y `diagnostics` (un `200` no implica calidad perfecta).

              ## Documento: url vs inline_base64

              Exactamente **uno** de los dos:

              - `inline_base64` — ideal en local (esta collection lo usa con fixtures golden).
              - `url` — HTTPS firmada; el host debe estar en `FETCH_ALLOWED_HOSTS`.

              `content_type` es obligatorio y manda (no se infiere por extension). Hoy lo util
              local es `application/pdf`.

              ## Errores

              Cuerpo siempre:

              ```json
              { "error": { "code": "...", "message": "...", "detail": {} } }
              ```

              Codigos habituales: `UNAUTHORIZED`, `INVALID_PROFILE`, `INVALID_REQUEST`,
              `FINGERPRINT_MISMATCH`, `DOCUMENT_UNREADABLE`, `NO_ROWS_FOUND`,
              `UNSUPPORTED_CONTENT_TYPE`, `SOURCE_FETCH_FAILED`.

              Contrato completo: `docs/02-contrato-api.md` en el repo.
            """
        ),
        encoding="utf-8",
    )

    dump_env(b64("acme-single"), b64("acme-multipage"), b64("acme-multiline"))

    write_folder(
        ROOT / "ops",
        "ops",
        1,
        "# Operacion\n\nProbes y versionado. Empieza por aqui para confirmar que el proceso responde\nantes de mandar PDFs.\n",
    )

    write_request(
        ROOT / "ops" / "health.yml",
        textwrap.dedent(
            """\
            info:
              name: GET health
              type: http
              seq: 1
              tags:
                - smoke
                - ops

            http:
              method: GET
              url: "{{baseUrl}}/health"
              auth:
                type: none

            runtime:
              assertions:
                - expression: res.status
                  operator: eq
                  value: "200"
              scripts:
                - type: tests
                  code: |-
                    test("health returns ok", function () {
                      expect(res.status).to.equal(200);
                      expect(res.body.status).to.equal("ok");
                    });

            settings:
              encodeUrl: true
              timeout: 10000
              followRedirects: true
              maxRedirects: 5

            docs: |-
              # GET /health

              **Liveness.** Sin autenticacion y sin dependencias.

              ## Cuando usarlo

              - Comprobar que uvicorn esta arriba.
              - Probe de orquestadores (Docker/K8s/Railway).

              ## Respuesta esperada

              ```json
              { "status": "ok" }
              ```

              HTTP `200` siempre que el proceso responda. No valida PyMuPDF ni tesseract.
            """
        ),
    )

    write_request(
        ROOT / "ops" / "ready.yml",
        textwrap.dedent(
            """\
            info:
              name: GET ready
              type: http
              seq: 2
              tags:
                - smoke
                - ops

            http:
              method: GET
              url: "{{baseUrl}}/ready"
              auth: inherit

            runtime:
              assertions:
                - expression: res.status
                  operator: eq
                  value: "200"
              scripts:
                - type: tests
                  code: |-
                    test("ready when pymupdf ok", function () {
                      expect(res.status).to.equal(200);
                      expect(res.body.status).to.equal("ready");
                      expect(res.body.checks.pymupdf).to.equal("ok");
                      expect(res.body.engine_version).to.be.a("string");
                    });

            settings:
              encodeUrl: true
              timeout: 10000
              followRedirects: true
              maxRedirects: 5

            docs: |-
              # GET /ready

              **Readiness.** Requiere Bearer. Verifica que PyMuPDF importa; si `OCR_ENABLED=true`,
              tambien exige que el binario `tesseract` responda a `--version`.

              ## Respuesta OK

              ```json
              {
                "status": "ready",
                "checks": { "pymupdf": "ok" },
                "engine_version": "1.0.0"
              }
              ```

              ## Degradado

              HTTP `503` con `"status": "degraded"` si algun check falla. El cuerpo incluye
              los mismos `checks` para diagnostico.
            """
        ),
    )

    write_request(
        ROOT / "ops" / "version.yml",
        textwrap.dedent(
            """\
            info:
              name: GET v1 version
              type: http
              seq: 3
              tags:
                - smoke
                - ops

            http:
              method: GET
              url: "{{baseUrl}}/v1/version"
              auth: inherit

            runtime:
              assertions:
                - expression: res.status
                  operator: eq
                  value: "200"
              scripts:
                - type: tests
                  code: |-
                    test("version advertises capabilities", function () {
                      expect(res.status).to.equal(200);
                      expect(res.body.engine_version).to.be.a("string");
                      expect(res.body.supported_strategies).to.include("columns");
                      expect(res.body.supported_content_types).to.include("application/pdf");
                    });

            settings:
              encodeUrl: true
              timeout: 10000
              followRedirects: true
              maxRedirects: 5

            docs: |-
              # GET /v1/version

              Capacidades del motor. El worker lo consulta al arrancar y registra
              `engine_version` en cada corrida.

              ## Respuesta

              ```json
              {
                "engine_version": "1.0.0",
                "profile_schema_version": 1,
                "supported_strategies": ["columns", "ruling", "regex"],
                "supported_content_types": [
                  "application/pdf",
                  "image/png",
                  "image/jpeg",
                  "image/tiff"
                ]
              }
              ```

              Requiere Bearer.
            """
        ),
    )

    write_folder(
        ROOT / "sample",
        "sample",
        2,
        "# POST /v1/sample\n\nDevuelve **evidencia de layout** (geometria). No interpreta roles de negocio.\nUsalo para construir o reparar un perfil antes de llamar a extract.\n",
    )

    write_request(
        ROOT / "sample" / "sample-acme-single.yml",
        textwrap.dedent(
            """\
            info:
              name: Sample · acme-single (golden)
              type: http
              seq: 1
              tags:
                - sample
                - golden
                - smoke

            http:
              method: POST
              url: "{{baseUrl}}/v1/sample"
              auth: inherit
              body:
                type: json
                data: |-
                  {
                    "document": {
                      "content_type": "application/pdf",
                      "inline_base64": "{{acmeSinglePdfBase64}}",
                      "filename": "acme-single-catalog.pdf"
                    },
                    "options": {
                      "pages": [1],
                      "max_lines_per_page": 120,
                      "ocr": "auto"
                    }
                  }

            runtime:
              assertions:
                - expression: res.status
                  operator: eq
                  value: "200"
              scripts:
                - type: tests
                  code: |-
                    test("sample recommends columns", function () {
                      expect(res.status).to.equal(200);
                      expect(res.body.recommended_strategy).to.equal("columns");
                      expect(res.body.pages).to.be.an("array").that.is.not.empty;
                      expect(res.body.pages[0].column_candidates.length).to.be.at.least(2);
                      expect(res.body.fingerprint).to.match(/^sha256:/);
                    });
                - type: after-response
                  code: |-
                    if (res.status === 200 && res.body.fingerprint) {
                      bru.setEnvVar("lastFingerprint", res.body.fingerprint);
                    }

            settings:
              encodeUrl: true
              timeout: 60000
              followRedirects: true
              maxRedirects: 5

            docs: |-
              # POST /v1/sample — fixture acme-single

              PDF golden de una pagina con tabla alineada por columnas (`columns`).

              ## Body

              | Campo | Valor |
              |---|---|
              | `document.content_type` | `application/pdf` |
              | `document.inline_base64` | variable `acmeSinglePdfBase64` |
              | `options.pages` | `[1]` — casi siempre basta |
              | `options.max_lines_per_page` | `120` — tope de tamano de respuesta |
              | `options.ocr` | `auto` |

              ## Que mirar en la respuesta

              | Campo | Esperado en este fixture |
              |---|---|
              | `recommended_strategy` | `columns` |
              | `is_scanned` | `false` |
              | `column_candidates[].x` | ~52, 268, 372, 468 (±4 pt vs profile) |
              | `ruling_lines.vertical` | `[]` (sin lineas de tabla dibujadas) |
              | `fingerprint` | `sha256:...` (se guarda en `lastFingerprint`) |

              ## Siguiente paso

              Usar esos `x` como `table.column_boundaries` (mas un margen derecho) y
              asignar roles en `columns` del perfil → request **Extract · acme-single**.
            """
        ),
    )

    write_request(
        ROOT / "sample" / "sample-custom-pdf.yml",
        textwrap.dedent(
            """\
            info:
              name: Sample · PDF custom (pdfBase64)
              type: http
              seq: 2
              tags:
                - sample
                - custom

            http:
              method: POST
              url: "{{baseUrl}}/v1/sample"
              auth: inherit
              body:
                type: json
                data: |-
                  {
                    "document": {
                      "content_type": "application/pdf",
                      "inline_base64": "{{pdfBase64}}",
                      "filename": "custom.pdf"
                    },
                    "options": {
                      "pages": [1],
                      "max_lines_per_page": 120,
                      "ocr": "auto"
                    }
                  }

            settings:
              encodeUrl: true
              timeout: 120000
              followRedirects: true
              maxRedirects: 5

            docs: |-
              # POST /v1/sample — tu PDF

              1. Genera el base64:

                 ```bash
                 base64 -i /ruta/a/tu.pdf | tr -d '\\n' | pbcopy
                 ```

              2. Pegalo en la variable de environment `pdfBase64`.
              3. Ejecuta este request.
              4. Anota `column_candidates`, `recommended_strategy` y texto de cabecera
                 en `pages[0].lines` para armar el perfil.

              Si `pdfBase64` esta vacio, el servidor devolvera error de documento ilegible
              o validacion fallida.
            """
        ),
    )

    write_folder(
        ROOT / "extract",
        "extract",
        3,
        "# POST /v1/extract\n\nAplica un **perfil** al documento y devuelve filas + diagnosticos.\nUn HTTP 200 significa que el documento se pudo leer; la calidad se mide en\n`diagnostics` e `issues` por fila.\n",
    )

    for seq, folder_name, pdf_var, title in [
        (1, "acme-single", "acmeSinglePdfBase64", "Extract · acme-single (golden)"),
        (2, "acme-multipage", "acmeMultipagePdfBase64", "Extract · acme-multipage (golden)"),
        (3, "acme-multiline", "acmeMultilinePdfBase64", "Extract · acme-multiline (golden)"),
    ]:
        body = extract_body(pdf_var, profile(folder_name))
        body_indented = "\n".join(f"      {line}" if line else "" for line in body.splitlines())
        write_request(
            ROOT / "extract" / f"extract-{folder_name}.yml",
            f"""\
info:
  name: {title}
  type: http
  seq: {seq}
  tags:
    - extract
    - golden
    - smoke

http:
  method: POST
  url: "{{{{baseUrl}}}}/v1/extract"
  auth: inherit
  body:
    type: json
    data: |-
{body_indented}

runtime:
  assertions:
    - expression: res.status
      operator: eq
      value: "200"
  scripts:
    - type: tests
      code: |-
        test("extract returns rows", function () {{
          expect(res.status).to.equal(200);
          expect(res.body.rows).to.be.an("array").that.is.not.empty;
          expect(res.body.diagnostics.strategy_used).to.equal("columns");
          expect(res.body.layout.fingerprint).to.match(/^sha256:/);
        }});

settings:
  encodeUrl: true
  timeout: 120000
  followRedirects: true
  maxRedirects: 5

docs: |-
  # POST /v1/extract — fixture {folder_name}

  Usa el PDF y el `profile.json` de `tests/fixtures/golden/{folder_name}/`.

  ## Options importantes

  | Option | Valor aqui | Nota |
  |---|---|---|
  | `fail_on_fingerprint_mismatch` | `false` | Evita 409 al depurar |
  | `include_bbox` | `true` | Ver geometria de cada fila |
  | `include_raw_words` | `false` | Solo depuracion profunda |

  ## Que mirar

  - `rows[].raw` / `text` — texto por columna
  - `rows[].parsed` — tipado (`price` como **string**, `quantity` int o `null`)
  - `rows[].issues` — filas malas no tumban la request
  - `diagnostics.rows_extracted`, `issues_by_code`, `duration_ms`

  Recuerda: **`None` ≠ `0`** en quantity/price ausentes.
""",
        )

    custom_profile = profile("acme-single")
    custom_body = {
        "document": {
            "content_type": "application/pdf",
            "inline_base64": "__PDF__",
            "filename": "custom.pdf",
        },
        "profile": custom_profile,
        "options": {
            "ocr": "auto",
            "max_pages": 200,
            "include_bbox": True,
            "include_raw_words": False,
            "fail_on_fingerprint_mismatch": False,
        },
    }
    cb = json.dumps(custom_body, ensure_ascii=False, indent=2).replace(
        '"__PDF__"', '"{{pdfBase64}}"'
    )
    cb_ind = "\n".join(f"      {line}" if line else "" for line in cb.splitlines())
    write_request(
        ROOT / "extract" / "extract-custom-pdf.yml",
        f"""\
info:
  name: Extract · PDF custom (pdfBase64 + perfil plantilla)
  type: http
  seq: 4
  tags:
    - extract
    - custom

http:
  method: POST
  url: "{{{{baseUrl}}}}/v1/extract"
  auth: inherit
  body:
    type: json
    data: |-
{cb_ind}

settings:
  encodeUrl: true
  timeout: 120000
  followRedirects: true
  maxRedirects: 5

docs: |-
  # POST /v1/extract — tu PDF

  1. Completa `pdfBase64` en el environment (igual que en Sample custom).
  2. Ajusta el `profile` del body:
     - `table.column_boundaries` desde los `x` de `/v1/sample`
     - `header_anchor.text` con una frase real de tu cabecera
     - `columns` / `parsing` segun el grower
  3. Empieza con `fail_on_fingerprint_mismatch: false`.
  4. Si `raw` sale bien pero `parsed` mal → tuning de parsers.
     Si `raw` ya viene mezclado → retoca boundaries / tolerancia.
""",
    )

    write_folder(
        ROOT / "errors",
        "errors",
        4,
        "# Casos de error\n\nRequests que deben fallar. Sirven para verificar codigos HTTP y el envelope\n`error.code` / `error.message` / `error.detail`.\n",
    )

    write_request(
        ROOT / "errors" / "unauthorized-missing-token.yml",
        textwrap.dedent(
            """\
            info:
              name: 401 · sin Authorization
              type: http
              seq: 1
              tags:
                - errors
                - auth

            http:
              method: GET
              url: "{{baseUrl}}/v1/version"
              auth:
                type: none

            runtime:
              assertions:
                - expression: res.status
                  operator: eq
                  value: "401"
              scripts:
                - type: tests
                  code: |-
                    test("missing bearer is unauthorized", function () {
                      expect(res.status).to.equal(401);
                      expect(res.body.error.code).to.equal("UNAUTHORIZED");
                    });

            settings:
              encodeUrl: true
              timeout: 10000

            docs: |-
              # 401 UNAUTHORIZED — token ausente

              Cualquier endpoint protegido sin cabecera `Authorization` debe responder 401.
              `/health` es la unica excepcion (no uses este patron ahi).
            """
        ),
    )

    write_request(
        ROOT / "errors" / "unauthorized-bad-token.yml",
        textwrap.dedent(
            """\
            info:
              name: 401 · Bearer incorrecto
              type: http
              seq: 2
              tags:
                - errors
                - auth

            http:
              method: GET
              url: "{{baseUrl}}/v1/version"
              auth:
                type: bearer
                token: "definitely-not-the-shared-secret-value!!"

            runtime:
              assertions:
                - expression: res.status
                  operator: eq
                  value: "401"
              scripts:
                - type: tests
                  code: |-
                    test("wrong bearer is unauthorized", function () {
                      expect(res.status).to.equal(401);
                      expect(res.body.error.code).to.equal("UNAUTHORIZED");
                    });

            settings:
              encodeUrl: true
              timeout: 10000

            docs: |-
              # 401 UNAUTHORIZED — secret incorrecto

              El servicio compara con `secrets.compare_digest` (tiempo constante).
              Un token de longitud distinta o contenido distinto → 401.
            """
        ),
    )

    write_request(
        ROOT / "errors" / "invalid-profile.yml",
        textwrap.dedent(
            """\
            info:
              name: 400 · INVALID_PROFILE
              type: http
              seq: 3
              tags:
                - errors
                - extract

            http:
              method: POST
              url: "{{baseUrl}}/v1/extract"
              auth: inherit
              body:
                type: json
                data: |-
                  {
                    "document": {
                      "content_type": "application/pdf",
                      "inline_base64": "{{acmeSinglePdfBase64}}",
                      "filename": "catalog.pdf"
                    },
                    "profile": {
                      "schema_version": 1,
                      "version": 1,
                      "this_is_not": "a valid profile"
                    },
                    "options": {
                      "fail_on_fingerprint_mismatch": false
                    }
                  }

            runtime:
              assertions:
                - expression: res.status
                  operator: eq
                  value: "400"
              scripts:
                - type: tests
                  code: |-
                    test("invalid profile returns 400", function () {
                      expect(res.status).to.equal(400);
                      expect(res.body.error.code).to.equal("INVALID_PROFILE");
                    });

            settings:
              encodeUrl: true
              timeout: 30000

            docs: |-
              # 400 INVALID_PROFILE

              El perfil no valida contra el esquema o es incoherente (roles duplicados,
              strategy sin campos requeridos, etc.). Ver `docs/03-perfil-de-extraccion.md`.
            """
        ),
    )

    write_request(
        ROOT / "errors" / "unsupported-content-type.yml",
        textwrap.dedent(
            """\
            info:
              name: 415 · UNSUPPORTED_CONTENT_TYPE
              type: http
              seq: 4
              tags:
                - errors
                - extract

            http:
              method: POST
              url: "{{baseUrl}}/v1/extract"
              auth: inherit
              body:
                type: json
                data: |-
                  {
                    "document": {
                      "content_type": "application/msword",
                      "inline_base64": "{{acmeSinglePdfBase64}}",
                      "filename": "catalog.doc"
                    },
                    "profile": {
                      "schema_version": 1,
                      "version": 1,
                      "document": { "kind": "pdf", "pages": "all" },
                      "table": {
                        "strategy": "columns",
                        "column_boundaries": [52, 268, 372, 468, 560],
                        "header_anchor": { "text": "BOTANICAL NAME", "match": "contains" }
                      },
                      "columns": [
                        { "role": "plant_name", "index": 0, "required": true },
                        { "role": "size", "index": 1, "required": true },
                        { "role": "price", "index": 2 },
                        { "role": "quantity", "index": 3 }
                      ]
                    },
                    "options": { "fail_on_fingerprint_mismatch": false }
                  }

            runtime:
              assertions:
                - expression: res.status
                  operator: eq
                  value: "415"
              scripts:
                - type: tests
                  code: |-
                    test("unsupported mime returns 415", function () {
                      expect(res.status).to.equal(415);
                      expect(res.body.error.code).to.equal("UNSUPPORTED_CONTENT_TYPE");
                    });

            settings:
              encodeUrl: true
              timeout: 30000

            docs: |-
              # 415 UNSUPPORTED_CONTENT_TYPE

              `content_type` no esta en la lista soportada. Manda el MIME declarado,
              no la extension del `filename`.
            """
        ),
    )

    write_request(
        ROOT / "errors" / "invalid-request-both-sources.yml",
        textwrap.dedent(
            """\
            info:
              name: 400 · INVALID_REQUEST (url + inline)
              type: http
              seq: 5
              tags:
                - errors
                - validation

            http:
              method: POST
              url: "{{baseUrl}}/v1/sample"
              auth: inherit
              body:
                type: json
                data: |-
                  {
                    "document": {
                      "content_type": "application/pdf",
                      "url": "https://fixtures.local/catalog.pdf",
                      "inline_base64": "{{acmeSinglePdfBase64}}",
                      "filename": "catalog.pdf"
                    },
                    "options": { "pages": [1] }
                  }

            runtime:
              scripts:
                - type: tests
                  code: |-
                    test("xor url/inline is enforced", function () {
                      expect(res.status).to.be.oneOf([400, 422]);
                      expect(res.body.error).to.exist;
                    });

            settings:
              encodeUrl: true
              timeout: 30000

            docs: |-
              # INVALID_REQUEST — url e inline_base64 a la vez

              El contrato exige **exactamente uno** de `url` o `inline_base64`.
              Este request manda ambos a proposito.
            """
        ),
    )

    Path("greenery-extractor/workspace.yml").write_text(
        textwrap.dedent(
            """\
            opencollection: 1.0.0
            info:
              name: "greenery-extractor"
              type: workspace

            collections:
              - name: "v1"
                path: "collections/v1"

            specs:

            docs: |-
              # Workspace greenery-extractor

              Abre esta carpeta como workspace en Bruno.

              Collection **v1** documenta y ejercita la API HTTP del microservicio
              `extractor` (M0-M5): ops, sample, extract y errores.

              Environment por defecto: **local** (`baseUrl` + `sharedSecret`).
            """
        ),
        encoding="utf-8",
    )

    print("generated", len(list(ROOT.rglob("*.yml"))), "yml files")


if __name__ == "__main__":
    main()
