"""Utilidades de test compartidas."""

from __future__ import annotations

from typing import Any


def minimal_profile(**overrides: Any) -> dict[str, Any]:
    """Perfil válido mínimo (strategy=columns) para tests."""
    payload: dict[str, Any] = {
        "schema_version": 1,
        "version": 1,
        "document": {"kind": "pdf", "pages": "all"},
        "table": {
            "strategy": "columns",
            "column_boundaries": [52.0, 268.5, 372.0, 468.0, 540.0],
            "boundary_tolerance": 4.0,
            "header_anchor": {
                "text": "BOTANICAL NAME",
                "match": "contains",
                "on_every_page": True,
                "offset_lines": 1,
            },
            "stop_patterns": [r"^\s*TOTAL\b"],
            "row_tolerance": 2.5,
        },
        "columns": [
            {"role": "plant_name", "index": 0, "required": True},
            {"role": "size", "index": 1, "required": True},
            {"role": "price", "index": 2},
            {"role": "quantity", "index": 3},
        ],
    }
    payload.update(overrides)
    return payload
