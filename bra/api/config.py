"""Configuration for the Backtest Reliability Analyzer API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ApiConfig:
    """Runtime configuration for BRA API services."""

    storage_dir: Path
    data_root: Path
    max_upload_size_bytes: int = 50 * 1024 * 1024  # 50 MB
    allowed_extensions: tuple[str, ...] = (".csv",)
    version: str = "0.1.0"
    app_name: str = "Backtest Reliability Analyzer API"

    @classmethod
    def from_env(cls) -> ApiConfig:
        storage_env = os.environ.get("BRA_STORAGE_DIR")
        if storage_env:
            storage_path = Path(storage_env).resolve()
        else:
            storage_path = Path("storage").resolve()

        data_root_env = os.environ.get("BRA_DATA_ROOT")
        if data_root_env:
            data_root_path = Path(data_root_env).resolve()
        else:
            data_root_path = Path("data").resolve()

        max_size_env = os.environ.get("BRA_MAX_UPLOAD_SIZE_BYTES")
        max_size = int(max_size_env) if max_size_env else 50 * 1024 * 1024

        return cls(
            storage_dir=storage_path,
            data_root=data_root_path,
            max_upload_size_bytes=max_size,
        )


def get_config() -> ApiConfig:
    """Return the global configuration instance."""
    return ApiConfig.from_env()
