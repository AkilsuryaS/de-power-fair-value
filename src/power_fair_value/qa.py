from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from power_fair_value.config import project_path
from power_fair_value.utils import ensure_dir, write_json


REQUIRED_COLUMNS = [
    "timestamp_utc",
    "da_price_eur_mwh",
    "load_da_forecast_mw",
    "wind_onshore_da_forecast_mw",
    "wind_offshore_da_forecast_mw",
    "solar_da_forecast_mw",
]


def _check(name: str, passed: bool, severity: str, detail: str) -> Dict[str, Any]:
    return {
        "name": name,
        "passed": bool(passed),
        "severity": severity,
        "detail": detail,
    }


def run_qa(df: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    checks.append(
        _check(
            "required_columns",
            not missing_columns,
            "critical",
            f"Missing columns: {missing_columns}" if missing_columns else "All required columns present.",
        )
    )

    row_count = len(df)
    start = pd.Timestamp(config["data"]["start"])
    end = pd.Timestamp(config["data"]["end"])
    expected_min_rows = int((end - start).days + 1) * 23
    checks.append(
        _check(
            "row_count",
            row_count >= expected_min_rows,
            "critical",
            f"Rows: {row_count}. Expected at least {expected_min_rows} for configured date range.",
        )
    )

    duplicate_count = int(df["timestamp_utc"].duplicated().sum())
    checks.append(
        _check(
            "duplicate_timestamps",
            duplicate_count == 0,
            "critical",
            f"Duplicate UTC timestamps: {duplicate_count}.",
        )
    )

    if row_count > 1:
        gaps = df["timestamp_utc"].sort_values().diff().dropna()
        bad_gaps = int((gaps != pd.Timedelta(hours=1)).sum())
    else:
        bad_gaps = 0
    checks.append(
        _check(
            "hourly_cadence",
            bad_gaps == 0,
            "critical",
            f"Non-hourly UTC intervals: {bad_gaps}.",
        )
    )

    null_counts = df[REQUIRED_COLUMNS].isna().sum().astype(int).to_dict()
    checks.append(
        _check(
            "missing_values",
            sum(null_counts.values()) == 0,
            "critical",
            f"Missing values by required column: {null_counts}.",
        )
    )

    price_ok = df["da_price_eur_mwh"].between(-500, 1000).all()
    checks.append(
        _check(
            "price_bounds",
            bool(price_ok),
            "critical",
            "All prices within [-500, 1000] EUR/MWh."
            if price_ok
            else "At least one price is outside [-500, 1000] EUR/MWh.",
        )
    )

    non_negative_cols = [
        "load_da_forecast_mw",
        "wind_onshore_da_forecast_mw",
        "wind_offshore_da_forecast_mw",
        "solar_da_forecast_mw",
    ]
    negative_counts = (df[non_negative_cols] < 0).sum().astype(int).to_dict()
    checks.append(
        _check(
            "driver_non_negative",
            sum(negative_counts.values()) == 0,
            "critical",
            f"Negative driver counts: {negative_counts}.",
        )
    )

    low_load_count = int((df["load_da_forecast_mw"] < 10000).sum())
    checks.append(
        _check(
            "load_floor",
            low_load_count == 0,
            "warning",
            f"Hours with load forecast below 10 GW: {low_load_count}.",
        )
    )

    report = {
        "market": config["market"]["name"],
        "bidding_zone": config["market"]["bidding_zone"],
        "data_start": config["data"]["start"],
        "data_end": config["data"]["end"],
        "rows": row_count,
        "checks": checks,
        "status": "passed"
        if all(c["passed"] for c in checks if c["severity"] == "critical")
        else "failed",
    }

    qa_dir = project_path(config, "outputs/qa")
    ensure_dir(qa_dir)
    write_json(qa_dir / "qa_report.json", report)
    (qa_dir / "qa_report.md").write_text(format_qa_markdown(report), encoding="utf-8")

    if report["status"] == "failed":
        failed = [c["name"] for c in checks if c["severity"] == "critical" and not c["passed"]]
        raise ValueError(f"Critical QA checks failed: {failed}")

    return report


def format_qa_markdown(report: Dict[str, Any]) -> str:
    rows = [
        "| Check | Severity | Status | Detail |",
        "|---|---:|---:|---|",
    ]
    for check in report["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        rows.append(
            f"| {check['name']} | {check['severity']} | {status} | {check['detail']} |"
        )
    return "\n".join(
        [
            f"# QA Report: {report['market']}",
            "",
            f"- Bidding zone: `{report['bidding_zone']}`",
            f"- Date range: `{report['data_start']}` to `{report['data_end']}`",
            f"- Rows: `{report['rows']}`",
            f"- Status: `{report['status'].upper()}`",
            "",
            *rows,
            "",
        ]
    )
