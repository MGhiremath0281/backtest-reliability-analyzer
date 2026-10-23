"""General validation endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status

from bra.parsing import parse_date
from bra.validators.lookahead import LookaheadConfig
from bra.validators.survivorship import BacktestConfig

from ..adapters import run_full_validation
from ..config import ApiConfig, get_config
from ..models import (
    FindingModel,
    ValidationRequest,
    ValidationResponse,
    ValidationSummaryModel,
)
from ..storage import StorageManager

router = APIRouter(tags=["General Validation"])


def get_storage(config: Annotated[ApiConfig, Depends(get_config)]) -> StorageManager:
    return StorageManager(config)


@router.post("/api/v1/validate", response_model=ValidationResponse)
def execute_validation(
    payload: ValidationRequest,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> ValidationResponse:
    """Trigger comprehensive validation across an uploaded or canonical dataset."""
    dataset_id = payload.dataset_id
    if not dataset_id and payload.run_id:
        run = storage.get_run(payload.run_id)
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run {payload.run_id!r} not found.",
            )
        dataset_id = run["dataset_id"]

    if not dataset_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either dataset_id or run_id must be provided.",
        )

    meta = storage.get_dataset_metadata(dataset_id)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id!r} not found.",
        )

    backtest: BacktestConfig | None = None
    if payload.backtest:
        bt = payload.backtest
        s_date = parse_date(bt.get("start_date")) if bt.get("start_date") else None
        e_date = parse_date(bt.get("end_date")) if bt.get("end_date") else None
        backtest = BacktestConfig(
            target_index=bt.get("target_index"),
            universe_symbols=tuple(bt.get("universe_symbols", ())),
            start_date=s_date,
            end_date=e_date,
            min_price_coverage=bt.get("min_price_coverage"),
        )

    look_config: LookaheadConfig | None = None
    if payload.lookahead_config:
        lc = payload.lookahead_config
        dec_dates = [
            parse_date(d) for d in lc.get("decision_dates", []) if parse_date(d)
        ]
        s_date = parse_date(lc.get("start_date")) if lc.get("start_date") else None
        e_date = parse_date(lc.get("end_date")) if lc.get("end_date") else None
        look_config = LookaheadConfig(
            target_index=lc.get("target_index"),
            universe_symbols=tuple(lc.get("universe_symbols", ())),
            start_date=s_date,
            end_date=e_date,
            decision_dates=tuple(sorted(set(dec_dates))),
            lookback_days=lc.get("lookback_days"),
        )

    report, findings, supported_analyses, missing_evidence = run_full_validation(
        dataset_id=dataset_id,
        storage=storage,
        analyzers=payload.analyzers,
        backtest=backtest,
        lookahead_config=look_config,
    )

    validation_id = f"val-{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    summary_counts = report.summary()

    val_summary = ValidationSummaryModel(
        status=report.overall_status.value,
        error_count=report.error_count,
        warning_count=report.warning_count,
        pass_count=summary_counts["pass"],
        dataset_count=summary_counts["dataset_count"],
    )

    response_data = ValidationResponse(
        validation_id=validation_id,
        dataset_id=dataset_id,
        status=report.overall_status.value,
        summary=val_summary,
        findings=findings,
        supported_analyses=supported_analyses,
        missing_evidence=missing_evidence,
        created_at=now,
    )

    storage.save_validation(validation_id, response_data.model_dump())
    return response_data


@router.get("/api/v1/validations/{validation_id}", response_model=ValidationResponse)
def get_validation(
    validation_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> ValidationResponse:
    """Retrieve full validation result by ID."""
    data = storage.get_validation(validation_id)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Validation {validation_id!r} not found.",
        )
    return ValidationResponse(**data)


@router.get(
    "/api/v1/validations/{validation_id}/findings", response_model=list[FindingModel]
)
def get_validation_findings(
    validation_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
    severity: Annotated[
        str | None, Query(description="Filter by severity: error, warning, info")
    ] = None,
    analyzer: Annotated[
        str | None, Query(description="Filter by analyzer name")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[FindingModel]:
    """Retrieve filtered and paginated findings from a validation."""
    data = storage.get_validation(validation_id)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Validation {validation_id!r} not found.",
        )

    findings = [FindingModel(**f) for f in data.get("findings", [])]
    if severity:
        findings = [f for f in findings if f.severity.lower() == severity.lower()]
    if analyzer:
        findings = [f for f in findings if f.analyzer.lower() == analyzer.lower()]

    return findings[offset : offset + limit]


@router.get(
    "/api/v1/validations/{validation_id}/summary", response_model=ValidationSummaryModel
)
def get_validation_summary(
    validation_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> ValidationSummaryModel:
    """Retrieve summary metrics and status for a validation."""
    data = storage.get_validation(validation_id)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Validation {validation_id!r} not found.",
        )
    return ValidationSummaryModel(**data["summary"])
