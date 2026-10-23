"""Adapters connecting API requests to existing BRA validation and analysis engines."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from uuid import uuid4

from ..csv_io import Table, read_csv
from ..discovery import DatasetSpec, discover_datasets
from ..models import DatasetResult, Report, Severity
from ..runner import _validate_table
from ..validators import (
    corporate_actions,
    lookahead,
    survivorship,
)
from ..validators.lookahead import LookaheadConfig
from ..validators.survivorship import BacktestConfig
from .mapping import compute_auto_mapping_for_file
from .models import FindingModel
from .preparation import prepare_dataset
from .schemas import CANONICAL_SCHEMAS
from .storage import EXISTING_DATASET_ID, StorageManager

SCHEMA_TO_KIND: dict[str, str] = {
    "prices": "prices",
    "corporate_actions": "corporate_actions",
    "financials_legacy": "financials",
    "financials_integrated": "integrated_financials",
    "current_listing": "current_listing",
    "delistings": "delistings",
    "name_changes": "name_changes",
    "symbol_changes": "symbol_changes",
    "index_snapshot": "index_snapshot",
}


def load_dataset_tables(
    dataset_id: str,
    storage: StorageManager,
) -> tuple[Path, dict[str, list[Table]], list[DatasetSpec]]:
    """Load tables and specs for a dataset, whether existing or uploaded.

    Returns (root_path, tables_by_kind, specs).
    """
    if dataset_id == EXISTING_DATASET_ID:
        root = storage.data_root
        specs = discover_datasets(root)
        tables_by_kind: dict[str, list[Table]] = defaultdict(list)
        for spec in specs:
            if spec.path and spec.path.is_file():
                table = read_csv(spec.path)
                tables_by_kind[spec.kind].append(table)
        return root, tables_by_kind, specs

    dataset_dir = storage.get_dataset_dir(dataset_id)
    if not dataset_dir.is_dir():
        raise ValueError(f"Dataset {dataset_id} does not exist.")

    metadata = storage.get_dataset_metadata(dataset_id) or {}
    prepared_dir = dataset_dir / "prepared"

    # If not prepared yet, run preparation automatically
    if not prepared_dir.is_dir() or not any(prepared_dir.glob("*.csv")):
        prepare_dataset(dataset_id, storage)

    tables_by_kind = defaultdict(list)
    specs: list[DatasetSpec] = []

    prepared_csvs = sorted(prepared_dir.glob("*.csv")) if prepared_dir.is_dir() else []
    if prepared_csvs:
        for p in prepared_csvs:
            # Stem might be schema_type or schema_type_fileid
            base_kind = p.stem.split("_")[0]
            # Match schema
            matched_schema = None
            for s in CANONICAL_SCHEMAS:
                if p.stem.startswith(s):
                    matched_schema = s
                    break

            schema_key = matched_schema or base_kind
            kind = SCHEMA_TO_KIND.get(schema_key, schema_key)

            table = read_csv(p)
            tables_by_kind[kind].append(table)

            spec = DatasetSpec(
                dataset_id=f"{kind}:{p.stem}",
                category=kind,
                kind=kind,
                label=f"Dataset {p.name}",
                path=p,
                relative_path=p.name,
            )
            specs.append(spec)
    else:
        # Fallback to uploads
        uploaded_files = metadata.get("files", [])
        mapping_data = storage.get_mapping(dataset_id) or {}
        mappings_by_file = {m["file_id"]: m for m in mapping_data.get("mappings", [])}

        for file_info in uploaded_files:
            file_id = file_info["file_id"]
            file_path = storage.get_file_path(dataset_id, file_id)
            if not file_path or not file_path.is_file():
                continue

            table = read_csv(file_path)
            mapping_spec = mappings_by_file.get(file_id)
            if mapping_spec:
                schema_type = mapping_spec["schema_type"]
            else:
                schema_type, _ = compute_auto_mapping_for_file(table.headers)

            kind = SCHEMA_TO_KIND.get(schema_type, schema_type)
            tables_by_kind[kind].append(table)
            spec = DatasetSpec(
                dataset_id=f"{kind}:{file_id}",
                category=kind,
                kind=kind,
                label=file_info.get("original_filename", file_id),
                path=file_path,
                relative_path=file_path.name,
            )
            specs.append(spec)

    return dataset_dir, tables_by_kind, specs


def extract_findings_from_result(
    result: DatasetResult,
    analyzer: str,
) -> list[FindingModel]:
    """Convert DatasetResult issues and detailed metrics findings to FindingModel."""
    findings: list[FindingModel] = []
    seen: set[str] = set()

    # 1. Source table issues
    for issue in result.issues:
        key = f"{issue.code}:{issue.row}:{issue.column}:{issue.message}"
        if key in seen:
            continue
        seen.add(key)
        findings.append(
            FindingModel(
                id=f"fnd-{uuid4().hex[:8]}",
                analyzer=analyzer,
                code=issue.code,
                classification="violation"
                if issue.severity == Severity.ERROR
                else "warning",
                severity=issue.severity.value,
                message=issue.message,
                row=issue.row,
                column=issue.column,
                symbol=None,
                date=None,
                evidence=None,
                limitations=None,
                remediation=None,
            )
        )

    # 2. Detailed metrics findings if available
    metrics_findings = result.metrics.get("findings", {})
    detailed = metrics_findings.get("detailed_findings", [])
    for df in detailed:
        code = df.get("code", "finding")
        explanation = df.get("explanation", "")
        kind = df.get("kind", "fact")
        severity_val = df.get("severity") or (
            "warning" if kind in {"risk", "limitation", "suspicious"} else "info"
        )
        key = f"{code}:{explanation}"
        if key in seen:
            continue
        seen.add(key)

        findings.append(
            FindingModel(
                id=f"fnd-{uuid4().hex[:8]}",
                analyzer=analyzer,
                code=code,
                classification=kind,
                severity=severity_val,
                message=explanation,
                evidence=df.get("evidence"),
                limitations=df.get("limitations"),
                remediation=df.get("remediation"),
            )
        )

    return findings


def run_survivorship_analysis(
    dataset_id: str,
    storage: StorageManager,
    backtest: BacktestConfig | None = None,
) -> tuple[DatasetResult, list[FindingModel]]:
    """Execute real survivorship-bias analyzer against the dataset."""
    root, tables_by_kind, _ = load_dataset_tables(dataset_id, storage)
    result = survivorship.analyze(root, tables_by_kind, backtest=backtest)
    findings = extract_findings_from_result(result, analyzer="survivorship")
    return result, findings


def run_lookahead_analysis(
    dataset_id: str,
    storage: StorageManager,
    config: LookaheadConfig | None = None,
) -> tuple[DatasetResult, list[FindingModel]]:
    """Execute real look-ahead analyzer against the dataset."""
    root, tables_by_kind, _ = load_dataset_tables(dataset_id, storage)
    result = lookahead.analyze(root, tables_by_kind, config=config)
    findings = extract_findings_from_result(result, analyzer="lookahead")
    return result, findings


def run_corporate_actions_analysis(
    dataset_id: str,
    storage: StorageManager,
    expected_symbol: str | None = None,
) -> tuple[DatasetResult, list[FindingModel]]:
    """Execute real corporate actions validator against the dataset."""
    _root, tables_by_kind, _ = load_dataset_tables(dataset_id, storage)
    ca_tables = tables_by_kind.get("corporate_actions", []) + tables_by_kind.get(
        "derived_corporate_actions", []
    )
    price_table = (
        tables_by_kind.get("prices", [None])[0]
        or tables_by_kind.get("derived_prices", [None])[0]
    )

    result = DatasetResult(
        dataset_id=f"corporate_actions:{dataset_id}",
        category="corporate_actions",
        label="Corporate Actions Analysis",
        path="corporate_actions",
    )

    if not ca_tables:
        result.add_warning(
            "corporate_actions.missing",
            "No corporate action records were found in this dataset.",
        )
    else:
        for table in ca_tables:
            for issue in table.issues:
                result.add(issue)
            corporate_actions.validate(
                table,
                result,
                expected_symbol=expected_symbol,
                price_table=price_table,
            )

    findings = extract_findings_from_result(result, analyzer="corporate_actions")
    return result, findings


def run_full_validation(
    dataset_id: str,
    storage: StorageManager,
    analyzers: list[str] | None = None,
    backtest: BacktestConfig | None = None,
    lookahead_config: LookaheadConfig | None = None,
) -> tuple[Report, list[FindingModel], list[str], list[str]]:
    """Run validation and selected analyzers on the dataset.

    Returns (report, all_findings, supported_analyses, missing_evidence).
    """
    root, tables_by_kind, specs = load_dataset_tables(dataset_id, storage)
    report = Report(data_root=str(root))
    all_findings: list[FindingModel] = []
    supported_analyses: list[str] = []
    missing_evidence: list[str] = []

    # 1. Structural table validation
    for spec in specs:
        result = DatasetResult(
            dataset_id=spec.dataset_id,
            category=spec.category,
            label=spec.label,
            path=spec.relative_path,
        )
        if spec.path and spec.path.is_file():
            table = read_csv(spec.path)
            for issue in table.issues:
                result.add(issue)
            result.row_count = len(table.rows)
            if table.readable:
                try:
                    _validate_table(spec, table, result, tables_by_kind=tables_by_kind)
                except Exception as exc:  # noqa: BLE001
                    result.add_error("runner.validator_exception", str(exc))
        else:
            result.add_error("discovery.dataset_missing", "File not found.")

        report.datasets.append(result)
        all_findings.extend(
            extract_findings_from_result(result, analyzer="schema_validation")
        )

    # Evidence capabilities assessment
    has_prices = bool(
        tables_by_kind.get("prices") or tables_by_kind.get("derived_prices")
    )
    has_ca = bool(
        tables_by_kind.get("corporate_actions")
        or tables_by_kind.get("derived_corporate_actions")
    )
    has_financials = bool(
        tables_by_kind.get("financials") or tables_by_kind.get("integrated_financials")
    )
    has_listings = bool(
        tables_by_kind.get("current_listing") or tables_by_kind.get("delistings")
    )

    if has_prices or has_listings:
        supported_analyses.append("survivorship")
    else:
        missing_evidence.append(
            "survivorship: requires prices, delistings, or current listings."
        )

    if has_financials or has_ca or has_prices:
        supported_analyses.append("lookahead")
    else:
        missing_evidence.append(
            "lookahead: requires financial filings, corporate actions, or price series."
        )

    if has_ca:
        supported_analyses.append("corporate_actions")
    else:
        missing_evidence.append("corporate_actions: requires corporate action records.")

    active_analyzers = analyzers or ["survivorship", "lookahead", "corporate_actions"]

    # 2. Survivorship
    if "survivorship" in active_analyzers:
        surv_result, surv_findings = run_survivorship_analysis(
            dataset_id, storage, backtest=backtest
        )
        report.datasets.append(surv_result)
        all_findings.extend(surv_findings)

    # 3. Look-ahead
    if "lookahead" in active_analyzers:
        look_result, look_findings = run_lookahead_analysis(
            dataset_id, storage, config=lookahead_config
        )
        report.datasets.append(look_result)
        all_findings.extend(look_findings)

    # 4. Corporate actions
    if "corporate_actions" in active_analyzers and has_ca:
        ca_result, ca_findings = run_corporate_actions_analysis(dataset_id, storage)
        report.datasets.append(ca_result)
        all_findings.extend(ca_findings)

    return report, all_findings, supported_analyses, missing_evidence
