"""Minimal, read-only XLSX reading using only the standard library.

The project only needs the values, sheet names, and document properties of the
collected delisting workbook. This module intentionally does not evaluate
formulas, formats, or styles, and it never writes to the workbook.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CORE_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"

NS = {"m": MAIN_NS}
CELL_REF_RE = re.compile(r"^(?P<column>[A-Z]+)")


class XlsxError(ValueError):
    """Raised when a workbook cannot be read as a supported XLSX file."""


@dataclass(frozen=True)
class Sheet:
    """One worksheet, preserving row order and cell text as recorded."""

    name: str
    rows: list[list[str]] = field(default_factory=list)

    @property
    def headers(self) -> list[str]:
        return self.rows[0] if self.rows else []


@dataclass(frozen=True)
class Workbook:
    """Read-only workbook contents and available document properties."""

    path: Path
    sheets: list[Sheet]
    properties: dict[str, str] = field(default_factory=dict)

    def sheet(self, name: str) -> Sheet | None:
        for sheet in self.sheets:
            if sheet.name == name:
                return sheet
        return None


def _column_index(reference: str) -> int:
    match = CELL_REF_RE.match(reference)
    if match is None:
        raise XlsxError(f"Invalid cell reference: {reference!r}")
    index = 0
    for character in match.group("column"):
        index = index * 26 + ord(character) - 64
    return index


def _text_content(element: ET.Element) -> str:
    return "".join(node.text or "" for node in element.iter(f"{{{MAIN_NS}}}t"))


def _resolve_target(target: str) -> str:
    target = target.replace("\\", "/")
    if target.startswith("/"):
        return target.lstrip("/")
    if target.startswith("xl/"):
        return target
    return f"xl/{target}"


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    name = "xl/sharedStrings.xml"
    if name not in archive.namelist():
        return []
    root = ET.fromstring(archive.read(name))
    return [_text_content(item) for item in root.findall(f"{{{MAIN_NS}}}si")]


def _cell_value(cell: ET.Element, shared: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        inline = cell.find(f"{{{MAIN_NS}}}is")
        return _text_content(inline) if inline is not None else ""

    value = cell.find(f"{{{MAIN_NS}}}v")
    if value is None or value.text is None:
        return ""

    if cell_type == "s":
        try:
            return shared[int(value.text)]
        except (ValueError, IndexError) as exc:
            raise XlsxError(f"Invalid shared-string index: {value.text!r}") from exc
    return value.text


def _sheet_rows(root: ET.Element, shared: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    sheet_data = root.find(f"{{{MAIN_NS}}}sheetData")
    if sheet_data is None:
        return rows

    for row in sheet_data.findall(f"{{{MAIN_NS}}}row"):
        values: dict[int, str] = {}
        for cell in row.findall(f"{{{MAIN_NS}}}c"):
            reference = cell.attrib.get("r", "")
            values[_column_index(reference)] = _cell_value(cell, shared)
        if not values:
            continue
        width = max(values)
        rows.append([values.get(index, "") for index in range(1, width + 1)])
    return rows


def _document_properties(archive: zipfile.ZipFile) -> dict[str, str]:
    name = "docProps/core.xml"
    if name not in archive.namelist():
        return {}
    root = ET.fromstring(archive.read(name))
    properties: dict[str, str] = {}
    for child in root:
        local_name = child.tag.rsplit("}", 1)[-1]
        if child.text and child.text.strip():
            properties[local_name] = child.text.strip()
    return properties


def read_xlsx(path: str | Path) -> Workbook:
    """Read an XLSX workbook without modifying it.

    Raises ``XlsxError`` for a missing, unreadable, or structurally unsupported
    workbook. Callers decide whether that is a validation failure.
    """

    source = Path(path)
    if not source.is_file():
        raise XlsxError(f"Workbook does not exist: {source}")
    if not zipfile.is_zipfile(source):
        raise XlsxError(f"Not a readable XLSX/ZIP file: {source}")

    try:
        with zipfile.ZipFile(source) as archive:
            shared = _shared_strings(archive)
            workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
            relationships_root = ET.fromstring(
                archive.read("xl/_rels/workbook.xml.rels")
            )
            relationships = {
                relationship.attrib["Id"]: relationship.attrib["Target"]
                for relationship in relationships_root
            }

            sheets: list[Sheet] = []
            sheets_element = workbook_root.find(f"{{{MAIN_NS}}}sheets")
            if sheets_element is None:
                raise XlsxError("Workbook contains no sheets element.")

            for sheet_element in sheets_element:
                name = sheet_element.attrib.get("name", "")
                relationship_id = sheet_element.attrib.get(f"{{{REL_NS}}}id", "")
                target = relationships.get(relationship_id)
                if not target:
                    raise XlsxError(f"Missing relationship for sheet {name!r}.")
                worksheet = ET.fromstring(archive.read(_resolve_target(target)))
                sheets.append(Sheet(name=name, rows=_sheet_rows(worksheet, shared)))

            return Workbook(
                path=source,
                sheets=sheets,
                properties=_document_properties(archive),
            )
    except (KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
        raise XlsxError(f"Could not read workbook {source}: {exc}") from exc
