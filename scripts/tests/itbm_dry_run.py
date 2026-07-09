#!/usr/bin/env python3
"""Dry-run fixture for the independent task-branch mode (DRAFT-2 rev c2 §17).

Builds real temporary git repos + worktrees and drives record-checkpoint /
prepare-review-2 end to end, asserting the positive path and the fail-closed
gates. No model calls; self-contained. Run: python3 scripts/tests/itbm_dry_run.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
STAGE = "toy-stage"
# NOTE: task branches live under a separate `task/` namespace, NOT nested under
# the integration ref. Git cannot hold both `stage/toy` and `stage/toy/backend`
# (a ref file blocks a same-named ref directory).
BR_BE = "task/toy/backend-glm"
BR_FE = "task/toy/frontend-kimi"
INTEG = "stage/toy"


def git(args, cwd, check=True):
    r = subprocess.run(["git", *args], cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} @ {cwd}:\n{r.stdout}")
    return r


def run_script(name, args, cwd):
    return subprocess.run([sys.executable, str(SCRIPTS / name), *args], cwd=str(cwd),
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def setup(root: Path, stage_test_command="test -f backend/app.py && test -f frontend/ui.js", ship_scripts=False):
    """Create repo, base commit with frozen status.json, integration + task branches + worktrees."""
    repo = root / "repo"
    repo.mkdir()
    git(["init", "-q", "-b", "main"], repo)
    git(["config", "user.email", "t@t"], repo)
    git(["config", "user.name", "t"], repo)
    write(repo / "backend" / "app.py", "V = 1\n")
    write(repo / "frontend" / "ui.js", "const v = 1;\n")
    git(["add", "-A"], repo)
    git(["commit", "-qm", "init"], repo)
    git(["checkout", "-qb", INTEG], repo)
    frozen = {
        "stage_id": STAGE,
        "workflow": "stage-delivery",
        "independent_task_branch_mode": {"enabled": True},
        "status": "implementing",
        "stage_test_command": stage_test_command,
        "tasks": [
            {"id": "backend", "branch": BR_BE, "owner": "claude_glm",
             "allowed_scope": {"product_paths": ["backend"], "test_command": "test -f backend/app.py", "allow_harness_change": False}},
            {"id": "frontend", "branch": BR_FE, "owner": "kimi",
             "allowed_scope": {"product_paths": ["frontend"], "test_command": "test -f frontend/ui.js", "allow_harness_change": False}},
        ],
    }
    write(repo / "reports" / "agent-runs" / STAGE / "status.json", json.dumps(frozen, indent=2) + "\n")
    write(repo / "reports" / "agent-runs" / STAGE / "70-handoff.md", "# handoff\n")
    if ship_scripts:
        (repo / "scripts").mkdir(exist_ok=True)
        for name in ("validate-stage.py", "_itbm.py"):
            shutil.copy(SCRIPTS / name, repo / "scripts" / name)
    git(["add", "-A"], repo)
    git(["commit", "-qm", "frozen status"], repo)
    base = git(["rev-parse", "HEAD"], repo).stdout.strip()
    git(["branch", BR_BE, base], repo)
    git(["branch", BR_FE, base], repo)
    wt_be = root / "wt-backend"
    wt_fe = root / "wt-frontend"
    git(["worktree", "add", "-q", str(wt_be), BR_BE], repo)
    git(["worktree", "add", "-q", str(wt_fe), BR_FE], repo)
    return repo, base, wt_be, wt_fe


def implement(wt: Path, task_id: str, product_edit):
    """Simulate an implementer: mutate product + write impl report (uncommitted)."""
    product_edit(wt)
    write(wt / "reports" / "agent-runs" / STAGE / "evidence" / task_id / "20-implementation.md", f"# impl {task_id}\n")


def checkpoint(repo, base, task_id, branch, wt):
    return run_script("record-checkpoint", [STAGE, "--task", task_id, "--branch", branch,
                                            "--task-worktree", str(wt), "--base-sha", base], cwd=repo)


def make_review1(wt: Path, task_id: str, verdict="ACCEPT", fp=None):
    ev = wt / "reports" / "agent-runs" / STAGE / "evidence" / task_id
    cp = json.loads((ev / "checkpoint.json").read_text())
    fp = fp if fp is not None else cp["task_diff_fingerprint"]
    write(ev / "30-review-1.md", f"# review-1 {task_id}: {verdict}\n")
    write(ev / "review-1.verdict.json", json.dumps({"verdict": verdict, "diff_fingerprint": fp}) + "\n")
    write(ev / "review-1.attempts.json", json.dumps({"invalid_json_attempts": {"kimi": 0, "claude_glm": 0}, "recorded_by": "human"}) + "\n")


def pr2(repo, base, wt_be, wt_fe):
    return run_script("prepare-review-2", [STAGE, "--base-sha", base, "--integration-branch", INTEG,
                                           "--backend-worktree", str(wt_be), "--frontend-worktree", str(wt_fe),
                                           "--human-decision", "proceed_to_review_2", "--rationale", "test", "--no-validator"], cwd=repo)


RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail and not cond else ""))


def scenario(fn):
    root = Path(tempfile.mkdtemp(prefix="itbm-"))
    try:
        fn(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- positive happy path: ①②③④ ----
def test_happy(root):
    print("happy path (①②③④):")
    repo, base, wt_be, wt_fe = setup(root)
    implement(wt_be, "backend", lambda w: write(w / "backend" / "app.py", "V = 2\n"))
    implement(wt_fe, "frontend", lambda w: write(w / "frontend" / "ui.js", "const v = 2;\n"))
    r1 = checkpoint(repo, base, "backend", BR_BE, wt_be)
    r2 = checkpoint(repo, base, "frontend", BR_FE, wt_fe)
    check("② record-checkpoint backend OK", r1.returncode == 0, r1.stdout)
    check("② record-checkpoint frontend OK", r2.returncode == 0, r2.stdout)
    make_review1(wt_be, "backend")
    make_review1(wt_fe, "frontend")
    r3 = pr2(repo, base, wt_be, wt_fe)
    check("①③ prepare-review-2 OK (metadata not colliding, rebind holds)", r3.returncode == 0, r3.stdout)
    status = json.loads((repo / "reports" / "agent-runs" / STAGE / "status.json").read_text())
    check("④ status review_2 + integration fingerprint + human_decision",
          status.get("status") == "review_2" and bool(status.get("integration_diff_fingerprint")) and bool(status.get("human_decision")),
          json.dumps(status.get("status")))
    # ④ independent recompute of integration fingerprint
    sys.path.insert(0, str(SCRIPTS))
    import _itbm
    head = git(["rev-parse", status["head_sha"]], repo).stdout.strip()
    recomputed = _itbm.canonical_fingerprint(repo, base, head, STAGE)
    check("④ integration fingerprint recomputes byte-identical", recomputed == status["integration_diff_fingerprint"],
          f"{recomputed} vs {status['integration_diff_fingerprint']}")


# ---- ⑤ review-1 non-ACCEPT blocks ----
def test_non_accept(root):
    print("⑤ review-1 non-ACCEPT blocks:")
    repo, base, wt_be, wt_fe = setup(root)
    implement(wt_be, "backend", lambda w: write(w / "backend" / "app.py", "V = 2\n"))
    implement(wt_fe, "frontend", lambda w: write(w / "frontend" / "ui.js", "const v = 2;\n"))
    checkpoint(repo, base, "backend", BR_BE, wt_be)
    checkpoint(repo, base, "frontend", BR_FE, wt_fe)
    make_review1(wt_be, "backend", verdict="REWORK")
    make_review1(wt_fe, "frontend")
    r = pr2(repo, base, wt_be, wt_fe)
    check("⑤ prepare-review-2 BLOCKED on non-ACCEPT", r.returncode == 1 and "ACCEPT" in r.stdout)


# ---- ⑥ product intersection non-empty ----
def test_intersection(root):
    print("⑥ product intersection non-empty blocks:")
    repo, base, wt_be, wt_fe = setup(root)
    # both edit backend/app.py (frontend reaching into backend product path)
    implement(wt_be, "backend", lambda w: write(w / "backend" / "app.py", "V = 2\n"))
    # frontend also writes a backend file -> out of its scope; record-checkpoint should block first,
    # so to reach pr2 intersection, give frontend a scope that also allows backend via a shared file.
    write(wt_fe / "frontend" / "ui.js", "const v = 2;\n")
    write(wt_fe / "shared.txt", "x\n")  # out of frontend scope
    implement(wt_fe, "frontend", lambda w: None)
    checkpoint(repo, base, "backend", BR_BE, wt_be)
    rf = checkpoint(repo, base, "frontend", BR_FE, wt_fe)
    check("⑥ record-checkpoint blocks out-of-scope file (shared.txt)", rf.returncode == 1 and "out-of-scope" in rf.stdout)


# ---- ⑧ anti-stale-tip ----
def test_stale_tip(root):
    print("⑧ anti-stale-tip blocks post-review-1 amend:")
    repo, base, wt_be, wt_fe = setup(root)
    implement(wt_be, "backend", lambda w: write(w / "backend" / "app.py", "V = 2\n"))
    implement(wt_fe, "frontend", lambda w: write(w / "frontend" / "ui.js", "const v = 2;\n"))
    checkpoint(repo, base, "backend", BR_BE, wt_be)
    checkpoint(repo, base, "frontend", BR_FE, wt_fe)
    make_review1(wt_be, "backend")
    make_review1(wt_fe, "frontend")
    # sneak an extra commit onto backend AFTER review-1
    write(wt_be / "backend" / "sneak.py", "BAD = 1\n")
    git(["add", "-A"], wt_be)
    git(["commit", "-qm", "sneak"], wt_be)
    r = pr2(repo, base, wt_be, wt_fe)
    check("⑧ prepare-review-2 BLOCKED on stale tip", r.returncode == 1 and "anti-stale-tip" in r.stdout)


# ---- ⑦ rebind mismatch (tamper product_rebind_hash) ----
def test_rebind_mismatch(root):
    print("⑦ rebind mismatch blocks:")
    repo, base, wt_be, wt_fe = setup(root)
    implement(wt_be, "backend", lambda w: write(w / "backend" / "app.py", "V = 2\n"))
    implement(wt_fe, "frontend", lambda w: write(w / "frontend" / "ui.js", "const v = 2;\n"))
    checkpoint(repo, base, "backend", BR_BE, wt_be)
    checkpoint(repo, base, "frontend", BR_FE, wt_fe)
    make_review1(wt_be, "backend")
    make_review1(wt_fe, "frontend")
    cpf = wt_be / "reports" / "agent-runs" / STAGE / "evidence" / "backend" / "checkpoint.json"
    cp = json.loads(cpf.read_text())
    cp["product_rebind_hash"] = "deadbeef"
    cpf.write_text(json.dumps(cp))
    r = pr2(repo, base, wt_be, wt_fe)
    check("⑦ prepare-review-2 BLOCKED on rebind mismatch", r.returncode == 1 and "rebind mismatch" in r.stdout)


# ---- ⑪ immutable-script guard ----
def test_immutable_guard(root):
    print("⑪ immutable-script guard blocks:")
    repo, base, wt_be, wt_fe = setup(root)
    write(wt_be / "scripts" / "evil.py", "print('x')\n")  # touches protected scripts/
    implement(wt_be, "backend", lambda w: write(w / "backend" / "app.py", "V = 2\n"))
    r = checkpoint(repo, base, "backend", BR_BE, wt_be)
    check("⑪ record-checkpoint BLOCKED on protected-path change", r.returncode == 1 and "immutable-guard" in r.stdout)


# ---- ⑫/⑮ atomic rollback on full-test failure ----
def test_rollback(root):
    print("⑫/⑮ atomic rollback on full-test failure:")
    repo, base, wt_be, wt_fe = setup(root, stage_test_command="test -f backend/DOES_NOT_EXIST")
    implement(wt_be, "backend", lambda w: write(w / "backend" / "app.py", "V = 2\n"))
    implement(wt_fe, "frontend", lambda w: write(w / "frontend" / "ui.js", "const v = 2;\n"))
    checkpoint(repo, base, "backend", BR_BE, wt_be)
    checkpoint(repo, base, "frontend", BR_FE, wt_fe)
    make_review1(wt_be, "backend")
    make_review1(wt_fe, "frontend")
    t0 = git(["rev-parse", INTEG], repo).stdout.strip()
    r = pr2(repo, base, wt_be, wt_fe)
    tip = git(["rev-parse", INTEG], repo).stdout.strip()
    check("⑫/⑮ prepare-review-2 BLOCKED + rolled back to T0 (no residue)",
          r.returncode == 1 and tip == t0, f"rc={r.returncode} tip==t0={tip==t0}")


# ---- ⑯ single-owner smoke ----
def test_single_owner(root):
    print("⑯ single-owner smoke:")
    repo, base, wt_be, wt_fe = setup(root)
    # single owner works on the integration branch directly
    write(repo / "backend" / "app.py", "V = 9\n")
    r = run_script("record-checkpoint", [STAGE, "--single-owner", "--branch", INTEG,
                                         "--task-worktree", str(repo), "--base-sha", base], cwd=repo)
    check("⑯ single-owner record-checkpoint OK", r.returncode == 0, r.stdout)
    # F3: single-owner recorder now writes top-level status.json review metadata
    status = json.loads((repo / "reports" / "agent-runs" / STAGE / "status.json").read_text())
    check("⑯ single-owner writes top-level status.json base/head/fingerprint/changed_files",
          bool(status.get("base_sha")) and bool(status.get("head_sha"))
          and bool(status.get("diff_fingerprint"))
          and "backend/app.py" in status.get("changed_files", []),
          json.dumps({k: status.get(k) for k in ("base_sha", "head_sha", "diff_fingerprint", "changed_files")}))


# ---- ⑰ single-owner --dry-run guard: --dry-run rejected without --single-owner ----
def test_dry_run_requires_single_owner(root):
    print("⑰ single-owner --dry-run guard rejects --dry-run without --single-owner:")
    repo, base, wt_be, wt_fe = setup(root)
    write(repo / "backend" / "app.py", "V = 9\n")
    head_before = git(["rev-parse", "HEAD"], repo).stdout.strip()
    status_before = git(["status", "--short"], repo).stdout
    # --dry-run without --single-owner (and without --task) must be blocked by the
    # guard before the double-owner path can mutate the repository.
    r = run_script("record-checkpoint", [STAGE, "--dry-run", "--branch", INTEG,
                                         "--task-worktree", str(repo), "--base-sha", base], cwd=repo)
    head_after = git(["rev-parse", "HEAD"], repo).stdout.strip()
    status_after = git(["status", "--short"], repo).stdout
    check("⑰ --dry-run without --single-owner is BLOCKED with a clear ItbmError",
          r.returncode == 1 and "single-owner" in r.stdout and "RECORD-CHECKPOINT BLOCKED" in r.stdout,
          r.stdout)
    check("⑰ rejected --dry-run performs no repository mutation",
          head_after == head_before and status_after == status_before,
          f"head_before={head_before[:12]} head_after={head_after[:12]} "
          f"status_unchanged={status_after == status_before}")


# ---- ⑯ single-owner --dry-run does not mutate the repository ----
def test_single_owner_dry_run(root):
    print("⑯ single-owner --dry-run performs no repository mutation:")
    repo, base, wt_be, wt_fe = setup(root)
    write(repo / "backend" / "app.py", "V = 9\n")
    head_before = git(["rev-parse", "HEAD"], repo).stdout.strip()
    status_before = git(["status", "--short"], repo).stdout
    r = run_script("record-checkpoint", [STAGE, "--single-owner", "--dry-run", "--branch", INTEG,
                                         "--task-worktree", str(repo), "--base-sha", base], cwd=repo)
    head_after = git(["rev-parse", "HEAD"], repo).stdout.strip()
    status_after = git(["status", "--short"], repo).stdout
    status = json.loads((repo / "reports" / "agent-runs" / STAGE / "status.json").read_text())
    check("⑯ single-owner --dry-run OK and leaves HEAD unchanged",
          r.returncode == 0 and head_after == head_before,
          f"rc={r.returncode} head_before={head_before[:12]} head_after={head_after[:12]}")
    check("⑯ single-owner --dry-run leaves git status --short unchanged",
          status_after == status_before,
          f"before={status_before!r} after={status_after!r}")
    check("⑯ single-owner --dry-run leaves status.json metadata unwritten",
          status.get("base_sha") is None and status.get("head_sha") is None,
          r.stdout)


# ---- validator: --phase pre-review passes on the mode's task-local layout ----
def test_validator(root):
    print("validator pre-review (task-local mapping):")
    repo, base, wt_be, wt_fe = setup(root, ship_scripts=True)
    implement(wt_be, "backend", lambda w: write(w / "backend" / "app.py", "V = 2\n"))
    implement(wt_fe, "frontend", lambda w: write(w / "frontend" / "ui.js", "const v = 2;\n"))
    checkpoint(repo, base, "backend", BR_BE, wt_be)
    checkpoint(repo, base, "frontend", BR_FE, wt_fe)
    make_review1(wt_be, "backend")
    make_review1(wt_fe, "frontend")
    pr2(repo, base, wt_be, wt_fe)
    v = subprocess.run([sys.executable, "scripts/validate-stage.py", STAGE, "--phase", "pre-review"],
                       cwd=str(repo), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    check("validate-stage --phase pre-review PASSES on task-local evidence", v.returncode == 0 and "PASSED" in v.stdout, v.stdout)


def main():
    for fn in (test_happy, test_non_accept, test_intersection, test_stale_tip,
               test_rebind_mismatch, test_immutable_guard, test_rollback, test_single_owner,
               test_single_owner_dry_run, test_dry_run_requires_single_owner, test_validator):
        scenario(fn)
    passed = sum(1 for _, ok in RESULTS if ok)
    total = len(RESULTS)
    print(f"\n{passed}/{total} assertions passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
