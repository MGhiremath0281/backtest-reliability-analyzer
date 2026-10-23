"""Data normalization and preparation service."""

from __future__ import annotations

import csv
from typing import Any

from ..csv_io import read_csv
from .mapping import compute_auto_mapping_for_file
from .schemas import CANONICAL_SCHEMAS
from .storage import StorageManager


def prepare_dataset(dataset_id: str, storage: StorageManager) -> dict[str, Any]:
    """Transform uploaded CSV files into canonical, normalized datasets.

    Original uploaded files are strictly read-only and preserved.
    """
    metadata = storage.get_dataset_metadata(dataset_id)
    if not metadata:
        raise ValueError(f"Dataset {dataset_id} not found.")

    if metadata.get("is_existing"):
        return {
            "dataset_id": dataset_id,
            "status": "ready",
            "prepared_files": [
                {
                    "filename": f["original_filename"],
                    "schema_type": f.get("detected_schema") or "existing",
                    "row_count": f.get("row_count", 0),
                    "columns": f.get("headers", []),
                }
                for f in metadata.get("files", [])
            ],
            "total_records": metadata.get("total_rows", 0),
            "review_flags": {},
            "warnings": [],
        }

    dataset_path = storage.get_dataset_dir(dataset_id)
    prepared_dir = dataset_path / "prepared"
    prepared_dir.mkdir(parents=True, exist_ok=True)

    mapping_data = storage.get_mapping(dataset_id) or {}
    mappings_by_file: dict[str, dict[str, Any]] = {
        m["file_id"]: m for m in mapping_data.get("mappings", [])
    }

    files = metadata.get("files", [])
    prepared_files: list[dict[str, Any]] = []
    total_records = 0
    warnings: list[str] = []
    review_flags: dict[str, int] = {}

    for file_info in files:
        file_id = file_info["file_id"]
        file_path = storage.get_file_path(dataset_id, file_id)
        if not file_path or not file_path.is_file():
            warnings.append(
                f"File {file_info.get('original_filename')} missing from storage."
            )
            continue

        raw_table = read_csv(file_path)
        if not raw_table.readable:
            warnings.append(
                f"File {file_info.get('original_filename')} is unreadable or malformed."
            )
            continue

        # Determine mapping
        mapping_spec = mappings_by_file.get(file_id)
        if mapping_spec:
            schema_type = mapping_spec["schema_type"]
            col_map = mapping_spec["column_mapping"]
        else:
            # Auto-detect mapping
            schema_type, col_map = compute_auto_mapping_for_file(raw_table.headers)
            warnings.append(
                f"Auto-mapped {file_info['original_filename']} to {schema_type}."
            )

        schema_def = CANONICAL_SCHEMAS.get(schema_type)
        if not schema_def:
            warnings.append(
                f"Unsupported schema {schema_type} for file {file_info['original_filename']}."
            )
            continue

        # Prepare normalized headers
        canonical_headers = [col.name for col in schema_def.columns]

        # Invert mapping: source_col -> target_col
        # Build rows
        prepared_rows: list[list[str]] = []
        for row in raw_table.rows:
            row_data: dict[str, str] = {}
            for src_col, tgt_col in col_map.items():
                row_data[tgt_col] = row.get(src_col)

            # Defaults and cleanups
            if schema_type == "prices":
                if not row_data.get("Series"):
                    row_data["Series"] = "EQ"
                if row_data.get("Symbol"):
                    row_data["Symbol"] = row_data["Symbol"].strip().upper()

            out_row = [row_data.get(header, "") for header in canonical_headers]
            prepared_rows.append(out_row)

        # Write prepared file
        safe_name = f"{schema_type}.csv"
        # If multiple files of same schema, disambiguate with file_id
        target_path = prepared_dir / safe_name
        if target_path.exists():
            target_path = prepared_dir / f"{schema_type}_{file_id}.csv"

        with open(target_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(canonical_headers)
            writer.writerows(prepared_rows)

        prepared_count = len(prepared_rows)
        total_records += prepared_count

        prepared_files.append(
            {
                "filename": target_path.name,
                "schema_type": schema_type,
                "row_count": prepared_count,
                "columns": canonical_headers,
                "source_file": file_info["original_filename"],
            }
        )

    result = {
        "dataset_id": dataset_id,
        "status": "prepared",
        "prepared_files": prepared_files,
        "total_records": total_records,
        "review_flags": review_flags,
        "warnings": warnings,
    }

    storage.save_preparation(dataset_id, result)
    return result
