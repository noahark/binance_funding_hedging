#!/usr/bin/env python3
"""Record-level pre-accept validation over every historical stage in a repo.

Fixture gate (harness-design: any validator change must run the full fixture
before review). Per stage this runs the record-level half of `--phase
pre-accept` and skips context-of-the-moment assertions (clean worktree,
current branch / recheck-on-main): status vocabulary, fingerprint recompute,
required files, task shape, acceptance (reviews/tests/exceptions/identity),
and task coverage. `_template/` placeholders are excluded.

Usage:
  python3 scripts/validate-all-stages.py --repo-root <path> [--baseline-out F]
  python3 scripts/validate-all-stages.py --repo-root <path> --compare F

Verdicts per stage: green | green_with_exception | red (errors listed).
Exit code is 0 on success; --compare exits 1 when any stage verdict differs
from the baseline (the caller judges diffs against the registered migration
table). Read-only: never mutates the target repo.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_stage", Path(__file__).with_name("validate-stage.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_one(vs, root: Path, stage_dir: Path) -> dict:
    status_doc = vs.load_status(stage_dir)
    phase = "pre-accept"
    errors: list[str] = []
    applied: list[dict[str, str]] = []
    errors.extend(vs.validate_common(root, stage_dir, status_doc, phase))
    errors.extend(vs.validate_parallel_mode(root, stage_dir, status_doc, phase))
    errors.extend(vs.validate_required_files(stage_dir, status_doc, phase))
    errors.extend(vs.validate_tasks(root, stage_dir, status_doc, None))
    acc_errors, acc_applied = vs.validate_acceptance(root, stage_dir, status_doc)
    errors.extend(acc_errors)
    cov_errors, cov_applied = vs.validate_task_coverage(root, stage_dir, status_doc)
    errors.extend(cov_errors)
    applied = vs._merge_applied(acc_applied, cov_applied)
    if errors:
        verdict = "red"
    elif applied:
        verdict = "green_with_exception"
    else:
        verdict = "green"
    return {
        "stage_id": status_doc.get("stage_id", stage_dir.name),
        "status": status_doc.get("status"),
        "verdict": verdict,
        "applied_exceptions": applied,
        "errors": errors,
    }


def iter_stage_dirs(root: Path) -> list[Path]:
    runs = root / "reports" / "agent-runs"
    return sorted(
        d for d in runs.iterdir()
        if d.is_dir() and d.name != "_template" and (d / "status.json").is_file()
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, help="target repository root")
    parser.add_argument("--baseline-out", help="write results JSON to this path")
    parser.add_argument("--compare", help="baseline JSON to diff against")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    if not (root / "reports" / "agent-runs").is_dir():
        print(f"not a harness repo (no reports/agent-runs): {root}", file=sys.stderr)
        return 2

    vs = _load_validator()
    results = {}
    for stage_dir in iter_stage_dirs(root):
        try:
            record = validate_one(vs, root, stage_dir)
        except Exception as exc:  # a broken stage record must not kill the sweep
            record = {
                "stage_id": stage_dir.name,
                "status": None,
                "verdict": "red",
                "applied_exceptions": [],
                "errors": [f"fixture runner error: {exc}"],
            }
        results[record["stage_id"]] = record

    counts = {"green": 0, "green_with_exception": 0, "red": 0}
    for stage_id, record in sorted(results.items()):
        counts[record["verdict"]] += 1
        line = f"{record['verdict']:20s} {stage_id}"
        if record["applied_exceptions"]:
            tags = ", ".join(
                f"{e['assertion_id']}@{e['scope']}" for e in record["applied_exceptions"]
            )
            line += f"  ({tags})"
        print(line)
        for err in record["errors"]:
            print(f"{'':20s} - {err}")
    print(
        f"summary: {counts['green']} green, "
        f"{counts['green_with_exception']} green_with_exception, {counts['red']} red "
        f"({len(results)} stages, repo={root.name})"
    )

    if args.baseline_out:
        out = Path(args.baseline_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
        print(f"baseline written: {out}")

    if args.compare:
        baseline = json.loads(Path(args.compare).read_text())
        drift = False
        for stage_id, record in sorted(results.items()):
            old = baseline.get(stage_id)
            old_verdict = old.get("verdict") if old else "<absent>"
            if old_verdict != record["verdict"]:
                drift = True
                print(f"FLIP {stage_id}: {old_verdict} -> {record['verdict']}")
        for stage_id in sorted(set(baseline) - set(results)):
            drift = True
            print(f"REMOVED {stage_id}: was {baseline[stage_id]['verdict']}")
        if drift:
            print("compare: DRIFT vs baseline (judge against migration table)")
            return 1
        print("compare: no drift vs baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
