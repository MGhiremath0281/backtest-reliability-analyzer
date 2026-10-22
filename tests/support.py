"""Reusable constants and fixtures for tests (no real data dependencies)."""

from __future__ import annotations

import csv
import zipfile
from datetime import date
from io import StringIO
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from bra.models import DatasetResult

PRICE_HEADERS = [
    "Symbol",
    "Series",
    "Date",
    "Prev Close",
    "Open Price",
    "High Price",
    "Low Price",
    "Last Price",
    "Close Price",
    "Average Price",
    "Total Traded Quantity",
    "Turnover ₹",
    "No. of Trades",
    "Deliverable Qty",
    "% Dly Qt to Traded Qty",
]

CA_HEADERS = [
    "SYMBOL",
    "COMPANY NAME",
    "SERIES",
    "PURPOSE",
    "FACE VALUE",
    "EX-DATE",
    "RECORD DATE",
    "BOOK CLOSURE START DATE",
    "BOOK CLOSURE END DATE",
]

LEGACY_FINANCIAL_HEADERS = [
    "COMPANY NAME",
    "AUDITED / UNAUDITED",
    "CUMULATIVE / NON-CUMULATIVE",
    "CONSOLIDATED / NON-CONSOLIDATED",
    "IND AS/ NON IND AS",
    "PERIOD",
    "PERIOD ENDED",
    "RELATING TO",
    "** XBRL",
    "Exchange Received Time",
    "Exchange Dissemination Time",
    "Time Taken",
]

INTEGRATED_FINANCIAL_HEADERS = [
    "SYMBOL \n",
    "COMPANY NAME \n",
    "QUARTER END DATE \n",
    "TYPE OF SUBMISSION \n",
    "AUDITED / UNAUDITED \n",
    "CONSOLIDATED / STANDALONE \n",
    "DETAILS \n",
    "XBRL \n",
    "BROADCAST DATE/TIME \n",
    "REVISED DATE/TIME \n",
    "REVISION REMARKS \n",
    "EXCHANGE DISSEMINATION TIME \n",
    "TIME TAKEN \n",
]

CURRENT_LISTING_HEADERS = [
    "SYMBOL",
    "NAME OF COMPANY",
    "SERIES",
    "DATE OF LISTING",
    "PAID UP VALUE",
    "MARKET LOT",
    "ISIN NUMBER",
    "FACE VALUE",
]

NAME_CHANGE_HEADERS = [
    "SYMBOL",
    "OLD NAME OF THE COMPANY",
    "NEW NAME OF THE COMPANY",
    "EFFECTIVE DATE",
]

SYMBOL_CHANGE_HEADERS = [
    "NAME OF THE COMPANY",
    "OLD SYMBOL",
    "NEW SYMBOL",
    "EFFECTIVE DATE",
]

DELISTING_HEADERS = [
    "Symbol",
    "ISIN",
    "Company Name",
    "Board",
    "Delisted Date",
    "Type of Delisting",
]

VALID_ISIN = "INE009A01021"


def make_result(dataset_id: str = "test:dataset") -> DatasetResult:
    return DatasetResult(
        dataset_id=dataset_id,
        category="test",
        label="Test dataset",
        path="test.csv",
    )


def issue_codes(result: DatasetResult) -> list[str]:
    return [issue.code for issue in result.issues]


def price_row(
    date: str,
    *,
    symbol: str = "INFY",
    series: str = "EQ",
    open_price: str = "100",
    high: str = "110",
    low: str = "90",
    close: str = "105",
    **overrides: str,
) -> list[str]:
    values = {
        "Symbol": symbol,
        "Series": series,
        "Date": date,
        "Prev Close": "100",
        "Open Price": open_price,
        "High Price": high,
        "Low Price": low,
        "Last Price": close,
        "Close Price": close,
        "Average Price": "101",
        "Total Traded Quantity": "1,000",
        "Turnover ₹": "100000",
        "No. of Trades": "10",
        "Deliverable Qty": "100",
        "% Dly Qt to Traded Qty": "10",
    }
    values.update(overrides)
    return [values[column] for column in PRICE_HEADERS]


def ca_row(
    *,
    symbol: str = "INFY",
    company: str = "Infosys Limited",
    purpose: str = "Dividend - Rs 10 Per Share",
    ex_date: str = "15-Jun-2024",
    record_date: str = "16-Jun-2024",
    closure_start: str = "-",
    closure_end: str = "-",
) -> list[str]:
    return [
        symbol,
        company,
        "EQ",
        purpose,
        "5",
        ex_date,
        record_date,
        closure_start,
        closure_end,
    ]


