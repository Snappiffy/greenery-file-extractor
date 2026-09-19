"""Genera fixtures golden de M3 (columns) y M5 (ruling, regex)."""

from __future__ import annotations

import json
from collections.abc import Callable
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

PARSING = {
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
}


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
    page.insert_text((COL_PLANT, 140), "Ficus lyrata", fontsize=9)
    page.insert_text((COL_SIZE, 140), '10"', fontsize=9)
    page.insert_text((COL_PRICE, 140), "$42.50", fontsize=9)
    page.insert_text((COL_QTY, 140), "12", fontsize=9)
    page.insert_text((COL_PLANT, 156), "Dracaena marginata", fontsize=9)
    page.insert_text((COL_SIZE, 156), '14"', fontsize=9)
    page.insert_text((COL_PRICE, 156), "$68.00", fontsize=9)
    page.insert_text((COL_QTY, 156), "4", fontsize=9)
    page.insert_text((COL_PLANT, 168), "'Colorama' Character Specimen", fontsize=9)
    page.insert_text((COL_PLANT, 184), "Monstera deliciosa", fontsize=9)
    page.insert_text((COL_SIZE, 184), '10"', fontsize=9)
    page.insert_text((COL_PRICE, 184), "$35.00", fontsize=9)
    page.insert_text((COL_QTY, 184), "8", fontsize=9)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    doc.close()


def build_ruling(path: Path) -> None:
    """Tabla con líneas vectoriales visibles para pdfplumber."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    cols = [50.0, 110.0, 280.0, 340.0, 420.0, 500.0]
    rows_y = [100.0, 120.0, 140.0, 160.0, 180.0, 200.0]
    for x in cols:
        page.draw_line(p1=(x, rows_y[0]), p2=(x, rows_y[-1]), color=(0, 0, 0), width=0.5)
    for y in rows_y:
        page.draw_line(p1=(cols[0], y), p2=(cols[-1], y), color=(0, 0, 0), width=0.5)

    headers = ("CODE", "Item", "SIZE", "PRICE", "AVAIL")
    data = [
        ("A-1", "Ficus lyrata", '10"', "$42.50", "Yes"),
        ("A-2", "Monstera deliciosa", '14"', "$68.00", "No"),
        ("A-3", "Dracaena marginata", '10"', "$35.00", "Yes"),
        ("A-4", "Pothos golden", '6"', "$12.50", "Yes"),
    ]
    for index, header in enumerate(headers):
        page.insert_text((cols[index] + 4, rows_y[0] + 14), header, fontsize=8)
    for row_index, row in enumerate(data):
        for col_index, value in enumerate(row):
            page.insert_text(
                (cols[col_index] + 4, rows_y[row_index + 1] + 14),
                value,
                fontsize=8,
            )

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    doc.close()


def build_regex(path: Path) -> None:
    """Una línea por producto con formato fijo."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((52, 72), "ACME CATALOG — LINE FORMAT", fontsize=11)
    lines = [
        'ACM-0001 Ficus lyrata 10" $42.50 12',
        'ACM-0002 Monstera deliciosa 14" $68.00 4',
        'ACM-0003 Dracaena marginata 10" $35.00 8',
        'ACM-0004 Pothos golden 6" $12.50 30',
    ]
    y = 120.0
    for line in lines:
        page.insert_text((52, y), line, fontsize=9)
        y += 16.0
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    doc.close()


PROFILE = {
    "schema_version": 1,
    "version": 1,
    "document": {"kind": "pdf", "pages": "all"},
    "table": {
        "strategy": "columns",
        "column_boundaries": [52.0, 268.0, 372.0, 468.0, 560.0],
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
    "parsing": PARSING,
}

PROFILE_RULING = {
    "schema_version": 1,
    "version": 1,
    "document": {"kind": "pdf", "pages": "all"},
    "table": {
        "strategy": "ruling",
        "ruling": {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "snap_tolerance": 3.0,
        },
        "header_anchor": {
            "text": "Item",
            "match": "contains",
            "on_every_page": True,
            "offset_lines": 0,
        },
        "stop_patterns": [],
        "multiline": {"enabled": False},
    },
    "columns": [
        {"role": "grower_code", "index": 0},
        {"role": "plant_name", "index": 1, "required": True},
        {"role": "size", "index": 2, "required": True},
        {"role": "price", "index": 3},
        {"role": "availability", "index": 4},
    ],
    "parsing": {
        **PARSING,
        "availability": {
            "true_values": ["yes", "y", "available", "in stock", "avail", "x"],
            "false_values": ["no", "n", "sold out", "so", "unavailable", "none", "0"],
            "empty_means": "true",
        },
    },
}

PROFILE_REGEX = {
    "schema_version": 1,
    "version": 1,
    "document": {"kind": "pdf", "pages": "all"},
    "table": {
        "strategy": "regex",
        "line_pattern": (
            r"^(?P<grower_code>[A-Z]{3}-\d{4})\s+"
            r"(?P<plant_name>.+?)\s+"
            r"(?P<size>\d+(?:\.\d+)?\"?)\s+"
            r"\$(?P<price>[\d,]+\.\d{2})\s+"
            r"(?P<quantity>\d+|-)$"
        ),
        "header_anchor": {
            "text": "ACME CATALOG",
            "match": "contains",
            "on_every_page": False,
            "offset_lines": 0,
        },
        "stop_patterns": [],
        "multiline": {"enabled": False},
    },
    "columns": [
        {"role": "grower_code", "index": 0},
        {"role": "plant_name", "index": 1, "required": True},
        {"role": "size", "index": 2, "required": True},
        {"role": "price", "index": 3},
        {"role": "quantity", "index": 4},
    ],
    "parsing": PARSING,
}


def _write_folder(
    folder: Path,
    profile: dict,
    notes: str,
    builder: Callable[[Path], None],
) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "profile.json").write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    (folder / "NOTES.md").write_text(notes, encoding="utf-8")
    builder(folder / "catalog.pdf")


def main() -> None:
    _write_folder(
        ROOT / "acme-single",
        PROFILE,
        "Tabla alineada por espacios, una página (columns).\n",
        build_single_page,
    )
    _write_folder(
        ROOT / "acme-multipage",
        PROFILE,
        "Varias páginas con cabecera repetida.\n",
        build_multipage,
    )
    _write_folder(
        ROOT / "acme-multiline",
        PROFILE,
        "Nombres que se parten en dos líneas (fusión multilínea).\n",
        build_multiline,
    )
    _write_folder(
        ROOT / "acme-ruling",
        PROFILE_RULING,
        "Tabla con líneas dibujadas (ruling).\n",
        build_ruling,
    )
    _write_folder(
        ROOT / "acme-regex",
        PROFILE_REGEX,
        "Línea por producto con formato fijo (regex).\n",
        build_regex,
    )


if __name__ == "__main__":
    main()
