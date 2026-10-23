"""Column mapping validation and auto-suggestion services."""

from __future__ import annotations

from typing import Any

from .schemas import CANONICAL_SCHEMAS, suggest_column_mappings


def validate_file_mapping(
    headers: list[str],
    schema_type: str,
    column_mapping: dict[str, str],
) -> dict[str, Any]:
    """Validate a source-to-canonical column mapping for a single CSV file."""
    if schema_type not in CANONICAL_SCHEMAS:
        return {
            "valid": False,
            "errors": [f"Unknown canonical schema type: {schema_type!r}"],
            "unmapped_source_columns": headers,
            "missing_required_columns": [],
        }

    schema_def = CANONICAL_SCHEMAS[schema_type]
    valid_targets = {col.name for col in schema_def.columns}
    required_targets = set(schema_def.required_columns)

    errors: list[str] = []
    seen_targets: dict[str, str] = {}  # target -> source

    for source_col, target_col in column_mapping.items():
        if source_col not in headers:
            errors.append(f"Source column {source_col!r} does not exist in the file.")
        if target_col not in valid_targets:
            errors.append(
                f"Target column {target_col!r} is not a valid field for schema {schema_type!r}."
            )
        if target_col in seen_targets:
            errors.append(
                f"Conflicting mapping: both {seen_targets[target_col]!r} and {source_col!r} map to {target_col!r}."
            )
        seen_targets[target_col] = source_col

    unmapped_sources = [h for h in headers if h not in column_mapping]
    mapped_targets = set(column_mapping.values())
    missing_required = sorted(required_targets - mapped_targets)

    if missing_required:
        errors.append(
            f"Missing required canonical column(s) for {schema_type}: {', '.join(missing_required)}."
        )

    is_valid = len(errors) == 0

    return {
        "valid": is_valid,
        "errors": errors,
        "unmapped_source_columns": unmapped_sources,
        "missing_required_columns": missing_required,
    }


def compute_auto_mapping_for_file(
    headers: list[str],
    preferred_schema: str | None = None,
) -> tuple[str, dict[str, str]]:
    """Auto-detect schema and generate recommended column mappings."""
    return suggest_column_mappings(headers, preferred_schema)
