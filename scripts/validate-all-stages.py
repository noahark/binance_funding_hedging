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
from collections import Counter
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
    errors.extend(
        vs.validate_review_artifact_protocol(
            root, stage_dir, status_doc, phase, vs.active_stage_id(root)
        )
    )
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


def _exception_keys(applied) -> list[str]:
    """Normalize applied_exceptions to comparable 'assertion_id@scope' keys."""
    return sorted(
        f"{entry.get('assertion_id')}@{entry.get('scope')}" for entry in applied or []
    )


def diff_results(baseline: dict, current: dict) -> list[str]:
    """Three-way fixture diff per stage: verdict + complete error multiset +
    normalized applied_exceptions. Returns drift lines (empty == no drift).

    Every difference is printed with a category tag (FLIP / ERRDRIFT /
    EXCDRIFT / ADDED / REMOVED); whether a drift line is registered in the
    migration table is judged by the caller, never silently absorbed here.
    """
    drift: list[str] = []
    for stage_id in sorted(set(baseline) | set(current)):
        old = baseline.get(stage_id)
        new = current.get(stage_id)
        if old is None:
            drift.append(f"ADDED {stage_id}: verdict={new.get('verdict')}")
            continue
        if new is None:
            drift.append(f"REMOVED {stage_id}: was verdict={old.get('verdict')}")
            continue
        if old.get("verdict") != new.get("verdict"):
            drift.append(f"FLIP {stage_id}: {old.get('verdict')} -> {new.get('verdict')}")
        old_errors = Counter(old.get("errors") or [])
        new_errors = Counter(new.get("errors") or [])
        if old_errors != new_errors:
            drift.append(
                f"ERRDRIFT {stage_id}: error multiset changed "
                f"({sum(old_errors.values())} -> {sum(new_errors.values())})"
            )
            for err, count in sorted((old_errors - new_errors).items()):
                drift.append(f"  -{'' if count == 1 else f' x{count}'} {err}")
            for err, count in sorted((new_errors - old_errors).items()):
                drift.append(f"  +{'' if count == 1 else f' x{count}'} {err}")
        old_exc = _exception_keys(old.get("applied_exceptions"))
        new_exc = _exception_keys(new.get("applied_exceptions"))
        if old_exc != new_exc:
            drift.append(f"EXCDRIFT {stage_id}: {old_exc} -> {new_exc}")
    return drift


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
        drift = diff_results(baseline, results)
        for line in drift:
            print(line)
        if drift:
            print("compare: DRIFT vs baseline (judge against migration table)")
            return 1
        print("compare: no drift vs baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
