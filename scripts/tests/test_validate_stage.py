#!/usr/bin/env python3
"""Tests for scripts/validate-stage.py friction fixes (F1, F4).

F1: an unselected review_2.primary_provider preference must not be treated as
    the selected reviewer identity for designer-overlap / implementer-overlap
    checks, while a selected reviewer must still enforce isolation.
F4: --evidence-out writes the validation output only when validation passes,
    so it can replace `... | tee <repo-file>` without dirtying the worktree
    before the clean-worktree check.

validate-stage.py has a hyphen in its filename, so it is loaded via importlib.
Run: python3 scripts/tests/test_validate_stage.py
"""

from __future__ import annotations

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


def main():
    for fn in (
        test_unselected_primary_provider_no_designer_overlap,
        test_selected_reviewer_enforces_overlap,
        test_selected_reviewer_implementer_ban,
        test_selected_reviewer_unrelated_is_clean,
        test_evidence_out_on_pass,
        test_evidence_out_on_fail,
    ):
        fn()
    passed = sum(1 for _, ok in RESULTS if ok)
    total = len(RESULTS)
    print(f"\n{passed}/{total} assertions passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
