#!/usr/bin/env python3
"""Independently verify the R results using Python's standard library.

This verifier reads the saved public CPI snapshots and recomputes the reported
changes. It does not download data, edit the analysis, or render/publish the site.
Run from any directory: python3 /path/to/posts/everyday-prices/verify.py
"""

import csv
import hashlib
import json
import math
from pathlib import Path
import re
from datetime import date as Date


POST = Path(__file__).resolve().parent
BASELINE = "2019-12-01"
ENDPOINT = "2024-12-01"
EXPECTED_DATES = [
    f"{year:04d}-{month:02d}-01"
    for year in range(2018, 2025)
    for month in range(1, 13)
    if (2018, 12) <= (year, month) <= (2024, 12)
]
DISPLAYED_DATES = [date for date in EXPECTED_DATES if date >= BASELINE]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def keyed(rows, columns, name):
    result = {tuple(row[column] for column in columns): row for row in rows}
    require(len(result) == len(rows), f"Duplicate {name} keys")
    return result


def main():
    series = read_csv(POST / "config" / "series.csv")
    config = keyed(series, ["series_id"], "configuration")
    ids = [row["series_id"] for row in series]
    require(len(ids) == 6, "Expected six configured series")
    require(len({row["label"] for row in series}) == 6, "Duplicate labels")
    manifest = json.loads((POST / "data/raw/provenance.json").read_text())
    files = keyed(manifest["files"], ["series_id"], "manifest")
    require(set(files) == set(config), "Manifest and configuration IDs differ")

    tables = POST / "results/tables"
    monthly = read_csv(tables / "monthly.csv")
    monthly_keys = keyed(monthly, ["series_id", "date"], "monthly results")
    expected_keys = {(sid, date) for sid in ids for date in DISPLAYED_DATES}
    require(set(monthly_keys) == expected_keys, "Displayed series/month keys differ")
    endpoint = keyed(read_csv(tables / "endpoint.csv"), ["series_id"], "endpoint")
    summary = json.loads((POST / "results/summary.json").read_text())
    summary_endpoint = keyed(summary["series"], ["series_id"], "summary endpoint")
    peaks = keyed(read_csv(tables / "peak-annual-inflation.csv"), ["series_id"], "peak")
    summary_peaks = keyed(summary["peak_annual_inflation"], ["series_id"], "summary peak")
    audit = keyed(read_csv(tables / "audit.csv"), ["series_id"], "audit")
    sensitivity = keyed(
        read_csv(tables / "endpoint-sensitivity.csv"),
        ["series_id", "date"],
        "endpoint sensitivity",
    )
    sensitivity_dates = ["2023-12-01", ENDPOINT]
    require(
        set(sensitivity) == {(sid, date) for sid in ids for date in sensitivity_dates},
        "Endpoint sensitivity keys differ",
    )
    for name, rows in [
        ("endpoint", endpoint), ("summary endpoint", summary_endpoint),
        ("peak", peaks), ("summary peak", summary_peaks), ("audit", audit),
    ]:
        require(set(rows) == set(config), f"{name} series IDs differ")

    numeric_comparisons = 0

    def close(actual, expected, description):
        nonlocal numeric_comparisons
        actual = float(actual)
        require(
            math.isfinite(actual)
            and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-9),
            f"{description}: saved {actual}, recomputed {expected}",
        )
        numeric_comparisons += 1

    raw_indexes = {}
    computed = {}
    raw_rows = 0
    for cfg in series:
        sid, label = cfg["series_id"], cfg["label"]
        path = POST / "data/raw" / f"{sid}.csv"
        provenance = files[(sid,)]
        require(provenance["file"] == path.name, f"Manifest filename differs: {sid}")
        require(provenance["label"] == label, f"Manifest label differs: {sid}")
        require(
            hashlib.md5(path.read_bytes()).hexdigest() == provenance["md5"],
            f"Raw snapshot checksum differs: {sid}",
        )
        rows = read_csv(path)
        require(list(rows[0]) == ["observation_date", sid], f"Raw schema differs: {sid}")
        dates = [row["observation_date"] for row in rows]
        require(dates == EXPECTED_DATES, f"Raw calendar is incomplete or duplicated: {sid}")
        require(len(rows) == provenance["rows"], f"Manifest row count differs: {sid}")
        raw_rows += len(rows)
        index = {row["observation_date"]: float(row[sid]) for row in rows}
        require(
            all(math.isfinite(value) and value > 0 for value in index.values()),
            f"Raw values are missing, nonfinite, or nonpositive: {sid}",
        )
        raw_indexes[sid] = index
        base = index[BASELINE]
        for date in DISPLAYED_DATES:
            prior = f"{int(date[:4]) - 1:04d}" + date[4:]
            require(prior in index, f"Prior-year month missing: {sid} {date}")
            values = {
                "index": index[date],
                "baseline_index": base,
                "cumulative_pct": 100 * (index[date] / base - 1),
                "annual_pct": 100 * (index[date] / index[prior] - 1),
            }
            computed[(sid, date)] = values
            saved = monthly_keys[(sid, date)]
            require(saved["label"] == label, f"Monthly label differs: {sid}")
            for field, value in values.items():
                close(saved[field], value, f"Monthly {sid} {date} {field}")

        for saved_rows in [endpoint, summary_endpoint]:
            saved = saved_rows[(sid,)]
            require(saved["label"] == label, f"Endpoint label differs: {sid}")
            for field in ["cumulative_pct", "annual_pct"]:
                close(saved[field], computed[(sid, ENDPOINT)][field], f"Endpoint {sid} {field}")
        peak_date = max(DISPLAYED_DATES, key=lambda date: computed[(sid, date)]["annual_pct"])
        for saved_rows in [peaks, summary_peaks]:
            saved = saved_rows[(sid,)]
            require(saved["label"] == label, f"Peak label differs: {sid}")
            require(saved["peak_date"] == peak_date, f"Peak date differs: {sid}")
            close(saved["peak_annual_pct"], computed[(sid, peak_date)]["annual_pct"], f"Peak {sid}")
        saved_audit = audit[(sid,)]
        require(int(saved_audit["raw_rows"]) == len(rows), f"Audit raw count differs: {sid}")
        require(int(saved_audit["displayed_months"]) == len(DISPLAYED_DATES), f"Audit month count differs: {sid}")
        require(int(saved_audit["duplicate_dates"]) == 0, f"Audit duplicate claim differs: {sid}")
        require(int(saved_audit["missing_values"]) == 0, f"Audit missing-value claim differs: {sid}")
        require(saved_audit["checksum_match"] == "TRUE", f"Audit checksum claim differs: {sid}")
        close(saved_audit["baseline_cumulative_pct"], 0, f"Baseline audit {sid}")
        for date in sensitivity_dates:
            saved = sensitivity[(sid, date)]
            require(saved["label"] == label, f"Sensitivity label differs: {sid}")
            for field in ["index", "baseline_index", "cumulative_pct", "annual_pct"]:
                close(saved[field], computed[(sid, date)][field], f"Sensitivity {sid} {date} {field}")

    category_ids = [cfg["series_id"] for cfg in series if cfg["role"] == "category"]
    require(len(category_ids) == 5, "Expected five selected categories")
    for date in sensitivity_dates:
        ordered = sorted(category_ids, key=lambda sid: -computed[(sid, date)]["cumulative_pct"])
        for rank, sid in enumerate(ordered, start=1):
            close(sensitivity[(sid, date)]["category_rank"], rank, f"Sensitivity rank {sid} {date}")
            if date == ENDPOINT:
                close(endpoint[(sid,)]["category_rank"], rank, f"Endpoint rank {sid}")
                close(summary_endpoint[(sid,)]["category_rank"], rank, f"Summary rank {sid}")

    gas = raw_indexes["CUUR0000SETB01"]
    gas_peak = max(DISPLAYED_DATES, key=gas.get)
    require(summary["gas_peak_date"] == gas_peak, "Gasoline peak date differs")
    close(summary["gas_fall_from_peak_pct"], 100 * (gas[ENDPOINT] / gas[gas_peak] - 1), "Gasoline decline from peak")
    grocery = raw_indexes["CUUR0000SAF11"]
    grocery_peak = max(DISPLAYED_DATES, key=lambda date: computed[("CUUR0000SAF11", date)]["annual_pct"])
    require(summary["grocery_peak_inflation_date"] == grocery_peak, "Grocery inflation peak date differs")
    close(summary["grocery_peak_inflation_pct"], computed[("CUUR0000SAF11", grocery_peak)]["annual_pct"], "Grocery inflation peak")
    close(summary["grocery_change_after_peak_inflation_pct"], 100 * (grocery[ENDPOINT] / grocery[grocery_peak] - 1), "Grocery change after inflation peak")
    require(summary["baseline"] == BASELINE and summary["endpoint"] == ENDPOINT, "Summary dates differ")
    require(summary["categories"] == 5 and summary["months_per_series"] == 61, "Summary dimensions differ")

    validation = json.loads((POST / "results/validation.json").read_text())
    expected_validation = {
        "source_files": 6, "raw_months_per_series": 73, "displayed_rows": 366,
        "missing_displayed_values": 0, "unique_series_month_keys": True,
        "complete_monthly_calendars": True, "twelve_month_matches_verified": True,
        "snapshot_md5_verified": True,
    }
    require(validation == expected_validation, "Saved validation claims differ from checked inputs")

    # Inspect the actual saved Plotly payload, rather than only its R source.
    # This checks the initial lines, both selector alternatives, and numeric hover
    # contents. Actual clicking, zooming, and rendering still need a browser.
    figure_html = (POST / "results/price-explorer.html").read_text(encoding="utf-8")
    payloads = re.findall(
        r'<script type="application/json" data-for="[^"]+">(.*?)</script>',
        figure_html, flags=re.DOTALL,
    )
    require(len(payloads) == 1, "Expected exactly one saved Plotly widget payload")
    widget = json.loads(payloads[0])["x"]
    traces = widget["data"]
    require(len(traces) == 6, "Expected six displayed Plotly traces")
    menus = widget["layout"]["updatemenus"]
    require(len(menus) == 1, "Expected one measure selector")
    buttons = menus[0]["buttons"]
    require(
        [button["label"] for button in buttons] == ["Since Dec 2019", "Year-over-year"],
        "Saved Plotly selector labels differ",
    )
    for button in buttons:
        require(button["method"] == "update", "Unexpected Plotly selector method")
        require(len(button["args"][0]["y"]) == 6, "Selector trace count differs")
        require(button["args"][1]["yaxis"]["ticksuffix"] == "%", "Selector axis lacks percent units")
    for i, cfg in enumerate(series):
        sid, label = cfg["series_id"], cfg["label"]
        trace = traces[i]
        require(trace["name"] == label, f"Saved Plotly trace label differs: {sid}")
        require(trace["x"] == DISPLAYED_DATES, f"Saved Plotly dates differ: {sid}")
        require(len(trace["y"]) == 61, f"Saved Plotly trace length differs: {sid}")
        require(len(trace.get("text", [])) == 61, f"Numeric hover payload missing: {sid}")
        for j, date in enumerate(DISPLAYED_DATES):
            expected = computed[(sid, date)]
            close(trace["y"][j], expected["cumulative_pct"], f"Plotly initial {sid} {date}")
            for button, field in zip(buttons, ["cumulative_pct", "annual_pct"]):
                close(button["args"][0]["y"][i][j], expected[field], f"Plotly selector {sid} {date} {field}")
            hover = trace["text"][j]
            month = Date.fromisoformat(date).strftime("%b %Y")
            require(label in hover and month in hover, f"Hover identification differs: {sid} {date}")
            for field in ["cumulative_pct", "annual_pct"]:
                require(
                    f"{expected[field]:.1f}%" in hover,
                    f"Hover number differs or is missing: {sid} {date} {field}",
                )
        templates = trace["hovertemplate"]
        if isinstance(templates, str):
            templates = [templates]
        require(
            all(template == "%{text}<extra></extra>" for template in templates),
            f"Hover template does not use the checked payload: {sid}",
        )
    report = {
        "status": "passed", "raw_files_checked": len(series),
        "raw_rows_checked": raw_rows, "displayed_rows_checked": len(monthly),
        "numeric_comparisons": numeric_comparisons,
        "plotly_traces_checked": len(traces), "plotly_hover_rows_checked": len(monthly),
        "checks": [
            "Raw schemas, labels, IDs, checksums, positive finite indexes and complete monthly calendars",
            "All displayed indexes, baseline indexes, cumulative changes and exact 12-month changes",
            "Endpoint summaries, category ranks, peak dates and rates, and 2023/2024 sensitivity tables",
            "Gasoline peak decline, grocery post-peak change, audit counts and saved validation claims",
            "Saved Plotly lines, both selector value arrays, and numeric/date hover text",
        ],
        "limits": [
            "This verifies arithmetic and internal consistency, not the original BLS collection process.",
            "This script does not test browser controls, article prose, or empirical uncertainty.",
        ],
    }
    target = POST / "results/verification.json"
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
