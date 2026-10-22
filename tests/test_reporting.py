"""Report generation tests."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

from bra.models import DatasetResult, Report
from bra.reporting import has_failures, print_console, write_json


def build_report() -> Report:
    passed = DatasetResult(
        dataset_id="prices:PASS",
        category="historical_prices",
        label="Passing prices",
        path="raw/pass.csv",
        row_count=2,
        coverage={
            "date_column": "Date",
            "start": "2024-01-01",
            "end": "2024-01-02",
        },
    )
    warned = DatasetResult(
        dataset_id="prices:WARN",
        category="historical_prices",
        label="Warning prices",
        path="raw/warn.csv",
        row_count=1,
    )
    warned.add_warning("csv.bom", "BOM present.")
    failed = DatasetResult(
        dataset_id="listing:FAIL",
        category="listing_reference",
        label="Failing listing",
        path="reference/listing.csv",
        row_count=1,
    )
    failed.add_error("listings.duplicate_record", "Duplicate record.", row=2)
    return Report(data_root="data", datasets=[passed, warned, failed])


def test_json_report_contains_statuses_and_counts(tmp_path: Path):
    report = build_report()
    path = write_json(report, tmp_path / "nested/report.json")

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["overall_status"] == "FAIL"
    assert payload["summary"] == {
        "dataset_count": 3,
        "pass": 1,
        "warn": 1,
        "fail": 1,
        "error_count": 1,
        "warning_count": 1,
    }
    assert payload["datasets"][0]["status"] == "PASS"
    assert payload["datasets"][1]["status"] == "WARN"
    assert payload["datasets"][2]["status"] == "FAIL"
    assert payload["datasets"][2]["issues"][0]["row"] == 2


def test_json_report_is_reproducible(tmp_path: Path):
    report = build_report()
    first = write_json(report, tmp_path / "first.json")
    second = write_json(report, tmp_path / "second.json")

    assert first.read_bytes() == second.read_bytes()
    assert "generated_at" not in first.read_text(encoding="utf-8")


def test_console_summary_is_readable():
    report = build_report()
    stream = StringIO()

    print_console(report, report_path="reports/report.json", file=stream)
    output = stream.getvalue()

    assert "Backtest Reliability Analyzer - Data Validation" in output
    assert "PASS" in output
    assert "WARN" in output
    assert "FAIL" in output
    assert "Overall status: FAIL" in output
    assert "Duplicate record." in output
    assert "reports/report.json" in output


def test_warnings_alone_do_not_count_as_failures():
    report = Report(data_root="data")
    warned = DatasetResult(
        dataset_id="prices:WARN",
        category="historical_prices",
        label="Warning prices",
        path="raw/warn.csv",
    )
    warned.add_warning("csv.bom", "BOM present.")
    report.datasets.append(warned)

    assert report.overall_status.value == "WARN"
    assert not has_failures(report)
