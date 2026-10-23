"""Look-ahead bias analyzer endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status

from bra.parsing import parse_date
from bra.validators.lookahead import LookaheadConfig

from ..adapters import run_lookahead_analysis
from ..config import ApiConfig, get_config
from ..models import FindingModel, LookaheadAnalysisRequest
from ..storage import StorageManager

router = APIRouter(prefix="/api/v1/analyze/lookahead", tags=["Look-Ahead Bias"])


def get_storage(config: Annotated[ApiConfig, Depends(get_config)]) -> StorageManager:
    return StorageManager(config)


@router.post("", status_code=status.HTTP_201_CREATED)
def trigger_lookahead_analysis(
    payload: LookaheadAnalysisRequest,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> dict[str, Any]:
    """Execute look-ahead bias detection against the specified dataset."""
    meta = storage.get_dataset_metadata(payload.dataset_id)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {payload.dataset_id!r} not found.",
        )

    config: LookaheadConfig | None = None
    if (
        payload.decision_dates
        or payload.target_index
        or payload.start_date
        or payload.end_date
        or payload.universe_symbols
        or payload.lookback_days is not None
    ):
        dec_dates = [parse_date(d) for d in payload.decision_dates if parse_date(d)]
        s_date = parse_date(payload.start_date) if payload.start_date else None
        e_date = parse_date(payload.end_date) if payload.end_date else None
        config = LookaheadConfig(
            target_index=payload.target_index,
            universe_symbols=tuple(payload.universe_symbols),
            start_date=s_date,
            end_date=e_date,
            decision_dates=tuple(sorted(set(dec_dates))),
            lookback_days=payload.lookback_days,
        )

    result, findings = run_lookahead_analysis(
        dataset_id=payload.dataset_id,
        storage=storage,
        config=config,
    )

    analysis_id = f"look-{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    analysis_payload = {
        "analysis_id": analysis_id,
        "type": "lookahead",
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
def get_lookahead_analysis(
    analysis_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> dict[str, Any]:
    """Retrieve complete look-ahead analysis results."""
    data = storage.get_analysis(analysis_id)
    if not data or data.get("type") != "lookahead":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lookahead analysis {analysis_id!r} not found.",
        )
    return data


@router.get("/{analysis_id}/findings", response_model=list[FindingModel])
def get_lookahead_findings(
    analysis_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
    severity: Annotated[
        str | None, Query(description="Filter by severity: error, warning, info")
    ] = None,
    classification: Annotated[
        str | None,
        Query(
            description="Filter by classification: confirmed, suspicious, insufficient, check"
        ),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[FindingModel]:
    """Inspect temporal ordering findings, violations, and evidence."""
    data = storage.get_analysis(analysis_id)
    if not data or data.get("type") != "lookahead":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lookahead analysis {analysis_id!r} not found.",
        )

    findings = [FindingModel(**f) for f in data.get("findings", [])]
    if severity:
        findings = [f for f in findings if f.severity.lower() == severity.lower()]
    if classification:
        findings = [
            f for f in findings if f.classification.lower() == classification.lower()
        ]

    return findings[offset : offset + limit]


@router.get("/{analysis_id}/timeline")
def get_lookahead_timeline(
    analysis_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> dict[str, Any]:
    """Inspect event availability timelines and publication timing distributions."""
    data = storage.get_analysis(analysis_id)
    if not data or data.get("type") != "lookahead":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lookahead analysis {analysis_id!r} not found.",
        )

    metrics = data.get("metrics", {})
    return {
        "analysis_id": analysis_id,
        "dataset_id": data.get("dataset_id"),
        "financial_publication": metrics.get("financial_publication", {}),
        "financial_revisions": metrics.get("financial_revisions", {}),
        "corporate_action_timing": metrics.get("corporate_action_timing", {}),
        "point_in_time_universe": metrics.get("point_in_time_universe", {}),
        "price_availability": metrics.get("price_availability", {}),
    }
