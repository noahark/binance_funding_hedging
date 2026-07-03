#!/usr/bin/env python3
"""Validate Harness stage state before review or acceptance.

This script is intentionally dependency-free. It turns the Harness evidence
rules into an executable gate so model controllers cannot pass review by
inventing status values or fingerprint protocols.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ALLOWED_STATUSES = {
    "planned",
    "designing",
    "implementing",
    "testing",
    "review_1",
    "fixing",
    "review_2",
    "accepted",
    "paused",
    "decision_models_exhausted",
    "development_models_exhausted",
    "stage_accepted_waiting_user",
    "human_escalation_required",
}

PRE_REVIEW_STATUSES = {"review_1", "review_2"}
PRE_ACCEPT_STATUSES = {"accepted", "stage_accepted_waiting_user"}


class ValidationError(Exception):
    pass


def run(args: list[str], *, cwd: Path, text: bool = True) -> str | bytes:
    result = subprocess.run(
        args,
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
    )
    if result.returncode != 0:
        stderr = result.stderr if text else result.stderr.decode("utf-8", "replace")
        raise ValidationError(f"command failed: {' '.join(args)}\n{stderr.strip()}")
    return result.stdout


def repo_root() -> Path:
    out = run(["git", "rev-parse", "--show-toplevel"], cwd=Path.cwd())
    return Path(str(out).strip())


def resolve_stage(root: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_dir():
        return candidate.resolve()
    stage_dir = root / "reports" / "agent-runs" / value
    if stage_dir.is_dir():
        return stage_dir
    raise ValidationError(f"stage directory not found: {value}")


def load_status(stage_dir: Path) -> dict[str, Any]:
    path = stage_dir / "status.json"
    if not path.exists():
        raise ValidationError(f"missing {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {path}: {exc}") from exc


def require_clean_worktree(root: Path) -> None:
    porcelain = str(run(["git", "status", "--porcelain"], cwd=root))
    if porcelain.strip():
        raise ValidationError(
            "review/acceptance gates require a clean committed worktree; "
            "commit or revert these changes first:\n" + porcelain.rstrip()
        )


def require_commit(root: Path, sha: str, field: str) -> None:
    if not sha:
        raise ValidationError(f"missing {field}")
    run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=root)


def compute_diff_fingerprint(root: Path, stage_dir: Path, base_sha: str, head_sha: str) -> str:
    status_rel = (stage_dir / "status.json").relative_to(root).as_posix()
    diff = run(
        [
            "git",
            "diff",
            "--binary",
            f"{base_sha}..{head_sha}",
            "--",
            ".",
            f":(exclude){status_rel}",
        ],
        cwd=root,
        text=False,
    )
    digest = hashlib.sha256(diff).hexdigest()
    return f"{head_sha}:{digest}"


def truthy(value: Any) -> bool:
    return value is True or str(value).lower() in {"true", "valid", "pass", "passed", "accept"}


def validate_common(root: Path, stage_dir: Path, status_doc: dict[str, Any], phase: str) -> list[str]:
    errors: list[str] = []
    status = status_doc.get("status")
    if status not in ALLOWED_STATUSES:
        errors.append(f"status is not allowed: {status!r}")

    if phase == "pre-review" and status not in PRE_REVIEW_STATUSES:
        errors.append(f"pre-review requires status in {sorted(PRE_REVIEW_STATUSES)}, got {status!r}")
    if phase == "pre-accept" and status not in PRE_ACCEPT_STATUSES:
        errors.append(f"pre-accept requires status in {sorted(PRE_ACCEPT_STATUSES)}, got {status!r}")

    fingerprint_required = (
        phase in {"pre-review", "pre-accept"}
        or status in PRE_REVIEW_STATUSES
        or status in PRE_ACCEPT_STATUSES
    )

    base_sha = status_doc.get("base_sha")
    head_sha = status_doc.get("head_sha")
    recorded = status_doc.get("diff_fingerprint")
    if fingerprint_required:
        for field, value in (("base_sha", base_sha), ("head_sha", head_sha), ("diff_fingerprint", recorded)):
            if not value:
                errors.append(f"missing {field}")

    if base_sha and head_sha:
        try:
            require_commit(root, base_sha, "base_sha")
            require_commit(root, head_sha, "head_sha")
        except ValidationError as exc:
            errors.append(str(exc))
        if fingerprint_required and base_sha == head_sha:
            errors.append("head_sha must differ from base_sha before review/acceptance")

    if recorded and ":" not in str(recorded):
        errors.append("diff_fingerprint must be '<head_sha>:<sha256>'")

    if base_sha and head_sha and recorded:
        try:
            expected = compute_diff_fingerprint(root, stage_dir, base_sha, head_sha)
            if recorded != expected:
                errors.append(f"diff_fingerprint mismatch: recorded={recorded}, expected={expected}")
        except ValidationError as exc:
            errors.append(str(exc))

    if "worktree_fingerprint" in status_doc:
        errors.append("worktree_fingerprint is not an allowed Harness field")
    if status_doc.get("commit_state") == "uncommitted_working_tree":
        errors.append("uncommitted_working_tree cannot enter a review/acceptance gate")

    return errors


def validate_required_files(stage_dir: Path, phase: str) -> list[str]:
    required = ["00-task.md", "10-design.md", "11-adr.md", "20-implementation.md", "60-test-output.txt", "70-handoff.md"]
    if phase == "pre-accept":
        required += ["30-review-1.md", "50-review-2.md"]
    missing = [name for name in required if not (stage_dir / name).exists()]
    return [f"missing required stage file: {name}" for name in missing]


def validate_acceptance(status_doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    tests = status_doc.get("tests", {})
    if not isinstance(tests, dict) or str(tests.get("status", "")).lower() not in {"pass", "passed"}:
        errors.append("pre-accept requires tests.status pass/passed")
    for key in ("review_1", "review_2"):
        review = status_doc.get(key, {})
        if not isinstance(review, dict):
            errors.append(f"{key} must be an object")
            continue
        if review.get("verdict") != "ACCEPT":
            errors.append(f"{key}.verdict must be ACCEPT")
        if not truthy(review.get("json_schema_valid")):
            errors.append(f"{key}.json_schema_valid must be true")
        if review.get("diff_fingerprint") != status_doc.get("diff_fingerprint"):
            errors.append(f"{key}.diff_fingerprint must match status.diff_fingerprint")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an AI Project Harness stage")
    parser.add_argument("stage", help="stage id or path under reports/agent-runs")
    parser.add_argument("--phase", choices=["pre-review", "pre-accept", "checkpoint"], default="checkpoint")
    args = parser.parse_args()

    try:
        root = repo_root()
        stage_dir = resolve_stage(root, args.stage)
        status_doc = load_status(stage_dir)

        errors: list[str] = []
        if args.phase in {"pre-review", "pre-accept"}:
            try:
                require_clean_worktree(root)
            except ValidationError as exc:
                errors.append(str(exc))
        errors.extend(validate_common(root, stage_dir, status_doc, args.phase))
        if args.phase in {"pre-review", "pre-accept"}:
            errors.extend(validate_required_files(stage_dir, args.phase))
        if args.phase == "pre-accept":
            errors.extend(validate_acceptance(status_doc))

        if errors:
            print("STAGE VALIDATION FAILED")
            for err in errors:
                print(f"- {err}")
            return 1

        print("STAGE VALIDATION PASSED")
        print(f"stage={stage_dir.relative_to(root)}")
        print(f"phase={args.phase}")
        print(f"status={status_doc.get('status')}")
        if status_doc.get("diff_fingerprint"):
            print(f"diff_fingerprint={status_doc['diff_fingerprint']}")
        return 0
    except ValidationError as exc:
        print("STAGE VALIDATION FAILED")
        print(f"- {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
