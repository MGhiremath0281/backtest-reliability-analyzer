"""Shared test fixtures.

All fixtures write to temporary directories. The collected source datasets are
never read or modified by the test suite.
"""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

import pytest


@pytest.fixture
def make_csv(tmp_path: Path):
    """Create a CSV fixture under ``tmp_path`` and return its path."""

    def _make(
        relative: str,
        headers: list[str] | None = None,
        rows: list[list[str]] | None = None,
        *,
        bom: bool = False,
        raw: str | None = None,
        raw_bytes: bytes | None = None,
    ) -> Path:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)

        if raw_bytes is not None:
            path.write_bytes(raw_bytes)
            return path

        if raw is None:
            buffer = StringIO()
            writer = csv.writer(buffer, lineterminator="\n")
            if headers is not None:
                writer.writerow(headers)
            for row in rows or []:
                writer.writerow(row)
            raw = buffer.getvalue()

        data = raw.encode("utf-8")
        if bom and not data.startswith(b"\xef\xbb\xbf"):
            data = b"\xef\xbb\xbf" + data
        path.write_bytes(data)
        return path

    return _make
