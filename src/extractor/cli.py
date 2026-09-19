"""CLI de depuración del extractor."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

from extractor import ENGINE_VERSION
from extractor.adapters.readers.pymupdf_reader import PyMuPdfReader
from extractor.api.serialize import serialize_extract_result, serialize_sample_result
from extractor.application.extract_document import (
    DocumentInput,
    ExtractOptions,
    extract_document,
)
from extractor.application.sample_document import SampleOptions, sample_document
from extractor.domain.errors import InvalidProfileError
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
    Profile,
    QuantityConfig,
    SizeConfig,
    TextConfig,
)


class _NoFetch:
    def fetch(self, url: str) -> bytes:
        raise RuntimeError(f"network disabled in CLI: {url}")


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


def _document_from_file(path: Path, content_type: str) -> DocumentInput:
    data = path.read_bytes()
    return DocumentInput(
        content_type=content_type,
        filename=path.name,
        inline_base64=base64.b64encode(data).decode("ascii"),
    )


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


def cmd_sample(args: argparse.Namespace) -> int:
    path = Path(args.file)
    result = sample_document(
        document=_document_from_file(path, "application/pdf"),
        options=SampleOptions(pages=[1], max_lines_per_page=args.max_lines),
        fetcher=_NoFetch(),
        reader_for=lambda _ct: PyMuPdfReader(),
        engine_version=ENGINE_VERSION,
    )
    payload = serialize_sample_result(result).model_dump(mode="json")
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    path = Path(args.file)
    profile_path = Path(args.profile)
    try:
        profile = Profile.from_payload(json.loads(profile_path.read_text(encoding="utf-8")))
    except InvalidProfileError:
        raise
    except Exception as exc:
        raise InvalidProfileError(str(exc), detail={}) from exc

    result = extract_document(
        document=_document_from_file(path, "application/pdf"),
        profile=profile,
        options=ExtractOptions(fail_on_fingerprint_mismatch=False),
        fetcher=_NoFetch(),
        reader_for=lambda _ct: PyMuPdfReader(),
        engine_version=ENGINE_VERSION,
    )
    payload = serialize_extract_result(result).model_dump(mode="json")
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

    sample_cmd = sub.add_parser("sample", help="Sample layout evidence from a PDF")
    sample_cmd.add_argument("--file", required=True, help="Path to PDF")
    sample_cmd.add_argument("--max-lines", type=int, default=120)
    sample_cmd.set_defaults(func=cmd_sample)

    extract_cmd = sub.add_parser("extract", help="Extract rows with a profile")
    extract_cmd.add_argument("--file", required=True, help="Path to PDF")
    extract_cmd.add_argument("--profile", required=True, help="Path to profile JSON")
    extract_cmd.set_defaults(func=cmd_extract)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
