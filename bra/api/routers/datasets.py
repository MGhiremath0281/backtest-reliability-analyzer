"""Dataset management endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)

from bra.csv_io import read_csv

from ..adapters import run_full_validation
from ..config import ApiConfig, get_config
from ..models import (
    DatasetDetail,
    DatasetPreviewResponse,
    DatasetSchemaResponse,
    DatasetSummary,
    DatasetUploadResponse,
    FileInfo,
    FileSchemaDetail,
    QualitySummaryResponse,
    ValidationResponse,
    ValidationSummaryModel,
)
from ..schemas import detect_candidate_schema, infer_column_type
from ..storage import EXISTING_DATASET_ID, StorageManager

router = APIRouter(prefix="/api/v1/datasets", tags=["Dataset Management"])


def get_storage(config: Annotated[ApiConfig, Depends(get_config)]) -> StorageManager:
    return StorageManager(config)


@router.post(
    "/upload",
    response_model=DatasetUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_dataset(
    files: Annotated[list[UploadFile], File(description="One or more CSV files")],
    config: Annotated[ApiConfig, Depends(get_config)],
    storage: Annotated[StorageManager, Depends(get_storage)],
    name: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
) -> DatasetUploadResponse:
    """Upload one or multiple CSV files to register a new dataset."""
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one file must be uploaded.",
        )

    prepared_file_payloads: list[tuple[str, bytes]] = []
    for upload in files:
        filename = upload.filename or "upload.csv"
        ext = f".{filename.split('.')[-1].lower()}" if "." in filename else ""
        if ext not in config.allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file type {ext!r} for {filename!r}. Supported extensions: {', '.join(config.allowed_extensions)}.",
            )

        contents = await upload.read()
        if len(contents) > config.max_upload_size_bytes:
            raise HTTPException(
                status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413),
                detail=(
                    f"File {filename!r} ({len(contents)} bytes) exceeds the configured limit "
                    f"of {config.max_upload_size_bytes} bytes."
                ),
            )
        prepared_file_payloads.append((filename, contents))

    dataset_meta = storage.create_dataset(name=name, description=description)
    dataset_id = dataset_meta["dataset_id"]

    registered_files: list[FileInfo] = []
    total_rows = 0

    for orig_name, data in prepared_file_payloads:
        saved = storage.save_uploaded_file(dataset_id, orig_name, data)
        table = read_csv(saved["path"])
        row_count = len(table.rows)
        total_rows += row_count

        schema_candidate, confidence = detect_candidate_schema(table.headers)

        now = datetime.now(timezone.utc).isoformat()
        file_info = FileInfo(
            file_id=saved["file_id"],
            original_filename=saved["original_filename"],
            stored_filename=saved["stored_filename"],
            size_bytes=saved["size_bytes"],
            row_count=row_count,
            headers=table.headers,
            detected_schema=schema_candidate,
            confidence=round(confidence, 2) if confidence else None,
            uploaded_at=now,
        )
        registered_files.append(file_info)

    dataset_meta["files"] = [f.model_dump() for f in registered_files]
    dataset_meta["file_count"] = len(registered_files)
    dataset_meta["total_rows"] = total_rows
    storage.save_dataset_metadata(dataset_id, dataset_meta)

    return DatasetUploadResponse(
        dataset_id=dataset_id,
        message=f"Successfully registered {len(registered_files)} file(s).",
        files=registered_files,
    )


@router.get("", response_model=list[DatasetSummary])
def list_datasets(
    storage: Annotated[StorageManager, Depends(get_storage)],
    include_existing: Annotated[
        bool, Query(description="Include existing repository dataset")
    ] = True,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[DatasetSummary]:
    """List all available datasets (uploaded and canonical)."""
    raw_list = storage.list_datasets(include_existing=include_existing)
    summaries: list[DatasetSummary] = []
    for d in raw_list[offset : offset + limit]:
        summaries.append(
            DatasetSummary(
                dataset_id=d["dataset_id"],
                name=d.get("name"),
                description=d.get("description"),
                is_existing=d.get("is_existing", False),
                file_count=d.get("file_count", len(d.get("files", []))),
                total_rows=d.get("total_rows", 0),
                created_at=d.get("created_at", ""),
                status=d.get("status", "ready"),
                mapping_status=d.get("mapping_status", "unmapped"),
                preparation_status=d.get("preparation_status", "unprepared"),
            )
        )
    return summaries


@router.get("/{dataset_id}", response_model=DatasetDetail)
def get_dataset(
    dataset_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> DatasetDetail:
    """Retrieve details and file inventory of a dataset."""
    meta = storage.get_dataset_metadata(dataset_id)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id!r} not found.",
        )
    return DatasetDetail(
        dataset_id=meta["dataset_id"],
        name=meta.get("name"),
        description=meta.get("description"),
        is_existing=meta.get("is_existing", False),
        file_count=meta.get("file_count", len(meta.get("files", []))),
        total_rows=meta.get("total_rows", 0),
        created_at=meta.get("created_at", ""),
        status=meta.get("status", "ready"),
        mapping_status=meta.get("mapping_status", "unmapped"),
        preparation_status=meta.get("preparation_status", "unprepared"),
        files=[FileInfo(**f) for f in meta.get("files", [])],
    )


@router.get("/{dataset_id}/preview", response_model=DatasetPreviewResponse)
def preview_dataset(
    dataset_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
    file_id: Annotated[
        str | None, Query(description="Specific file ID to preview")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DatasetPreviewResponse:
    """Preview rows from a dataset file."""
    meta = storage.get_dataset_metadata(dataset_id)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id!r} not found.",
        )

    files = meta.get("files", [])
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dataset contains no files.",
        )

    target_file = None
    if file_id:
        for f in files:
            if f.get("file_id") == file_id:
                target_file = f
                break
        if not target_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File {file_id!r} not found in dataset {dataset_id!r}.",
            )
    else:
        target_file = files[0]

    path = storage.get_file_path(dataset_id, target_file["file_id"])
    if not path or not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File content not found on storage.",
        )

    table = read_csv(path)
    total_rows = len(table.rows)
    paged_rows = table.rows[offset : offset + limit]
    row_dicts = [row.values for row in paged_rows]

    return DatasetPreviewResponse(
        dataset_id=dataset_id,
        file_id=target_file["file_id"],
        filename=target_file["original_filename"],
        headers=table.headers,
        rows=row_dicts,
        total_rows=total_rows,
        limit=limit,
        offset=offset,
    )


@router.get("/{dataset_id}/schema", response_model=DatasetSchemaResponse)
def get_dataset_schema(
    dataset_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> DatasetSchemaResponse:
    """Inspect actual column names and inferred types for all dataset files."""
    meta = storage.get_dataset_metadata(dataset_id)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id!r} not found.",
        )

    files = meta.get("files", [])
    schema_details: list[FileSchemaDetail] = []

    for f in files:
        file_id = f["file_id"]
        path = storage.get_file_path(dataset_id, file_id)
        if not path or not path.is_file():
            continue

        table = read_csv(path)
        types_map: dict[str, str] = {}
        for h in table.headers:
            sample_values = [row.get(h) for row in table.rows[:100]]
            types_map[h] = infer_column_type(sample_values)

        schema_candidate, confidence = detect_candidate_schema(table.headers)

        schema_details.append(
            FileSchemaDetail(
                file_id=file_id,
                filename=f["original_filename"],
                headers=table.headers,
                inferred_types=types_map,
                detected_schema=schema_candidate,
                confidence=round(confidence, 2) if confidence else None,
            )
        )

    return DatasetSchemaResponse(dataset_id=dataset_id, files=schema_details)


@router.post("/{dataset_id}/validate", response_model=ValidationResponse)
def validate_dataset(
    dataset_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> ValidationResponse:
    """Run structural integrity and schema validation on the dataset."""
    meta = storage.get_dataset_metadata(dataset_id)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id!r} not found.",
        )

    report, findings, supported_analyses, missing_evidence = run_full_validation(
        dataset_id=dataset_id,
        storage=storage,
        analyzers=["survivorship", "lookahead", "corporate_actions"],
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


@router.get("/{dataset_id}/validation", response_model=ValidationResponse)
def get_dataset_validation(
    dataset_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> ValidationResponse:
    """Retrieve the latest validation results for a dataset."""
    meta = storage.get_dataset_metadata(dataset_id)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id!r} not found.",
        )

    latest = storage.get_dataset_latest_validation(dataset_id)
    if not latest:
        return validate_dataset(dataset_id, storage=storage)

    return ValidationResponse(**latest)


@router.get("/{dataset_id}/quality-summary", response_model=QualitySummaryResponse)
def get_dataset_quality_summary(
    dataset_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> QualitySummaryResponse:
    """Calculate an overall data quality summary and score for the dataset."""
    meta = storage.get_dataset_metadata(dataset_id)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id!r} not found.",
        )

    files = meta.get("files", [])
    blank_row_counts: dict[str, int] = {}
    missing_required_counts: dict[str, int] = {}
    duplicate_counts: dict[str, int] = {}
    total_rows = 0
    total_issues = 0

    for f in files:
        file_id = f["file_id"]
        fname = f["original_filename"]
        path = storage.get_file_path(dataset_id, file_id)
        if not path or not path.is_file():
            continue

        table = read_csv(path)
        total_rows += len(table.rows)

        blanks = sum(1 for issue in table.issues if issue.code == "csv.blank_rows")
        blank_row_counts[fname] = blanks

        errs = table.error_count
        missing_required_counts[fname] = errs
        total_issues += errs + table.warning_count

    quality_score = max(0.0, 100.0 - min(100.0, (total_issues * 5.0)))
    _, _, supported, missing = run_full_validation(
        dataset_id=dataset_id, storage=storage, analyzers=[]
    )

    return QualitySummaryResponse(
        dataset_id=dataset_id,
        file_count=len(files),
        total_rows=total_rows,
        quality_score=round(quality_score, 1),
        blank_row_counts=blank_row_counts,
        missing_required_counts=missing_required_counts,
        duplicate_counts=duplicate_counts,
        supported_analyzers=supported,
        missing_evidence=missing,
    )


@router.post("/{dataset_id}/delete-request")
def request_dataset_deletion(
    dataset_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> dict[str, str]:
    """Request safe deletion of an uploaded dataset."""
    if dataset_id == EXISTING_DATASET_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete canonical repository dataset.",
        )
    meta = storage.get_dataset_metadata(dataset_id)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id!r} not found.",
        )

    storage.delete_dataset(dataset_id)
    return {"message": f"Dataset {dataset_id} deleted successfully."}


@router.delete("/{dataset_id}")
def delete_dataset(
    dataset_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> dict[str, str]:
    """Delete an uploaded dataset."""
    if dataset_id == EXISTING_DATASET_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete canonical repository dataset.",
        )

    meta = storage.get_dataset_metadata(dataset_id)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id!r} not found.",
        )

    storage.delete_dataset(dataset_id)
    return {"message": f"Dataset {dataset_id} deleted successfully."}
