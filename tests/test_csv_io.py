"""CSV integrity tests."""

from __future__ import annotations

from pathlib import Path

from bra.csv_io import read_csv


def codes(table) -> list[str]:
    return [issue.code for issue in table.issues]


def test_reads_bom_whitespace_and_newline_headers(make_csv):
    path = make_csv(
        "clean.csv",
        ["Symbol  ", "Date\n", "Close Price  "],
        [["INFY", "22-Oct-2026", "1,153.35"]],
        bom=True,
    )

    table = read_csv(path)

    assert table.headers == ["Symbol", "Date", "Close Price"]
    assert table.rows[0].get("Date") == "22-Oct-2026"
    assert table.rows[0].get("Close Price") == "1,153.35"
    assert "csv.bom" in codes(table)
    assert "csv.header_whitespace" in codes(table)
    assert table.readable
    assert table.headers_ok


def test_duplicate_headers_are_a_failure(make_csv):
    path = make_csv("duplicate.csv", ["Symbol", "Symbol ", "Date"], [["A", "B", "C"]])

    table = read_csv(path)

    assert "csv.header_duplicate" in codes(table)
    assert not table.headers_ok


def test_blank_header_is_a_failure(make_csv):
    path = make_csv("blank-header.csv", ["Symbol", "  "], [["A", "B"]])

    table = read_csv(path)

    assert "csv.header_blank" in codes(table)
    assert not table.headers_ok


def test_empty_file_is_a_failure(make_csv):
    path = make_csv("empty.csv", raw="")

    table = read_csv(path)

    assert "csv.empty" in codes(table)
    assert not table.readable


def test_header_only_file_is_a_failure(make_csv):
    path = make_csv("header-only.csv", ["Symbol", "Date"], [])

    table = read_csv(path)

    assert "csv.no_data_rows" in codes(table)
    assert table.rows == []


def test_field_count_mismatch_skips_bad_row_but_keeps_good_rows(make_csv):
    path = make_csv(
        "field-count.csv",
        ["Symbol", "Date"],
        [["INFY", "22-Oct-2026"], ["TCS"]],
    )

    table = read_csv(path)

    assert "csv.field_count" in codes(table)
    assert len(table.rows) == 1
    assert table.rows[0].get("Symbol") == "INFY"


def test_malformed_quoting_is_reported(make_csv):
    path = make_csv(
        "malformed.csv",
        raw='Symbol,Date\n"INFY,22-Oct-2026\n',
    )

    table = read_csv(path)

    assert "csv.malformed" in codes(table)


def test_missing_file_is_reported(tmp_path: Path):
    table = read_csv(tmp_path / "does-not-exist.csv")

    assert not table.readable
    assert [issue.code for issue in table.issues] == ["csv.missing_file"]


def test_directory_path_is_unreadable(tmp_path: Path):
    path = tmp_path / "directory.csv"
    path.mkdir()

    table = read_csv(path)

    assert not table.readable
    assert [issue.code for issue in table.issues] == ["csv.unreadable"]


def test_invalid_utf8_is_reported(make_csv):
    path = make_csv("invalid.csv", raw_bytes=b"Symbol,Date\nINFY,\xff\n")

    table = read_csv(path)

    assert "csv.encoding" in codes(table)
    assert not table.readable


def test_blank_lines_are_reported_and_ignored(make_csv):
    path = make_csv(
        "blank-lines.csv",
        raw="Symbol,Date\n\nINFY,22-Oct-2026\n\n",
    )

    table = read_csv(path)

    assert "csv.blank_rows" in codes(table)
    assert len(table.rows) == 1


def test_reading_does_not_modify_source_file(make_csv):
    path = make_csv("immutable.csv", ["Symbol"], [["INFY"]])
    before = path.read_bytes()

    read_csv(path)

    assert path.read_bytes() == before
