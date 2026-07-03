"""Shared pytest fixtures.

All tests run offline against the frozen raw samples captured in the contract
stage. No network access is permitted in the test suite.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = (
    REPO_ROOT
    / "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw"
)
SCHEMA_PATH = REPO_ROOT / "schemas/api/public-market/snapshot.schema.json"
FROZEN_SAMPLE = (
    REPO_ROOT
    / "reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/public-market-snapshot.json"
)
_FUNDING_RATE_RE = re.compile(r"fapi-v1-fundingRate-(.+)-limit\d+\.json$")


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


@pytest.fixture(scope="session")
def raw_inputs() -> dict:
    def load(name: str):
        return json.loads((RAW_DIR / name).read_text())

    funding = {}
    for path in sorted(RAW_DIR.glob("fapi-v1-fundingRate-*-limit*.json")):
        match = _FUNDING_RATE_RE.search(path.name)
        if match:
            funding[match.group(1)] = json.loads(path.read_text())

    return {
        "futures": load("fapi-v1-exchangeInfo.json"),
        "premium": load("fapi-v1-premiumIndex.json"),
        "spot": load("api-v3-exchangeInfo-curated-BTCETHXVG.json"),
        "funding": funding,
    }


@pytest.fixture(scope="session")
def frozen_normalized() -> dict:
    return json.loads(FROZEN_SAMPLE.read_text())
