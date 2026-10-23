"""Comprehensive test suite for the Backtest Reliability Analyzer (BRA) REST API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bra.api.app import create_app
from bra.api.config import ApiConfig, get_config
from bra.api.storage import EXISTING_DATASET_ID


@pytest.fixture
def api_test_env(tmp_path: Path):
    """Provide an isolated API test environment with temporary storage and canonical data."""
    storage_dir = tmp_path / "storage"
    data_dir = tmp_path / "data"
    storage_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    # Set up small canonical dataset in data_dir
    raw_dir = data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    price_csv = raw_dir / "TO-01-01-2021-CANON-ALL-N.csv"
    price_csv.write_text(
        "Symbol,Series,Date,Prev Close,Open Price,High Price,Low Price,Last Price,Close Price,Average Price,Total Traded Quantity,Turnover ₹,No. of Trades,Deliverable Qty,% Dly Qt to Traded Qty\n"
        "CANON,EQ,2021-01-01,98.0,100.0,105.0,99.0,102.0,102.0,101.5,10000,1015000.0,500,6000,60.0\n",
        encoding="utf-8",
    )

    config = ApiConfig(
        storage_dir=storage_dir,
        data_root=data_dir,
        max_upload_size_bytes=500 * 1024,  # 500 KB limit for upload tests
        version="0.1.0",
    )

    app = create_app(config)
    app.dependency_overrides[get_config] = lambda: config

    with TestClient(app) as client:
        yield client, storage_dir, data_dir, config


# ---------------------------------------------------------------------------
# 1. Health and Metadata Responses
# ---------------------------------------------------------------------------


def test_health_and_metadata(api_test_env):
    client, _, _, _ = api_test_env

    # Root health
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["app"] == "backtest-reliability-analyzer"
    assert "analyzers" in data
    assert data["analyzers"]["survivorship"] == "available"

    # API v1 health
    v1_resp = client.get("/api/v1/health")
    assert v1_resp.status_code == 200
    assert v1_resp.json()["status"] == "ok"

    # Metadata
    meta_resp = client.get("/api/v1/metadata")
    assert meta_resp.status_code == 200
    meta = meta_resp.json()
    assert meta["version"] == "0.1.0"
    analyzer_names = [a["name"] for a in meta["registered_analyzers"]]
    assert "survivorship" in analyzer_names
    assert "lookahead" in analyzer_names
    assert "corporate_actions" in analyzer_names

    schema_types = [s["schema_type"] for s in meta["supported_schemas"]]
    assert "prices" in schema_types
    assert "corporate_actions" in schema_types
    assert "financials_legacy" in schema_types


# ---------------------------------------------------------------------------
# 2. Uploading One CSV
# ---------------------------------------------------------------------------


def test_upload_single_csv(api_test_env):
    client, storage_dir, _, _ = api_test_env

    csv_content = (
        "Date,Ticker,Open,High,Low,Close,Vol\n"
        "2021-01-01,ABC,100,105,95,102,1000\n"
        "2021-01-02,ABC,102,108,101,107,1500\n"
    )

    files = {"files": ("market_data.csv", csv_content, "text/csv")}
    resp = client.post(
        "/api/v1/datasets/upload", files=files, data={"name": "Provider A Prices"}
    )

    assert resp.status_code == 201
    data = resp.json()
    assert "dataset_id" in data
    dataset_id = data["dataset_id"]
    assert len(data["files"]) == 1
    file_info = data["files"][0]
    assert file_info["original_filename"] == "market_data.csv"
    assert file_info["row_count"] == 2
    assert file_info["detected_schema"] == "prices"

    # Verify physical file existence in isolated storage
    dataset_dir = storage_dir / "datasets" / dataset_id
    assert dataset_dir.is_dir()
    uploads = list((dataset_dir / "uploads").glob("*.csv"))
    assert len(uploads) == 1


# ---------------------------------------------------------------------------
# 3. Uploading Multiple Related CSVs
# ---------------------------------------------------------------------------


def test_upload_multiple_csvs(api_test_env):
    client, _, _, _ = api_test_env

    prices_csv = (
        "Symbol,Series,Date,Open Price,High Price,Low Price,Close Price\n"
        "INFY,EQ,2021-01-01,1300,1350,1290,1340\n"
    )
    ca_csv = (
        "SYMBOL,COMPANY NAME,PURPOSE,EX-DATE\n"
        "INFY,Infosys Ltd,Dividend Rs 15,2021-05-20\n"
    )

    files = [
        ("files", ("infy_prices.csv", prices_csv, "text/csv")),
        ("files", ("infy_actions.csv", ca_csv, "text/csv")),
    ]
    resp = client.post("/api/v1/datasets/upload", files=files)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["files"]) == 2
    detected = {f["original_filename"]: f["detected_schema"] for f in data["files"]}
    assert detected["infy_prices.csv"] == "prices"
    assert detected["infy_actions.csv"] == "corporate_actions"


# ---------------------------------------------------------------------------
# 4. Dataset Listing, Details, Preview, and Schema
# ---------------------------------------------------------------------------


def test_dataset_listing_details_preview_and_schema(api_test_env):
    client, _, _, _ = api_test_env

    csv_data = "Symbol,Series,Date,Close Price\nTCS,EQ,2021-01-01,3000\nTCS,EQ,2021-01-02,3050\n"
    up_resp = client.post(
        "/api/v1/datasets/upload",
        files={"files": ("tcs.csv", csv_data, "text/csv")},
    )
    dataset_id = up_resp.json()["dataset_id"]

    # List datasets
    list_resp = client.get("/api/v1/datasets")
    assert list_resp.status_code == 200
    ids = [d["dataset_id"] for d in list_resp.json()]
    assert dataset_id in ids
    assert EXISTING_DATASET_ID in ids  # Canonical dataset also available

    # Details
    detail_resp = client.get(f"/api/v1/datasets/{dataset_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["dataset_id"] == dataset_id
    assert len(detail["files"]) == 1

    # Preview
    prev_resp = client.get(f"/api/v1/datasets/{dataset_id}/preview?limit=1&offset=0")
    assert prev_resp.status_code == 200
    preview = prev_resp.json()
    assert preview["total_rows"] == 2
    assert len(preview["rows"]) == 1
    assert preview["rows"][0]["Symbol"] == "TCS"
    assert preview["rows"][0]["Close Price"] == "3000"

    # Schema inspection
    schema_resp = client.get(f"/api/v1/datasets/{dataset_id}/schema")
    assert schema_resp.status_code == 200
    schemas = schema_resp.json()
    assert len(schemas["files"]) == 1
    types = schemas["files"][0]["inferred_types"]
    assert types["Date"] == "date"
    assert types["Close Price"] in {"int", "float"}


# ---------------------------------------------------------------------------
# 5. Column Mapping with Different Source Column Names
# ---------------------------------------------------------------------------


def test_column_mapping_with_different_source_names(api_test_env):
    client, _, _, _ = api_test_env

    # Provider with non-standard names
    vendor_csv = (
        "trade_date,ticker,closing_val,opening_val,high_val,low_val\n"
        "2021-03-01,WIPRO,400,395,405,390\n"
    )
    up_resp = client.post(
        "/api/v1/datasets/upload",
        files={"files": ("wipro_vendor.csv", vendor_csv, "text/csv")},
    )
    dataset_id = up_resp.json()["dataset_id"]
    file_id = up_resp.json()["files"][0]["file_id"]

    # Inspect auto-mapping suggestions
    get_map_resp = client.get(f"/api/v1/datasets/{dataset_id}/mapping")
    assert get_map_resp.status_code == 200
    auto_map = get_map_resp.json()["auto_suggestions"][file_id]
    assert auto_map.get("trade_date") == "Date"
    assert auto_map.get("ticker") == "Symbol"

    # Explicitly post customized column mapping
    mapping_payload = {
        "mappings": [
            {
                "file_id": file_id,
                "schema_type": "prices",
                "column_mapping": {
                    "trade_date": "Date",
                    "ticker": "Symbol",
                    "opening_val": "Open Price",
                    "high_val": "High Price",
                    "low_val": "Low Price",
                    "closing_val": "Close Price",
                },
            }
        ]
    }
    set_map_resp = client.post(
        f"/api/v1/datasets/{dataset_id}/mapping", json=mapping_payload
    )
    assert set_map_resp.status_code == 200
    assert set_map_resp.json()["all_valid"] is True


# ---------------------------------------------------------------------------
# 6. Preparation Without Changing Original Files
# ---------------------------------------------------------------------------


def test_preparation_without_modifying_original_files(api_test_env):
    client, storage_dir, _, _ = api_test_env

    raw_text = "trade_date,ticker,closing_val\n2021-01-01,RELIANCE,2000\n"
    up_resp = client.post(
        "/api/v1/datasets/upload",
        files={"files": ("raw_prices.csv", raw_text, "text/csv")},
    )
    dataset_id = up_resp.json()["dataset_id"]
    file_id = up_resp.json()["files"][0]["file_id"]

    # Path to original uploaded file
    orig_path = (
        storage_dir / "datasets" / dataset_id / "uploads" / f"{file_id}_raw_prices.csv"
    )
    orig_content_before = orig_path.read_text(encoding="utf-8")

    # Map and Prepare
    prep_resp = client.post(f"/api/v1/datasets/{dataset_id}/prepare")
    assert prep_resp.status_code == 200
    prep_data = prep_resp.json()
    assert prep_data["status"] == "prepared"

    # Check original file remains byte-for-byte identical
    orig_content_after = orig_path.read_text(encoding="utf-8")
    assert orig_content_before == orig_content_after

    # Check normalized file was created in prepared/
    prep_file = storage_dir / "datasets" / dataset_id / "prepared" / "prices.csv"
    assert prep_file.is_file()
    prep_content = prep_file.read_text(encoding="utf-8")
    assert "Close Price" in prep_content
    assert "Symbol" in prep_content
    assert "Series" in prep_content  # Defaulted to EQ


# ---------------------------------------------------------------------------
# 7. Validation Success and Failure Cases
# ---------------------------------------------------------------------------


def test_validation_success_and_failure_cases(api_test_env):
    client, _, _, _ = api_test_env

    # Valid dataset
    valid_csv = (
        "Symbol,Series,Date,Prev Close,Open Price,High Price,Low Price,Last Price,Close Price\n"
        "GOOD,EQ,2021-01-01,100,100,105,95,102,102\n"
    )
    v_up = client.post(
        "/api/v1/datasets/upload", files={"files": ("good.csv", valid_csv, "text/csv")}
    )
    good_id = v_up.json()["dataset_id"]

    v_resp = client.post("/api/v1/validate", json={"dataset_id": good_id})
    assert v_resp.status_code == 200
    v_data = v_resp.json()
    assert v_data["status"] in {"PASS", "WARN"}

    # Invalid dataset (missing required columns and duplicate records)
    invalid_csv = "Symbol,Date\nBAD,2021-01-01\nBAD,2021-01-01\n"
    b_up = client.post(
        "/api/v1/datasets/upload", files={"files": ("bad.csv", invalid_csv, "text/csv")}
    )
    bad_id = b_up.json()["dataset_id"]

    b_resp = client.post("/api/v1/validate", json={"dataset_id": bad_id})
    assert b_resp.status_code == 200
    b_data = b_resp.json()
    assert b_data["status"] == "FAIL"
    assert b_data["summary"]["error_count"] > 0
    codes = [f["code"] for f in b_data["findings"]]
    assert any("missing" in c or "duplicate" in c for c in codes)


# ---------------------------------------------------------------------------
# 8. Real Analyzer Invocations: Survivorship, Lookahead, Corporate Actions
# ---------------------------------------------------------------------------


def test_analyzer_survivorship_real_engine(api_test_env):
    client, _, _, _ = api_test_env

    # Delisting record and price history
    delist_csv = (
        "Symbol,ISIN,Company Name,Delisted Date,Type of Delisting\n"
        "OLDCO,INE999A01019,Old Company Ltd,2021-06-30,Compulsory\n"
    )
    price_csv = (
        "Symbol,Series,Date,Prev Close,Open Price,High Price,Low Price,Last Price,Close Price\n"
        "OLDCO,EQ,2021-01-01,50,50,55,48,52,52\n"
    )
    files = [
        ("files", ("delistings.csv", delist_csv, "text/csv")),
        ("files", ("prices.csv", price_csv, "text/csv")),
    ]
    up_resp = client.post("/api/v1/datasets/upload", files=files)
    dataset_id = up_resp.json()["dataset_id"]

    # Analyze survivorship
    resp = client.post(
        "/api/v1/analyze/survivorship",
        json={
            "dataset_id": dataset_id,
            "start_date": "2021-01-01",
            "end_date": "2021-12-31",
        },
    )
    assert resp.status_code == 201
    analysis_id = resp.json()["analysis_id"]

    # Verify universe and delisted endpoints
    univ_resp = client.get(f"/api/v1/analyze/survivorship/{analysis_id}/universe")
    assert univ_resp.status_code == 200

    delist_resp = client.get(f"/api/v1/analyze/survivorship/{analysis_id}/delisted")
    assert delist_resp.status_code == 200
    assert "delisted_coverage" in delist_resp.json()


def test_analyzer_lookahead_real_engine(api_test_env):
    client, _, _, _ = api_test_env

    fin_csv = (
        "COMPANY NAME,PERIOD ENDED,Exchange Dissemination Time\n"
        "Test Corp,2021-03-31,2021-05-15 18:30:00\n"
    )
    up_resp = client.post(
        "/api/v1/datasets/upload",
        files={"files": ("fin.csv", fin_csv, "text/csv")},
    )
    dataset_id = up_resp.json()["dataset_id"]

    resp = client.post(
        "/api/v1/analyze/lookahead",
        json={"dataset_id": dataset_id, "decision_dates": ["2021-05-01", "2021-06-01"]},
    )
    assert resp.status_code == 201
    analysis_id = resp.json()["analysis_id"]

    # Check timeline
    timeline_resp = client.get(f"/api/v1/analyze/lookahead/{analysis_id}/timeline")
    assert timeline_resp.status_code == 200
    assert "financial_publication" in timeline_resp.json()


def test_analyzer_corporate_actions_real_engine(api_test_env):
    client, _, _, _ = api_test_env

    # CA with record date preceding ex-date (known violation tested in existing suite)
    ca_csv = (
        "SYMBOL,COMPANY NAME,PURPOSE,EX-DATE,RECORD DATE\n"
        "SPLITCO,Split Corp,Split 1:1,2021-04-10,2021-04-05\n"
    )
    price_csv = (
        "Symbol,Series,Date,Prev Close,Open Price,High Price,Low Price,Last Price,Close Price\n"
        "SPLITCO,EQ,2021-04-01,100,100,105,95,100,100\n"
        "SPLITCO,EQ,2021-04-11,250,250,260,240,255,255\n"
    )
    files = [
        ("files", ("ca.csv", ca_csv, "text/csv")),
        ("files", ("prices.csv", price_csv, "text/csv")),
    ]
    up_resp = client.post("/api/v1/datasets/upload", files=files)
    dataset_id = up_resp.json()["dataset_id"]

    resp = client.post(
        "/api/v1/analyze/corporate-actions",
        json={"dataset_id": dataset_id, "expected_symbol": "SPLITCO"},
    )
    assert resp.status_code == 201
    analysis_id = resp.json()["analysis_id"]

    findings_resp = client.get(
        f"/api/v1/analyze/corporate-actions/{analysis_id}/findings"
    )
    assert findings_resp.status_code == 200
    codes = [f["code"] for f in findings_resp.json()]
    assert "corporate_actions.confirmed_inconsistency" in codes


# ---------------------------------------------------------------------------
# 9 & 10. Combined Runs (All Analyzers & Selective Analyzers)
# ---------------------------------------------------------------------------


def test_combined_runs_all_and_selective(api_test_env):
    client, _, _, _ = api_test_env

    p_csv = "Symbol,Series,Date,Open Price,High Price,Low Price,Close Price\nAAA,EQ,2021-01-01,10,12,9,11\n"
    up_resp = client.post(
        "/api/v1/datasets/upload", files={"files": ("p.csv", p_csv, "text/csv")}
    )
    dataset_id = up_resp.json()["dataset_id"]

    # All three analyzers
    all_resp = client.post(
        "/api/v1/analysis-runs",
        json={
            "dataset_id": dataset_id,
            "analyzers": ["survivorship", "lookahead", "corporate_actions"],
        },
    )
    assert all_resp.status_code == 201
    all_data = all_resp.json()
    assert all_data["status"] == "completed"
    assert "survivorship" in all_data["analyzers_executed"]
    assert "lookahead" in all_data["analyzers_executed"]
    run_id = all_data["run_id"]

    # Query run details, summary, and events
    get_run = client.get(f"/api/v1/analysis-runs/{run_id}")
    assert get_run.status_code == 200

    summary_resp = client.get(f"/api/v1/analysis-runs/{run_id}/summary")
    assert summary_resp.status_code == 200
    assert "overall_status" in summary_resp.json()

    events_resp = client.get(f"/api/v1/analysis-runs/{run_id}/events")
    assert events_resp.status_code == 200
    assert len(events_resp.json()) >= 2

    # Selective run (only lookahead)
    sel_resp = client.post(
        "/api/v1/analysis-runs",
        json={
            "dataset_id": dataset_id,
            "analyzers": ["lookahead"],
        },
    )
    assert sel_resp.status_code == 201
    assert sel_resp.json()["analyzers_executed"] == ["lookahead"]
    assert "survivorship" not in sel_resp.json()["analyzers_executed"]


# ---------------------------------------------------------------------------
# 11. Insufficient Evidence and Missing Required Files
# ---------------------------------------------------------------------------


def test_insufficient_evidence_and_missing_required_files(api_test_env):
    client, _, _, _ = api_test_env

    # Upload only a delistings file without any price or corporate action data
    delist_csv = (
        "Symbol,ISIN,Company Name,Delisted Date,Type of Delisting\n"
        "GONE,INE000A01011,Gone Corp,2021-01-01,Voluntary\n"
    )
    up_resp = client.post(
        "/api/v1/datasets/upload",
        files={"files": ("delist.csv", delist_csv, "text/csv")},
    )
    dataset_id = up_resp.json()["dataset_id"]

    resp = client.post("/api/v1/analysis-runs", json={"dataset_id": dataset_id})
    assert resp.status_code == 201
    run_id = resp.json()["run_id"]

    findings_resp = client.get(f"/api/v1/analysis-runs/{run_id}/findings")
    findings = findings_resp.json()
    # Honest missing-evidence limitation reported, not crash or fabricated numbers
    limitation_codes = [
        f["code"]
        for f in findings
        if f["classification"] in {"limitation", "warning", "insufficient"}
    ]
    assert any(
        "missing" in c or "limitation" in c or "insufficient" in c
        for c in limitation_codes
    )


# ---------------------------------------------------------------------------
# 12. Unknown IDs Return 404
# ---------------------------------------------------------------------------


def test_unknown_ids_return_404(api_test_env):
    client, _, _, _ = api_test_env

    assert client.get("/api/v1/datasets/non_existent_id").status_code == 404
    assert client.get("/api/v1/validations/non_existent_id").status_code == 404
    assert client.get("/api/v1/analyze/survivorship/non_existent_id").status_code == 404
    assert client.get("/api/v1/analyze/lookahead/non_existent_id").status_code == 404
    assert (
        client.get("/api/v1/analyze/corporate-actions/non_existent_id").status_code
        == 404
    )
    assert client.get("/api/v1/analysis-runs/non_existent_id").status_code == 404
    assert client.get("/api/v1/reports/non_existent_id").status_code == 404
    assert (
        client.get("/api/v1/reports/non_existent_id/download?format=json").status_code
        == 404
    )


# ---------------------------------------------------------------------------
# 13. Malformed CSV, Unsupported Extension, and Oversized File
# ---------------------------------------------------------------------------


def test_malformed_csv_and_oversized_file(api_test_env):
    client, _, _, config = api_test_env

    # Unsupported extension
    resp_ext = client.post(
        "/api/v1/datasets/upload",
        files={"files": ("test.txt", "some,text\n", "text/plain")},
    )
    assert resp_ext.status_code == 415

    # Oversized file
    oversized_content = "A,B,C\n" + ("1,2,3\n" * 100000)
    assert len(oversized_content) > config.max_upload_size_bytes
    resp_size = client.post(
        "/api/v1/datasets/upload",
        files={"files": ("big.csv", oversized_content, "text/csv")},
    )
    assert resp_size.status_code == 413

    # Malformed CSV row count mismatch
    malformed_csv = "A,B,C\n1,2\n3,4,5,6\n"
    resp_malformed = client.post(
        "/api/v1/datasets/upload",
        files={"files": ("malformed.csv", malformed_csv, "text/csv")},
    )
    assert (
        resp_malformed.status_code == 201
    )  # Registered, but validation will flag errors
    dataset_id = resp_malformed.json()["dataset_id"]

    val_resp = client.post("/api/v1/validate", json={"dataset_id": dataset_id})
    assert val_resp.json()["status"] == "FAIL"


# ---------------------------------------------------------------------------
# 14. Report JSON and CSV Export Content
# ---------------------------------------------------------------------------


def test_reports_json_and_csv_export(api_test_env):
    client, _, _, _ = api_test_env

    csv_data = "Symbol,Series,Date,Open Price,High Price,Low Price,Close Price\nTCS,EQ,2021-01-01,100,110,90,105\n"
    up_resp = client.post(
        "/api/v1/datasets/upload", files={"files": ("tcs.csv", csv_data, "text/csv")}
    )
    dataset_id = up_resp.json()["dataset_id"]

    run_resp = client.post("/api/v1/analysis-runs", json={"dataset_id": dataset_id})
    report_id = run_resp.json()["report_id"]

    # Report metadata
    rep_meta = client.get(f"/api/v1/reports/{report_id}")
    assert rep_meta.status_code == 200
    assert rep_meta.json()["report_id"] == report_id

    # JSON download
    json_dl = client.get(f"/api/v1/reports/{report_id}/download?format=json")
    assert json_dl.status_code == 200
    assert json_dl.headers["content-type"] == "application/json"
    downloaded_data = json.loads(json_dl.text)
    assert downloaded_data["report_id"] == report_id

    # CSV download
    csv_dl = client.get(f"/api/v1/reports/{report_id}/download?format=csv")
    assert csv_dl.status_code == 200
    assert "text/csv" in csv_dl.headers["content-type"]
    assert "Finding ID,Analyzer,Finding Code" in csv_dl.text

    # PDF / XLSX rejection with clear message
    pdf_dl = client.get(f"/api/v1/reports/{report_id}/download?format=pdf")
    assert pdf_dl.status_code == 501
    xlsx_dl = client.get(f"/api/v1/reports/{report_id}/download?format=xlsx")
    assert xlsx_dl.status_code == 501


# ---------------------------------------------------------------------------
# 15. Concurrent Datasets Isolation
# ---------------------------------------------------------------------------


def test_concurrent_datasets_isolation(api_test_env):
    client, _, _, _ = api_test_env

    # Dataset A (Stock AAA)
    csv_a = "Symbol,Series,Date,Open Price,High Price,Low Price,Close Price\nAAA,EQ,2021-01-01,10,12,9,11\n"
    ds_a = client.post(
        "/api/v1/datasets/upload", files={"files": ("a.csv", csv_a, "text/csv")}
    ).json()["dataset_id"]

    # Dataset B (Stock BBB)
    csv_b = "Symbol,Series,Date,Open Price,High Price,Low Price,Close Price\nBBB,EQ,2021-01-01,200,220,190,210\n"
    ds_b = client.post(
        "/api/v1/datasets/upload", files={"files": ("b.csv", csv_b, "text/csv")}
    ).json()["dataset_id"]

    # Run analysis on A
    run_a = client.post("/api/v1/analysis-runs", json={"dataset_id": ds_a}).json()[
        "run_id"
    ]
    # Run analysis on B
    run_b = client.post("/api/v1/analysis-runs", json={"dataset_id": ds_b}).json()[
        "run_id"
    ]

    # Verify previews do not leak
    prev_a = client.get(f"/api/v1/datasets/{ds_a}/preview").json()
    prev_b = client.get(f"/api/v1/datasets/{ds_b}/preview").json()
    assert prev_a["rows"][0]["Symbol"] == "AAA"
    assert prev_b["rows"][0]["Symbol"] == "BBB"

    # Verify run A findings do not cross-contaminate run B
    detail_a = client.get(f"/api/v1/analysis-runs/{run_a}").json()
    detail_b = client.get(f"/api/v1/analysis-runs/{run_b}").json()
    assert detail_a["dataset_id"] == ds_a
    assert detail_b["dataset_id"] == ds_b


# ---------------------------------------------------------------------------
# 16. Canonical Dataset Selection & Deletion Protection
# ---------------------------------------------------------------------------


def test_canonical_dataset_selection_and_protection(api_test_env):
    client, _, _, _ = api_test_env

    # Existing canonical dataset is inspectable
    resp = client.get(f"/api/v1/datasets/{EXISTING_DATASET_ID}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_existing"] is True

    # Cannot delete canonical dataset
    del_resp = client.delete(f"/api/v1/datasets/{EXISTING_DATASET_ID}")
    assert del_resp.status_code == 400
    assert "Cannot delete canonical repository dataset" in del_resp.json()["detail"]


# ---------------------------------------------------------------------------
# 17. API Restart Persistence
# ---------------------------------------------------------------------------


def test_api_restart_persistence(api_test_env):
    client, _storage_dir, _data_dir, config = api_test_env

    csv_data = "Symbol,Series,Date,Open Price,High Price,Low Price,Close Price\nSAVE,EQ,2021-01-01,10,12,9,11\n"
    up_resp = client.post(
        "/api/v1/datasets/upload", files={"files": ("save.csv", csv_data, "text/csv")}
    )
    dataset_id = up_resp.json()["dataset_id"]

    run_resp = client.post("/api/v1/analysis-runs", json={"dataset_id": dataset_id})
    run_id = run_resp.json()["run_id"]
    report_id = run_resp.json()["report_id"]

    # Simulate restart by creating a new app instance pointing to the same storage_dir
    new_app = create_app(config)
    new_app.dependency_overrides[get_config] = lambda: config

    with TestClient(new_app) as new_client:
        # Dataset metadata persists
        d_resp = new_client.get(f"/api/v1/datasets/{dataset_id}")
        assert d_resp.status_code == 200

        # Analysis run persists
        r_resp = new_client.get(f"/api/v1/analysis-runs/{run_id}")
        assert r_resp.status_code == 200
        assert r_resp.json()["run_id"] == run_id

        # Report persists
        rep_resp = new_client.get(f"/api/v1/reports/{report_id}")
        assert rep_resp.status_code == 200


# ---------------------------------------------------------------------------
# 18. No Silent Fallback to Sample Data
# ---------------------------------------------------------------------------


def test_no_silent_fallback_to_sample_data(api_test_env):
    client, _, _, _ = api_test_env

    # Upload empty file
    empty_csv = ""
    up_resp = client.post(
        "/api/v1/datasets/upload", files={"files": ("empty.csv", empty_csv, "text/csv")}
    )
    dataset_id = up_resp.json()["dataset_id"]

    # Validation must fail honestly and not silently substitute demo data
    val_resp = client.post("/api/v1/validate", json={"dataset_id": dataset_id})
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["status"] == "FAIL"
    codes = [f["code"] for f in val_data["findings"]]
    assert any("empty" in c or "no_header" in c for c in codes)
