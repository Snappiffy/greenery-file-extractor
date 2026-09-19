"""Verifica las reglas de dependencia entre capas con AST."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "extractor"

# Capas y módulos externos que no pueden importar.
FORBIDDEN: dict[str, set[str]] = {
    "domain": {
        "extractor.engine",
        "extractor.application",
        "extractor.adapters",
        "extractor.api",
        "fastapi",
        "fitz",
        "pymupdf",
        "pdfplumber",
        "httpx",
        "PIL",
        "pytesseract",
    },
    "engine": {
        "extractor.api",
        "extractor.adapters",
        "extractor.application",
        "fastapi",
        "fitz",
        "pymupdf",
        "pdfplumber",
        "httpx",
    },
    "application": {
        "extractor.api",
        "fastapi",
        "fitz",
        "pymupdf",
        "pdfplumber",
    },
    "adapters": {
        "extractor.api",
        "extractor.engine",
        "extractor.application",
        "fastapi",
    },
}


def _layer_of(relative: Path) -> str | None:
    if not relative.parts:
        return None
    top = relative.parts[0]
    if top in FORBIDDEN:
        return top
    return None


def _imported_modules(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.append(node.module)
    return names


def _violations_for(path: Path, layer: str) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    forbidden = FORBIDDEN[layer]
    found: list[str] = []
    for name in _imported_modules(tree):
        for banned in forbidden:
            if name == banned or name.startswith(banned + "."):
                found.append(f"{path.relative_to(SRC_ROOT)} imports {name}")
    return found


def test_layering_rules() -> None:
    """Cada módulo respeta las fronteras de capa definidas en docs/06."""
    if not SRC_ROOT.exists():
        pytest.skip("src/extractor aún no existe")

    violations: list[str] = []
    for path in SRC_ROOT.rglob("*.py"):
        relative = path.relative_to(SRC_ROOT)
        layer = _layer_of(relative)
        if layer is None:
            continue
        violations.extend(_violations_for(path, layer))

    assert violations == [], "Violaciones de capas:\n" + "\n".join(violations)
