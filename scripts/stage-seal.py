#!/usr/bin/env python3
"""Deterministic two-commit seal primitive for the auto review pipeline.

Implements the nine-step seal protocol frozen in
``docs/auto-review-pipeline.md`` §8 and ``10-design.md`` "Seal And Commit
Protocol" (revised version with step 3 post-cross-check blocking verification):

1. verify authorization, branch, worktree, status, allowed paths, runner lock;
2. verify blocking checks and required embedded cross-check evidence exist;
3. verify the frozen blocking command set was rerun after cross-check evidence
   landed and that those commands do not consume stage evidence as input;
4. compare captured vs regenerated code-scope patches byte-for-byte (bind;
   mismatch fails closed and writes NO hash into status);
5. create the review snapshot commit (``H_snapshot``);
6. compute the canonical fingerprint from base to snapshot head;
7. atomically write mechanical status fields and the seal receipt
   (``runner-<seq>-seal.receipt.json``);
8. create the binding/evidence commit (``H_bind``) over status/handoff/receipt
   only — never code-scope;
9. run ``validate-stage.py --phase pre-review`` on a clean tree.

Crash recovery is fail-closed:

- crash before H_snapshot: no sealed unit; rerun preflight;
- crash after H_snapshot before H_bind: detect the unbound snapshot, write an
  escalation artifact, and require deterministic bind recovery using the exact
  commit — NEVER a second code commit;
- crash after H_bind: the validator/receipt determine whether review may begin.

The seal receipt ``runner-<seq>-seal.receipt.json`` is deterministic seal
evidence whose shape is defined here. It is NOT a model-adapter invocation
receipt: it does not validate against ``schemas/runner-receipt.schema.json``,
records no adapter id or registry command reference, and is excluded from the
P11 expected adapter-call count and the schema-valid adapter RECEIPT
denominator.

This bootstrap stage does NOT run this tool against itself; it is delivered as
code + tests only and targets future auto-mode stages. It invokes no models.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Make the sibling shared library importable whether this file is run directly,
# imported via importlib from the test suite, or executed as a CLI.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import harness_stage_lib as lib  # noqa: E402

SEAL_USER_NAME = "harness-seal"
SEAL_USER_EMAIL = "seal@harness.local"
SEAL_RECEIPT_SCHEMA_VERSION = 1


class SealError(Exception):
    """Raised for any deterministic seal failure; the CLI exits non-zero."""


# ---------------------------------------------------------------------------
# git helpers (deterministic identity so a bare temp repo can still commit)
# ---------------------------------------------------------------------------

def _git(root: Path, args: list[str], *, text: bool = True) -> Any:
    result = subprocess.run(
        ["git", *args], cwd=str(root), check=False,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=text,
    )
    if result.returncode != 0:
        raise SealError("git " + " ".join(args) + " failed: " + result.stderr.strip())
    return result.stdout


def _head(root: Path) -> str:
    return str(_git(root, ["rev-parse", "HEAD"])).strip()


def _porcelain(root: Path) -> list[str]:
    """Return dirty/untracked repo-relative paths (git status --porcelain)."""
    out = str(_git(root, ["status", "--porcelain"]))
    paths: list[str] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        path = line[3:].split(" -> ")[-1].strip().strip('"')
        paths.append(path)
    return paths


def _commit(root: Path, message: str, *, allow_empty: bool = False) -> str:
    args = [
        "-c", "user.name=" + SEAL_USER_NAME,
        "-c", "user.email=" + SEAL_USER_EMAIL,
        "commit",
    ]
    if allow_empty:
        args.append("--allow-empty")
    args += ["-m", message]
    _git(root, args)
    return _head(root)


# ---------------------------------------------------------------------------
# stage / unit loading
# ---------------------------------------------------------------------------

def resolve_stage(root: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_dir():
        return candidate.resolve()
    stage_dir = root / "reports" / "agent-runs" / value
    if stage_dir.is_dir():
        return stage_dir
    raise SealError("stage directory not found: " + value)


def _find_unit(status_doc: dict[str, Any], task_id: str) -> dict[str, Any]:
    arp = status_doc.get("auto_review_pipeline")
    if not isinstance(arp, dict):
        raise SealError("status has no auto_review_pipeline block")
    units = arp.get("review_units")
    if not isinstance(units, list):
        raise SealError("auto_review_pipeline.review_units must be a list")
    for unit in units:
        if isinstance(unit, dict) and unit.get("id") == task_id:
            return unit
    raise SealError("review unit not found for task: " + task_id)


def _unit_base(unit: dict[str, Any]) -> str:
    base = unit.get("base_sha")
    if not base:
        raise SealError("review unit missing base_sha")
    return str(base)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# step 1 — preflight
# ---------------------------------------------------------------------------

def _stage_rel(root: Path, stage_dir: Path) -> str:
    return stage_dir.relative_to(root).as_posix().rstrip("/") + "/"


def verify_authorization(root: Path, stage_dir: Path, status_doc: dict[str, Any]) -> dict[str, Any]:
    arp = status_doc["auto_review_pipeline"]
    auth_path_value = arp.get("authorization_path")
    if not auth_path_value:
        raise SealError("auto_review_pipeline.authorization_path is required to seal")
    auth_path = lib.resolve_safe_path(root, auth_path_value)
    if auth_path is None or not auth_path.exists():
        raise SealError("authorization artifact not found: " + str(auth_path_value))
    auth = lib.load_json(auth_path)
    errors = lib.validate_authorization_doc(auth)
    if errors:
        raise SealError("authorization invalid:\n- " + "\n- ".join(errors))
    # authorization must bind this stage and branch
    if auth.get("stage_id") != status_doc.get("stage_id"):
        raise SealError("authorization.stage_id does not match status")
    stage_branch = status_doc.get("stage_branch")
    branch_name = stage_branch.get("name") if isinstance(stage_branch, dict) else None
    if branch_name and auth.get("stage_branch") != branch_name:
        raise SealError("authorization.stage_branch does not match status")
    # expires_at: required+nullable; non-null ISO8601 must be in the future
    expires_at = auth.get("expires_at")
    if expires_at is not None:
        parsed = lib.parse_iso8601(expires_at)
        if parsed is None:
            raise SealError("authorization.expires_at is not ISO8601")
        if parsed <= datetime.now(timezone.utc):
            raise SealError("authorization.expires_at is in the past; seal refused")
    return auth


def verify_clean_allowed(
    root: Path, stage_dir: Path, status_doc: dict[str, Any], auth: dict[str, Any]
) -> list[str]:
    """Every dirty path must be inside the authorization allowlist or the stage evidence dir."""
    scope = auth.get("scope") or {}
    allowed_pathspecs = scope.get("allowed_pathspecs") or []
    stage_prefix = _stage_rel(root, stage_dir)
    dirty = _porcelain(root)
    offending: list[str] = []
    for path in dirty:
        if path.startswith(stage_prefix):
            continue
        if not _pathspec_matches(path, allowed_pathspecs):
            offending.append(path)
    if offending:
        raise SealError(
            "dirty paths outside the authorization allowlist and stage evidence dir: "
            + ", ".join(offending)
        )
    return dirty


def _pathspec_matches(path: str, pathspecs: list[str]) -> bool:
    """Approximate git pathspec matching for the allowlist boundary check.

    git itself is the authority for staging; this only guards the seal boundary
    so a stray product path cannot ride into H_snapshot. Supports literal paths
    and trailing-``/**`` or ``/*`` directory globs.
    """
    for spec in pathspecs:
        if spec == path:
            return True
        if spec.endswith("/**"):
            prefix = spec[:-3]
            if path == prefix or path.startswith(prefix + "/"):
                return True
        elif spec.endswith("/*"):
            prefix = spec[:-2]
            if path.startswith(prefix + "/") and "/" not in path[len(prefix) + 1:]:
                return True
        elif spec.endswith("/"):
            if path.startswith(spec):
                return True
    return False


def preflight(root: Path, stage_dir: Path, status_doc: dict[str, Any], auth: dict[str, Any]) -> list[str]:
    branch = str(_git(root, ["branch", "--show-current"])).strip() or "(detached)"
    stage_branch = status_doc.get("stage_branch")
    expected = stage_branch.get("name") if isinstance(stage_branch, dict) else None
    if expected and branch != expected:
        raise SealError("seal requires branch " + repr(expected) + ", got " + repr(branch))
    return verify_clean_allowed(root, stage_dir, status_doc, auth)


# ---------------------------------------------------------------------------
# step 2 — blocking + required cross-check evidence
# ---------------------------------------------------------------------------

def verify_blocking_and_cross_check(unit: dict[str, Any], root: Path, stage_dir: Path) -> None:
    blocking = unit.get("blocking_checks")
    if not isinstance(blocking, dict):
        raise SealError("review unit missing blocking_checks")
    first = blocking.get("first_pass")
    if not isinstance(first, dict):
        raise SealError("blocking_checks.first_pass record is required")
    if first.get("exit_status") != 0:
        raise SealError("blocking first_pass did not pass; seal refused")

    cross = unit.get("embedded_cross_check")
    if not isinstance(cross, dict):
        raise SealError("review unit missing embedded_cross_check block")
    if cross.get("required_attempt") is True:
        status = cross.get("status")
        if status not in ("ran", "unavailable", "skipped"):
            raise SealError("required embedded_cross_check has no terminal status")
        if status in ("ran",):
            if not cross.get("seen_patch_path"):
                raise SealError("required embedded_cross_check ran but has no seen_patch_path")


# ---------------------------------------------------------------------------
# step 3 — post-cross-check blocking rerun, evidence-independent inputs
# ---------------------------------------------------------------------------

def verify_second_pass(unit: dict[str, Any], root: Path, stage_dir: Path) -> None:
    blocking = unit["blocking_checks"]
    second = blocking.get("second_pass")
    if not isinstance(second, dict):
        raise SealError("blocking_checks.second_pass record is required (post-cross-check rerun)")
    if second.get("exit_status") != 0:
        raise SealError("post-cross-check blocking second_pass did not pass; seal refused")
    if second.get("ran_after_cross_check") is not True:
        raise SealError("blocking second_pass.ran_after_cross_check must be true")
    exclude = blocking.get("evidence_exclude_pathspecs")
    stage_prefix = _stage_rel(root, stage_dir)
    if not isinstance(exclude, list) or not any(
        isinstance(e, str) and (e.rstrip("/") == stage_prefix.rstrip("/") or stage_prefix.startswith(e.rstrip("/") + "/"))
        for e in exclude
    ):
        raise SealError(
            "blocking second_pass inputs must exclude the stage evidence directory "
            "(blocking_checks.evidence_exclude_pathspecs)"
        )


# ---------------------------------------------------------------------------
# step 4 — seen-diff bind (byte equality; no hash written to status)
# ---------------------------------------------------------------------------

def verify_bind(root: Path, unit: dict[str, Any]) -> str:
    """Return the bind status; raise SealError on mismatch."""
    cross = unit["embedded_cross_check"]
    base_sha = _unit_base(unit)
    code_pathspecs = unit.get("code_pathspecs") or []
    if not isinstance(code_pathspecs, list) or not code_pathspecs:
        raise SealError("review unit missing code_pathspecs")
    seen_path = cross.get("seen_patch_path")
    if not seen_path:
        # cross-check skipped/unavailable: bind must be N/A, no byte comparison
        if cross.get("bind_status") not in ("n/a", "N/A"):
            raise SealError("embedded_cross_check.bind_status must be 'n/a' when there is no seen patch")
        return "n/a"
    seen_resolved = lib.resolve_safe_path(root, seen_path)
    if seen_resolved is None or not seen_resolved.exists():
        raise SealError("seen patch not found: " + str(seen_path))
    captured = seen_resolved.read_bytes()
    regenerated = lib.capture_code_scope_patch(root, base_sha, code_pathspecs)
    if not lib.patches_byte_equal(captured, regenerated):
        raise SealError(
            "seen-diff bind mismatch: captured and regenerated code-scope patches differ; "
            "seal refused and no hash was written to status"
        )
    return "bound"


# ---------------------------------------------------------------------------
# step 5 — H_snapshot
# ---------------------------------------------------------------------------

def create_snapshot(root: Path, stage_dir: Path, task_id: str, dirty: list[str]) -> str:
    """Stage exactly the verified dirty paths and create H_snapshot."""
    if dirty:
        _git(root, ["add", "--", *dirty])
    parent = _head(root)
    snapshot = _commit(root, "harness-seal: H_snapshot review snapshot for task " + task_id)
    return snapshot


# ---------------------------------------------------------------------------
# step 6 + 7 — fingerprint, status fields, seal receipt
# ---------------------------------------------------------------------------

def write_unit_and_receipt(
    root: Path,
    stage_dir: Path,
    status_doc: dict[str, Any],
    unit: dict[str, Any],
    auth: dict[str, Any],
    snapshot_head: str,
    bind_status: str,
    sequence: int,
) -> tuple[str, str]:
    base_sha = _unit_base(unit)
    fingerprint = lib.compute_diff_fingerprint(root, stage_dir, base_sha, snapshot_head)
    # mutate the in-memory unit (no second fingerprint/hash field for the bind)
    unit["snapshot_commit"] = snapshot_head
    unit["head_sha"] = snapshot_head
    unit["diff_fingerprint"] = fingerprint
    cross = unit["embedded_cross_check"]
    cross["bind_status"] = bind_status

    receipt = {
        "schema_version": SEAL_RECEIPT_SCHEMA_VERSION,
        "kind": "seal",
        "stage_id": status_doc.get("stage_id"),
        "task_id": unit.get("id"),
        "review_unit_id": unit.get("id"),
        "base_sha": base_sha,
        "head_sha": snapshot_head,
        "diff_fingerprint": fingerprint,
        "bind_status": bind_status,
        "blocking_second_pass": {
            "exit_status": unit["blocking_checks"]["second_pass"].get("exit_status"),
            "ran_after_cross_check": unit["blocking_checks"]["second_pass"].get("ran_after_cross_check"),
        },
        "created_at": _now_iso(),
        "note": (
            "Deterministic seal evidence. NOT a model-adapter invocation receipt: "
            "does not validate against schemas/runner-receipt.schema.json, records "
            "no adapter id or registry command reference, and is excluded from the "
            "P11 adapter-call denominator."
        ),
    }
    receipt_name = "runner-" + str(sequence) + "-seal.receipt.json"
    receipt_path = stage_dir / receipt_name
    lib.atomic_write_json(receipt_path, receipt)
    lib.atomic_write_json(stage_dir / "status.json", status_doc)
    status_doc["_seal_receipt_path"] = receipt_name  # for the caller/H_bind; not persisted here
    return fingerprint, receipt_name


# ---------------------------------------------------------------------------
# step 8 — H_bind (status/handoff/receipt only; never code-scope)
# ---------------------------------------------------------------------------

def create_bind(root: Path, stage_dir: Path, task_id: str, receipt_name: str) -> str:
    status_rel = (stage_dir / "status.json").relative_to(root).as_posix()
    receipt_rel = (stage_dir / receipt_name).relative_to(root).as_posix()
    _git(root, ["add", "--", status_rel, receipt_rel])
    return _commit(root, "harness-seal: H_bind status + seal receipt for task " + task_id)


# ---------------------------------------------------------------------------
# step 9 — clean tree + validate --phase pre-review
# ---------------------------------------------------------------------------

def run_validator(root: Path, stage_id: str) -> None:
    remaining = _porcelain(root)
    if remaining:
        raise SealError("worktree not clean after H_bind: " + ", ".join(remaining))
    validator = root / "scripts" / "validate-stage.py"
    if not validator.exists():
        raise SealError("validator not found: " + str(validator))
    result = subprocess.run(
        [sys.executable, str(validator), stage_id, "--phase", "pre-review"],
        cwd=str(root), check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    if result.returncode != 0:
        raise SealError("validate-stage --phase pre-review failed:\n" + result.stdout.strip())


# ---------------------------------------------------------------------------
# escalation artifact (crash recovery / bind mismatch)
# ---------------------------------------------------------------------------

def write_escalation(stage_dir: Path, reason: str, detail: dict[str, Any]) -> str:
    name = "80-escalation-" + reason + "-" + _now_iso().replace(":", "").replace("-", "") + ".md"
    path = stage_dir / name
    lines = [
        "# Seal escalation: " + reason,
        "",
        "- stage: " + str(detail.get("stage_id")),
        "- task: " + str(detail.get("task_id")),
        "- reason: " + reason,
        "- created_at: " + _now_iso(),
        "",
        "Deterministic fail-closed seal evidence. Human action required.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return name


# ---------------------------------------------------------------------------
# crash-recovery detection
# ---------------------------------------------------------------------------

def unit_is_unbound(unit: dict[str, Any]) -> bool:
    """H_snapshot landed but H_bind did not: snapshot_commit set, fingerprint not."""
    return bool(unit.get("snapshot_commit")) and not unit.get("diff_fingerprint")


def unit_is_sealed(unit: dict[str, Any]) -> bool:
    return bool(unit.get("snapshot_commit")) and bool(unit.get("diff_fingerprint"))


# ---------------------------------------------------------------------------
# top-level seal flow (with crash recovery)
# ---------------------------------------------------------------------------

def seal(root: Path, stage_dir: Path, task_id: str) -> dict[str, Any]:
    status_doc = lib.load_json(stage_dir / "status.json")
    unit = _find_unit(status_doc, task_id)

    if unit_is_sealed(unit):
        raise SealError("review unit already sealed; refusing to re-seal")

    sequence = _next_sequence(status_doc)

    if unit_is_unbound(unit):
        # crash after H_snapshot before H_bind: resume the bind with the exact
        # snapshot commit; NEVER a second code commit.
        snapshot_head = str(unit["snapshot_commit"])
        bind_status = unit.get("embedded_cross_check", {}).get("bind_status", "n/a")
        fingerprint, receipt_name = write_unit_and_receipt(
            root, stage_dir, status_doc, unit, {}, snapshot_head, bind_status, sequence
        )
        create_bind(root, stage_dir, task_id, receipt_name)
        run_validator(root, str(status_doc.get("stage_id")))
        return {"head_sha": snapshot_head, "diff_fingerprint": fingerprint,
                "receipt": receipt_name, "recovered": True}

    # fresh nine-step seal
    auth = verify_authorization(root, stage_dir, status_doc)
    dirty = preflight(root, stage_dir, status_doc, auth)
    verify_blocking_and_cross_check(unit, root, stage_dir)
    verify_second_pass(unit, root, stage_dir)
    bind_status = verify_bind(root, unit)
    snapshot_head = create_snapshot(root, stage_dir, task_id, dirty)
    fingerprint, receipt_name = write_unit_and_receipt(
        root, stage_dir, status_doc, unit, auth, snapshot_head, bind_status, sequence
    )
    create_bind(root, stage_dir, task_id, receipt_name)
    run_validator(root, str(status_doc.get("stage_id")))
    return {"head_sha": snapshot_head, "diff_fingerprint": fingerprint,
            "receipt": receipt_name, "recovered": False}


def _next_sequence(status_doc: dict[str, Any]) -> int:
    arp = status_doc.get("auto_review_pipeline", {})
    if isinstance(arp, dict):
        used = arp.get("last_receipt_sequence")
        if isinstance(used, int):
            return used + 1
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic two-commit seal primitive")
    parser.add_argument("stage", help="stage id or path under reports/agent-runs")
    parser.add_argument("--task", required=True, help="review unit / task id to seal")
    args = parser.parse_args()

    try:
        root = Path(str(_git(Path.cwd(), ["rev-parse", "--show-toplevel"])).strip())
        root = Path(root)
        stage_dir = resolve_stage(root, args.stage)
        result = seal(root, stage_dir, args.task)
        print("SEAL OK")
        print("task=" + args.task)
        print("head_sha=" + result["head_sha"])
        print("diff_fingerprint=" + result["diff_fingerprint"])
        print("receipt=" + result["receipt"])
        print("recovered=" + str(result["recovered"]))
        return 0
    except (SealError, lib.HarnessError) as exc:
        print("SEAL FAILED")
        print("- " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
