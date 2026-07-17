#!/usr/bin/env python3
"""A1-A8 adversarial cases for the D3-v2 waypoint coverage model (T1 DoD).

Runs against the TEMPLATE repo's rewritten scripts/validate-stage.py, using
real commits from the template repo for synthetic stages and the real
bookticker stage (funding repo, in-memory status copy) for A7. Read-only:
no repo files are created or modified. Output is archived as
61-adversarial-d3v2.txt.

Usage: python3 61-adversarial-d3v2.driver.py <template_repo> <funding_repo>
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

TEMPLATE = Path(sys.argv[1]).resolve()
FUNDING = Path(sys.argv[2]).resolve()

spec = importlib.util.spec_from_file_location(
    "validate_stage", TEMPLATE / "scripts" / "validate-stage.py"
)
vs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vs)

SYNTH_DIR = TEMPLATE / "reports" / "agent-runs" / "_synthetic-a-case"


def shas(repo: Path, rev: str) -> str:
    return subprocess.run(
        ["git", "rev-parse", rev], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def blob_sha256(repo: Path, path: str) -> str:
    blob = subprocess.run(
        ["git", "cat-file", "-p", f"HEAD:{path}"], cwd=repo,
        capture_output=True, check=True,
    ).stdout
    return hashlib.sha256(blob).hexdigest()


# Three linear commits from template history: base < W1 < head.
BASE = shas(TEMPLATE, "cdef1ee~~2")
W1 = shas(TEMPLATE, "cdef1ee~~1")
HEAD = shas(TEMPLATE, "cdef1ee~")
print(f"synthetic commits: base={BASE[:8]} W1={W1[:8]} head={HEAD[:8]}")


def fp(base: str, head: str, stage_dir: Path = SYNTH_DIR) -> str:
    return vs.compute_diff_fingerprint(TEMPLATE, stage_dir, base, head)


FULL_FP = fp(BASE, HEAD)
PREFIX_FP = fp(BASE, W1)


def synth_doc(**over) -> dict:
    doc = {
        "stage_id": "_synthetic-a-case",
        "status": "accepted",
        "base_sha": BASE,
        "head_sha": HEAD,
        "diff_fingerprint": FULL_FP,
        "tasks": [
            {"id": "t1", "base_sha": BASE, "head_sha": W1},
            {"id": "t2", "base_sha": W1, "head_sha": HEAD},
        ],
        "review_1": {"diff_fingerprint": "garbage:0000"},
        "review_2": {"diff_fingerprint": "garbage:1111"},
    }
    doc.update(over)
    return doc


def valid_exception(scope: str) -> dict:
    return {
        "assertion_id": "review_fingerprint_trails_status",
        "authorizer": "user",
        "applies_to_fingerprint": FULL_FP,
        "scope": scope,
        "reason": "adversarial case fixture",
        "at": "2026-07-17T16:00:00Z",
        "evidence_file": "AGENTS.md",
        "evidence_sha256": blob_sha256(TEMPLATE, "AGENTS.md"),
    }


def coverage(doc: dict, stage_dir: Path = SYNTH_DIR, root: Path = TEMPLATE):
    return vs.validate_task_coverage(root, stage_dir, doc)


RESULTS = []


def check(name: str, expect: str, ok: bool, detail: str):
    RESULTS.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}: expect {expect} :: {detail}")


# A1: no vouch at all -> uncovered segment fail
errs, applied = coverage(synth_doc())
check("A1", "uncovered-segment error, nothing applied",
      any("uncovered segment" in e for e in errs) and not applied, f"errors={errs}")

# A2: complete-looking nested task own-review (even with a PERFECT fingerprint)
# must NOT vouch — the own-review coverage path is deleted.
doc = synth_doc()
doc["tasks"][0]["review_1"] = {
    "reviewer": "kimi", "provider": "moonshot_kimi", "model": "kimi-code",
    "verdict": "ACCEPT", "json_schema_valid": True, "diff_fingerprint": FULL_FP,
}
doc["tasks"][1]["review_1"] = copy.deepcopy(doc["tasks"][0]["review_1"])
errs, applied = coverage(doc)
check("A2", "nested own-review vouches nothing -> uncovered-segment fail",
      any("uncovered segment" in e for e in errs) and not applied, f"errors={errs}")

# A3: waypoint endpoints != base/head -> fail
errs, _ = coverage(synth_doc(coverage_waypoints=[W1, HEAD]))
check("A3a", "first waypoint != base -> fail",
      any("coverage_waypoints[0]" in e for e in errs), f"errors={errs}")
errs, _ = coverage(synth_doc(coverage_waypoints=[BASE, W1]))
check("A3b", "last waypoint != head -> fail",
      any("coverage_waypoints[-1]" in e for e in errs), f"errors={errs}")

# A4: malformed waypoints -> fail
errs, _ = coverage(synth_doc(coverage_waypoints="notalist"))
check("A4a", "non-list waypoints -> fail", bool(errs), f"errors={errs}")
errs, _ = coverage(synth_doc(coverage_waypoints=[BASE]))
check("A4b", "single waypoint -> fail", bool(errs), f"errors={errs}")
errs, _ = coverage(synth_doc(coverage_waypoints=[BASE, BASE, HEAD]))
check("A4c", "duplicate waypoints -> fail",
      any("duplicate" in e for e in errs), f"errors={errs}")
errs, _ = coverage(synth_doc(coverage_waypoints=[BASE, "0" * 40, HEAD]))
check("A4d", "non-commit waypoint -> fail",
      any("coverage_waypoints[1]" in e for e in errs), f"errors={errs}")

# A5: single-task degenerate unchanged (no coverage errors even with garbage reviews)
doc = synth_doc()
doc["tasks"] = [{"id": "only", "base_sha": BASE, "head_sha": HEAD}]
errs, applied = coverage(doc)
check("A5", "single task -> ([], []) degenerate", errs == [] and applied == [],
      f"errors={errs}")

# A6: full-range review_2 match greens the whole range (default waypoints)
doc = synth_doc()
doc["review_2"] = {"diff_fingerprint": FULL_FP}
errs, applied = coverage(doc)
check("A6", "full-range review_2 -> no coverage errors", errs == [] and applied == [],
      f"errors={errs}")

# A7: bookticker REAL data + class-1 exception -> full record-level suite greens
# with the exception surfaced (stage_dir must be the real one for fingerprint
# path identity; status is modified in memory only).
bk_dir = FUNDING / "reports" / "agent-runs" / "2026-07-bookticker-open-columns-v1"
bk = json.loads((bk_dir / "status.json").read_text())
bk_exc = {
    "assertion_id": "review_fingerprint_trails_status",
    "authorizer": "user",
    "applies_to_fingerprint": bk["diff_fingerprint"],
    "scope": "review_1",
    "reason": "adversarial case A7 (simulates T3 record)",
    "at": "2026-07-17T16:00:00Z",
    "evidence_file": "reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md",
    "evidence_sha256": blob_sha256(
        FUNDING, "reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md"),
}
bk["authorized_exceptions"] = [bk_exc]
errs = []
errs += vs.validate_common(FUNDING, bk_dir, bk, "pre-accept")
errs += vs.validate_parallel_mode(FUNDING, bk_dir, bk, "pre-accept")
errs += vs.validate_required_files(bk_dir, bk, "pre-accept")
errs += vs.validate_tasks(FUNDING, bk_dir, bk, None)
acc_e, acc_a = vs.validate_acceptance(FUNDING, bk_dir, bk)
errs += acc_e
cov_e, cov_a = vs.validate_task_coverage(FUNDING, bk_dir, bk)
errs += cov_e
applied = vs._merge_applied(acc_a, cov_a)
check("A7", "bookticker real data + class-1 -> zero errors, exception surfaced",
      errs == [] and applied == [
          {"assertion_id": "review_fingerprint_trails_status", "scope": "review_1"}],
      f"errors={errs} applied={applied}")

# A8a: forged waypoints with no vouch -> every segment uncovered
doc = synth_doc(coverage_waypoints=[BASE, W1, HEAD])
errs, applied = coverage(doc)
check("A8a", "explicit waypoints, no vouch -> uncovered-segment fail",
      sum("uncovered segment" in e for e in errs) == 2 and not applied, f"errors={errs}")

# A8b: valid exception scoped review_1 but review_1 matches NOTHING ->
# exception vouches nothing, still fails closed (my review strengthening).
doc = synth_doc(coverage_waypoints=[BASE, W1, HEAD])
doc["authorized_exceptions"] = [valid_exception("review_1")]
errs, applied = coverage(doc)
check("A8b", "exception without matched prefix vouches NOTHING -> still fail",
      sum("uncovered segment" in e for e in errs) == 2 and not applied,
      f"errors={errs} applied={applied}")

# A8c: rule 3 positive — review_1 matches prefix base..W1, valid exception
# scope=review_1 vouches the trailing segment -> coverage green, applied surfaced.
doc = synth_doc(coverage_waypoints=[BASE, W1, HEAD])
doc["review_1"] = {"diff_fingerprint": PREFIX_FP}
doc["authorized_exceptions"] = [valid_exception("review_1")]
errs, applied = coverage(doc)
check("A8c", "prefix match + exception -> green, exception applied",
      errs == [] and applied == [
          {"assertion_id": "review_fingerprint_trails_status", "scope": "review_1"}],
      f"errors={errs} applied={applied}")

# A8d: task-scoped exception vouches only the segment ENDING at task.head
# (must be a declared waypoint).
doc = synth_doc(coverage_waypoints=[BASE, W1, HEAD])
doc["authorized_exceptions"] = [valid_exception("task:t1")]
errs, applied = coverage(doc)
check("A8d1", "task:t1 exception vouches segment 0 only -> segment 1 uncovered",
      errs == [f"uncovered segment {W1}..{HEAD}: needs a top-level review prefix "
               f"match or a class-1 authorized_exception"]
      and applied == [
          {"assertion_id": "review_fingerprint_trails_status", "scope": "task:t1"}],
      f"errors={errs} applied={applied}")
doc = synth_doc(coverage_waypoints=[BASE, W1, HEAD])
doc["tasks"][1]["head_sha"] = "f" * 40  # not a waypoint (not even a commit)
doc["authorized_exceptions"] = [valid_exception("task:t2")]
errs, _ = coverage(doc)
check("A8d2", "task.head not a waypoint -> recorded error",
      any("is not a coverage waypoint" in e for e in errs), f"errors={errs}")

print()
failed = [n for n, ok in RESULTS if not ok]
print(f"A-CASE SUMMARY: {len(RESULTS) - len(failed)}/{len(RESULTS)} passed"
      + (f"; FAILED: {failed}" if failed else " — all adversarial expectations hold"))
sys.exit(1 if failed else 0)