def legacy_financial_row(
    *,
    company: str = "Infosys Limited",
    period: str = "31-Dec-2024",
    received: str = "16-Jan-2025 19:42:10",
    disseminated: str = "16-Jan-2025 19:42:44",
    consolidation: str = "Consolidated",
    period_label: str = "Quarterly",
) -> list[str]:
    return [
        company,
        "Audited",
        "Non-cumulative",
        consolidation,
        "Ind-AS New",
        period_label,
        period,
        "Third Quarter",
        "https://example.invalid/xbrl.xml",
        received,
        disseminated,
        "00:00:34",
    ]


def integrated_financial_row(
    *,
    symbol: str = "INFY",
    company: str = "Infosys Limited",
    period: str = "31-Dec-2024",
    submission: str = "Original",
    consolidation: str = "Consolidated",
    broadcast: str = "16-Jan-2025 19:42:00",
    disseminated: str = "16-Jan-2025 19:42:44",
) -> list[str]:
    return [
        symbol,
        company,
        period,
        submission,
        "Audited",
        consolidation,
        "https://example.invalid/details.html",
        "https://example.invalid/xbrl.xml",
        broadcast,
        "",
        "",
        disseminated,
        "00:00:44",
    ]


def current_listing_row(
    *,
    symbol: str = "INFY",
    name: str = "Infosys Limited",
    series: str = "EQ",
    listing_date: str = "06-OCT-2008",
    isin: str = VALID_ISIN,
) -> list[str]:
    return [symbol, name, series, listing_date, "5", "1", isin, "5"]


def name_change_row(
    *,
    symbol: str = "INFY",
    old_name: str = "Old Infosys Limited",
    new_name: str = "Infosys Limited",
    effective_date: str = "15-JUN-2011",
) -> list[str]:
    return [symbol, old_name, new_name, effective_date]


def symbol_change_row(
    *,
    name: str = "Infosys Limited",
    old_symbol: str = "INFYOLD",
    new_symbol: str = "INFY",
    effective_date: str = "15-JUN-2011",
) -> list[str]:
    return [name, old_symbol, new_symbol, effective_date]


def delisting_row(
    *,
    symbol: str = "OLDTECH",
    isin: str = "INE123A01018",
    name: str = "Old Tech Limited",
    board: str = "Main Board",
    delisted_date: str = "2024-01-15",
    delisting_type: str = "Voluntary Delisting",
) -> list[str]:
    return [symbol, isin, name, board, delisted_date, delisting_type]


def write_csv(
    path: Path,
    headers: list[str],
    rows: list[list[str]],
    *,
    bom: bool = False,
) -> Path:
    """Write a test CSV and return its path."""

    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    data = buffer.getvalue().encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)
    return path


def create_valid_data_root(base: Path, *, bom: bool = False) -> Path:
    """Create a complete, minimal, valid data tree for CLI tests."""

    write_csv(
        base / "raw/22-10-2021-TO-22-10-2026-INFY-ALL-N.csv",
        PRICE_HEADERS,
        [
            price_row("22-Oct-2026"),
            price_row("21-Oct-2026"),
        ],
        bom=bom,
    )
    write_csv(
        base / "reference/corporate_actions/"
        "CF-CA-equities-INFY-22-10-2021-to-22-10-2026.csv",
        CA_HEADERS,
        [ca_row()],
    )
    write_csv(
        base / "reference/financial_results/"
        "CF-FR-equities-INFY-22-10-2021-to-22-10-2026.csv",
        LEGACY_FINANCIAL_HEADERS,
        [legacy_financial_row()],
    )
    write_csv(
        base / "reference/financial_results/additional/"
        "CF-Integrated-Filing-equities-Integrated Filing- Financials-INFY-"
        "01-01-2025-to-22-10-2026.csv",
        [header.strip() for header in INTEGRATED_FINANCIAL_HEADERS],
        [integrated_financial_row()],
    )
    write_csv(
        base / "reference/listing_history/EQUITY_L.csv",
        CURRENT_LISTING_HEADERS,
        [current_listing_row()],
    )
    write_csv(
        base / "reference/listing_history/namechange.csv",
        NAME_CHANGE_HEADERS,
        [name_change_row()],
    )
    write_csv(
        base / "reference/listing_history/symbolchange.csv",
        SYMBOL_CHANGE_HEADERS,
        [symbol_change_row()],
    )
    write_csv(
        base / "processed/delisted_companies_2021-2026.csv",
        DELISTING_HEADERS,
        [delisting_row()],
    )
    write_csv(
        base / "processed/main_board_delistings_2021-2026.csv",
        DELISTING_HEADERS,
        [delisting_row()],
    )
    return base


