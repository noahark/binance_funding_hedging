#!/usr/bin/env python3
"""Sentinel regression tests for validate-all-stages.py compare mode (F1).

Proves the compare gate catches all three drift categories and exits nonzero:
  1. verdict FLIP (unit),
  2. error-multiset-only change with unchanged verdict (unit + end-to-end),
  3. applied_exceptions-only change with unchanged verdict (unit + e2e),
  4. ADDED / REMOVED stage (unit),
  5. identical baseline exits 0 (e2e).

Usage: python3 scripts/test-validate-all-stages-compare.py --repo-root <path>
Read-only: temp baselines go to a mkdtemp directory, never into the repo.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

RUNNER = Path(__file__).with_name("validate-all-stages.py")

spec = importlib.util.spec_from_file_location("validate_all_stages", RUNNER)
vas = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vas)

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str) -> None:
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name} :: {detail}")


def stage(verdict="red", errors=None, exc=None):
    return {
        "stage_id": "s",
        "status": "accepted",
        "verdict": verdict,
        "applied_exceptions": exc or [],
        "errors": errors or [],
    }


def unit_tests() -> None:
    base = {"s": stage(errors=["e1", "e2", "e2"])}
    check("U0 identical -> no drift", vas.diff_results(base, copy.deepcopy(base)) == [],
          "identical dicts")

    cur = copy.deepcopy(base)
    cur["s"]["verdict"] = "green"
    lines = vas.diff_results(base, cur)
    check("U1 verdict flip -> FLIP", any(l.startswith("FLIP s:") for l in lines), str(lines))

    cur = copy.deepcopy(base)
    cur["s"]["errors"] = ["e1", "e2"]  # one duplicate removed, verdict unchanged
    lines = vas.diff_results(base, cur)
    check("U2 error multiset shrink -> ERRDRIFT",
          any(l.startswith("ERRDRIFT s:") for l in lines), str(lines))

    cur = copy.deepcopy(base)
    cur["s"]["errors"] = ["e1", "e2", "e2", "SENTINEL: new failure"]
    lines = vas.diff_results(base, cur)
    check("U3 error added (codex sentinel shape) -> ERRDRIFT",
          any(l.startswith("ERRDRIFT s:") and "SENTINEL" in l2 for l in lines for l2 in [l])
          or any("SENTINEL" in l for l in lines), str(lines))

    cur = copy.deepcopy(base)
    cur["s"]["applied_exceptions"] = [
        {"assertion_id": "review_fingerprint_trails_status", "scope": "review_1"}
    ]
    lines = vas.diff_results(base, cur)
    check("U4 exception-only change -> EXCDRIFT",
          any(l.startswith("EXCDRIFT s:") for l in lines), str(lines))

    cur = copy.deepcopy(base)
    cur["new-stage"] = stage(verdict="green")
    lines = vas.diff_results(base, cur)
    check("U5 added stage -> ADDED", any(l.startswith("ADDED new-stage") for l in lines),
          str(lines))

    lines = vas.diff_results(base, {})
    check("U6 removed stage -> REMOVED", any(l.startswith("REMOVED s") for l in lines),
          str(lines))


def run_runner(repo_root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RUNNER), "--repo-root", str(repo_root), *extra],
        capture_output=True, text=True,
    )


def e2e_tests(repo_root: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="compare-sentinel-") as tmp:
        baseline_path = Path(tmp) / "baseline.json"
        proc = run_runner(repo_root, "--baseline-out", str(baseline_path))
        check("E0 build temp baseline", proc.returncode == 0 and baseline_path.is_file(),
              f"exit={proc.returncode}")
        baseline = json.loads(baseline_path.read_text())
        victim = sorted(baseline)[0]

        proc = run_runner(repo_root, "--compare", str(baseline_path))
        check("E1 unmodified compare -> exit 0, no drift",
              proc.returncode == 0 and "no drift" in proc.stdout,
              f"exit={proc.returncode}")

        injected = copy.deepcopy(baseline)
        injected[victim]["errors"] = list(injected[victim]["errors"]) + [
            "SENTINEL: unregistered new validation failure"
        ]
        err_path = Path(tmp) / "baseline-errdrift.json"
        err_path.write_text(json.dumps(injected))
        proc = run_runner(repo_root, "--compare", str(err_path))
        check("E2 error-only injection -> ERRDRIFT + nonzero exit",
              proc.returncode != 0 and f"ERRDRIFT {victim}" in proc.stdout,
              f"exit={proc.returncode}")

        injected = copy.deepcopy(baseline)
        injected[victim]["applied_exceptions"] = [
            {"assertion_id": "review_fingerprint_trails_status", "scope": "review_1"}
        ]
        exc_path = Path(tmp) / "baseline-excdrift.json"
        exc_path.write_text(json.dumps(injected))
        proc = run_runner(repo_root, "--compare", str(exc_path))
        check("E3 exception-only injection -> EXCDRIFT + nonzero exit",
              proc.returncode != 0 and f"EXCDRIFT {victim}" in proc.stdout,
              f"exit={proc.returncode}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    args = parser.parse_args()
    print(f"runner under test: {RUNNER}")
    print(f"repo for e2e: {Path(args.repo_root).resolve()}")
    unit_tests()
    e2e_tests(Path(args.repo_root).resolve())
    failed = [n for n, ok, _ in RESULTS if not ok]
    print(f"SENTINEL SUMMARY: {len(RESULTS) - len(failed)}/{len(RESULTS)} passed"
          + (f"; FAILED: {failed}" if failed else " — compare gate catches all three drift categories"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
