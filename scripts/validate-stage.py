#!/usr/bin/env python3
"""Validate Harness stage state before review or acceptance.

This script is intentionally dependency-free. It turns the Harness evidence
rules into an executable gate so stage operators cannot pass review by
inventing status values or fingerprint protocols.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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
    "blocked",
    "abandoned",
}

PRE_REVIEW_STATUSES = {"review_1", "review_2"}
PRE_ACCEPT_STATUSES = {"accepted", "stage_accepted_waiting_user"}
DISPATCH_READY_REQUIRED_FILES = ["00-task.md", "10-design.md", "11-adr.md"]
EMBEDDED_CHECKPOINT_FAILURE_CLASSES = {
    "model_unavailable",
    "adapter_missing",
    "command_error",
    "permission_error",
    "timeout",
    "invalid_pre_review_output",
    "scope_or_contract_dispute",
}
BRANCH_RETAINED_TERMINAL_STATUSES = {
    "blocked",
    "abandoned",
    "human_escalation_required",
    "decision_models_exhausted",
    "development_models_exhausted",
}
REVIEWER_PRIOR_INVOLVEMENTS = {"none", "direction_synthesis", "breakdown", "design"}
PROVIDER_IDENTITIES = {
    "codex": "openai",
    "gpt": "openai",
    "openai": "openai",
    "claude": "anthropic",
    "anthropic": "anthropic",
    "fable5": "anthropic",
    "claude_glm": "zhipu_glm",
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


def current_branch(root: Path) -> str:
    branch = str(run(["git", "branch", "--show-current"], cwd=root)).strip()
    if branch:
        return branch
    return "(detached)"


def require_commit_in_current_history(root: Path, sha: str, field: str) -> None:
    require_commit(root, sha, field)
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", sha, "HEAD"],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise ValidationError(f"{field} is not reachable from current HEAD: {sha}")


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


def provider_identity(value: Any) -> str | None:
    """Return normalized model-vendor identity from status fields."""
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


def normalize_tasks(status_doc: dict[str, Any]) -> tuple[list[Any], list[str]]:
    """Return tasks as a list while accepting legacy dict-keyed status files."""
    raw = status_doc.get("tasks", [])
    if raw is None:
        return [], []
    if isinstance(raw, list):
        return raw, []
    if isinstance(raw, dict):
        normalized: list[Any] = []
        for key, value in raw.items():
            if isinstance(value, dict):
                task = dict(value)
                task.setdefault("id", str(key))
                normalized.append(task)
            else:
                normalized.append({"id": str(key), "_invalid_task_value": value})
        return normalized, []
    return [], ["tasks must be a list or object when present"]


def task_map(status_doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tasks, _ = normalize_tasks(status_doc)
    out: dict[str, dict[str, Any]] = {}
    for task in tasks:
        if isinstance(task, dict) and task.get("id") is not None:
            out[str(task["id"])] = task
    return out


def load_registry_text(root: Path) -> str:
    path = root / "agents" / "registry.yaml"
    if not path.exists():
        raise ValidationError("missing agents/registry.yaml")
    return path.read_text(encoding="utf-8")


def parse_review_1_selection(registry_text: str) -> tuple[dict[str, str], list[str]]:
    """Parse the small registry subset used for cross-review routing.

    The Harness keeps validate-stage.py dependency-free, so this intentionally
    parses only the machine-shaped lines used by rotation/model_policies.
    """
    explicit: dict[str, str] = {}
    for match in re.finditer(r"implementer_provider_([A-Za-z0-9_]+):\s*([A-Za-z0-9_]+)", registry_text):
        explicit[match.group(1)] = match.group(2)

    defaults: list[str] = []
    match = re.search(r"default_preference:\s*\[([^\]]+)\]", registry_text)
    if match:
        defaults = [item.strip().strip("'\"") for item in match.group(1).split(",") if item.strip()]
    return explicit, defaults


def expected_cross_reviewer(root: Path, implementer_provider: str | None) -> str | None:
    if not implementer_provider:
        return None
    explicit, defaults = parse_review_1_selection(load_registry_text(root))
    if implementer_provider in explicit:
        return explicit[implementer_provider]
    implementer_identity = provider_identity(implementer_provider)
    for candidate in defaults:
        if provider_identity(candidate) != implementer_identity:
            return candidate
    return None


def registry_has_embedded_review_command(root: Path, adapter: str) -> bool:
    registry_text = load_registry_text(root)
    in_adapter = False
    for line in registry_text.splitlines():
        if line.startswith("  ") and not line.startswith("    ") and line.strip().endswith(":"):
            in_adapter = line.strip() == f"{adapter}:"
            continue
        if in_adapter and line.startswith("    embedded_read_only_review_command:"):
            return True
    return False


def collect_implementer_identities(status_doc: dict[str, Any]) -> set[str]:
    identities: set[str] = set()
    implementer = status_doc.get("implementer")
    identity = provider_identity(implementer)
    if identity:
        identities.add(identity)

    for key in ("implementers", "fix_authors"):
        values = status_doc.get(key, [])
        if isinstance(values, list):
            for item in values:
                identity = provider_identity(item)
                if identity:
                    identities.add(identity)

    tasks, _ = normalize_tasks(status_doc)
    for task in tasks:
        if not isinstance(task, dict):
            continue
        for key in ("owner", "implementer", "fix_author"):
            identity = provider_identity(task.get(key))
            if identity:
                identities.add(identity)
    return identities


def collect_designer_identities(status_doc: dict[str, Any]) -> set[str]:
    identities: set[str] = set()
    for key in ("designer", "direction_synthesizer", "breakdown_author"):
        identity = provider_identity(status_doc.get(key))
        if identity:
            identities.add(identity)

    design = status_doc.get("design", {})
    if isinstance(design, dict):
        for key in ("designer", "direction_synthesizer", "breakdown_author"):
            identity = provider_identity(design.get(key))
            if identity:
                identities.add(identity)
    return identities


def review_selected_identity(review: dict[str, Any]) -> str | None:
    """Identity of the actually-selected reviewer.

    Probes only the fields that record a confirmed reviewer selection
    (reviewer / provider / selected_provider). It deliberately excludes
    primary_provider, which is an unselected preference (the preferred
    final-reviewer provider before selection) and must not be treated as the
    reviewer's provider identity for provider-isolation / designer-overlap
    checks. Using review_provider_identity() for those checks caused false
    designer-overlap failures whenever an unselected review_2.primary_provider
    happened to match the designer provider.
    """
    for key in ("reviewer", "provider", "selected_provider"):
        identity = provider_identity(review.get(key))
        if identity:
            return identity
    return None


def review_provider_identity(review: dict[str, Any]) -> str | None:
    """Full identity probing including the primary_provider preference.

    Use review_selected_identity() for provider-isolation and designer-overlap
    checks (before and around reviewer selection). This full probe is kept for
    validating a COMPLETED review whose every identity field is expected to be
    set; it must not drive isolation decisions because primary_provider is only
    a preference.
    """
    for key in ("reviewer", "provider", "selected_provider", "primary_provider"):
        identity = provider_identity(review.get(key))
        if identity:
            return identity
    return None


def evidence_path_exists(root: Path, stage_dir: Path, value: Any) -> bool:
    if not value:
        return False
    values = value if isinstance(value, list) else [value]
    for item in values:
        if not item:
            continue
        path = Path(str(item))
        candidates = []
        if path.is_absolute():
            candidates.append(path)
        else:
            candidates.extend([root / path, stage_dir / path])
        if any(candidate.exists() for candidate in candidates):
            return True
    return False


def validate_parallel_mode(root: Path, stage_dir: Path, status_doc: dict[str, Any], phase: str) -> list[str]:
    errors: list[str] = []

    tasks, task_shape_errors = normalize_tasks(status_doc)
    tasks_by_id = task_map(status_doc)
    errors.extend(task_shape_errors)
    for task in tasks:
        if isinstance(task, dict) and "embedded_reviews" in task:
            errors.append("parallel-mode embedded_reviews must be top-level status.embedded_reviews, not tasks[].embedded_reviews")

    parallel_mode = status_doc.get("parallel_mode", {})
    if parallel_mode in (None, {}):
        return errors
    if not isinstance(parallel_mode, dict):
        return ["parallel_mode must be an object when present"]
    if not truthy(parallel_mode.get("enabled")):
        embedded = status_doc.get("embedded_reviews", {})
        if embedded not in ({}, None):
            errors.append("embedded_reviews should be empty unless parallel_mode.enabled is true")
        return errors

    contract = parallel_mode.get("contract") or "docs/parallel-development-mode.md"
    if not evidence_path_exists(root, stage_dir, contract):
        errors.append(f"parallel_mode.contract does not exist: {contract}")
    if not truthy(parallel_mode.get("r10_dispatch_tail_required")):
        errors.append("parallel_mode.enabled requires r10_dispatch_tail_required=true")
    if not truthy(parallel_mode.get("r4_diff_reconciliation_required")):
        errors.append("parallel_mode.enabled requires r4_diff_reconciliation_required=true")

    embedded = status_doc.get("embedded_reviews")
    if not isinstance(embedded, dict):
        errors.append("parallel_mode.enabled requires top-level embedded_reviews object")
        return errors
    if phase in {"pre-review", "pre-accept"} and not embedded:
        errors.append("parallel_mode pre-review/pre-accept requires at least one embedded_reviews entry")

    for key, entry in embedded.items():
        prefix = f"embedded_reviews.{key}"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be an object")
            continue
        rounds = entry.get("rounds")
        if phase in {"pre-review", "pre-accept"} and (not isinstance(rounds, int) or rounds < 1):
            errors.append(f"{prefix}.rounds must be an integer >= 1 before review")

        for field in ("task_id", "scope", "implementer", "reviewer", "prompt_path"):
            if field not in entry:
                errors.append(f"{prefix} missing {field}")
        if entry.get("prompt_path") and not evidence_path_exists(root, stage_dir, entry.get("prompt_path")):
            errors.append(f"{prefix}.prompt_path does not exist: {entry.get('prompt_path')}")

        artifacts = entry.get("round_artifacts", [])
        if not isinstance(artifacts, list):
            errors.append(f"{prefix}.round_artifacts must be a list")
            continue
        if isinstance(rounds, int) and rounds > 0 and len(artifacts) < rounds:
            errors.append(f"{prefix}.round_artifacts has fewer entries than rounds")

        for artifact in artifacts:
            if not isinstance(artifact, dict):
                errors.append(f"{prefix}.round_artifacts entries must be objects")
                continue
            round_no = artifact.get("round", "?")
            for path_field in ("dispatch_path", "worktree_diff_path", "raw_output_path"):
                path_value = artifact.get(path_field)
                if not path_value:
                    errors.append(f"{prefix}.round_artifacts[{round_no}] missing {path_field}")
                elif not evidence_path_exists(root, stage_dir, path_value):
                    errors.append(f"{prefix}.round_artifacts[{round_no}].{path_field} does not exist: {path_value}")
            fix_report = artifact.get("fix_report_path")
            if fix_report and not evidence_path_exists(root, stage_dir, fix_report):
                errors.append(f"{prefix}.round_artifacts[{round_no}].fix_report_path does not exist: {fix_report}")

        if phase == "pre-accept":
            formal = entry.get("formal_review")
            if not isinstance(formal, dict):
                errors.append(f"{prefix}.formal_review is required before acceptance")
            else:
                for field in ("output", "base_sha", "head_sha", "diff_fingerprint", "verdict"):
                    if not formal.get(field):
                        errors.append(f"{prefix}.formal_review missing {field}")
                if formal.get("output") and not evidence_path_exists(root, stage_dir, formal.get("output")):
                    errors.append(f"{prefix}.formal_review.output does not exist: {formal.get('output')}")
                base_sha = formal.get("base_sha")
                head_sha = formal.get("head_sha")
                fingerprint = formal.get("diff_fingerprint")
                if base_sha and head_sha and fingerprint:
                    try:
                        require_commit(root, str(base_sha), f"{prefix}.formal_review.base_sha")
                        require_commit(root, str(head_sha), f"{prefix}.formal_review.head_sha")
                        expected = compute_diff_fingerprint(root, stage_dir, str(base_sha), str(head_sha))
                        if fingerprint != expected:
                            errors.append(f"{prefix}.formal_review diff_fingerprint mismatch: recorded={fingerprint}, expected={expected}")
                    except ValidationError as exc:
                        errors.append(str(exc))
                task_id = entry.get("task_id") or key
                task = tasks_by_id.get(str(task_id))
                if task and task.get("diff_fingerprint") and fingerprint and task.get("diff_fingerprint") != fingerprint:
                    errors.append(f"{prefix}.formal_review.diff_fingerprint must match task {task_id} diff_fingerprint")

    return errors


def validate_stage_branch(root: Path, status_doc: dict[str, Any], phase: str) -> list[str]:
    """Enforce stage branch rules only for stages that opt in via status.json."""
    errors: list[str] = []
    stage_branch = status_doc.get("stage_branch")
    if stage_branch in ({}, None):
        return errors
    if not isinstance(stage_branch, dict):
        return ["stage_branch must be an object when present"]

    name = stage_branch.get("name")
    if not name:
        return errors
    name = str(name)
    branch = current_branch(root)
    status = status_doc.get("status")
    merged_back = truthy(stage_branch.get("merged_back_to_main"))
    created_from_main_sha = stage_branch.get("created_from_main_sha")
    if not created_from_main_sha:
        errors.append("stage_branch.name requires stage_branch.created_from_main_sha")
    else:
        try:
            require_commit(root, str(created_from_main_sha), "stage_branch.created_from_main_sha")
        except ValidationError as exc:
            errors.append(str(exc))

    if status == "accepted" and merged_back:
        if branch != "main":
            errors.append(
                "accepted stage with stage_branch.merged_back_to_main=true must be rechecked on main"
            )
        if not stage_branch.get("merge_strategy"):
            errors.append("accepted merged stage requires stage_branch.merge_strategy")
        merged_back_sha = stage_branch.get("merged_back_sha")
        if not merged_back_sha:
            errors.append("accepted merged stage requires stage_branch.merged_back_sha")
        else:
            try:
                require_commit_in_current_history(root, str(merged_back_sha), "stage_branch.merged_back_sha")
            except ValidationError as exc:
                errors.append(str(exc))
        return errors

    if phase in {"checkpoint", "dispatch-ready", "pre-review", "pre-accept"} and branch != name:
        errors.append(
            f"{phase} requires current branch {name!r} for this stage, got {branch!r}"
        )

    if status in BRANCH_RETAINED_TERMINAL_STATUSES and branch == name:
        return errors

    return errors


def _checklist_for_task(status_doc: dict[str, Any], task: dict[str, Any]) -> dict[str, Any] | None:
    checklist = task.get("r10_checklist")
    if isinstance(checklist, dict):
        return checklist
    task_id = task.get("id")
    all_checklists = status_doc.get("r10_checklists", {})
    if isinstance(all_checklists, dict) and task_id is not None:
        value = all_checklists.get(str(task_id))
        if isinstance(value, dict):
            return value
    return None


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_dispatch_ready(root: Path, stage_dir: Path, status_doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    parallel_mode = status_doc.get("parallel_mode", {})
    if not isinstance(parallel_mode, dict) or not truthy(parallel_mode.get("enabled")):
        return errors

    for name in DISPATCH_READY_REQUIRED_FILES:
        if not (stage_dir / name).exists():
            errors.append(f"dispatch-ready missing required stage file: {name}")

    complexity = status_doc.get("complexity", {})
    classification = complexity.get("classification") if isinstance(complexity, dict) else None
    if classification in {"MEDIUM", "HIGH", "MILESTONE"} and not (stage_dir / "12-development-breakdown.md").exists():
        errors.append("dispatch-ready missing required stage file: 12-development-breakdown.md")

    tasks, task_shape_errors = normalize_tasks(status_doc)
    errors.extend(task_shape_errors)
    object_tasks = [task for task in tasks if isinstance(task, dict)]
    if len(object_tasks) < 2:
        errors.append("parallel dispatch-ready requires at least two task objects")

    for task in object_tasks:
        task_id = str(task.get("id", "<missing-id>"))
        prefix = f"task {task_id} r10_checklist"
        owner_provider = provider_key(task.get("owner") or task.get("implementer"))
        expected_reviewer = expected_cross_reviewer(root, owner_provider)
        checklist = _checklist_for_task(status_doc, task)
        if not isinstance(checklist, dict):
            errors.append(f"{prefix} missing; use tasks[].r10_checklist or r10_checklists.{task_id}")
            continue

        string_fields = [
            "task_prompt_path",
            "embedded_review_prompt_path",
            "self_tests_command",
            "diff_patch_command",
            "diff_patch_path",
            "cross_review_adapter",
            "cross_review_command_ref",
            "cross_review_raw_output_path",
            "cross_review_dispatch_path",
            "pass_branch",
            "blocker_branch",
        ]
        for field in string_fields:
            if not _nonempty_string(checklist.get(field)):
                errors.append(f"{prefix}.{field} must be a non-empty string")

        for path_field in ("task_prompt_path", "embedded_review_prompt_path"):
            value = checklist.get(path_field)
            if value and not evidence_path_exists(root, stage_dir, value):
                errors.append(f"{prefix}.{path_field} does not exist: {value}")

        diff_patch_path = checklist.get("diff_patch_path")
        if _nonempty_string(diff_patch_path) and not str(diff_patch_path).endswith(".diff.patch"):
            errors.append(f"{prefix}.diff_patch_path must end with .diff.patch")
        raw_output_path = checklist.get("cross_review_raw_output_path")
        if _nonempty_string(raw_output_path) and not str(raw_output_path).endswith(".raw-output.md"):
            errors.append(f"{prefix}.cross_review_raw_output_path must end with .raw-output.md")
        dispatch_path = checklist.get("cross_review_dispatch_path")
        if _nonempty_string(dispatch_path) and not str(dispatch_path).endswith(".dispatch.md"):
            errors.append(f"{prefix}.cross_review_dispatch_path must end with .dispatch.md")

        if expected_reviewer:
            adapter = checklist.get("cross_review_adapter")
            if adapter != expected_reviewer:
                errors.append(
                    f"{prefix}.cross_review_adapter must be {expected_reviewer!r} for implementer provider {owner_provider!r}, got {adapter!r}"
                )
            expected_ref = f"agents/registry.yaml#adapters.{expected_reviewer}.embedded_read_only_review_command"
            if checklist.get("cross_review_command_ref") != expected_ref:
                errors.append(f"{prefix}.cross_review_command_ref must be {expected_ref!r}")
            if not registry_has_embedded_review_command(root, expected_reviewer):
                errors.append(f"registry missing adapters.{expected_reviewer}.embedded_read_only_review_command")
        elif owner_provider:
            errors.append(f"{prefix}: no cross-review reviewer can be derived for implementer provider {owner_provider!r}")
        else:
            errors.append(f"{prefix}: missing task owner/implementer provider")

        if checklist.get("next_dispatch_executor") != "self":
            errors.append(f"{prefix}.next_dispatch_executor must be 'self'")
        if checklist.get("manual_user_handoff_allowed") is not False:
            errors.append(f"{prefix}.manual_user_handoff_allowed must be false")
        if checklist.get("max_rounds") != 2:
            errors.append(f"{prefix}.max_rounds must be 2")

        unavailable = checklist.get("unavailable_branch")
        if not isinstance(unavailable, dict):
            errors.append(f"{prefix}.unavailable_branch must be an object")
        else:
            classes = unavailable.get("failure_classes")
            if not isinstance(classes, list) or not classes:
                errors.append(f"{prefix}.unavailable_branch.failure_classes must be a non-empty list")
            else:
                unknown = [item for item in classes if item not in EMBEDDED_CHECKPOINT_FAILURE_CLASSES]
                if unknown:
                    errors.append(f"{prefix}.unavailable_branch.failure_classes contains unknown values: {unknown}")
            artifact = unavailable.get("escalation_artifact")
            if not _nonempty_string(artifact) or not str(artifact).endswith(".dispatch.md"):
                errors.append(f"{prefix}.unavailable_branch.escalation_artifact must be a .dispatch.md path")

    return errors


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


def itbm_enabled(status_doc: dict[str, Any]) -> bool:
    mode = status_doc.get("independent_task_branch_mode", {})
    return isinstance(mode, dict) and truthy(mode.get("enabled"))


def validate_itbm_required_files(stage_dir: Path, status_doc: dict[str, Any], phase: str) -> list[str]:
    """Task-local evidence mapping for independent task-branch mode (decision D)."""
    errors: list[str] = []
    if not (stage_dir / "70-handoff.md").exists():
        errors.append("missing required stage file: 70-handoff.md")
    tasks, _ = normalize_tasks(status_doc)
    for task in tasks:
        if not isinstance(task, dict) or task.get("id") is None:
            continue
        tid = str(task["id"])
        ev = stage_dir / "evidence" / tid
        for name in ("checkpoint.json", "30-review-1.md"):
            if not (ev / name).exists():
                errors.append(f"missing task-local evidence: evidence/{tid}/{name}")
    return errors


def validate_required_files(stage_dir: Path, status_doc: dict[str, Any], phase: str) -> list[str]:
    if itbm_enabled(status_doc):
        return validate_itbm_required_files(stage_dir, status_doc, phase)
    required = ["00-task.md", "10-design.md", "11-adr.md", "20-implementation.md", "60-test-output.txt", "70-handoff.md"]
    complexity = status_doc.get("complexity", {})
    classification = complexity.get("classification") if isinstance(complexity, dict) else None
    if status_doc.get("workflow") == "stage-delivery" and classification in {"MEDIUM", "HIGH", "MILESTONE"}:
        required.append("12-development-breakdown.md")
    if phase == "pre-accept":
        required += ["30-review-1.md", "50-review-2.md"]
    missing = [name for name in required if not (stage_dir / name).exists()]
    return [f"missing required stage file: {name}" for name in missing]


def validate_itbm_dispatch_ready(root: Path, stage_dir: Path, status_doc: dict[str, Any]) -> list[str]:
    """dispatch-ready gate for independent task-branch mode (decision B: own flag).

    validate_dispatch_ready() no-ops without parallel_mode.enabled, so the frozen
    allowed_scope / forbidden-path checks are re-implemented under this flag.
    """
    if not itbm_enabled(status_doc):
        return []
    errors: list[str] = []
    tasks, shape = normalize_tasks(status_doc)
    errors.extend(shape)
    object_tasks = [t for t in tasks if isinstance(t, dict)]
    if len(object_tasks) < 2:
        errors.append("independent_task_branch_mode dispatch-ready requires at least two tasks")
    for task in object_tasks:
        tid = str(task.get("id", "<missing-id>"))
        if not task.get("branch"):
            errors.append(f"task {tid}: missing branch")
        scope = task.get("allowed_scope")
        if not isinstance(scope, dict):
            errors.append(f"task {tid}: allowed_scope must be an object")
            continue
        if not scope.get("product_paths"):
            errors.append(f"task {tid}: allowed_scope.product_paths must be non-empty (frozen pre-dispatch)")
        if scope.get("allow_harness_change") is not False:
            errors.append(f"task {tid}: product task allow_harness_change must be false (decision E)")
    return errors


def validate_review_identity(root: Path, stage_dir: Path, status_doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    implementer_identities = collect_implementer_identities(status_doc)
    designer_identities = collect_designer_identities(status_doc)

    review_1 = status_doc.get("review_1", {})
    if isinstance(review_1, dict):
        identity = review_selected_identity(review_1)
        if identity and identity in implementer_identities:
            errors.append("review_1 provider identity must differ from implementation/fix author provider identity")

    review_2 = status_doc.get("review_2", {})
    if not isinstance(review_2, dict):
        return errors

    reviewer_identity = review_selected_identity(review_2)
    if reviewer_identity and reviewer_identity in implementer_identities:
        errors.append("review_2 provider identity must differ from every implementation/fix author provider identity; no override is allowed")

    if reviewer_identity and reviewer_identity in designer_identities:
        involvement = review_2.get("reviewer_prior_involvement")
        if involvement not in REVIEWER_PRIOR_INVOLVEMENTS or involvement == "none":
            errors.append("review_2 designer-overlap override requires reviewer_prior_involvement to be direction_synthesis, breakdown, or design")
        if not review_2.get("fallback_reason"):
            errors.append("review_2 designer-overlap override requires fallback_reason")

        override = review_2.get("design_conflict_override", {})
        evidence = None
        if isinstance(override, dict):
            evidence = (
                override.get("unrelated_reviewer_unavailable_evidence")
                or override.get("evidence_file")
                or override.get("evidence_files")
            )
        evidence = evidence or review_2.get("unrelated_reviewer_unavailable_evidence") or review_2.get("override_evidence_file")
        if not evidence_path_exists(root, stage_dir, evidence):
            errors.append("review_2 designer-overlap override requires an existing unrelated reviewer unavailable evidence file")

    for key in ("review_1", "review_2"):
        review = status_doc.get(key, {})
        if not isinstance(review, dict):
            continue
        attempts = review.get("invalid_json_attempts")
        if isinstance(attempts, int) and attempts > 2:
            errors.append(f"{key}.invalid_json_attempts exceeds the per-model limit of 2")
    return errors


def validate_tasks(root: Path, stage_dir: Path, status_doc: dict[str, Any], task_id: str | None) -> list[str]:
    errors: list[str] = []
    tasks, task_shape_errors = normalize_tasks(status_doc)
    errors.extend(task_shape_errors)
    if task_shape_errors:
        return errors

    selected = tasks
    if task_id:
        selected = [task for task in tasks if isinstance(task, dict) and task.get("id") == task_id]
        if not selected:
            return [f"task not found in status.json tasks: {task_id}"]

    for task in selected:
        if not isinstance(task, dict):
            errors.append("each task entry must be an object")
            continue
        prefix = f"task {task.get('id', '<missing-id>')}"
        if "_invalid_task_value" in task:
            errors.append(f"{prefix}: task value must be an object")
            continue
        owner_identity = provider_identity(task.get("owner") or task.get("implementer"))
        review = task.get("review_1", {})
        reviewer_identity = review_provider_identity(review) if isinstance(review, dict) else None
        if owner_identity and reviewer_identity and owner_identity == reviewer_identity:
            errors.append(f"{prefix}: review_1 provider identity must differ from owner/implementer provider identity")

        for field in ("base_sha", "head_sha", "diff_fingerprint"):
            if task.get(field) and not isinstance(task.get(field), str):
                errors.append(f"{prefix}: {field} must be a string")
        if task.get("base_sha") and task.get("head_sha") and task.get("diff_fingerprint"):
            try:
                require_commit(root, task["base_sha"], f"{prefix}.base_sha")
                require_commit(root, task["head_sha"], f"{prefix}.head_sha")
                expected = compute_diff_fingerprint(root, stage_dir, task["base_sha"], task["head_sha"])
                if task["diff_fingerprint"] != expected:
                    errors.append(f"{prefix}: diff_fingerprint mismatch: recorded={task['diff_fingerprint']}, expected={expected}")
            except ValidationError as exc:
                errors.append(str(exc))
    return errors


def validate_acceptance(root: Path, stage_dir: Path, status_doc: dict[str, Any]) -> list[str]:
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
    errors.extend(validate_review_identity(root, stage_dir, status_doc))
    errors.extend(validate_tasks(root, stage_dir, status_doc, None))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an AI Project Harness stage")
    parser.add_argument("stage", help="stage id or path under reports/agent-runs")
    parser.add_argument(
        "--phase",
        choices=["dispatch-ready", "pre-review", "pre-accept", "checkpoint"],
        default="checkpoint",
    )
    parser.add_argument("--task", help="optional task id for task-level fingerprint and cross-review checks")
    parser.add_argument(
        "--evidence-out",
        help="write the validation output to this path only when validation passes; "
        "never written on failure so a dirty-worktree or other failure is not masked",
    )
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
        errors.extend(validate_stage_branch(root, status_doc, args.phase))
        errors.extend(validate_parallel_mode(root, stage_dir, status_doc, args.phase))
        if args.phase == "dispatch-ready":
            errors.extend(validate_dispatch_ready(root, stage_dir, status_doc))
            errors.extend(validate_itbm_dispatch_ready(root, stage_dir, status_doc))
        if args.phase in {"pre-review", "pre-accept"}:
            errors.extend(validate_required_files(stage_dir, status_doc, args.phase))
            errors.extend(validate_tasks(root, stage_dir, status_doc, args.task))
            if args.phase == "pre-review":
                errors.extend(validate_review_identity(root, stage_dir, status_doc))
        if args.phase == "pre-accept":
            errors.extend(validate_acceptance(root, stage_dir, status_doc))

        if errors:
            output = "STAGE VALIDATION FAILED\n" + "\n".join(f"- {err}" for err in errors) + "\n"
            print(output, end="")
            return 1

        try:
            stage_label = str(stage_dir.relative_to(root))
        except ValueError:
            stage_label = str(stage_dir)
        lines = [
            "STAGE VALIDATION PASSED",
            f"stage={stage_label}",
            f"phase={args.phase}",
            f"status={status_doc.get('status')}",
        ]
        if status_doc.get("diff_fingerprint"):
            lines.append(f"diff_fingerprint={status_doc['diff_fingerprint']}")
        output = "\n".join(lines) + "\n"
        print(output, end="")

        # Evidence capture (F4): write the output only after every check passed.
        # A dirty-worktree or any other failure returns above, so this file is
        # never created to mask a real failure. This lets stage operators use
        # `validate-stage.py --phase pre-review --evidence-out <path>` instead of
        # `... | tee <path>`, which would dirty the worktree before the
        # clean-worktree check on the next run.
        if args.evidence_out:
            evidence_path = Path(args.evidence_out)
            if not evidence_path.is_absolute():
                evidence_path = (Path.cwd() / evidence_path)
            evidence_path.parent.mkdir(parents=True, exist_ok=True)
            evidence_path.write_text(output)
        return 0
    except ValidationError as exc:
        print("STAGE VALIDATION FAILED")
        print(f"- {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