def excel_serial(value: date) -> str:
    """Return the Excel 1900-system serial for a date."""

    return str((value - date(1899, 12, 30)).days)


def write_xlsx(
    path: Path,
    sheets: dict[str, list[list[str]]],
    *,
    properties: dict[str, str] | None = None,
) -> Path:
    """Write a minimal XLSX workbook for read-only reader tests."""

    path.parent.mkdir(parents=True, exist_ok=True)
    sheet_items = list(sheets.items())

    content_types = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
    ]
    for index in range(1, len(sheet_items) + 1):
        content_types.append(
            f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
    content_types.append("</Types>")

    workbook_sheets = []
    relationships = []
    for index, (name, _) in enumerate(sheet_items, start=1):
        workbook_sheets.append(
            f'<sheet name={quoteattr(name)} sheetId="{index}" '
            f'r:id="rId{index}"/>'
        )
        relationships.append(
            f'<Relationship Id="rId{index}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{index}.xml"/>'
        )

    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets>{"".join(workbook_sheets)}</sheets>'
        "</workbook>"
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'{"".join(relationships)}'
        "</Relationships>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" '
        'Target="docProps/core.xml"/>'
        "</Relationships>"
    )

    props = properties or {}
    core_properties = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        (
            '<cp:coreProperties '
            'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        ),
    ]
    property_tags = {
        "title": "dc:title",
        "creator": "dc:creator",
    }
    for key, value in props.items():
        tag = property_tags.get(key, f"cp:{key}")
        core_properties.append(f"<{tag}>{escape(value)}</{tag}>")
    core_properties.append("</cp:coreProperties>")

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "".join(content_types))
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("docProps/core.xml", "".join(core_properties))

        for index, (_, rows) in enumerate(sheet_items, start=1):
            cells: list[str] = []
            for row_number, values in enumerate(rows, start=1):
                row_cells = []
                for column_number, value in enumerate(values, start=1):
                    if value == "":
                        continue
                    letters = ""
                    position = column_number
                    while position:
                        position, remainder = divmod(position - 1, 26)
                        letters = chr(65 + remainder) + letters
                    row_cells.append(
                        f'<c r="{letters}{row_number}" t="inlineStr">'
                        f'<is><t xml:space="preserve">{escape(str(value))}</t></is></c>'
                    )
                if row_cells:
                    cells.append(
                        f'<row r="{row_number}">{"".join(row_cells)}</row>'
                    )
            worksheet = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                f'<sheetData>{"".join(cells)}</sheetData>'
                "</worksheet>"
            )
            archive.writestr(f"xl/worksheets/sheet{index}.xml", worksheet)

    return path


def create_prepare_data_root(base: Path) -> Path:
    """Create a valid tree that also contains the delisting workbook."""

    create_valid_data_root(base)
    workbook = base / (
        "reference/listing_history/"
        "Copy_of_List_of_delisted_Companies_test.xlsx"
    )
    write_xlsx(
        workbook,
        {
            "delisted": [
                DELISTING_HEADERS,
                [
                    "OLDTECH",
                    "INE123A01018",
                    "Old Tech Limited",
                    "Main Board",
                    excel_serial(date(2024, 1, 15)),
                    "Voluntary Delisting",
                ],
            ],
            "Add Data-Comp. Delisted": [
                DELISTING_HEADERS,
                [
                    "OLDTECH",
                    "INE123A01018",
                    "Old Tech Limited",
                    "Main Board",
                    excel_serial(date(2024, 1, 15)),
                    "Compulsory Delisting",
                ],
            ],
            "Exit Provided": [
                DELISTING_HEADERS,
                [
                    "OLDTECH",
                    "INE123A01018",
                    "Old Tech Limited",
                    "Main Board",
                    excel_serial(date(2024, 1, 15)),
                    "Voluntary Delisting",
                ],
            ],
        },
        properties={"title": "Test delisting workbook", "creator": "pytest"},
    )
    return base

