"""Health and system metadata endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from ..config import ApiConfig, get_config
from ..models import HealthResponse, MetadataResponse
from ..schemas import CANONICAL_SCHEMAS
from ..storage import StorageManager

router = APIRouter(tags=["Health & System"])


def get_storage(config: Annotated[ApiConfig, Depends(get_config)]) -> StorageManager:
    return StorageManager(config)


@router.get("/health", response_model=HealthResponse)
def root_health(
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> HealthResponse:
    """Basic service health check."""
    storage_ok = storage.storage_dir.exists() and storage.datasets_dir.exists()
    return HealthResponse(
        status="ok" if storage_ok else "degraded",
        app="backtest-reliability-analyzer",
        version="0.1.0",
        storage="healthy" if storage_ok else "storage_unavailable",
        analyzers={
            "survivorship": "available",
            "lookahead": "available",
            "corporate_actions": "available",
        },
    )


@router.get("/api/v1/health", response_model=HealthResponse)
def api_v1_health(
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> HealthResponse:
    """Detailed dependency health check."""
    return root_health(storage)


@router.get("/api/v1/metadata", response_model=MetadataResponse)
def api_v1_metadata(
    config: Annotated[ApiConfig, Depends(get_config)],
) -> MetadataResponse:
    """System metadata reporting actual registered capabilities."""
    analyzers_info: list[dict[str, Any]] = [
        {
            "name": "survivorship",
            "label": "Survivorship Bias Analyzer",
            "description": (
                "Evaluates historical universe reconstruction, delisted securities reconciliation, "
                "price coverage, and backtest-specific universe membership integrity."
            ),
            "supported_inputs": [
                "prices",
                "delistings",
                "current_listing",
                "name_changes",
                "symbol_changes",
                "index_snapshot",
            ],
            "supports_backtest_config": True,
        },
        {
            "name": "lookahead",
            "label": "Look-Ahead Bias Analyzer",
            "description": (
                "Measures temporal ordering between decision dates, reporting periods, and availability "
                "timestamps across financial results, corporate actions, and price series."
            ),
            "supported_inputs": [
                "financials_legacy",
                "financials_integrated",
                "corporate_actions",
                "prices",
                "index_snapshot",
            ],
            "supports_backtest_config": True,
        },
        {
            "name": "corporate_actions",
            "label": "Corporate Actions Consistency Analyzer",
            "description": (
                "Validates entitlement dates, record date vs ex-date ordering, pre/post event price coverage, "
                "and suspicious price discontinuities around split and bonus events."
            ),
            "supported_inputs": ["corporate_actions", "prices"],
            "supports_backtest_config": False,
        },
    ]

    schemas_info = [schema.to_dict() for schema in CANONICAL_SCHEMAS.values()]

    file_handling = {
        "max_upload_size_bytes": config.max_upload_size_bytes,
        "max_upload_size_mb": config.max_upload_size_bytes // (1024 * 1024),
        "supported_extensions": list(config.allowed_extensions),
        "supported_encodings": ["utf-8", "utf-8-sig", "windows-1252"],
        "csv_delimiter": ",",
    }

    application_config = {
        "app_name": config.app_name,
        "version": config.version,
        "storage_mode": "isolated_directory",
        "read_only_canonical": True,
    }

    return MetadataResponse(
        version=config.version,
        app_name=config.app_name,
        registered_analyzers=analyzers_info,
        supported_schemas=schemas_info,
        file_handling=file_handling,
        application_config=application_config,
    )
