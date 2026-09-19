"""Parsers de campos tipados."""

from extractor.domain.parsing.availability import parse_availability
from extractor.domain.parsing.price import parse_price
from extractor.domain.parsing.quantity import parse_quantity
from extractor.domain.parsing.size import parse_size
from extractor.domain.parsing.text import normalize_text

__all__ = [
    "normalize_text",
    "parse_availability",
    "parse_price",
    "parse_quantity",
    "parse_size",
]
