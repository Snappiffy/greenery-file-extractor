"""Perfil de extracción y validación semántica."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from extractor.domain.errors import InvalidProfileError

ColumnRole = Literal[
    "plant_name",
    "size",
    "price",
    "quantity",
    "availability",
    "grower_code",
    "notes",
]

StrategyName = Literal["columns", "ruling", "regex"]
SizeDimension = Literal["pot_diameter", "pot_volume", "plant_height", "spread"]


def _compile_regex(pattern: str, *, where: str) -> re.Pattern[str]:
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise InvalidProfileError(
            f"Invalid regex in {where}: {exc}",
            detail={"where": where, "pattern": pattern, "error": str(exc)},
        ) from exc


class HeaderAnchor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    match: Literal["contains", "exact", "regex"] = "contains"
    on_every_page: bool = True
    offset_lines: int = 1

    @model_validator(mode="after")
    def _compile_if_regex(self) -> HeaderAnchor:
        if self.match == "regex":
            _compile_regex(self.text, where="table.header_anchor.text")
        return self


class RulingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vertical_strategy: str = "lines"
    horizontal_strategy: str = "lines"
    snap_tolerance: float = 3.0


class MultilineConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    continuation_max_gap: float = 14.0
    join_with: str = " "


class TableConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: StrategyName = "columns"
    column_boundaries: list[float] | None = None
    boundary_tolerance: float = 4.0
    ruling: RulingConfig | None = None
    line_pattern: str | None = None
    header_anchor: HeaderAnchor | None = None
    stop_patterns: list[str] = Field(default_factory=list)
    row_tolerance: float = 2.5
    multiline: MultilineConfig = Field(default_factory=MultilineConfig)

    @field_validator("stop_patterns")
    @classmethod
    def _compile_stop_patterns(cls, value: list[str]) -> list[str]:
        for index, pattern in enumerate(value):
            _compile_regex(pattern, where=f"table.stop_patterns[{index}]")
        return value


class ColumnConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: ColumnRole
    index: int = Field(ge=0)
    required: bool = False


class PriceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strip: list[str] = Field(default_factory=lambda: ["$", "USD", "ea", "/ea", "each"])
    decimal_separator: str = "."
    thousands_separator: str = ","
    on_range: Literal["min", "max", "issue"] = "min"
    empty_means: Literal["unknown", "zero"] = "unknown"
    max_reasonable: Decimal = Decimal("10000.00")

    @field_validator("max_reasonable", mode="before")
    @classmethod
    def _parse_max_reasonable(cls, value: object) -> object:
        if isinstance(value, str):
            try:
                return Decimal(value)
            except InvalidOperation as exc:
                raise ValueError(f"invalid max_reasonable: {value}") from exc
        return value


class QuantityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    empty_means: Literal["unknown", "zero"] = "unknown"
    on_non_numeric: Literal["issue", "null"] = "issue"


class AvailabilityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    true_values: list[str] = Field(
        default_factory=lambda: ["yes", "y", "available", "in stock", "avail", "x", "✓"]
    )
    false_values: list[str] = Field(
        default_factory=lambda: ["no", "n", "sold out", "so", "unavailable", "none", "0"]
    )
    empty_means: Literal["true", "false", "unknown"] = "true"
    derive_from_quantity: bool = False


class SizePattern(BaseModel):
    model_config = ConfigDict(extra="forbid")

    regex: str
    unit: str
    dimension: SizeDimension

    @field_validator("regex")
    @classmethod
    def _must_compile(cls, value: str) -> str:
        _compile_regex(value, where="parsing.size.patterns.regex")
        return value


_DEFAULT_SIZE_PATTERNS: list[dict[str, str]] = [
    {"regex": r'(?P<v>\d+(?:\.\d+)?)\s*"', "unit": "in", "dimension": "pot_diameter"},
    {"regex": r"(?P<v>\d+(?:\.\d+)?)\s*in\b", "unit": "in", "dimension": "pot_diameter"},
    {"regex": r"#(?P<v>\d+)", "unit": "gal", "dimension": "pot_volume"},
    {"regex": r"(?P<v>\d+(?:\.\d+)?)\s*gal\b", "unit": "gal", "dimension": "pot_volume"},
    {
        "regex": r"(?P<v>\d+(?:\.\d+)?)\s*(?:ft|')\s*(?:HT|tall)",
        "unit": "ft",
        "dimension": "plant_height",
    },
]


class SizeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patterns: list[SizePattern] = Field(
        default_factory=lambda: [SizePattern.model_validate(p) for p in _DEFAULT_SIZE_PATTERNS]
    )
    on_multiple_matches: Literal["issue", "first"] = "issue"
    on_no_match: Literal["issue", "null"] = "issue"


class TextConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collapse_whitespace: bool = True
    trim: bool = True
    normalize_unicode: Literal["NFKC"] = "NFKC"
    drop_soft_hyphens: bool = True


class ParsingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    price: PriceConfig = Field(default_factory=PriceConfig)
    quantity: QuantityConfig = Field(default_factory=QuantityConfig)
    availability: AvailabilityConfig = Field(default_factory=AvailabilityConfig)
    size: SizeConfig = Field(default_factory=SizeConfig)
    text: TextConfig = Field(default_factory=TextConfig)


class FiltersConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    drop_rows_matching: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "plant_name": [r"^$", r"^NOTES?\b", r"^\*+$", r"^-+$"],
        }
    )
    drop_rows_where_all_empty: list[str] = Field(
        default_factory=lambda: ["price", "quantity", "availability"]
    )
    min_plant_name_length: int = 3

    @model_validator(mode="after")
    def _compile_drop_patterns(self) -> FiltersConfig:
        for role, patterns in self.drop_rows_matching.items():
            for index, pattern in enumerate(patterns):
                _compile_regex(pattern, where=f"filters.drop_rows_matching.{role}[{index}]")
        return self


class DocumentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["pdf", "image"] = "pdf"
    pages: str | list[int] = "all"
    skip_pages_matching: list[str] = Field(default_factory=list)
    password: str | None = None

    @field_validator("skip_pages_matching")
    @classmethod
    def _compile_skip_patterns(cls, value: list[str]) -> list[str]:
        for index, pattern in enumerate(value):
            _compile_regex(pattern, where=f"document.skip_pages_matching[{index}]")
        return value


class Profile(BaseModel):
    """Perfil de extracción normalizado y validado."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    profile_id: str | None = None
    grower_id: str | None = None
    version: int = 1
    layout_fingerprint: str | None = None
    document: DocumentConfig = Field(default_factory=DocumentConfig)
    table: TableConfig = Field(default_factory=TableConfig)
    columns: list[ColumnConfig]
    parsing: ParsingConfig = Field(default_factory=ParsingConfig)
    filters: FiltersConfig = Field(default_factory=FiltersConfig)

    @model_validator(mode="after")
    def _semantic_rules(self) -> Profile:
        roles = [column.role for column in self.columns]
        duplicates = sorted({role for role in roles if roles.count(role) > 1})
        if duplicates:
            raise InvalidProfileError(
                f"Duplicate column roles: {', '.join(duplicates)}",
                detail={"duplicate_roles": duplicates},
            )

        role_set = set(roles)
        if "plant_name" not in role_set or "size" not in role_set:
            raise InvalidProfileError(
                "Columns must include plant_name and size.",
                detail={"roles": roles},
            )

        for column in self.columns:
            if column.role in {"plant_name", "size"} and not column.required:
                raise InvalidProfileError(
                    f"Column '{column.role}' must have required=true.",
                    detail={"role": column.role},
                )

        strategy = self.table.strategy
        if strategy == "columns":
            boundaries = self.table.column_boundaries
            if boundaries is None or len(boundaries) < 2:
                raise InvalidProfileError(
                    "strategy=columns requires column_boundaries with at least 2 values.",
                    detail={},
                )
            if any(boundaries[i] >= boundaries[i + 1] for i in range(len(boundaries) - 1)):
                raise InvalidProfileError(
                    "column_boundaries must be strictly increasing.",
                    detail={"column_boundaries": boundaries},
                )
            max_index = len(boundaries) - 2
            for column in self.columns:
                if column.index > max_index:
                    raise InvalidProfileError(
                        f"Column index {column.index} out of range for column_boundaries.",
                        detail={
                            "role": column.role,
                            "index": column.index,
                            "max_index": max_index,
                        },
                    )

        if strategy == "regex":
            if not self.table.line_pattern:
                raise InvalidProfileError(
                    "strategy=regex requires table.line_pattern.",
                    detail={},
                )
            compiled = _compile_regex(self.table.line_pattern, where="table.line_pattern")
            group_names = set(compiled.groupindex)
            for column in self.columns:
                if column.role not in group_names:
                    raise InvalidProfileError(
                        f"line_pattern is missing named group for role '{column.role}'.",
                        detail={"role": column.role, "groups": sorted(group_names)},
                    )

        if strategy == "ruling" and self.table.ruling is None:
            self.table = self.table.model_copy(update={"ruling": RulingConfig()})

        return self

    @classmethod
    def from_payload(cls, data: dict[str, Any]) -> Profile:
        """Valida y normaliza un perfil recibido por HTTP o CLI."""
        try:
            return cls.model_validate(data)
        except InvalidProfileError:
            raise
        except ValidationError as exc:
            unwrapped = _unwrap_invalid_profile(exc)
            if unwrapped is not None:
                raise unwrapped from exc
            raise InvalidProfileError(
                f"Invalid profile: {exc.error_count()} validation error(s)",
                detail={"errors": exc.errors(include_url=False)},
            ) from exc
        except Exception as exc:
            raise InvalidProfileError(
                f"Invalid profile: {exc}",
                detail={"error": str(exc)},
            ) from exc


def _unwrap_invalid_profile(exc: BaseException) -> InvalidProfileError | None:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, InvalidProfileError):
            return current
        current = current.__cause__ or current.__context__
    for error in getattr(exc, "errors", lambda: [])():
        ctx = error.get("ctx") if isinstance(error, dict) else None
        if isinstance(ctx, dict):
            error_exc = ctx.get("error")
            if isinstance(error_exc, InvalidProfileError):
                return error_exc
    return None
