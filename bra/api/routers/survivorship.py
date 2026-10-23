"""Survivorship bias analyzer endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status

from bra.parsing import parse_date
from bra.validators.survivorship import BacktestConfig

from ..adapters import run_survivorship_analysis
from ..config import ApiConfig, get_config
from ..models import FindingModel, SurvivorshipAnalysisRequest
from ..storage import StorageManager

router = APIRouter(prefix="/api/v1/analyze/survivorship", tags=["Survivorship Bias"])


def get_storage(config: Annotated[ApiConfig, Depends(get_config)]) -> StorageManager:
    return StorageManager(config)


@router.post("", status_code=status.HTTP_201_CREATED)
def trigger_survivorship_analysis(
    payload: SurvivorshipAnalysisRequest,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> dict[str, Any]:
    """Execute survivorship bias analyzer against the specified dataset."""
    meta = storage.get_dataset_metadata(payload.dataset_id)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {payload.dataset_id!r} not found.",
        )

    backtest: BacktestConfig | None = None
    if (
        payload.target_index
        or payload.start_date
        or payload.end_date
        or payload.universe_symbols
        or payload.min_price_coverage is not None
    ):
        s_date = parse_date(payload.start_date) if payload.start_date else None
        e_date = parse_date(payload.end_date) if payload.end_date else None
        backtest = BacktestConfig(
            target_index=payload.target_index,
            universe_symbols=tuple(payload.universe_symbols),
            start_date=s_date,
            end_date=e_date,
            min_price_coverage=payload.min_price_coverage,
        )

    result, findings = run_survivorship_analysis(
        dataset_id=payload.dataset_id,
        storage=storage,
        backtest=backtest,
    )

    analysis_id = f"surv-{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    analysis_payload = {
        "analysis_id": analysis_id,
        "type": "survivorship",
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
def get_survivorship_analysis(
    analysis_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> dict[str, Any]:
    """Retrieve complete survivorship analysis results."""
    data = storage.get_analysis(analysis_id)
    if not data or data.get("type") != "survivorship":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Survivorship analysis {analysis_id!r} not found.",
        )
    return data


@router.get("/{analysis_id}/universe")
def get_survivorship_universe(
    analysis_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> dict[str, Any]:
    """Inspect historical universe reconstruction and membership metrics."""
    data = storage.get_analysis(analysis_id)
    if not data or data.get("type") != "survivorship":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Survivorship analysis {analysis_id!r} not found.",
        )

    metrics = data.get("metrics", {})
    return {
        "analysis_id": analysis_id,
        "dataset_id": data.get("dataset_id"),
        "membership": metrics.get("membership", {}),
        "universe_coverage": metrics.get("universe_coverage", {}),
        "current_listings": metrics.get("current_listings", {}),
    }


@router.get("/{analysis_id}/delisted")
def get_survivorship_delisted(
    analysis_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> dict[str, Any]:
    """Inspect delisted security reconciliation, match classes, and price coverage."""
    data = storage.get_analysis(analysis_id)
    if not data or data.get("type") != "survivorship":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Survivorship analysis {analysis_id!r} not found.",
        )

    metrics = data.get("metrics", {})
    return {
        "analysis_id": analysis_id,
        "dataset_id": data.get("dataset_id"),
        "delisted_coverage": metrics.get("delisted_coverage", {}),
        "symbol_changes": metrics.get("symbol_changes", {}),
    }


@router.get("/{analysis_id}/findings", response_model=list[FindingModel])
def get_survivorship_findings(
    analysis_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
    severity: Annotated[
        str | None, Query(description="Filter by severity: error, warning, info")
    ] = None,
    kind: Annotated[
        str | None,
        Query(
            description="Filter by classification kind: fact, risk, limitation, check"
        ),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[FindingModel]:
    """Inspect findings, risks, and evidence from a survivorship analysis."""
    data = storage.get_analysis(analysis_id)
    if not data or data.get("type") != "survivorship":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Survivorship analysis {analysis_id!r} not found.",
        )

    findings = [FindingModel(**f) for f in data.get("findings", [])]
    if severity:
        findings = [f for f in findings if f.severity.lower() == severity.lower()]
    if kind:
        findings = [f for f in findings if f.classification.lower() == kind.lower()]

    return findings[offset : offset + limit]
