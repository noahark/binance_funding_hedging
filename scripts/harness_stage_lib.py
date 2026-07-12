#!/usr/bin/env python3
"""Shared Harness stage mechanics (stdlib-only).

This module is the single canonical home for the deterministic, reusable
mechanics shared by the stage validator (``scripts/validate-stage.py``) and the
seal primitive (``scripts/stage-seal.py``). It is intentionally dependency-free:
no ``jsonschema``, no ``yaml``. The T1 JSON Schema files under ``schemas/`` are
the authoritative *written* contract; the hand-written structural validators
below are the *runtime* authority. The tests feed identical positive/negative
fixtures through both so the two cannot drift silently.

The module contains no workflow judgement and no model routing policy. Routing
and transition policy live in ``workflows/templates/stage-delivery.yaml`` and
the runner (``scripts/auto-review-runner.py``, a T3 concern).

Public surface consumed by the validator, seal tool, and tests:

- ``compute_diff_fingerprint`` — byte-identical to the historical validator
  implementation (single canonical path).
- ``capture_code_scope_patch`` / ``patches_byte_equal`` — the seen-diff bind
  primitives; byte comparison only, never a hash or status field.
- ``atomic_write_json`` / ``load_json`` — crash-safe JSON IO.
- ``PROVIDER_IDENTITIES`` / ``provider_identity`` / ``provider_key`` — provider
  normalization (a superset of the validator's historical table).
- ``is_safe_repo_relative_path`` / ``resolve_safe_path`` — stage/worktree-safe
  path resolution (absolute, ``..`` traversal, symlink escape, control chars).
- ``validate_authorization_doc`` / ``validate_receipt_doc`` — hand-written
  structural validators covering the full constraint surface of the two schemas,
  including the cross-field semantics JSON Schema cannot express.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


class HarnessError(Exception):
    """Raised for deterministic mechanical failures (git, IO, path safety)."""


# ---------------------------------------------------------------------------
# git helper
# ---------------------------------------------------------------------------

def _run_git(root: Path, args: list[str], *, text: bool = False) -> Any:
    """Run a git command under ``root`` and return stdout (bytes unless text)."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(root),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
    )
    if result.returncode != 0:
        stderr = result.stderr if text else result.stderr.decode("utf-8", "replace")
        raise HarnessError(
            "git " + " ".join(args) + " failed: " + stderr.strip()
        )
    return result.stdout


# ---------------------------------------------------------------------------
# diff fingerprint (frozen formula, single canonical implementation)
# ---------------------------------------------------------------------------

def compute_diff_fingerprint(
    root: Path, stage_dir: Path, base_sha: str, head_sha: str
) -> str:
    """Return ``"<head_sha>:<sha256>"`` over the binary diff of the range.

    Byte-identical to the historical ``validate-stage.py`` implementation: same
    git argument order, same ``:(exclude)<stage>/status.json`` exclusion
    (status records the fingerprint, so it must not feed its own computation),
    sha256 over the raw diff bytes. The formula is frozen in AGENTS.md Hard
    Gates and docs/auto-review-pipeline.md §8; do not change it.
    """
    root = Path(root)
    status_rel = (Path(stage_dir) / "status.json").relative_to(root).as_posix()
    diff = _run_git(
        root,
        [
            "diff",
            "--binary",
            f"{base_sha}..{head_sha}",
            "--",
            ".",
            f":(exclude){status_rel}",
        ],
        text=False,
    )
    digest = hashlib.sha256(diff).hexdigest()
    return f"{head_sha}:{digest}"


def capture_code_scope_patch(
    root: Path, base_revision: str, pathspecs: list[str]
) -> bytes:
    """Capture raw ``git diff --binary`` bytes for a frozen base + ordered pathspecs.

    ``base_revision`` is any git revision expression git accepts: a bare commit
    (compares the working tree against that commit, used to capture the seen
    patch before cross-check) or a ``<base>..<head>`` range (used to regenerate
    the patch after the snapshot commit). No text decoding/re-encoding occurs;
    the bytes are returned verbatim for byte-equality comparison.
    """
    args = ["diff", "--binary", str(base_revision), "--"]
    args.extend(str(p) for p in pathspecs)
    return _run_git(root, args, text=False)


