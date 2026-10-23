"""Combined analysis-run orchestration endpoints."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import StringIO
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status

from bra.parsing import parse_date
from bra.validators.lookahead import LookaheadConfig
from bra.validators.survivorship import BacktestConfig

from ..adapters import (
    load_dataset_tables,
    run_corporate_actions_analysis,
    run_lookahead_analysis,
    run_survivorship_analysis,
)
from ..config import ApiConfig, get_config
from ..models import (
    AnalysisRunRequest,
    AnalysisRunResponse,
    FindingModel,
)
from ..storage import StorageManager

router = APIRouter(prefix="/api/v1/analysis-runs", tags=["Analysis Runs"])


def get_storage(config: Annotated[ApiConfig, Depends(get_config)]) -> StorageManager:
    return StorageManager(config)


@router.post(
    "", response_model=AnalysisRunResponse, status_code=status.HTTP_201_CREATED
)
def create_analysis_run(
    payload: AnalysisRunRequest,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> AnalysisRunResponse:
    """Execute a multi-analyzer reliability analysis run against a dataset."""
    meta = storage.get_dataset_metadata(payload.dataset_id)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {payload.dataset_id!r} not found.",
        )

    run_id = f"run-{uuid4().hex[:12]}"
    report_id = f"rep-{uuid4().hex[:12]}"
    start_time = datetime.now(timezone.utc).isoformat()

    events: list[dict[str, Any]] = [
        {"timestamp": start_time, "event": "run_initialized", "run_id": run_id}
    ]

    backtest: BacktestConfig | None = None
    if payload.backtest:
        bt = payload.backtest
        s_date = parse_date(bt.start_date) if bt.start_date else None
        e_date = parse_date(bt.end_date) if bt.end_date else None
        backtest = BacktestConfig(
            target_index=bt.target_index,
            universe_symbols=tuple(bt.universe_symbols),
            start_date=s_date,
            end_date=e_date,
            min_price_coverage=bt.min_price_coverage,
        )

    look_config: LookaheadConfig | None = None
    if payload.lookahead:
        lc = payload.lookahead
        dec_dates = [parse_date(d) for d in lc.decision_dates if parse_date(d)]
        s_date = parse_date(lc.start_date) if lc.start_date else None
        e_date = parse_date(lc.end_date) if lc.end_date else None
        look_config = LookaheadConfig(
            target_index=lc.target_index,
            universe_symbols=tuple(lc.universe_symbols),
            start_date=s_date,
            end_date=e_date,
            decision_dates=tuple(sorted(set(dec_dates))),
            lookback_days=lc.lookback_days,
        )

    _, _tables_by_kind, _ = load_dataset_tables(payload.dataset_id, storage)

    analyzers_requested = payload.analyzers or [
        "survivorship",
        "lookahead",
        "corporate_actions",
    ]
    analyzers_executed: list[str] = []
    analyzers_skipped: list[str] = []
    analyzer_results: dict[str, Any] = {}
    consolidated_findings: list[FindingModel] = []
    limitations: list[str] = []

    total_errors = 0
    total_warnings = 0

    if "survivorship" in analyzers_requested:
        events.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": "survivorship_started",
            }
        )
        try:
            surv_res, surv_findings = run_survivorship_analysis(
                payload.dataset_id, storage, backtest=backtest
            )
            analyzers_executed.append("survivorship")
            analyzer_results["survivorship"] = {
                "status": surv_res.status.value,
                "error_count": surv_res.error_count,
                "warning_count": surv_res.warning_count,
                "metrics": surv_res.metrics,
            }
            consolidated_findings.extend(surv_findings)
            total_errors += surv_res.error_count
            total_warnings += surv_res.warning_count
        except Exception as exc:  # noqa: BLE001
            limitations.append(f"Survivorship analysis failed: {exc}")
            analyzers_skipped.append("survivorship")

    if "lookahead" in analyzers_requested:
        events.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": "lookahead_started",
            }
        )
        try:
            look_res, look_findings = run_lookahead_analysis(
                payload.dataset_id, storage, config=look_config
            )
            analyzers_executed.append("lookahead")
            analyzer_results["lookahead"] = {
                "status": look_res.status.value,
                "error_count": look_res.error_count,
                "warning_count": look_res.warning_count,
                "metrics": look_res.metrics,
            }
            consolidated_findings.extend(look_findings)
            total_errors += look_res.error_count
            total_warnings += look_res.warning_count
        except Exception as exc:  # noqa: BLE001
            limitations.append(f"Look-ahead analysis failed: {exc}")
            analyzers_skipped.append("lookahead")

    if "corporate_actions" in analyzers_requested:
        events.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": "corporate_actions_started",
            }
        )
        exp_sym = (
            payload.corporate_actions.expected_symbol
            if payload.corporate_actions
            else None
        )
        try:
            ca_res, ca_findings = run_corporate_actions_analysis(
                payload.dataset_id, storage, expected_symbol=exp_sym
            )
            analyzers_executed.append("corporate_actions")
            analyzer_results["corporate_actions"] = {
                "status": ca_res.status.value,
                "error_count": ca_res.error_count,
                "warning_count": ca_res.warning_count,
                "metrics": ca_res.metrics,
            }
            consolidated_findings.extend(ca_findings)
            total_errors += ca_res.error_count
            total_warnings += ca_res.warning_count
        except Exception as exc:  # noqa: BLE001
            limitations.append(f"Corporate actions analysis failed: {exc}")
            analyzers_skipped.append("corporate_actions")

    completion_time = datetime.now(timezone.utc).isoformat()
    events.append({"timestamp": completion_time, "event": "run_completed"})

    run_status = "completed"
    if analyzers_skipped and analyzers_executed:
        run_status = "partial_failure"
    elif not analyzers_executed:
        run_status = "failed"

    overall_status = "PASS"
    if total_errors > 0 or run_status == "failed":
        overall_status = "FAIL"
    elif total_warnings > 0:
        overall_status = "WARN"

    summary: dict[str, Any] = {
        "overall_status": overall_status,
        "total_analyzers": len(analyzers_requested),
        "executed_count": len(analyzers_executed),
        "skipped_count": len(analyzers_skipped),
        "error_count": total_errors,
        "warning_count": total_warnings,
        "findings_count": len(consolidated_findings),
        "by_analyzer": {
            a: {
                "status": analyzer_results.get(a, {}).get("status", "skipped"),
                "errors": analyzer_results.get(a, {}).get("error_count", 0),
                "warnings": analyzer_results.get(a, {}).get("warning_count", 0),
            }
            for a in analyzers_requested
        },
    }

    run_payload: dict[str, Any] = {
        "run_id": run_id,
        "dataset_id": payload.dataset_id,
        "status": run_status,
        "created_at": start_time,
        "completed_at": completion_time,
        "analyzers_requested": analyzers_requested,
        "analyzers_executed": analyzers_executed,
        "analyzers_skipped": analyzers_skipped,
        "error_count": total_errors,
        "warning_count": total_warnings,
        "findings_count": len(consolidated_findings),
        "summary": summary,
        "analyzer_results": analyzer_results,
        "findings": [f.model_dump() for f in consolidated_findings],
        "limitations": limitations,
        "events": events,
        "report_id": report_id,
    }

    storage.save_run(run_id, run_payload)

    csv_buf = StringIO()
    writer = csv.writer(csv_buf)
    writer.writerow(
        [
            "Finding ID",
            "Analyzer",
            "Finding Code",
            "Severity",
            "Classification",
            "Message",
            "Row",
            "Column",
            "Remediation",
        ]
    )
    for f in consolidated_findings:
        writer.writerow(
            [
                f.id,
                f.analyzer,
                f.code,
                f.severity,
                f.classification,
                f.message,
                f.row or "",
                f.column or "",
                f.remediation or "",
            ]
        )

    report_data = {
        "report_id": report_id,
        "run_id": run_id,
        "dataset_id": payload.dataset_id,
        "created_at": completion_time,
        "overall_status": overall_status,
        "summary": summary,
        "analyzers": analyzers_executed,
        "findings": [f.model_dump() for f in consolidated_findings],
        "limitations": limitations,
        "available_formats": ["json", "csv"],
    }
    storage.save_report(report_id, report_data, csv_content=csv_buf.getvalue())

    return AnalysisRunResponse(
        run_id=run_id,
        dataset_id=payload.dataset_id,
        status=run_status,
        created_at=start_time,
        completed_at=completion_time,
        analyzers_requested=analyzers_requested,
        analyzers_executed=analyzers_executed,
        analyzers_skipped=analyzers_skipped,
        error_count=total_errors,
        warning_count=total_warnings,
        findings_count=len(consolidated_findings),
        summary=summary,
        report_id=report_id,
    )


@router.get("", response_model=list[dict[str, Any]])
def list_analysis_runs(
    storage: Annotated[StorageManager, Depends(get_storage)],
    dataset_id: Annotated[str | None, Query(description="Filter by dataset ID")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict[str, Any]]:
    """List historical analysis runs."""
    all_runs = storage.list_runs(dataset_id=dataset_id)
    return [
        {
            "run_id": r["run_id"],
            "dataset_id": r["dataset_id"],
            "status": r["status"],
            "created_at": r["created_at"],
            "completed_at": r.get("completed_at"),
            "analyzers_executed": r.get("analyzers_executed", []),
            "findings_count": r.get("findings_count", 0),
            "report_id": r.get("report_id"),
        }
        for r in all_runs[offset : offset + limit]
    ]


@router.get("/{run_id}")
def get_analysis_run(
    run_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> dict[str, Any]:
    """Retrieve full details of an analysis run."""
    run = storage.get_run(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis run {run_id!r} not found.",
        )
    return run


@router.get("/{run_id}/findings", response_model=list[FindingModel])
def get_analysis_run_findings(
    run_id: str,
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
    """Retrieve consolidated findings from an analysis run."""
    run = storage.get_run(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis run {run_id!r} not found.",
        )

    findings = [FindingModel(**f) for f in run.get("findings", [])]
    if severity:
        findings = [f for f in findings if f.severity.lower() == severity.lower()]
    if analyzer:
        findings = [f for f in findings if f.analyzer.lower() == analyzer.lower()]

    return findings[offset : offset + limit]


@router.get("/{run_id}/summary")
def get_analysis_run_summary(
    run_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> dict[str, Any]:
    """Retrieve consolidated summary counts and completion status for an analysis run."""
    run = storage.get_run(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis run {run_id!r} not found.",
        )
    return run.get("summary", {})


@router.post("/{run_id}/cancel")
def cancel_analysis_run(
    run_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> dict[str, Any]:
    """Request cancellation of an analysis run."""
    run = storage.get_run(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis run {run_id!r} not found.",
        )
    return {
        "run_id": run_id,
        "status": run.get("status", "completed"),
        "cancellable": False,
        "message": f"Run {run_id} has already completed execution.",
    }


@router.get("/{run_id}/events")
def get_analysis_run_events(
    run_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> list[dict[str, Any]]:
    """Retrieve execution lifecycle events for an analysis run."""
    run = storage.get_run(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis run {run_id!r} not found.",
        )
    return run.get("events", [])
