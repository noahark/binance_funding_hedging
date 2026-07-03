"""Orchestrate public market discovery: samples -> candidate classification."""

from __future__ import annotations

import csv
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from backend.adapters.binance_public import capture_samples, load_json_file
from backend.domain.classification import ClassificationResult, classify_symbol
from backend.domain.funding import (
    FundingSnapshot,
    get_funding_field_semantics,
    normalize_premium_index_entry,
    summarize_funding_history,
)
from backend.domain.symbols import SymbolInfo, join_futures_spot
from backend.domain.trading_rules import compute_effective_rules

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures"

CANDIDATE_FIELDS = [
    "symbol",
    "base_asset",
    "quote_asset",
    "perp_status",
    "spot_status",
    "route_class",
    "asset_tag",
    "asset_tag_confidence",
    "asset_tag_source",
    "positive_funding_candidate",
    "negative_funding_status",
    "current_funding_rate",
    "next_funding_time",
    "funding_history_summary",
    "futures_min_notional",
    "spot_min_notional",
    "effective_min_notional",
    "futures_step_size",
    "spot_step_size",
    "data_timestamp",
    "source_files",
    "exclusion_reason",
    "funding_signal_status",
]


def _decimal_str(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _index_premium(premium_index: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {entry["symbol"]: entry for entry in premium_index}


def _load_funding_history(sample_dir: Path, symbol: str) -> list[dict[str, Any]]:
    path = sample_dir / f"fapi_funding_rate_{symbol}.json"
    if not path.exists():
        return []
    data = load_json_file(path)
    return data if isinstance(data, list) else []


def build_candidate_row(
    symbol_info: SymbolInfo,
    classification: ClassificationResult,
    premium_entry: dict[str, Any] | None,
    funding_history: list[dict[str, Any]],
    effective_rules: Any,
    funding_snapshot: Any,
    data_timestamp: int,
    source_files: list[str],
) -> dict[str, Any]:
    """Build one candidate row dict with string-serialized numerics."""
    history_summary = summarize_funding_history(funding_history)
    if funding_snapshot.funding_history_summary:
        history_summary = {**history_summary, **funding_snapshot.funding_history_summary}

    return {
        "symbol": symbol_info.symbol,
        "base_asset": symbol_info.base_asset,
        "quote_asset": symbol_info.quote_asset,
        "perp_status": symbol_info.perp_status,
        "spot_status": symbol_info.spot_status,
        "route_class": classification.route_class,
        "asset_tag": classification.asset_tag,
        "asset_tag_confidence": classification.asset_tag_confidence,
        "asset_tag_source": classification.asset_tag_source,
        "positive_funding_candidate": classification.positive_funding_candidate,
        "negative_funding_status": classification.negative_funding_status,
        "current_funding_rate": _decimal_str(funding_snapshot.current_funding_rate),
        "next_funding_time": (
            str(funding_snapshot.next_funding_time)
            if funding_snapshot.next_funding_time is not None
            else None
        ),
        "funding_history_summary": history_summary,
        "futures_min_notional": _decimal_str(effective_rules.futures_min_notional),
        "spot_min_notional": _decimal_str(effective_rules.spot_min_notional),
        "effective_min_notional": _decimal_str(effective_rules.effective_min_notional),
        "futures_step_size": _decimal_str(effective_rules.futures_step_size),
        "spot_step_size": _decimal_str(effective_rules.spot_step_size),
        "data_timestamp": str(data_timestamp),
        "source_files": source_files,
        "exclusion_reason": classification.exclusion_reason,
        "funding_signal_status": funding_snapshot.funding_signal_status,
    }


def discover_from_samples(sample_dir: Path) -> dict[str, Any]:
    """Build candidate classification from saved public samples."""
    fapi_info = load_json_file(sample_dir / "fapi_exchange_info.json")
    spot_info = load_json_file(sample_dir / "spot_exchange_info.json")
    premium_index = load_json_file(sample_dir / "fapi_premium_index.json")
    if not isinstance(premium_index, list):
        premium_index = [premium_index]

    sample_index_path = sample_dir / "sample-index.json"
    if sample_index_path.exists():
        sample_index = load_json_file(sample_index_path)
        data_timestamp = int(sample_index.get("data_timestamp", "0"))
    else:
        data_timestamp = 1700000000000

    premium_by_symbol = _index_premium(premium_index)
    joined = join_futures_spot(fapi_info, spot_info)

    source_files = [
        "fapi_exchange_info.json",
        "spot_exchange_info.json",
        "fapi_premium_index.json",
    ]

    rows: list[dict[str, Any]] = []
    for sym_info in joined:
        classification = classify_symbol(sym_info)
        premium_entry = premium_by_symbol.get(sym_info.symbol)
        funding_history = _load_funding_history(sample_dir, sym_info.symbol)

        if premium_entry:
            funding_snapshot = normalize_premium_index_entry(premium_entry, data_timestamp)
        else:
            funding_snapshot = FundingSnapshot(
                current_funding_rate=None,
                next_funding_time=None,
                funding_history_summary={},
                funding_signal_status="STALE_OR_PREVIOUS_PERIOD",
            )

        effective_rules = compute_effective_rules(
            sym_info.futures_filters,
            sym_info.spot_filters,
        )

        row_sources = list(source_files)
        hist_file = f"fapi_funding_rate_{sym_info.symbol}.json"
        if (sample_dir / hist_file).exists():
            row_sources.append(hist_file)

        rows.append(
            build_candidate_row(
                sym_info,
                classification,
                premium_entry,
                funding_history,
                effective_rules,
                funding_snapshot,
                data_timestamp,
                row_sources,
            )
        )

    return {
        "funding_field_semantics": get_funding_field_semantics(),
        "data_timestamp": str(data_timestamp),
        "candidates": rows,
    }


def write_candidate_outputs(sample_dir: Path, output: dict[str, Any]) -> None:
    """Write candidate-classification.json and .csv."""
    json_path = sample_dir / "candidate-classification.json"
    json_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    csv_path = sample_dir / "candidate-classification.csv"
    rows = output["candidates"]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        if not rows:
            writer = csv.DictWriter(fh, fieldnames=CANDIDATE_FIELDS)
            writer.writeheader()
            return

        writer = csv.DictWriter(fh, fieldnames=CANDIDATE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            flat = dict(row)
            flat["funding_history_summary"] = json.dumps(row.get("funding_history_summary", {}))
            flat["source_files"] = json.dumps(row.get("source_files", []))
            flat["positive_funding_candidate"] = str(row.get("positive_funding_candidate"))
            writer.writerow(flat)


def run_discovery(
    sample_dir: Path | None = None,
    *,
    use_fixtures: bool = False,
) -> Path:
    """Run full discovery pipeline; returns output directory."""
    if use_fixtures:
        sample_dir = FIXTURES_DIR
    elif sample_dir is None:
        sample_dir = capture_samples()

    output = discover_from_samples(sample_dir)
    write_candidate_outputs(sample_dir, output)
    return sample_dir


def main() -> None:
    """CLI entry: capture live samples and emit candidate classification."""
    out_dir = run_discovery()
    print(f"Wrote candidate classification to {out_dir}")


if __name__ == "__main__":
    main()