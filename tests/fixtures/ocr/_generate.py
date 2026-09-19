"""Genera PDF escaneado (solo imagen) para tests OCR."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent

PROFILE = {
    "schema_version": 1,
    "version": 1,
    "document": {"kind": "pdf", "pages": "all"},
    "table": {
        "strategy": "regex",
        "line_pattern": (
            r"^(?P<plant_name>.+?)\s*\|\s*"
            r"(?P<size>\d+(?:\.\d+)?\"?)\s*\|\s*"
            r"\$(?P<price>[\d,]+\.\d{2})\s*\|\s*"
            r"(?P<quantity>\d+)$"
        ),
        "header_anchor": {
            "text": "BOTANICAL NAME",
            "match": "contains",
            "on_every_page": False,
            "offset_lines": 0,
        },
        "stop_patterns": [],
        "multiline": {"enabled": False},
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
                {
                    "regex": r'(?P<v>\d+(?:\.\d+)?)\s*"',
                    "unit": "in",
                    "dimension": "pot_diameter",
                }
            ]
        },
    },
}


def _font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def build_scanned_pdf(path: Path) -> None:
    """PDF sin capa de texto: una imagen con filas pipe-separated."""
    image = Image.new("RGB", (1400, 520), "white")
    draw = ImageDraw.Draw(image)
    font = _font(32)
    draw.text((40, 40), "BOTANICAL NAME | SIZE | PRICE | QTY", fill="black", font=font)
    rows = [
        'Ficus lyrata | 10" | $42.50 | 12',
        'Monstera deliciosa | 14" | $68.00 | 4',
        'Dracaena marginata | 10" | $35.00 | 8',
    ]
    y = 120
    for line in rows:
        draw.text((40, y), line, fill="black", font=font)
        y += 70

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    png = buffer.getvalue()

    doc = pymupdf.open()
    page = doc.new_page(width=700, height=260)
    page.insert_image(page.rect, stream=png)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    doc.close()


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    build_scanned_pdf(ROOT / "scanned.pdf")
    (ROOT / "profile.json").write_text(json.dumps(PROFILE, indent=2) + "\n", encoding="utf-8")
    (ROOT / "NOTES.md").write_text(
        "PDF escaneado (imagen embebida, sin texto nativo) para M7 OCR.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
