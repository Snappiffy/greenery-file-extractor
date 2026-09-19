"""Parseo de DraftRow → Row tipada."""

from __future__ import annotations

from extractor.domain.issues import Issue, IssueCode, Severity, make_issue
from extractor.domain.models import BBox, ParsedRow, Row
from extractor.domain.parsing import (
    normalize_text,
    parse_availability,
    parse_price,
    parse_quantity,
    parse_size,
)
from extractor.domain.profile import Profile
from extractor.engine.filters import DraftRow


def draft_to_row(draft: DraftRow, *, row_index: int, profile: Profile, include_bbox: bool) -> Row:
    text_cfg = profile.parsing.text
    raw = {role: value for role, value in draft.cells.items()}
    text = {role: normalize_text(value, text_cfg) for role, value in raw.items()}
    issues: list[Issue] = list(draft.issues)

    for column in profile.columns:
        if column.required and not raw.get(column.role, "").strip():
            issues.append(
                make_issue(
                    IssueCode.REQUIRED_COLUMN_EMPTY,
                    field=column.role,
                    detail=f"required column {column.role!r} is empty",
                )
            )

    plant_name = text.get("plant_name") or None
    size_value, size_issues = parse_size(
        text.get("size", ""),
        profile.parsing.size,
        plant_name=text.get("plant_name", ""),
    )
    issues.extend(size_issues)

    price_value, price_issues = parse_price(text.get("price", ""), profile.parsing.price)
    issues.extend(price_issues)

    quantity_value, quantity_issues = parse_quantity(
        text.get("quantity", ""),
        profile.parsing.quantity,
    )
    issues.extend(quantity_issues)

    has_availability = any(col.role == "availability" for col in profile.columns)
    availability_value, availability_issues = parse_availability(
        text.get("availability", ""),
        profile.parsing.availability,
        quantity=quantity_value,
        has_availability_column=has_availability,
    )
    issues.extend(availability_issues)

    grower_code = text.get("grower_code") or None
    notes = text.get("notes") or None
    if grower_code == "":
        grower_code = None
    if notes == "":
        notes = None

    parsed = ParsedRow(
        plant_name=plant_name,
        size=size_value,
        price=price_value,
        quantity=quantity_value,
        availability=availability_value,
        grower_code=grower_code,
        notes=notes,
    )

    bbox = None
    if include_bbox:
        bbox = BBox(
            page=draft.page,
            x0=round(draft.x0, 1),
            top=round(draft.top, 1),
            x1=round(draft.x1, 1),
            bottom=round(draft.bottom, 1),
        )

    return Row(
        row_index=row_index,
        page=draft.page,
        source_lines=list(draft.source_lines),
        raw=raw,
        text=text,
        parsed=parsed,
        issues=issues,
        bbox=bbox,
    )


def count_severity(rows: list[Row]) -> tuple[int, int]:
    errors = 0
    warnings = 0
    for row in rows:
        if any(issue.severity == Severity.ERROR for issue in row.issues):
            errors += 1
        if any(issue.severity == Severity.WARNING for issue in row.issues):
            warnings += 1
    return errors, warnings


def issues_by_code(rows: list[Row]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for issue in row.issues:
            key = issue.code.value
            counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))
