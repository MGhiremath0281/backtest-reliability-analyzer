#!/usr/bin/env python3
"""CI gate for the main validation command (``python -m bra``).

The validator exits 1 because of one known finding in the collected raw data:
117 groups of exact duplicate company-name-change records in
``data/reference/listing_history/namechange.csv`` (issue code
``listings.duplicate_record``; see ``docs/data-audit.md``). Raw source files
are never modified, so CI tolerates exactly this finding -- and nothing else --
while keeping it visible in the logs and as a GitHub Actions warning
annotation.

The gate fails when:

- the validator exits with an unexpected code, or does not write its report;
- the duplicate-group count differs from the expected number;
- any other dataset fails; or
- a failing dataset reports any issue other than the known one.

If the collected data or the validator changes, review the change and update
the expectations in this file deliberately.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

KNOWN_FAILING_DATASET = "name_changes:namechange"
KNOWN_ISSUE_CODE = "listings.duplicate_record"
EXPECTED_DUPLICATE_GROUPS = 117
REPORT_PATH = Path("reports/validation_report.json")


def evaluate_report(payload: dict[str, Any]) -> list[str]:
    """Return the problems found in a validation report.

    An empty list means the report shows exactly the one known failing
    dataset with exactly the expected number of duplicate-record groups.
    """

    problems: list[str] = []
    datasets = payload.get("datasets") or []
    failing = [d for d in datasets if d.get("status") == "FAIL"]

    if not failing:
        problems.append(
            "no failing datasets, but the known raw name-change duplicate "
            "finding is expected; either the collected data or the validator "
            "changed -- review the change and update this gate deliberately"
        )
        return problems

    known_groups = 0
    for dataset in failing:
        dataset_id = str(dataset.get("id", "<unknown>"))
        if dataset_id != KNOWN_FAILING_DATASET:
            problems.append(
                f"unexpected failing dataset: {dataset_id} "
                f"(errors={dataset.get('error_count', '?')})"
            )
            continue
        for issue in dataset.get("issues") or []:
            code = issue.get("code")
            severity = issue.get("severity")
            if code == KNOWN_ISSUE_CODE and severity == "error":
                known_groups += 1
            else:
                problems.append(
                    f"{dataset_id}: unexpected {severity} issue {code!r}: "
                    f"{issue.get('message', '<no message>')}"
                )

    if known_groups != EXPECTED_DUPLICATE_GROUPS:
        problems.append(
            f"known finding changed: {known_groups} duplicate-record group(s) "
            f"in {KNOWN_FAILING_DATASET}, expected {EXPECTED_DUPLICATE_GROUPS}; "
            "review the data diff and update this gate deliberately"
        )

    if not problems and payload.get("overall_status") != "FAIL":
        problems.append(
            "expected overall_status 'FAIL' for the known finding, got "
            f"{payload.get('overall_status')!r}"
        )

    return problems


def _annotate(level: str, message: str) -> None:
    """Emit a GitHub Actions annotation when running inside a workflow."""

    if os.environ.get("GITHUB_ACTIONS") == "true":
        escaped = (
            message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        )
        print(f"::{level} title=CI validation gate::{escaped}")


def main() -> int:
    print(f"Running validation: {sys.executable} -m bra", flush=True)
    result = subprocess.run(
        [sys.executable, "-m", "bra", "--json-report", str(REPORT_PATH)]
    )
    if result.returncode == 2:
        print(
            f"error: validator could not write its JSON report to {REPORT_PATH}",
            file=sys.stderr,
        )
        return 2
    if result.returncode not in (0, 1):
        print(
            f"error: validator exited with unexpected code {result.returncode}",
            file=sys.stderr,
        )
        return 1
    if not REPORT_PATH.is_file():
        print(
            f"error: expected JSON report at {REPORT_PATH} was not written",
            file=sys.stderr,
        )
        return 1

    payload = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    summary = payload.get("summary", {})
    problems = evaluate_report(payload)

    if problems:
        print()
        print("CI validation gate: FAILED")
        for problem in problems:
            print(f"  - {problem}")
            _annotate("error", problem)
        print()
        print(f"Reproduce locally with: {sys.executable} -m bra --verbose")
        print(
            "If this failure is expected, update scripts/ci_validate.py "
            "deliberately."
        )
        return 1

    print()
    print("CI validation gate: OK - report matches the known data state.")
    print(
        f"  Known raw finding tolerated: {KNOWN_FAILING_DATASET} reports "
        f"{EXPECTED_DUPLICATE_GROUPS} groups of exact duplicate records "
        f"({KNOWN_ISSUE_CODE}); {summary.get('fail', 0)} dataset(s) FAIL "
        "overall."
    )
    _annotate(
        "warning",
        f"{KNOWN_FAILING_DATASET}: {EXPECTED_DUPLICATE_GROUPS} groups of exact "
        f"duplicate records in raw namechange.csv ({KNOWN_ISSUE_CODE}); "
        "documented in docs/data-audit.md, tolerated by CI, never repaired in "
        "the source data",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