def patches_byte_equal(a: bytes, b: bytes) -> bool:
    """Seen-diff bind primitive: raw byte equality, never a hash or status field."""
    return bytes(a) == bytes(b)


# ---------------------------------------------------------------------------
# JSON IO
# ---------------------------------------------------------------------------

def load_json(path: Path | str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def atomic_write_json(path: Path | str, obj: Any) -> None:
    """Write JSON via a temp file in the same directory then ``os.replace``."""
    path = Path(path)
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(directory))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(obj, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# provider identity normalization (superset of the validator's table)
# ---------------------------------------------------------------------------

PROVIDER_IDENTITIES: dict[str, str] = {
    "codex": "openai",
    "gpt": "openai",
    "openai": "openai",
    "claude": "anthropic",
    "anthropic": "anthropic",
    "fable5": "anthropic",
    "claude_fable5": "anthropic",
    "claude_glm": "zhipu_glm",
    "glm": "zhipu_glm",
    "glm52": "zhipu_glm",
    "zhipu_glm": "zhipu_glm",
    "kimi": "moonshot_kimi",
    "kimi27": "moonshot_kimi",
    "moonshot_kimi": "moonshot_kimi",
    "grok": "xai_grok",
    "xai_grok": "xai_grok",
    "gemini": "google",
    "gemini3.1pro": "google",
    "google": "google",
}


def provider_identity(value: Any) -> str | None:
    """Return normalized model-vendor identity from status fields, or None."""
    if value is None:
        return None
    if isinstance(value, dict):
        for key in ("runtime_provider_identity", "provider_identity", "provider", "id", "model"):
            found = provider_identity(value.get(key))
            if found:
                return found
        return None
    text = str(value).strip()
    if not text:
        return None
    return PROVIDER_IDENTITIES.get(text, text)


def provider_key(value: Any) -> str | None:
    """Return the workflow/provider key used by registry routing rules."""
    if value is None:
        return None
    if isinstance(value, dict):
        for key in ("provider", "adapter", "id"):
            found = provider_key(value.get(key))
            if found:
                return found
        return None
    text = str(value).strip()
    return text or None


# ---------------------------------------------------------------------------
# safe path resolution
# ---------------------------------------------------------------------------

_CONTROL_CHAR_RE = re.compile(r"[\r\n\t\x00-\x1f\x7f]")


def is_safe_repo_relative_path(value: Any, *, nullable: bool = False) -> bool:
    """Mirror ``safe_required_repo_relative_path`` / safe-nullable from the schemas.

    Rejects absolute paths (leading ``/``), parent-directory traversal (``..``),
    and CR/LF/tab or any control character. Empty strings are invalid.
    """
    if value is None:
        return nullable
    if not isinstance(value, str) or len(value) == 0:
        return False
    if value.startswith("/"):
        return False
    if ".." in value:
        return False
    if _CONTROL_CHAR_RE.search(value):
        return False
    return True


def resolve_safe_path(
    root: Path, value: Any, *, nullable: bool = False
) -> Path | None:
    """Resolve a repo-relative path under ``root`` and reject symlink escape.

    Returns the resolved absolute path (or None when nullable and value is
    None). Raises ``HarnessError`` on absolute paths, ``..`` traversal, control
    characters, or a resolved location outside ``root`` (symlink escape).
    """
    if value is None:
        if nullable:
            return None
        raise HarnessError("path is required")
    if not is_safe_repo_relative_path(value, nullable=False):
        raise HarnessError("unsafe repo-relative path: " + repr(value))
    root_resolved = Path(root).resolve()
    candidate = (root_resolved / value).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise HarnessError("path escapes repository root: " + repr(value)) from exc
    return candidate


# ---------------------------------------------------------------------------
# ISO8601 parsing
# ---------------------------------------------------------------------------

def parse_iso8601(value: Any) -> datetime | None:
    """Parse an ISO8601 instant (``...Z`` tolerated), or return None if invalid."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def is_iso8601(value: Any) -> bool:
    return parse_iso8601(value) is not None


# ---------------------------------------------------------------------------
# frozen receipt contract constants (mirror schemas/runner-receipt.schema.json)
# ---------------------------------------------------------------------------

RECEIPT_REQUIRED: list[str] = [
    "schema_version", "stage_id", "sequence", "node", "attempt",
    "review_unit_id", "task_id", "adapter", "prompt_path", "raw_output_path",
    "verdict_path", "started_at", "completed_at", "exit_status", "timeout",
    "call_budget", "failure_class", "next_transition",
]
RECEIPT_NODES = {"implementation", "embedded_cross_check", "review_1", "fix"}
RECEIPT_ADAPTER_IDS = {"claude_glm", "kimi", "grok"}
RECEIPT_COMMAND_REFS = {
    "agents/registry.yaml#adapters.claude_glm.noninteractive_command",
    "agents/registry.yaml#adapters.claude_glm.embedded_read_only_review_command",
    "agents/registry.yaml#adapters.kimi.noninteractive_command",
    "agents/registry.yaml#adapters.kimi.embedded_read_only_review_command",
    "agents/registry.yaml#adapters.grok.development_command",
    "agents/registry.yaml#adapters.grok.optional_review_command",
}
# adapter.id -> allowed registry command refs (adapter-level allOf)
ADAPTER_ID_REFS: dict[str, set[str]] = {
    "claude_glm": {
        "agents/registry.yaml#adapters.claude_glm.noninteractive_command",
        "agents/registry.yaml#adapters.claude_glm.embedded_read_only_review_command",
    },
    "kimi": {
        "agents/registry.yaml#adapters.kimi.noninteractive_command",
        "agents/registry.yaml#adapters.kimi.embedded_read_only_review_command",
    },
    "grok": {
        "agents/registry.yaml#adapters.grok.development_command",
        "agents/registry.yaml#adapters.grok.optional_review_command",
    },
}
# node -> allowed registry command refs (top-level allOf)
NODE_WRITE_REFS = {  # implementation, fix
    "agents/registry.yaml#adapters.claude_glm.noninteractive_command",
    "agents/registry.yaml#adapters.kimi.noninteractive_command",
    "agents/registry.yaml#adapters.grok.development_command",
}
NODE_CROSSCHECK_REFS = {  # embedded_cross_check
    "agents/registry.yaml#adapters.claude_glm.embedded_read_only_review_command",
    "agents/registry.yaml#adapters.kimi.embedded_read_only_review_command",
}
# review_1 oneOf three frozen (id, ref) pairs
REVIEW_1_PAIRS = {
    ("grok", "agents/registry.yaml#adapters.grok.optional_review_command"),
    ("kimi", "agents/registry.yaml#adapters.kimi.embedded_read_only_review_command"),
    ("claude_glm", "agents/registry.yaml#adapters.claude_glm.embedded_read_only_review_command"),
}
RECEIPT_FAILURE_CLASSES = {
    None, "model_unavailable", "adapter_missing", "command_error", "permission_error",
    "timeout", "invalid_pre_review_output", "invalid_verdict_json",
    "scope_or_contract_dispute", "quota_exhausted", "auth_failure", "service_unavailable",
}
# next_transition enum == workflow allowed_next_transitions (9 values) + null
NEXT_TRANSITIONS = {
    None, "implementation", "embedded_cross_check", "blocking_check", "seal",
    "review_1", "fix", "awaiting_human", "completed_review_1", "human_escalation_required",
}


# ---------------------------------------------------------------------------
# frozen authorization contract constants
# ---------------------------------------------------------------------------

# v1 serial-only slim shape. Removed fields (authorized, allowed_adapters,
# review_1_provider, auto_high_end_dispatch_allowed, scope.topology,
# budgets.wall_clock_seconds, budgets.max_stage_rework,
# budgets.invalid_json_max_attempts_per_model) are intentionally absent from
# these sets so additionalProperties:false / the unknown-field check rejects any
# stale artifact carrying one of them. The stage-rework cap (3), invalid-JSON
# retry limit (2), allowed-adapter set, review-1 provider route, and
# high-end-dispatch flag are global workflow/registry invariants, not
# per-authorization fields.
AUTH_REQUIRED: list[str] = [
    "schema_version", "stage_id", "stage_branch", "contract_version",
    "authorized_by", "approval_evidence_path",
    "approval_recorded_by", "authorized_at", "expires_at", "scope",
    "budgets", "supersedes",
]
AUTH_SCOPE_KEYS = {"task_ids", "allowed_pathspecs", "forbidden_pathspecs"}
AUTH_BUDGET_KEYS = {
    "max_model_calls", "max_auto_code_changes",
}


def _is_int(value: Any) -> bool:
    """True for genuine integers (bool is excluded; JSON bools are not ints here)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_str(value: Any) -> bool:
    return isinstance(value, str)


def _is_unique_list(value: Any, *, item_ok: Any = None) -> bool:
    if not isinstance(value, list):
        return False
    return len(value) == len({json.dumps(i, sort_keys=True) for i in value})


# ---------------------------------------------------------------------------
# authorization structural validator
# ---------------------------------------------------------------------------

def validate_authorization_doc(doc: Any) -> list[str]:
    """Hand-written structural validation of an authorization artifact.

    Covers the full constraint surface of
    ``schemas/auto-review-authorization.schema.json`` plus the cross-field
    semantics JSON Schema cannot express. Returns a list of human-readable
    errors (empty when valid).
    """
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["authorization document must be an object"]

    unknown = set(doc.keys()) - set(AUTH_REQUIRED)
    if unknown:
        errors.append("authorization unknown fields: " + ", ".join(sorted(unknown)))
    for key in AUTH_REQUIRED:
        if key not in doc:
            errors.append("authorization missing required field: " + key)

    # schema_version const 1
    if "schema_version" in doc and not (_is_int(doc["schema_version"]) and doc["schema_version"] == 1):
        errors.append("authorization.schema_version must be integer const 1")
    # contract_version const
    if doc.get("contract_version") != "auto-review-pipeline/v1":
        errors.append("authorization.contract_version must be 'auto-review-pipeline/v1'")
    # authorized_by const human
    if doc.get("authorized_by") != "human":
        errors.append("authorization.authorized_by must be const 'human'")

    # stage_id
    if "stage_id" in doc and not (_is_str(doc["stage_id"]) and doc["stage_id"].strip()):
        errors.append("authorization.stage_id must be a non-empty string")
    # stage_branch: non-empty, no control chars
    if "stage_branch" in doc:
        sb = doc["stage_branch"]
        if not (_is_str(sb) and sb.strip()):
            errors.append("authorization.stage_branch must be a non-empty string")
        elif _CONTROL_CHAR_RE.search(sb):
            errors.append("authorization.stage_branch must not contain control characters")
    # approval_evidence_path: safe required path
    if "approval_evidence_path" in doc and not is_safe_repo_relative_path(doc["approval_evidence_path"]):
        errors.append("authorization.approval_evidence_path must be a safe repo-relative path")
    # approval_recorded_by non-empty
    if "approval_recorded_by" in doc and not (_is_str(doc["approval_recorded_by"]) and doc["approval_recorded_by"].strip()):
        errors.append("authorization.approval_recorded_by must be a non-empty string")
    # authorized_at ISO8601
    if "authorized_at" in doc and not is_iso8601(doc["authorized_at"]):
        errors.append("authorization.authorized_at must be an ISO8601 instant")
    # expires_at: required, nullable, ISO8601 when non-null
    if "expires_at" in doc:
        exp = doc["expires_at"]
        if exp is not None and not is_iso8601(exp):
            errors.append("authorization.expires_at must be null or an ISO8601 instant")
    # supersedes: safe nullable path
    if "supersedes" in doc and not is_safe_repo_relative_path(doc["supersedes"], nullable=True):
        errors.append("authorization.supersedes must be null or a safe repo-relative path")

    # scope

    if "scope" in doc:
        scope = doc["scope"]
        if not isinstance(scope, dict):
            errors.append("authorization.scope must be an object")
        else:
            s_unknown = set(scope.keys()) - AUTH_SCOPE_KEYS
            if s_unknown:
                errors.append("authorization.scope unknown fields: " + ", ".join(sorted(s_unknown)))
            for key in AUTH_SCOPE_KEYS:
                if key not in scope:
                    errors.append("authorization.scope missing required field: " + key)
            task_ids = scope.get("task_ids")
            if "task_ids" in scope and not (isinstance(task_ids, list) and task_ids and _is_unique_list(task_ids) and all(_is_str(t) and t for t in task_ids)):
                errors.append("authorization.scope.task_ids must be a non-empty unique list of non-empty strings")
            allowed = scope.get("allowed_pathspecs")
            if "allowed_pathspecs" in scope and not (isinstance(allowed, list) and allowed and _is_unique_list(allowed) and all(_is_str(p) and p for p in allowed)):
                errors.append("authorization.scope.allowed_pathspecs must be a non-empty unique list of non-empty strings")
            forbidden = scope.get("forbidden_pathspecs")
            if "forbidden_pathspecs" in scope and not (isinstance(forbidden, list) and _is_unique_list(forbidden) and all(_is_str(p) and p for p in forbidden)):
                errors.append("authorization.scope.forbidden_pathspecs must be a unique list of non-empty strings")

    # budgets
    if "budgets" in doc:
        budgets = doc["budgets"]
        if not isinstance(budgets, dict):
            errors.append("authorization.budgets must be an object")
        else:
            b_unknown = set(budgets.keys()) - AUTH_BUDGET_KEYS
            if b_unknown:
                errors.append("authorization.budgets unknown fields: " + ", ".join(sorted(b_unknown)))
            for key in AUTH_BUDGET_KEYS:
                if key not in budgets:
                    errors.append("authorization.budgets missing required field: " + key)
            if "max_model_calls" in budgets and not (_is_int(budgets["max_model_calls"]) and budgets["max_model_calls"] >= 1):
                errors.append("authorization.budgets.max_model_calls must be an integer >= 1")
            if "max_auto_code_changes" in budgets and not (_is_int(budgets["max_auto_code_changes"]) and 0 <= budgets["max_auto_code_changes"] <= 2):
                errors.append("authorization.budgets.max_auto_code_changes must be an integer in [0, 2]")

    return errors


# ---------------------------------------------------------------------------
# receipt structural validator
# ---------------------------------------------------------------------------

def validate_receipt_doc(doc: Any) -> list[str]:
    """Hand-written structural validation of a runner receipt.

    Covers the full constraint surface of ``schemas/runner-receipt.schema.json``
    plus the cross-field semantics JSON Schema cannot express (notably
    ``call_budget.after == before - 1`` and the three node-conditional
    adapter/ref pairings). Returns a list of human-readable errors.
    """
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["receipt document must be an object"]

    unknown = set(doc.keys()) - set(RECEIPT_REQUIRED)
    if unknown:
        errors.append("receipt unknown fields: " + ", ".join(sorted(unknown)))
    for key in RECEIPT_REQUIRED:
        if key not in doc:
            errors.append("receipt missing required field: " + key)

    # schema_version const 1
    if "schema_version" in doc and not (_is_int(doc["schema_version"]) and doc["schema_version"] == 1):
        errors.append("receipt.schema_version must be integer const 1")
    # stage_id non-empty
    if "stage_id" in doc and not (_is_str(doc["stage_id"]) and doc["stage_id"].strip()):
        errors.append("receipt.stage_id must be a non-empty string")
    # sequence / attempt positive ints
    if "sequence" in doc and not (_is_int(doc["sequence"]) and doc["sequence"] >= 1):
        errors.append("receipt.sequence must be an integer >= 1")
    if "attempt" in doc and not (_is_int(doc["attempt"]) and doc["attempt"] >= 1):
        errors.append("receipt.attempt must be an integer >= 1")
    # node enum
    node = doc.get("node")
    if "node" in doc and node not in RECEIPT_NODES:
        errors.append("receipt.node must be one of implementation/embedded_cross_check/review_1/fix")
    # review_unit_id / task_id: string or null
    for key in ("review_unit_id", "task_id"):
        if key in doc and doc[key] is not None and not _is_str(doc[key]):
            errors.append("receipt." + key + " must be a string or null")

    # adapter
    if "adapter" in doc:
        adapter = doc["adapter"]
        if not isinstance(adapter, dict):
            errors.append("receipt.adapter must be an object")
        else:
            a_unknown = set(adapter.keys()) - {"id", "registry_command_ref"}
            if a_unknown:
                errors.append("receipt.adapter unknown fields: " + ", ".join(sorted(a_unknown)))
            for key in ("id", "registry_command_ref"):
                if key not in adapter:
                    errors.append("receipt.adapter missing required field: " + key)
            aid = adapter.get("id")
            ref = adapter.get("registry_command_ref")
            if "id" in adapter and aid not in RECEIPT_ADAPTER_IDS:
                errors.append("receipt.adapter.id must be one of claude_glm/kimi/grok")
            if "registry_command_ref" in adapter and ref not in RECEIPT_COMMAND_REFS:
                errors.append("receipt.adapter.registry_command_ref is not a frozen anchored reference")
            # adapter-level allOf: id <-> ref
            if aid in ADAPTER_ID_REFS and ref not in ADAPTER_ID_REFS[aid]:
                errors.append("receipt.adapter.id " + repr(aid) + " does not match registry_command_ref " + repr(ref))
            # top-level allOf: node -> ref pairing
            if node == "review_1":
                if (aid, ref) not in REVIEW_1_PAIRS:
                    errors.append("review_1 adapter must be one of the three frozen (id, ref) pairs; got id=" + repr(aid) + " ref=" + repr(ref))
            elif node in ("implementation", "fix"):
                if ref not in NODE_WRITE_REFS:
                    errors.append(node + " registry_command_ref must be a write/noninteractive reference; got " + repr(ref))
            elif node == "embedded_cross_check":
                if ref not in NODE_CROSSCHECK_REFS:
                    errors.append("embedded_cross_check registry_command_ref must be an embedded read-only review reference; got " + repr(ref))

    # safe nullable paths
    for key in ("prompt_path", "raw_output_path", "verdict_path"):
        if key in doc and not is_safe_repo_relative_path(doc[key], nullable=True):
            errors.append("receipt." + key + " must be null or a safe repo-relative path")
    # timestamps
    if "started_at" in doc and not is_iso8601(doc["started_at"]):
        errors.append("receipt.started_at must be an ISO8601 instant")
    if "completed_at" in doc and doc["completed_at"] is not None and not is_iso8601(doc["completed_at"]):
        errors.append("receipt.completed_at must be null or an ISO8601 instant")
    # exit_status: integer or null
    if "exit_status" in doc and doc["exit_status"] is not None and not _is_int(doc["exit_status"]):
        errors.append("receipt.exit_status must be an integer or null")
    # timeout: boolean
    if "timeout" in doc and not isinstance(doc["timeout"], bool):
        errors.append("receipt.timeout must be a boolean")

    # call_budget
    if "call_budget" in doc:
        cb = doc["call_budget"]
        if not isinstance(cb, dict):
            errors.append("receipt.call_budget must be an object")
        else:
            cb_unknown = set(cb.keys()) - {"before", "after"}
            if cb_unknown:
                errors.append("receipt.call_budget unknown fields: " + ", ".join(sorted(cb_unknown)))
            for key in ("before", "after"):
                if key not in cb:
                    errors.append("receipt.call_budget missing required field: " + key)
            before = cb.get("before")
            after = cb.get("after")
            if "before" in cb and not (_is_int(before) and before >= 0):
                errors.append("receipt.call_budget.before must be an integer >= 0")
            if "after" in cb and not (_is_int(after) and after >= 0):
                errors.append("receipt.call_budget.after must be an integer >= 0")
            # cross-field: after == before - 1
            if _is_int(before) and _is_int(after) and after != before - 1:
                errors.append("receipt.call_budget.after must equal before - 1")

    # failure_class enum
    if "failure_class" in doc and doc["failure_class"] not in RECEIPT_FAILURE_CLASSES:
        errors.append("receipt.failure_class is not in the frozen failure-class set")
    # next_transition enum (== workflow allowed_next_transitions + null)
    if "next_transition" in doc and doc["next_transition"] not in NEXT_TRANSITIONS:
        errors.append("receipt.next_transition is not in the frozen transition set")

    return errors
