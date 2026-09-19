"""Genera fixtures golden de M3 (columns)."""

from __future__ import annotations

from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent

COL_PLANT = 52.0
COL_SIZE = 268.0
COL_PRICE = 372.0
COL_QTY = 468.0

ROWS = [
    ("Ficus lyrata", '10"', "$42.50", "12"),
    ("Monstera deliciosa", '14"', "$68.00", "4"),
    ("Dracaena marginata", '10"', "$35.00", "8"),
    ("Sansevieria trifasciata", '8"', "$22.00", "20"),
    ("Pothos golden", '6"', "$12.50", "30"),
]


def _header(page: pymupdf.Page, title: str) -> None:
    page.insert_text((COL_PLANT, 72), title, fontsize=11)
    page.insert_text((COL_PLANT, 118), "BOTANICAL NAME", fontsize=10)
    page.insert_text((COL_SIZE, 118), "SIZE", fontsize=10)
    page.insert_text((COL_PRICE, 118), "PRICE", fontsize=10)
    page.insert_text((COL_QTY, 118), "QTY", fontsize=10)


def _rows(
    page: pymupdf.Page, rows: list[tuple[str, str, str, str]], start_y: float = 140.0
) -> None:
    y = start_y
    for plant, size, price, qty in rows:
        page.insert_text((COL_PLANT, y), plant, fontsize=9)
        page.insert_text((COL_SIZE, y), size, fontsize=9)
        page.insert_text((COL_PRICE, y), price, fontsize=9)
        page.insert_text((COL_QTY, y), qty, fontsize=9)
        y += 16.0


def build_single_page(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    _header(page, "ACME NURSERY — SPRING 2026")
    _rows(page, ROWS)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    doc.close()


def build_multipage(path: Path) -> None:
    doc = pymupdf.open()
    page1 = doc.new_page(width=612, height=792)
    _header(page1, "ACME NURSERY — SPRING 2026")
    _rows(page1, ROWS[:3])

    page2 = doc.new_page(width=612, height=792)
    _header(page2, "ACME NURSERY — SPRING 2026")
    _rows(page2, ROWS[3:])
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    doc.close()


def build_multiline(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    _header(page, "ACME NURSERY — SPRING 2026")
    # Fila 1 normal
    page.insert_text((COL_PLANT, 140), "Ficus lyrata", fontsize=9)
    page.insert_text((COL_SIZE, 140), '10"', fontsize=9)
    page.insert_text((COL_PRICE, 140), "$42.50", fontsize=9)
    page.insert_text((COL_QTY, 140), "12", fontsize=9)
    # Fila 2 parte 1 (con precio)
    page.insert_text((COL_PLANT, 156), "Dracaena marginata", fontsize=9)
    page.insert_text((COL_SIZE, 156), '14"', fontsize=9)
    page.insert_text((COL_PRICE, 156), "$68.00", fontsize=9)
    page.insert_text((COL_QTY, 156), "4", fontsize=9)
    # Continuación: solo plant_name, anclas vacías
    page.insert_text((COL_PLANT, 168), "'Colorama' Character Specimen", fontsize=9)
    # Fila 3
    page.insert_text((COL_PLANT, 184), "Monstera deliciosa", fontsize=9)
    page.insert_text((COL_SIZE, 184), '10"', fontsize=9)
    page.insert_text((COL_PRICE, 184), "$35.00", fontsize=9)
    page.insert_text((COL_QTY, 184), "8", fontsize=9)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    doc.close()


PROFILE = {
    "schema_version": 1,
    "version": 1,
    "document": {"kind": "pdf", "pages": "all"},
    "table": {
        "strategy": "columns",
        "column_boundaries": [40.0, 250.0, 350.0, 450.0, 560.0],
        "boundary_tolerance": 8.0,
        "header_anchor": {
            "text": "BOTANICAL NAME",
            "match": "contains",
            "on_every_page": True,
            "offset_lines": 0,
        },
        "stop_patterns": [r"^\s*TOTAL\b"],
        "row_tolerance": 3.0,
        "multiline": {"enabled": True, "continuation_max_gap": 14.0, "join_with": " "},
    },
    "columns": [
        {"role": "plant_name", "index": 0, "required": True},
        {"role": "size", "index": 1, "required": True},
        {"role": "price", "index": 2},
        {"role": "quantity", "index": 3},
    ],
    "parsing": {
        "price": {"strip": ["$", "USD", "ea", "/ea", "each"]},
        "size": {
            "patterns": [
                {"regex": r'(?P<v>\d+(?:\.\d+)?)\s*"', "unit": "in", "dimension": "pot_diameter"},
                {
                    "regex": r"(?P<v>\d+(?:\.\d+)?)\s*in\b",
                    "unit": "in",
                    "dimension": "pot_diameter",
                },
            ]
        },
    },
}


def main() -> None:
    import json

    single = ROOT / "acme-single"
    multi = ROOT / "acme-multipage"
    mline = ROOT / "acme-multiline"
    for folder in (single, multi, mline):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "profile.json").write_text(json.dumps(PROFILE, indent=2) + "\n", encoding="utf-8")
        (folder / "NOTES.md").write_text("", encoding="utf-8")

    build_single_page(single / "catalog.pdf")
    (single / "NOTES.md").write_text(
        "Tabla alineada por espacios, una página (columns).\n", encoding="utf-8"
    )

    build_multipage(multi / "catalog.pdf")
    (multi / "NOTES.md").write_text("Varias páginas con cabecera repetida.\n", encoding="utf-8")

    build_multiline(mline / "catalog.pdf")
    (mline / "NOTES.md").write_text(
        "Nombres que se parten en dos líneas (fusión multilínea).\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
