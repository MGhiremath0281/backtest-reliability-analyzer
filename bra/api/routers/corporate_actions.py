"""Corporate actions analyzer endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..adapters import run_corporate_actions_analysis
from ..config import ApiConfig, get_config
from ..models import CorporateActionsAnalysisRequest, FindingModel
from ..storage import StorageManager

router = APIRouter(
    prefix="/api/v1/analyze/corporate-actions", tags=["Corporate Actions"]
)


def get_storage(config: Annotated[ApiConfig, Depends(get_config)]) -> StorageManager:
    return StorageManager(config)


@router.post("", status_code=status.HTTP_201_CREATED)
def trigger_corporate_actions_analysis(
    payload: CorporateActionsAnalysisRequest,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> dict[str, Any]:
    """Execute corporate actions validation against the specified dataset."""
    meta = storage.get_dataset_metadata(payload.dataset_id)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {payload.dataset_id!r} not found.",
        )

    result, findings = run_corporate_actions_analysis(
        dataset_id=payload.dataset_id,
        storage=storage,
        expected_symbol=payload.expected_symbol,
    )

    analysis_id = f"ca-{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    analysis_payload = {
        "analysis_id": analysis_id,
        "type": "corporate_actions",
        "dataset_id": payload.dataset_id,
        "status": result.status.value,
        "row_count": result.row_count,
        "coverage": result.coverage,
        "metrics": result.metrics,
        "error_count": result.error_count,
        "warning_count": result.warning_count,
        "findings": [f.model_dump() for f in findings],
        "created_at": now,
    }

    storage.save_analysis(analysis_id, analysis_payload)

    return {
        "analysis_id": analysis_id,
        "dataset_id": payload.dataset_id,
        "status": result.status.value,
        "error_count": result.error_count,
        "warning_count": result.warning_count,
        "findings_count": len(findings),
        "created_at": now,
    }


@router.get("/{analysis_id}")
def get_corporate_actions_analysis(
    analysis_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> dict[str, Any]:
    """Retrieve complete corporate actions analysis results."""
    data = storage.get_analysis(analysis_id)
    if not data or data.get("type") != "corporate_actions":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Corporate actions analysis {analysis_id!r} not found.",
        )
    return data


@router.get("/{analysis_id}/findings", response_model=list[FindingModel])
def get_corporate_actions_findings(
    analysis_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
    severity: Annotated[
        str | None, Query(description="Filter by severity: error, warning, info")
    ] = None,
    code: Annotated[str | None, Query(description="Filter by finding code")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[FindingModel]:
    """Inspect corporate actions inconsistencies and price-discontinuity findings."""
    data = storage.get_analysis(analysis_id)
    if not data or data.get("type") != "corporate_actions":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Corporate actions analysis {analysis_id!r} not found.",
        )

    findings = [FindingModel(**f) for f in data.get("findings", [])]
    if severity:
        findings = [f for f in findings if f.severity.lower() == severity.lower()]
    if code:
        findings = [f for f in findings if code.lower() in f.code.lower()]

    return findings[offset : offset + limit]


@router.get("/{analysis_id}/coverage")
def get_corporate_actions_coverage(
    analysis_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> dict[str, Any]:
    """Inspect corporate action coverage, symbol summaries, and action breakdowns."""
    data = storage.get_analysis(analysis_id)
    if not data or data.get("type") != "corporate_actions":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Corporate actions analysis {analysis_id!r} not found.",
        )

    metrics = data.get("metrics", {})
    return {
        "analysis_id": analysis_id,
        "dataset_id": data.get("dataset_id"),
        "coverage": data.get("coverage"),
        "by_symbol": metrics.get("by_symbol", {}),
        "by_purpose": metrics.get("by_purpose", {}),
        "by_series": metrics.get("by_series", {}),
        "duplicate_records": metrics.get("duplicate_records", 0),
    }
