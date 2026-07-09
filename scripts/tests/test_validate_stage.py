#!/usr/bin/env python3
"""Tests for scripts/validate-stage.py friction fixes (F1, F4) and hardening
follow-ups (D1, D3, D4, D5).

F1: an unselected review_2.primary_provider preference must not be treated as
    the selected reviewer identity for designer-overlap / implementer-overlap
    checks, while a selected reviewer must still enforce isolation.
F4: --evidence-out writes the validation output only when validation passes,
    so it can replace `... | tee <repo-file>` without dirtying the worktree
    before the clean-worktree check.
D1: --evidence-out write failures surface a clean Harness error instead of an
    uncaught Python traceback.
D3: compute_diff_fingerprint pins -c diff.renames=true, matching _itbm.py.
D4: the status.json template exposes review_1.actual_model.
D5: the stage-delivery workflow encodes a mechanical fix return gate.

validate-stage.py has a hyphen in its filename, so it is loaded via importlib.
Run: python3 scripts/tests/test_validate_stage.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent


def load_validate_stage():
    spec = importlib.util.spec_from_file_location("validate_stage", SCRIPTS / "validate-stage.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VS = load_validate_stage()

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail and not cond else ""))


def make_status(**overrides):
    status = {
        "designer": None,
        "direction_synthesizer": None,
        "breakdown_author": None,
        "implementer": None,
        "implementers": [],
        "fix_authors": [],
        "review_1": {},
        "review_2": {},
        "tasks": [],
    }
    status.update(overrides)
    return status


# ---- F1: unselected primary_provider does not trip designer-overlap ----
def test_unselected_primary_provider_no_designer_overlap():
    print("F1: unselected review_2.primary_provider does not trip designer-overlap:")
    root = Path(tempfile.mkdtemp(prefix="vs-f1a-"))
    try:
        status = make_status(
            designer={"provider": "codex"},
            review_2={"primary_provider": "codex", "reviewer": None, "provider": None},
        )
        errors = VS.validate_review_identity(root, root, status)
        check("no designer-overlap error for unselected primary_provider=codex + designer=codex",
              not any("designer-overlap" in e for e in errors), str(errors))
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- F1: selected reviewer still enforces designer-overlap disclosure ----
def test_selected_reviewer_enforces_overlap():
    print("F1: selected review_2.reviewer still enforces designer-overlap disclosure:")
    root = Path(tempfile.mkdtemp(prefix="vs-f1b-"))
    try:
        status = make_status(
            designer={"provider": "codex"},
            review_2={"reviewer": "codex"},
        )
        errors = VS.validate_review_identity(root, root, status)
        check("selected reviewer=codex + designer=codex triggers designer-overlap disclosure errors",
              any("designer-overlap" in e for e in errors), str(errors))
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- F1: selected reviewer sharing implementer provider is a hard ban ----
def test_selected_reviewer_implementer_ban():
    print("F1: selected review_2.reviewer sharing implementer provider is a hard ban:")
    root = Path(tempfile.mkdtemp(prefix="vs-f1c-"))
    try:
        status = make_status(
            implementer={"provider": "kimi"},
            review_2={"reviewer": "kimi"},
        )
        errors = VS.validate_review_identity(root, root, status)
        check("selected reviewer=kimi + implementer=kimi is a no-override hard ban",
              any("no override" in e for e in errors), str(errors))
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- F1: selected reviewer unrelated to designer/implementer is clean ----
def test_selected_reviewer_unrelated_is_clean():
    print("F1: selected reviewer unrelated to designer/implementer is clean:")
    root = Path(tempfile.mkdtemp(prefix="vs-f1d-"))
    try:
        status = make_status(
            designer={"provider": "codex"},
            implementer={"provider": "claude_glm"},
            review_2={"reviewer": "kimi", "primary_provider": "codex"},
        )
        errors = VS.validate_review_identity(root, root, status)
        check("selected reviewer=kimi (unrelated) is clean even with primary_provider=codex",
              errors == [], str(errors))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def setup_stage_repo(status_doc):
    """Minimal git repo with reports/agent-runs/<stage>/status.json committed."""
    root = Path(tempfile.mkdtemp(prefix="vs-f4-"))
    stage = "toy-validate"
    repo = root / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=str(repo), check=True)
    stage_dir = repo / "reports" / "agent-runs" / stage
    stage_dir.mkdir(parents=True)
    (stage_dir / "status.json").write_text(json.dumps(status_doc, indent=2) + "\n")
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=str(repo), check=True)
    return repo, stage


def run_validator(repo, stage, *extra):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "validate-stage.py"), stage, "--phase", "checkpoint", *extra],
        cwd=str(repo), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )


# ---- F4: --evidence-out writes the output file only on PASS ----
def test_evidence_out_on_pass():
    print("F4: --evidence-out writes the validation output on PASS:")
    repo, stage = setup_stage_repo({"stage_id": "toy-validate", "status": "implementing", "workflow": "stage-delivery"})
    evidence = repo / "61-validate.txt"
    try:
        r = run_validator(repo, stage, "--evidence-out", str(evidence))
        check("validator PASSED", r.returncode == 0 and "STAGE VALIDATION PASSED" in r.stdout, r.stdout)
        check("evidence file created on PASS", evidence.exists())
        check("evidence file content equals stdout tail", evidence.exists() and evidence.read_text() == r.stdout)
    finally:
        shutil.rmtree(repo.parent, ignore_errors=True)


# ---- F4: --evidence-out does NOT create the file on FAIL ----
def test_evidence_out_on_fail():
    print("F4: --evidence-out does NOT create the file on FAIL:")
    repo, stage = setup_stage_repo({"stage_id": "toy-validate", "status": "BOGUS", "workflow": "stage-delivery"})
    evidence = repo / "61-validate.txt"
    try:
        r = run_validator(repo, stage, "--evidence-out", str(evidence))
        check("validator FAILED on bogus status", r.returncode == 1 and "STAGE VALIDATION FAILED" in r.stdout, r.stdout)
        check("evidence file NOT created on FAIL", not evidence.exists())
    finally:
        shutil.rmtree(repo.parent, ignore_errors=True)


# ---- D1: --evidence-out write failure is a clean Harness error ----
def test_evidence_out_write_failure_clean_error():
    print("D1: --evidence-out write failure yields a clean Harness error, no traceback:")
    repo, stage = setup_stage_repo({"stage_id": "toy-validate", "status": "implementing", "workflow": "stage-delivery"})
    # Make the evidence path's parent a regular file so mkdir/write raise OSError.
    blocker = repo / "blocker.txt"
    blocker.write_text("i am a regular file\n")
    bad_evidence = blocker / "out.txt"
    try:
        r = run_validator(repo, stage, "--evidence-out", str(bad_evidence))
        check("validator exits non-zero on evidence write failure", r.returncode == 1, r.stdout)
        check("clean Harness error names the evidence path",
              "evidence" in r.stdout.lower() and str(bad_evidence) in r.stdout, r.stdout)
        check("no uncaught Python traceback leaked", "Traceback" not in r.stdout, r.stdout)
    finally:
        shutil.rmtree(repo.parent, ignore_errors=True)


def _git_fingerprint(repo, base, head, status_rel, renames):
    """Independent recompute of the canonical fingerprint with an explicit rename flag."""
    cmd = [
        "git", "-c", f"diff.renames={'true' if renames else 'false'}",
        "diff", "--binary", f"{base}..{head}", "--", ".", f":(exclude){status_rel}",
    ]
    diff = subprocess.run(cmd, cwd=str(repo), stdout=subprocess.PIPE, check=True).stdout
    return f"{head}:{hashlib.sha256(diff).hexdigest()}"


# ---- D3: compute_diff_fingerprint pins diff.renames=true like _itbm ----
def test_fingerprint_pins_renames_true():
    print("D3: compute_diff_fingerprint pins diff.renames=true like _itbm:")
    repo, stage = setup_stage_repo({"stage_id": "toy-validate", "status": "implementing", "workflow": "stage-delivery"})
    stage_dir = repo / "reports" / "agent-runs" / stage
    status_rel = f"reports/agent-runs/{stage}/status.json"
    try:
        # Place the file at base so the base..head diff contains a real rename.
        (repo / "a.txt").write_text("content\n")
        subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True)
        subprocess.run(["git", "commit", "-qm", "add a.txt"], cwd=str(repo), check=True)
        base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo),
                              stdout=subprocess.PIPE, check=True, text=True).stdout.strip()
        subprocess.run(["git", "mv", "a.txt", "b.txt"], cwd=str(repo), check=True)
        subprocess.run(["git", "commit", "-qm", "rename a.txt to b.txt"], cwd=str(repo), check=True)
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo),
                              stdout=subprocess.PIPE, check=True, text=True).stdout.strip()
        # Hostile repo config: disable rename detection at the git level.
        subprocess.run(["git", "config", "diff.renames", "false"], cwd=str(repo), check=True)

        sys.path.insert(0, str(SCRIPTS))
        import _itbm
        vs_fp = VS.compute_diff_fingerprint(repo, stage_dir, base, head)
        itbm_fp = _itbm.canonical_fingerprint(repo, base, head, stage)
        check("validate-stage fingerprint equals _itbm canonical under diff.renames=false",
              vs_fp == itbm_fp, f"{vs_fp} vs {itbm_fp}")
        renames_true = _git_fingerprint(repo, base, head, status_rel, True)
        renames_false = _git_fingerprint(repo, base, head, status_rel, False)
        check("rename policy materially changes the binary diff (test is meaningful)",
              renames_true != renames_false, f"{renames_true} vs {renames_false}")
        check("both pinned canonical sites equal the renames=true recompute",
              vs_fp == renames_true, f"{vs_fp} vs {renames_true}")
    finally:
        shutil.rmtree(repo.parent, ignore_errors=True)


# ---- D4: the status.json template exposes review_1.actual_model ----
def test_template_review_1_actual_model():
    print("D4: template review_1 supports actual_model:")
    template_path = SCRIPTS.parent / "reports" / "agent-runs" / "_template" / "status.json"
    template = json.loads(template_path.read_text())
    check("top-level review_1 has actual_model",
          "actual_model" in (template.get("review_1") or {}), str(template.get("review_1")))
    tasks = template.get("tasks") or []
    task_r1 = tasks[0].get("review_1", {}) if tasks and isinstance(tasks[0], dict) else {}
    check("task-level review_1 has actual_model", "actual_model" in task_r1, str(task_r1))


# ---- D5: stage-delivery workflow encodes a mechanical fix return gate ----
def test_workflow_fix_return_gate():
    print("D5: fix stage encodes review-1/review-2 return gate:")
    yaml_text = (SCRIPTS.parent / "workflows" / "templates" / "stage-delivery.yaml").read_text()
    check("fix stage pins after_fix_from_review_1: review-1",
          "after_fix_from_review_1: review-1" in yaml_text, "missing return_gate after_fix_from_review_1")
    check("fix stage pins after_fix_from_review_2: review-2",
          "after_fix_from_review_2: review-2" in yaml_text, "missing return_gate after_fix_from_review_2")


def main():
    for fn in (
        test_unselected_primary_provider_no_designer_overlap,
        test_selected_reviewer_enforces_overlap,
        test_selected_reviewer_implementer_ban,
        test_selected_reviewer_unrelated_is_clean,
        test_evidence_out_on_pass,
        test_evidence_out_on_fail,
        test_evidence_out_write_failure_clean_error,
        test_fingerprint_pins_renames_true,
        test_template_review_1_actual_model,
        test_workflow_fix_return_gate,
    ):
        fn()
    passed = sum(1 for _, ok in RESULTS if ok)
    total = len(RESULTS)
    print(f"\n{passed}/{total} assertions passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
