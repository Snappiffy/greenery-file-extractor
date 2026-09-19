"""Genera PDFs de fixture para M2 (layout, precios, desplazamiento, cifrado)."""

from __future__ import annotations

from pathlib import Path

import pymupdf

FIXTURES = Path(__file__).resolve().parent

# Columnas base (x0 aproximado de cada campo).
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
    ("Calathea orbifolia", '10"', "$48.00", "6"),
    ("Alocasia amazonica", '12"', "$55.00", "3"),
    ("Philodendron birkin", '8"', "$28.00", "15"),
    ("ZZ plant", '10"', "$32.00", "9"),
    ("Snake plant laurentii", '10"', "$26.00", "11"),
]

ROWS_ALT_PRICES = [
    ("Ficus lyrata", '10"', "$99.99", "1"),
    ("Monstera deliciosa", '14"', "$11.00", "99"),
    ("Dracaena marginata", '10"', "$1.00", "2"),
    ("Sansevieria trifasciata", '8"', "$2.00", "3"),
    ("Pothos golden", '6"', "$3.50", "4"),
    ("Calathea orbifolia", '10"', "$4.00", "5"),
    ("Alocasia amazonica", '12"', "$5.00", "6"),
    ("Philodendron birkin", '8"', "$6.00", "7"),
    ("ZZ plant", '10"', "$7.00", "8"),
    ("Snake plant laurentii", '10"', "$8.00", "9"),
]


def _draw_list(
    page: pymupdf.Page,
    *,
    title: str,
    rows: list[tuple[str, str, str, str]],
    price_x: float = COL_PRICE,
) -> None:
    page.insert_text((COL_PLANT, 72), title, fontsize=11)
    page.insert_text((COL_PLANT, 118), "BOTANICAL NAME", fontsize=10)
    page.insert_text((COL_SIZE, 118), "SIZE", fontsize=10)
    page.insert_text((price_x, 118), "PRICE", fontsize=10)
    page.insert_text((COL_QTY, 118), "QTY", fontsize=10)

    y = 140.0
    for plant, size, price, qty in rows:
        page.insert_text((COL_PLANT, y), plant, fontsize=9)
        page.insert_text((COL_SIZE, y), size, fontsize=9)
        page.insert_text((price_x, y), price, fontsize=9)
        page.insert_text((COL_QTY, y), qty, fontsize=9)
        y += 16.0


def _save(doc: pymupdf.Document, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    doc.close()


def build_base(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    _draw_list(page, title="ACME NURSERY — SPRING 2026", rows=ROWS)
    _save(doc, path)


def build_alt_prices(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    _draw_list(page, title="ACME NURSERY — SPRING 2027", rows=ROWS_ALT_PRICES)
    _save(doc, path)


def build_shifted_column(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    _draw_list(
        page,
        title="ACME NURSERY — SPRING 2026",
        rows=ROWS,
        price_x=COL_PRICE + 30.0,
    )
    _save(doc, path)


def build_encrypted(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    _draw_list(page, title="ACME NURSERY — SPRING 2026", rows=ROWS)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(
        path,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw="secret",
        owner_pw="owner",
    )
    doc.close()


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    build_base(FIXTURES / "layout_base.pdf")
    build_alt_prices(FIXTURES / "layout_alt_prices.pdf")
    build_shifted_column(FIXTURES / "layout_shifted_price.pdf")
    build_encrypted(FIXTURES / "layout_encrypted.pdf")
    (FIXTURES / "NOTES.md").write_text(
        "Fixtures M2: mismo layout con precios/fechas distintas; "
        "columna PRICE desplazada 30 pt; PDF cifrado.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
