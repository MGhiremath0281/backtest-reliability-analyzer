"""Console and JSON report rendering."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TextIO

from .models import DatasetResult, Issue, Report, Severity, Status

DEFAULT_REPORT_PATH = "reports/validation_report.json"


def write_json(report: Report, path: str | Path) -> Path:
    """Write a deterministic JSON report, creating its parent directory."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        report.to_dict(),
        indent=2,
        ensure_ascii=False,
        sort_keys=False,
    )
    temporary = destination.with_name(destination.name + ".tmp")
    try:
        temporary.write_text(payload + "\n", encoding="utf-8")
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


def _coverage_text(dataset: DatasetResult) -> str:
    if not dataset.coverage:
        return "-"
    start = dataset.coverage.get("start") or "?"
    end = dataset.coverage.get("end") or "?"
    return f"{start}..{end}"


def _dataset_rows(datasets: list[DatasetResult]) -> list[str]:
    id_width = max([len("Dataset")] + [len(d.dataset_id) for d in datasets])
    coverage_width = max([len("Coverage")] + [len(_coverage_text(d)) for d in datasets])
    lines = [
        (
            f"{'Status':<6}  {'Dataset':<{id_width}}  "
            f"{'Rows':>8}  {'Coverage':<{coverage_width}}  "
            f"{'Errors':>6}  {'Warnings':>8}"
        ),
        (
            f"{'-' * 6}  {'-' * id_width}  {'-' * 8}  "
            f"{'-' * coverage_width}  {'-' * 6}  {'-' * 8}"
        ),
    ]
    for dataset in datasets:
        lines.append(
            f"{dataset.status.value:<6}  {dataset.dataset_id:<{id_width}}  "
            f"{dataset.row_count:>8,}  "
            f"{_coverage_text(dataset):<{coverage_width}}  "
            f"{dataset.error_count:>6}  {dataset.warning_count:>8}"
        )
    return lines


def _issue_line(issue: Issue) -> str:
    location = f"line {issue.row}: " if issue.row is not None else ""
    return f"{location}{issue.message}"


def _finding_rows(
    datasets: list[DatasetResult],
    *,
    verbose: bool,
    max_examples: int,
) -> list[str]:
    lines: list[str] = []
    for dataset in datasets:
        if not dataset.issues:
            continue
        lines.append("")
        lines.append(f"[{dataset.status.value}] {dataset.dataset_id} - {dataset.label}")
        lines.append(f"  Source: {dataset.path}")

        by_code: dict[tuple[Severity, str], list[Issue]] = {}
        for issue in dataset.issues:
            by_code.setdefault((issue.severity, issue.code), []).append(issue)

        for (severity, code), issues in sorted(
            by_code.items(),
            key=lambda item: (
                0 if item[0][0] is Severity.ERROR else 1,
                item[0][1],
            ),
        ):
            lines.append(f"  {severity.value.upper():<7} {code} ({len(issues)})")
            shown = issues if verbose else issues[:max_examples]
            for issue in shown:
                lines.append(f"    {_issue_line(issue)}")
            if len(issues) > len(shown):
                lines.append(
                    f"    ... {len(issues) - len(shown)} more occurrence(s); "
                    "use --verbose to show all."
                )
    return lines


def print_console(
    report: Report,
    *,
    report_path: str | Path | None = None,
    verbose: bool = False,
    max_examples: int = 3,
    file: TextIO | None = None,
) -> None:
    """Render a readable validation summary to the console."""

    stream = file or sys.stdout
    lines = [
        "Backtest Reliability Analyzer - Data Validation",
        f"Data root: {report.data_root}",
        "",
        *_dataset_rows(report.datasets),
        "",
        (
            f"Datasets: {len(report.datasets)}"
            f" | PASS: {report.summary()['pass']}"
            f" | WARN: {report.summary()['warn']}"
            f" | FAIL: {report.summary()['fail']}"
            f" | Errors: {report.error_count}"
            f" | Warnings: {report.warning_count}"
        ),
        f"Overall status: {report.overall_status.value}",
    ]

    findings = _finding_rows(
        report.datasets,
        verbose=verbose,
        max_examples=max_examples,
    )
    if findings:
        lines.append("")
        lines.append("Findings")
        lines.extend(findings)

    if report_path is not None:
        lines.extend(["", f"JSON report: {Path(report_path).as_posix()}"])

    print("\n".join(lines), file=stream)


def has_failures(report: Report) -> bool:
    """Return True when the report contains at least one failed dataset."""

    return report.overall_status is Status.FAIL
