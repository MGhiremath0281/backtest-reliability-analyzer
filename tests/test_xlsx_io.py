"""Read-only XLSX reader tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from bra.xlsx_io import XlsxError, read_xlsx

from .support import excel_serial, write_xlsx


def test_reads_sheets_and_document_properties(tmp_path: Path):
    path = write_xlsx(
        tmp_path / "book.xlsx",
        {
            "delisted": [
                ["Symbol", "Delisted Date"],
                ["OLDTECH", excel_serial(date(2024, 1, 15))],
            ],
            "Notes": [["text"], ["a | b"]],
        },
        properties={"title": "Example", "creator": "tests"},
    )

    workbook = read_xlsx(path)

    assert [sheet.name for sheet in workbook.sheets] == ["delisted", "Notes"]
    assert workbook.sheet("delisted").rows[1][0] == "OLDTECH"
    assert workbook.sheet("Notes").rows[1][0] == "a | b"
    assert workbook.properties["title"] == "Example"
    assert workbook.properties["creator"] == "tests"


def test_rejects_non_zip_file(tmp_path: Path):
    path = tmp_path / "not.xlsx"
    path.write_text("not a workbook", encoding="utf-8")

    with pytest.raises(XlsxError, match="Not a readable XLSX"):
        read_xlsx(path)


def test_rejects_missing_file(tmp_path: Path):
    with pytest.raises(XlsxError, match="does not exist"):
        read_xlsx(tmp_path / "missing.xlsx")
