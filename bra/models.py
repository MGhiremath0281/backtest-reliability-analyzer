"""Core data structures used by the validation engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    """Severity of a validation finding."""

    ERROR = "error"
    WARNING = "warning"


class Status(str, Enum):
    """Dataset and report status values."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True)
class Issue:
    """A single validation finding.

    Row numbers are 1-based physical line numbers in the source CSV, including
    the header line, so they can be used to inspect the original file directly.
    """

    code: str
    message: str
    severity: Severity = Severity.ERROR
    row: int | None = None
    column: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
        }
        if self.row is not None:
            data["row"] = self.row
        if self.column is not None:
            data["column"] = self.column
        return data


def error(
    code: str,
    message: str,
    *,
    row: int | None = None,
    column: str | None = None,
) -> Issue:
    """Create an error finding."""

    return Issue(code, message, Severity.ERROR, row, column)


def warning(
    code: str,
    message: str,
    *,
    row: int | None = None,
    column: str | None = None,
) -> Issue:
    """Create a warning finding."""

    return Issue(code, message, Severity.WARNING, row, column)


@dataclass
class DatasetResult:
    """Validation result for one logical dataset (usually one CSV file)."""

    dataset_id: str
    category: str
    label: str
    path: str
    row_count: int = 0
    coverage: dict[str, Any] | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)

    def add(self, issue: Issue) -> None:
        self.issues.append(issue)

    def add_error(
        self,
        code: str,
        message: str,
        *,
        row: int | None = None,
        column: str | None = None,
    ) -> None:
        self.issues.append(error(code, message, row=row, column=column))

    def add_warning(
        self,
        code: str,
        message: str,
        *,
        row: int | None = None,
        column: str | None = None,
    ) -> None:
        self.issues.append(warning(code, message, row=row, column=column))

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity is Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity is Severity.WARNING)

    @property
    def status(self) -> Status:
        if self.error_count:
            return Status.FAIL
        if self.warning_count:
            return Status.WARN
        return Status.PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.dataset_id,
            "category": self.category,
            "label": self.label,
            "path": self.path,
            "status": self.status.value,
            "row_count": self.row_count,
            "coverage": self.coverage,
            "metrics": self.metrics,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass
class Report:
    """Complete validation report."""

    data_root: str
    datasets: list[DatasetResult] = field(default_factory=list)
    schema_version: int = 1
    tool: str = "backtest-reliability-analyzer"

    @property
    def overall_status(self) -> Status:
        if any(dataset.status is Status.FAIL for dataset in self.datasets):
            return Status.FAIL
        if any(dataset.status is Status.WARN for dataset in self.datasets):
            return Status.WARN
        return Status.PASS

    @property
    def error_count(self) -> int:
        return sum(dataset.error_count for dataset in self.datasets)

    @property
    def warning_count(self) -> int:
        return sum(dataset.warning_count for dataset in self.datasets)

    def summary(self) -> dict[str, Any]:
        counts = {status.value: 0 for status in Status}
        for dataset in self.datasets:
            counts[dataset.status.value] += 1
        return {
            "dataset_count": len(self.datasets),
            "pass": counts[Status.PASS.value],
            "warn": counts[Status.WARN.value],
            "fail": counts[Status.FAIL.value],
            "error_count": self.error_count,
            "warning_count": self.warning_count,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "tool": self.tool,
            "data_root": self.data_root,
            "overall_status": self.overall_status.value,
            "summary": self.summary(),
            "datasets": [dataset.to_dict() for dataset in self.datasets],
        }
