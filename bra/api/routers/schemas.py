"""Schema mapping and preparation endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from bra.csv_io import read_csv

from ..config import ApiConfig, get_config
from ..mapping import compute_auto_mapping_for_file, validate_file_mapping
from ..models import (
    DatasetMappingResponse,
    FileMappingDetail,
    PreparationResponse,
    PreparedFileDetail,
    SetMappingRequest,
)
from ..preparation import prepare_dataset
from ..schemas import CANONICAL_SCHEMAS
from ..storage import StorageManager

router = APIRouter(tags=["Schema Mapping & Preparation"])


def get_storage(config: Annotated[ApiConfig, Depends(get_config)]) -> StorageManager:
    return StorageManager(config)


@router.get("/api/v1/schemas")
def list_schemas() -> list[dict[str, Any]]:
    """List all supported canonical BRA schema definitions."""
    return [schema.to_dict() for schema in CANONICAL_SCHEMAS.values()]


@router.get("/api/v1/schemas/{schema_type}")
def get_schema(schema_type: str) -> dict[str, Any]:
    """Retrieve detailed specification for a canonical schema type."""
    schema = CANONICAL_SCHEMAS.get(schema_type)
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schema type {schema_type!r} not found. Available schemas: {', '.join(CANONICAL_SCHEMAS.keys())}.",
        )
    return schema.to_dict()


@router.post(
    "/api/v1/datasets/{dataset_id}/mapping", response_model=DatasetMappingResponse
)
def set_dataset_mapping(
    dataset_id: str,
    payload: SetMappingRequest,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> DatasetMappingResponse:
    """Set or auto-generate column mappings for an uploaded dataset."""
    meta = storage.get_dataset_metadata(dataset_id)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id!r} not found.",
        )

    files = meta.get("files", [])
    mapping_details: list[FileMappingDetail] = []
    auto_suggestions: dict[str, dict[str, str]] = {}
    all_valid = True

    supplied_mappings = {m.file_id: m for m in payload.mappings}

    for f in files:
        fid = f["file_id"]
        fname = f["original_filename"]
        path = storage.get_file_path(dataset_id, fid)
        if not path or not path.is_file():
            continue

        table = read_csv(path)
        auto_schema, auto_map = compute_auto_mapping_for_file(table.headers)
        auto_suggestions[fid] = auto_map

        if fid in supplied_mappings:
            chosen_schema = supplied_mappings[fid].schema_type
            chosen_map = supplied_mappings[fid].column_mapping
        elif payload.auto_suggest:
            chosen_schema = auto_schema
            chosen_map = auto_map
        else:
            existing_mapping = storage.get_mapping(dataset_id) or {}
            existing_file_maps = {
                m["file_id"]: m for m in existing_mapping.get("mappings", [])
            }
            if fid in existing_file_maps:
                chosen_schema = existing_file_maps[fid]["schema_type"]
                chosen_map = existing_file_maps[fid]["column_mapping"]
            else:
                chosen_schema = auto_schema
                chosen_map = {}

        validation_res = validate_file_mapping(table.headers, chosen_schema, chosen_map)
        if not validation_res["valid"]:
            all_valid = False

        detail = FileMappingDetail(
            file_id=fid,
            filename=fname,
            schema_type=chosen_schema,
            column_mapping=chosen_map,
            unmapped_source_columns=validation_res["unmapped_source_columns"],
            missing_required_columns=validation_res["missing_required_columns"],
            valid=validation_res["valid"],
            errors=validation_res["errors"],
        )
        mapping_details.append(detail)

    storage.save_mapping(
        dataset_id,
        {
            "dataset_id": dataset_id,
            "mappings": [d.model_dump() for d in mapping_details],
            "all_valid": all_valid,
        },
    )

    return DatasetMappingResponse(
        dataset_id=dataset_id,
        mappings=mapping_details,
        all_valid=all_valid,
        auto_suggestions=auto_suggestions,
    )


@router.get(
    "/api/v1/datasets/{dataset_id}/mapping", response_model=DatasetMappingResponse
)
def get_dataset_mapping(
    dataset_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> DatasetMappingResponse:
    """Inspect current column mappings and auto-suggestions for a dataset."""
    meta = storage.get_dataset_metadata(dataset_id)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id!r} not found.",
        )

    existing = storage.get_mapping(dataset_id)
    if existing:
        auto_suggestions: dict[str, dict[str, str]] = {}
        for f in meta.get("files", []):
            fid = f["file_id"]
            p = storage.get_file_path(dataset_id, fid)
            if p and p.is_file():
                tbl = read_csv(p)
                _, amap = compute_auto_mapping_for_file(tbl.headers)
                auto_suggestions[fid] = amap

        return DatasetMappingResponse(
            dataset_id=dataset_id,
            mappings=[FileMappingDetail(**m) for m in existing.get("mappings", [])],
            all_valid=existing.get("all_valid", False),
            auto_suggestions=auto_suggestions,
        )

    return set_dataset_mapping(
        dataset_id,
        SetMappingRequest(mappings=[], auto_suggest=True),
        storage=storage,
    )


@router.post(
    "/api/v1/datasets/{dataset_id}/prepare", response_model=PreparationResponse
)
def prepare_dataset_endpoint(
    dataset_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> PreparationResponse:
    """Normalize and prepare working datasets using the defined column mappings."""
    meta = storage.get_dataset_metadata(dataset_id)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id!r} not found.",
        )

    try:
        prep_result = prepare_dataset(dataset_id, storage)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Preparation failed: {exc}",
        ) from exc

    return PreparationResponse(
        dataset_id=dataset_id,
        status=prep_result["status"],
        prepared_files=[PreparedFileDetail(**f) for f in prep_result["prepared_files"]],
        total_records=prep_result["total_records"],
        review_flags=prep_result.get("review_flags", {}),
        warnings=prep_result.get("warnings", []),
    )


@router.get(
    "/api/v1/datasets/{dataset_id}/preparation", response_model=PreparationResponse
)
def get_dataset_preparation(
    dataset_id: str,
    storage: Annotated[StorageManager, Depends(get_storage)],
) -> PreparationResponse:
    """Inspect preparation status and normalized working datasets."""
    meta = storage.get_dataset_metadata(dataset_id)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id!r} not found.",
        )

    prep = storage.get_preparation(dataset_id)
    if not prep:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id!r} has not been prepared yet.",
        )

    return PreparationResponse(
        dataset_id=dataset_id,
        status=prep["status"],
        prepared_files=[
            PreparedFileDetail(**f) for f in prep.get("prepared_files", [])
        ],
        total_records=prep.get("total_records", 0),
        review_flags=prep.get("review_flags", {}),
        warnings=prep.get("warnings", []),
    )
