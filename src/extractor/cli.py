"""CLI de depuración del extractor."""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from typing import Any

from extractor.domain.parsing import (
    normalize_text,
    parse_availability,
    parse_price,
    parse_quantity,
    parse_size,
)
from extractor.domain.profile import (
    AvailabilityConfig,
    PriceConfig,
    QuantityConfig,
    SizeConfig,
    TextConfig,
)


def _serialize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if hasattr(value, "model_dump"):
        data = value.model_dump(mode="json")
        magnitude = getattr(value, "magnitude", None)
        if "magnitude" in data and isinstance(magnitude, Decimal):
            data["magnitude"] = format(magnitude, "f")
        return data
    return value


def cmd_parse(args: argparse.Namespace) -> int:
    """Prueba un parser de campo desde la terminal."""
    parser_name: str = args.parser
    text: str = args.text
    value: Any
    issues: list[Any]

    if parser_name == "price":
        value, issues = parse_price(text, PriceConfig())
    elif parser_name == "quantity":
        value, issues = parse_quantity(text, QuantityConfig())
    elif parser_name == "availability":
        value, issues = parse_availability(text, AvailabilityConfig())
    elif parser_name == "size":
        value, issues = parse_size(text, SizeConfig(), plant_name=args.plant_name or "")
    elif parser_name == "text":
        value, issues = normalize_text(text, TextConfig()), []
    else:
        print(f"unknown parser: {parser_name}", file=sys.stderr)
        return 2

    payload = {
        "parser": parser_name,
        "input": text,
        "value": _serialize(value),
        "issues": [issue.model_dump(mode="json") for issue in issues],
    }
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="extractor")
    sub = parser.add_subparsers(dest="command", required=True)

    parse_cmd = sub.add_parser("parse", help="Test a field parser")
    parse_cmd.add_argument(
        "--parser",
        required=True,
        choices=["price", "quantity", "availability", "size", "text"],
    )
    parse_cmd.add_argument("--text", required=True, help="Input text to parse")
    parse_cmd.add_argument(
        "--plant-name",
        default="",
        help="Optional plant_name when testing size recovery",
    )
    parse_cmd.set_defaults(func=cmd_parse)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
