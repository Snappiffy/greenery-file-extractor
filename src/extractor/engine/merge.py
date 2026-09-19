"""Fusión de filas multilínea."""

from __future__ import annotations

from extractor.domain.issues import IssueCode, make_issue
from extractor.domain.profile import Profile
from extractor.engine.filters import DraftRow

_ANCHOR_PREFERENCE = ("price", "size", "grower_code")


def merge_multiline_rows(rows: list[DraftRow], profile: Profile) -> list[DraftRow]:
    """Fusiona continuaciones de plant_name según las cinco condiciones."""
    cfg = profile.table.multiline
    if not cfg.enabled or not rows:
        return rows

    anchors = _anchor_roles(profile)
    merged: list[DraftRow] = []
    for row in rows:
        if row.dropped:
            merged.append(row)
            continue
        if not merged:
            merged.append(row)
            continue
        prev = merged[-1]
        if prev.dropped:
            merged.append(row)
            continue
        if _is_continuation(prev, row, anchors=anchors, max_gap=cfg.continuation_max_gap):
            prev.cells["plant_name"] = (
                prev.cells.get("plant_name", "") + cfg.join_with + row.cells.get("plant_name", "")
            )
            prev.source_lines.extend(row.source_lines)
            prev.bottom = max(prev.bottom, row.bottom)
            prev.x0 = min(prev.x0, row.x0)
            prev.x1 = max(prev.x1, row.x1)
            prev.issues.append(
                make_issue(
                    IssueCode.MULTILINE_JOINED,
                    field="plant_name",
                    detail="joined continuation line into plant_name",
                )
            )
        else:
            merged.append(row)
    return merged


def _anchor_roles(profile: Profile) -> list[str]:
    present = {col.role for col in profile.columns}
    return [role for role in _ANCHOR_PREFERENCE if role in present]


def _is_continuation(
    prev: DraftRow,
    current: DraftRow,
    *,
    anchors: list[str],
    max_gap: float,
) -> bool:
    plant = current.cells.get("plant_name", "").strip()
    if not plant:
        return False
    if anchors and not all(not current.cells.get(role, "").strip() for role in anchors):
        return False
    gap = current.top - prev.bottom
    if gap < 0:
        gap = abs(current.top - prev.top)
    return gap <= max_gap
