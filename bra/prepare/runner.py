"""Orchestration for reproducible normalized-data preparation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .audit import build_audit, write_audit
from .common import TransformResult, input_hashes, write_csv_atomic
from .market import (
    prepare_corporate_actions,
    prepare_financials_integrated,
    prepare_financials_legacy,
    prepare_prices,
)
from .reference import (
    prepare_current_listings,
    prepare_delistings,
    prepare_name_changes,
    prepare_symbol_changes,
)

DEFAULT_OUTPUT_DIR = "data/processed/normalized"
DEFAULT_AUDIT_JSON = "reports/data_audit.json"
DEFAULT_AUDIT_DOC = "docs/data-audit.md"


@dataclass
class PreparationRun:
    """Everything one preparation run produced, ready for reporting."""

    transforms: list[TransformResult]
    output_paths: dict[str, Path]
    audit: dict
    audit_json: Path
    audit_doc: Path
    source_hashes: dict[Path, str] = field(default_factory=dict)

    def summary(self) -> dict[str, int]:
        return {
            "datasets": len(self.transforms),
            "input_records": sum(item.input_records for item in self.transforms),
            "output_records": sum(item.output_records for item in self.transforms),
        }


def prepare_transforms(data_root: Path) -> list[TransformResult]:
    """Build every normalized transform without writing any output."""

    delistings = prepare_delistings(data_root)
    current_listings = prepare_current_listings(data_root, delistings.rows)
    return [
        prepare_prices(data_root),
        prepare_corporate_actions(data_root),
        prepare_financials_legacy(data_root),
        prepare_financials_integrated(data_root),
        current_listings,
        prepare_name_changes(data_root),
        prepare_symbol_changes(data_root),
        delistings,
    ]


def prepare_all(
    data_root: str | Path,
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    audit_json: str | Path = DEFAULT_AUDIT_JSON,
    audit_doc: str | Path = DEFAULT_AUDIT_DOC,
) -> PreparationRun:
    """Prepare all derived datasets, then write the audit documents."""

    root = Path(data_root)
    destination = Path(output_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"Data root does not exist: {root}")

    transforms = prepare_transforms(root)
    sources = sorted(
        {
            source
            for transform in transforms
            for source in transform.sources
        }
    )
    hashes_before = input_hashes(sources)

    output_paths: dict[str, Path] = {}
    for transform in transforms:
        path = destination / transform.filename
        write_csv_atomic(path, transform.headers, transform.rows)
        output_paths[transform.name] = path

    hashes_after = input_hashes(sources)
    if hashes_before != hashes_after:
        raise RuntimeError(
            "A source file changed during preparation; refusing to publish the audit."
        )

    audit = build_audit(
        root,
        transforms,
        output_paths=output_paths,
        output_dir=destination,
    )
    audit["source_hashes"] = [
        {
            "path": source.relative_to(root).as_posix()
            if source.is_relative_to(root)
            else str(source),
            "sha256": hashes_after[source.as_posix()],
        }
        for source in sources
    ]

    json_path = Path(audit_json)
    doc_path = Path(audit_doc)
    write_audit(audit, json_path, doc_path)

    return PreparationRun(
        transforms=transforms,
        output_paths=output_paths,
        audit=audit,
        audit_json=json_path,
        audit_doc=doc_path,
        source_hashes=hashes_after,
    )
