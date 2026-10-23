"""Reports and export endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, Response

from ..config import ApiConfig, get_config
from ..models import ReportDetailResponse, ReportSummaryModel
from ..storage import StorageManager

router = APIRouter(prefix="/api/v1/reports", tags=["Reports & Exports"])


def get_storage(config: Annotated[ApiConfig, Depends(get_config)]) -> StorageManager:
    return StorageManager(config)


@router.get("", response_model=list[ReportSummaryModel])
def list_reports(
    storage: Annotated[StorageManager, Depends(get_storage)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ReportSummaryModel]:
    """List all available generated reliability reports."""
    all_reports = storage.list_reports()
    summaries: list[ReportSummaryModel] = []
    for r in all_reports[offset : offset + limit]:
        summaries.append(
            ReportSummaryModel(
                report_id=r["report_id"],
                run_id=r["run_id"],
                dataset_id=r["dataset_id"],
                created_at=r["created_at"],
                overall_status=r.get("overall_status", "PASS"),
                error_count=r.get("summary", {}).get("error_count", 0),
                warning_count=r.get("summary", {}).get("warning_count", 0),
                findings_count=len(r.get("findings", [])),
                available_formats=r.get("available_formats", ["json", "csv"]),
            )
        )
    return summaries


@router.get("/{report_id}", response_model=ReportDetailResponse)
def get_report(
    report_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> ReportDetailResponse:
    """Retrieve report metadata, findings summary, and limitations."""
    data = storage.get_report(report_id)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report {report_id!r} not found.",
        )
    return ReportDetailResponse(**data)


@router.get("/{report_id}/download")
def download_report(
    report_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
    format: Annotated[
        str, Query(description="Export format: json, csv, pdf, xlsx")
    ] = "json",
) -> Response:
    """Download analysis report in JSON or CSV format."""
    data = storage.get_report(report_id)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report {report_id!r} not found.",
        )

    fmt = format.lower().strip()

    if fmt == "json":
        json_path = storage.get_report_json_path(report_id)
        if not json_path or not json_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report JSON file for {report_id!r} not found.",
            )
        return FileResponse(
            path=json_path,
            media_type="application/json",
            filename=f"report_{report_id}.json",
        )

    if fmt == "csv":
        csv_path = storage.get_report_csv_path(report_id)
        if not csv_path or not csv_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report CSV file for {report_id!r} not found.",
            )
        return FileResponse(
            path=csv_path,
            media_type="text/csv",
            filename=f"report_{report_id}.csv",
        )

    if fmt == "pdf":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                "PDF export is not supported. A dedicated PDF rendering engine "
                "(such as ReportLab or WeasyPrint) is not part of this environment's "
                "standard dependencies."
            ),
        )

    if fmt == "xlsx":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                "XLSX export is not supported. The repository's Excel support is read-only "
                "without external spreadsheet generation dependencies."
            ),
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported format {format!r}. Supported formats: 'json', 'csv'.",
    )
