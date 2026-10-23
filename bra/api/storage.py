"""Isolated, file-based persistence for BRA datasets, analyses, runs, and reports."""

from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger("bra.api.storage")

from .config import ApiConfig, get_config

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
EXISTING_DATASET_ID = "existing-data"


def sanitize_id(resource_id: str) -> str:
    """Validate resource ID against path traversal."""
    if not resource_id or not SAFE_ID_RE.match(resource_id):
        raise ValueError(f"Invalid resource ID: {resource_id!r}")
    return resource_id


def sanitize_filename(filename: str) -> str:
    """Sanitize uploaded filename to prevent directory traversal."""
    name = Path(filename).name
    cleaned = re.sub(r"[^\w\s.-]", "_", name).strip()
    return cleaned or "data.csv"


class StorageManager:
    """Manages file storage for all API resources in an isolated directory."""

    def __init__(self, config: ApiConfig | None = None) -> None:
        self.config = config or get_config()
        self.storage_dir = self.config.storage_dir
        self.data_root = self.config.data_root

        # Ensure base directories exist
        self.datasets_dir = self.storage_dir / "datasets"
        self.validations_dir = self.storage_dir / "validations"
        self.analyses_dir = self.storage_dir / "analyses"
        self.runs_dir = self.storage_dir / "runs"
        self.reports_dir = self.storage_dir / "reports"

        for directory in (
            self.datasets_dir,
            self.validations_dir,
            self.analyses_dir,
            self.runs_dir,
            self.reports_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # Datasets
    # -----------------------------------------------------------------------

    def get_dataset_dir(self, dataset_id: str) -> Path:
        sanitized = sanitize_id(dataset_id)
        path = self.datasets_dir / sanitized
        return path

    def create_dataset(
        self,
        name: str | None = None,
        description: str | None = None,
        dataset_id: str | None = None,
    ) -> dict[str, Any]:
        new_id = dataset_id or f"ds-{uuid4().hex[:12]}"
        sanitize_id(new_id)

        dataset_path = self.get_dataset_dir(new_id)
        dataset_path.mkdir(parents=True, exist_ok=True)
        (dataset_path / "uploads").mkdir(parents=True, exist_ok=True)
        (dataset_path / "prepared").mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc).isoformat()
        metadata: dict[str, Any] = {
            "dataset_id": new_id,
            "name": name or f"Dataset {new_id}",
            "description": description or "",
            "is_existing": False,
            "created_at": now,
            "status": "uploaded",
            "mapping_status": "unmapped",
            "preparation_status": "unprepared",
            "files": [],
        }
        self.save_dataset_metadata(new_id, metadata)
        return metadata

    def save_dataset_metadata(self, dataset_id: str, metadata: dict[str, Any]) -> None:
        dataset_path = self.get_dataset_dir(dataset_id)
        dataset_path.mkdir(parents=True, exist_ok=True)
        meta_file = dataset_path / "metadata.json"
        meta_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    def get_dataset_metadata(self, dataset_id: str) -> dict[str, Any] | None:
        if dataset_id == EXISTING_DATASET_ID:
            return self._get_existing_dataset_metadata()

        dataset_path = self.get_dataset_dir(dataset_id)
        meta_file = dataset_path / "metadata.json"
        if not meta_file.is_file():
            return None
        try:
            return json.loads(meta_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _get_existing_dataset_metadata(self) -> dict[str, Any]:
        """Virtual metadata for canonical repository data."""
        data_path = self.data_root
        files_info: list[dict[str, Any]] = []

        if data_path.is_dir():
            csv_paths = sorted(data_path.rglob("*.csv"))
            for path in csv_paths:
                try:
                    rel = path.relative_to(data_path).as_posix()
                    size = path.stat().st_size
                except (OSError, ValueError):
                    rel = path.name
                    size = 0
                files_info.append(
                    {
                        "file_id": f"exist_{path.stem}",
                        "original_filename": rel,
                        "stored_filename": rel,
                        "size_bytes": size,
                        "row_count": 0,
                        "headers": [],
                        "detected_schema": None,
                        "confidence": 1.0,
                        "uploaded_at": "canonical",
                    }
                )

        return {
            "dataset_id": EXISTING_DATASET_ID,
            "name": "Canonical Repository Dataset",
            "description": "Pre-collected NSE historical data tree from the repository data directory.",
            "is_existing": True,
            "file_count": len(files_info),
            "total_rows": 0,
            "created_at": "canonical",
            "status": "ready",
            "mapping_status": "mapped",
            "preparation_status": "prepared",
            "files": files_info,
            "root_path": str(data_path),
        }

    def list_datasets(self, include_existing: bool = True) -> list[dict[str, Any]]:
        datasets: list[dict[str, Any]] = []

        if include_existing and self.data_root.is_dir():
            datasets.append(self._get_existing_dataset_metadata())

        if self.datasets_dir.is_dir():
            for item in sorted(self.datasets_dir.iterdir()):
                if item.is_dir():
                    meta = self.get_dataset_metadata(item.name)
                    if meta:
                        datasets.append(meta)

        return datasets

    def delete_dataset(self, dataset_id: str) -> bool:
        if dataset_id == EXISTING_DATASET_ID:
            raise PermissionError("Cannot delete canonical repository dataset.")

        dataset_path = self.get_dataset_dir(dataset_id)
        if not dataset_path.is_dir():
            return False

        shutil.rmtree(dataset_path)
        return True

    def save_uploaded_file(
        self,
        dataset_id: str,
        filename: str,
        contents: bytes,
    ) -> dict[str, Any]:
        """Save uploaded CSV file inside the dataset's uploads directory."""
        dataset_path = self.get_dataset_dir(dataset_id)
        uploads_dir = dataset_path / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)

        file_id = f"f_{uuid4().hex[:8]}"
        safe_name = sanitize_filename(filename)
        stored_name = f"{file_id}_{safe_name}"
        dest_path = uploads_dir / stored_name
        dest_path.write_bytes(contents)

        return {
            "file_id": file_id,
            "original_filename": safe_name,
            "stored_filename": stored_name,
            "size_bytes": len(contents),
            "path": dest_path,
        }

    def get_file_path(self, dataset_id: str, file_id: str) -> Path | None:
        if dataset_id == EXISTING_DATASET_ID:
            # Look up inside data_root
            for p in self.data_root.rglob("*.csv"):
                if f"exist_{p.stem}" == file_id or p.name == file_id:
                    return p
            return None

        dataset_path = self.get_dataset_dir(dataset_id)
        # Check uploads
        uploads_dir = dataset_path / "uploads"
        if uploads_dir.is_dir():
            for p in uploads_dir.glob(f"{file_id}_*"):
                if p.is_file():
                    return p
        # Check prepared
        prepared_dir = dataset_path / "prepared"
        if prepared_dir.is_dir():
            for p in prepared_dir.glob("*.csv"):
                if p.stem == file_id or p.name == file_id:
                    return p
        return None

    # -----------------------------------------------------------------------
    # Mapping and Preparation Storage
    # -----------------------------------------------------------------------

    def save_mapping(self, dataset_id: str, mapping_data: dict[str, Any]) -> None:
        dataset_path = self.get_dataset_dir(dataset_id)
        (dataset_path / "mapping.json").write_text(
            json.dumps(mapping_data, indent=2), encoding="utf-8"
        )
        # Update metadata mapping_status
        meta = self.get_dataset_metadata(dataset_id)
        if meta:
            meta["mapping_status"] = "mapped"
            self.save_dataset_metadata(dataset_id, meta)

    def get_mapping(self, dataset_id: str) -> dict[str, Any] | None:
        dataset_path = self.get_dataset_dir(dataset_id)
        mapping_file = dataset_path / "mapping.json"
        if not mapping_file.is_file():
            return None
        try:
            return json.loads(mapping_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def save_preparation(self, dataset_id: str, prep_data: dict[str, Any]) -> None:
        dataset_path = self.get_dataset_dir(dataset_id)
        (dataset_path / "preparation.json").write_text(
            json.dumps(prep_data, indent=2), encoding="utf-8"
        )
        meta = self.get_dataset_metadata(dataset_id)
        if meta:
            meta["preparation_status"] = "prepared"
            meta["status"] = "ready"
            self.save_dataset_metadata(dataset_id, meta)

    def get_preparation(self, dataset_id: str) -> dict[str, Any] | None:
        dataset_path = self.get_dataset_dir(dataset_id)
        prep_file = dataset_path / "preparation.json"
        if not prep_file.is_file():
            return None
        try:
            return json.loads(prep_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    # -----------------------------------------------------------------------
    # Validations Storage
    # -----------------------------------------------------------------------

    def save_validation(self, validation_id: str, data: dict[str, Any]) -> None:
        sanitized = sanitize_id(validation_id)
        path = self.validations_dir / f"{sanitized}.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        # Also link to dataset if available
        dataset_id = data.get("dataset_id")
        if dataset_id and dataset_id != EXISTING_DATASET_ID:
            d_path = self.get_dataset_dir(dataset_id)
            if d_path.is_dir():
                (d_path / "validation.json").write_text(
                    json.dumps(data, indent=2), encoding="utf-8"
                )

    def get_validation(self, validation_id: str) -> dict[str, Any] | None:
        sanitized = sanitize_id(validation_id)
        path = self.validations_dir / f"{sanitized}.json"
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def get_dataset_latest_validation(self, dataset_id: str) -> dict[str, Any] | None:
        if dataset_id == EXISTING_DATASET_ID:
            # Find latest validation with dataset_id == EXISTING_DATASET_ID
            matches = []
            for p in self.validations_dir.glob("*.json"):
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if data.get("dataset_id") == EXISTING_DATASET_ID:
                        matches.append(data)
                except (OSError, json.JSONDecodeError) as exc:
                    logger.debug("Skipping unreadable validation file: %s", exc)
                    continue
            if matches:
                matches.sort(key=lambda x: x.get("created_at", ""), reverse=True)
                return matches[0]
            return None

        d_path = self.get_dataset_dir(dataset_id)
        val_file = d_path / "validation.json"
        if val_file.is_file():
            try:
                return json.loads(val_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
        return None

    # -----------------------------------------------------------------------
    # Analyses Storage
    # -----------------------------------------------------------------------

    def save_analysis(self, analysis_id: str, data: dict[str, Any]) -> None:
        sanitized = sanitize_id(analysis_id)
        path = self.analyses_dir / f"{sanitized}.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_analysis(self, analysis_id: str) -> dict[str, Any] | None:
        sanitized = sanitize_id(analysis_id)
        path = self.analyses_dir / f"{sanitized}.json"
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    # -----------------------------------------------------------------------
    # Analysis Runs Storage
    # -----------------------------------------------------------------------

    def save_run(self, run_id: str, data: dict[str, Any]) -> None:
        sanitized = sanitize_id(run_id)
        path = self.runs_dir / f"{sanitized}.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        sanitized = sanitize_id(run_id)
        path = self.runs_dir / f"{sanitized}.json"
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def list_runs(self, dataset_id: str | None = None) -> list[dict[str, Any]]:
        runs: list[dict[str, Any]] = []
        for p in sorted(self.runs_dir.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if dataset_id is None or data.get("dataset_id") == dataset_id:
                    runs.append(data)
            except (OSError, json.JSONDecodeError) as exc:
                logger.debug("Skipping unreadable run file: %s", exc)
                continue
        runs.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return runs

    # -----------------------------------------------------------------------
    # Reports Storage
    # -----------------------------------------------------------------------

    def save_report(
        self,
        report_id: str,
        data: dict[str, Any],
        csv_content: str | None = None,
    ) -> None:
        sanitized = sanitize_id(report_id)
        json_path = self.reports_dir / f"{sanitized}.json"
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        if csv_content is not None:
            csv_path = self.reports_dir / f"{sanitized}.csv"
            csv_path.write_text(csv_content, encoding="utf-8")

    def get_report(self, report_id: str) -> dict[str, Any] | None:
        sanitized = sanitize_id(report_id)
        path = self.reports_dir / f"{sanitized}.json"
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def get_report_csv_path(self, report_id: str) -> Path | None:
        sanitized = sanitize_id(report_id)
        path = self.reports_dir / f"{sanitized}.csv"
        return path if path.is_file() else None

    def get_report_json_path(self, report_id: str) -> Path | None:
        sanitized = sanitize_id(report_id)
        path = self.reports_dir / f"{sanitized}.json"
        return path if path.is_file() else None

    def list_reports(self) -> list[dict[str, Any]]:
        reports: list[dict[str, Any]] = []
        for p in sorted(self.reports_dir.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                reports.append(data)
            except (OSError, json.JSONDecodeError) as exc:
                logger.debug("Skipping unreadable report file: %s", exc)
                continue
        reports.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return reports
