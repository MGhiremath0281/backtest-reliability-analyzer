"""CLI behavior and exit-code tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from bra.cli import main

from .support import PRICE_HEADERS, create_valid_data_root, price_row, write_csv


def test_cli_returns_zero_for_clean_data(tmp_path: Path, capsys):
    root = create_valid_data_root(tmp_path / "data")
    report_path = tmp_path / "report.json"

    exit_code = main(["--data-root", str(root), "--json-report", str(report_path)])

    assert exit_code == 0
    output = capsys.readouterr().out
    # Warnings do not fail the run; survivorship findings make the status WARN.
    assert "Overall status: WARN" in output
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "WARN"
    assert any(d["id"] == "survivorship:analysis" for d in payload["datasets"])


def test_cli_returns_zero_for_warnings_only(tmp_path: Path, capsys):
    root = create_valid_data_root(tmp_path / "data", bom=True)
    report_path = tmp_path / "report.json"

    exit_code = main(["--data-root", str(root), "--json-report", str(report_path)])

    assert exit_code == 0
    assert "Overall status: WARN" in capsys.readouterr().out
    assert json.loads(report_path.read_text())["overall_status"] == "WARN"


def test_cli_returns_one_for_critical_failure(tmp_path: Path, capsys):
    root = create_valid_data_root(tmp_path / "data")
    write_csv(
        root / "raw/22-10-2021-TO-22-10-2026-INFY-ALL-N.csv",
        PRICE_HEADERS,
        [price_row("22-Oct-2026"), price_row("22-Oct-2026")],
    )
    report_path = tmp_path / "report.json"

    exit_code = main(["--data-root", str(root), "--json-report", str(report_path)])

    assert exit_code == 1
    assert "Overall status: FAIL" in capsys.readouterr().out
    assert json.loads(report_path.read_text())["overall_status"] == "FAIL"


def test_cli_reports_missing_data_root(tmp_path: Path, capsys):
    report_path = tmp_path / "report.json"

    exit_code = main(
        [
            "--data-root",
            str(tmp_path / "missing"),
            "--json-report",
            str(report_path),
        ]
    )

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "Overall status: FAIL" in output
    assert report_path.is_file()


def test_module_entry_point_runs(tmp_path: Path):
    root = create_valid_data_root(tmp_path / "data")
    report_path = tmp_path / "subprocess-report.json"
    repo_root = Path(__file__).resolve().parents[1]

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "bra",
            "--data-root",
            str(root),
            "--json-report",
            str(report_path),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    # Warnings do not fail the run; survivorship findings make the status WARN.
    assert "Overall status: WARN" in completed.stdout
    assert report_path.is_file()
