#!/usr/bin/env python3
"""Shared review-artifact protocol v1 (`raw-plus-strict-json/v1`) helpers.

One standard-library-only module implements the schema-v1 verdict semantics
used by both the human-invoked capture CLI below and `scripts/validate-stage.py`.

Protocol v1 binds every formal review gate to two files inside the stage
evidence directory:

  - `<base>[-retry-N].raw-output.md`   exact captured stdout of one
    human-launched review adapter; must decode as exactly one JSON object with
    only JSON transport whitespace around it.
  - `<base>[-retry-N].verdict.json`    deterministic canonical serialization of
    that same object; no fences, no prose, no surrounding bytes, no trailing
    newline.

Frozen base names: serial Review-1 `30-review-1`, task Review-1
`30-review-1-<task-id>`, Review-2 `50-review-2`. `-retry-N` uses a positive
integer N.

Capture CLI (human-invoked, capture-only):

    python3 scripts/review_artifacts.py capture \
        --raw <already-captured-raw-file> \
        --verdict <verdict-output-path> \
        --schema schemas/review-verdict.schema.json \
        --producer-exit-status <adapter exit code captured by the operator> \
        [--session-id <id> --session-id-source <source>]

The helper never selects a model, never imports adapter registries, never
spawns a subprocess, never edits stage state, never commits, never retries, and
never advances the workflow. It consumes one already-captured raw file, refuses
to overwrite an existing verdict, publishes the canonical verdict atomically
(temp file + fsync + hard-link no-clobber, so a concurrent writer cannot be
silently clobbered), and prints a mechanical receipt. A non-zero producer exit
status fails the attempt; the raw file is retained as attempt evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

PROTOCOL_V1 = "raw-plus-strict-json/v1"

SERIAL_REVIEW_1_BASE = "30-review-1"
REVIEW_2_BASE = "50-review-2"
RAW_SUFFIX = ".raw-output.md"
VERDICT_SUFFIX = ".verdict.json"
_RETRY_RE = r"(?:-retry-(?P<retry>[1-9][0-9]*))?"
_TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")

# Schema-v1 vocabulary (mirrors schemas/review-verdict.schema.json; the fixture
# corpus in scripts/tests/test_review_artifacts.py compares this implementation
# against the schema file through the optional `jsonschema` oracle).
VERDICT_TOP_LEVEL_KEYS = {
    "schema_version",
    "stage_id",
    "role",
    "model",
    "verdict",
    "diff_fingerprint",
    "reviewer_prior_involvement",
    "reviewer_prior_involvement_notes",
    "reviewed_artifacts",
    "findings",
    "required_fixes",
    "residual_risks",
    "fix_start_prompt",
    "next_action",
}
VERDICT_REQUIRED_KEYS = [
    "schema_version",
    "stage_id",
    "role",
    "model",
    "verdict",
    "diff_fingerprint",
    "reviewer_prior_involvement",
    "reviewed_artifacts",
    "findings",
    "required_fixes",
    "next_action",
]
ROLES = {"designer_review", "first_reviewer", "final_reviewer", "reality_checker"}
VERDICTS = {"ACCEPT", "REWORK", "BLOCKED"}
INVOLVEMENTS = {"none", "direction_synthesis", "breakdown", "design"}
NEXT_ACTIONS = {
    "continue",
    "fix",
    "human_gate",
    "retry",
    "fallback",
    "decision_models_exhausted",
    "development_models_exhausted",
    "stage_accepted_waiting_user",
    "human_escalation_required",
}
SEVERITIES = {"P0", "P1", "P2", "P3"}
FINDING_KEYS = {"severity", "title", "file", "line", "evidence", "impact", "recommendation"}
FINDING_REQUIRED_KEYS = ["severity", "title", "evidence", "impact", "recommendation"]


class CaptureError(Exception):
    pass


def canonical_verdict_bytes(obj: dict[str, Any]) -> bytes:
    """Deterministic canonical JSON bytes: sorted keys, minimal separators,
    UTF-8, no surrounding bytes and no terminal newline."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _is_string(value: Any) -> bool:
    return isinstance(value, str)


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and len(value) >= 1


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def parse_single_json_object(data: bytes, label: str) -> tuple[dict[str, Any] | None, list[str]]:
    """Decode bytes as exactly one JSON object.

    Only JSON transport whitespace (space, tab, CR, LF) may surround the
    object. Markdown fences, prose, BOM, extra documents, or non-object roots
    are all invalid."""
    if not data:
        return None, [f"{label} is empty"]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, [f"{label} is not valid UTF-8: {exc}"]
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, [f"{label} is not exactly one JSON document: {exc}"]
    if not isinstance(obj, dict):
        return None, [f"{label} must decode to a JSON object, got {type(obj).__name__}"]
    return obj, []


def validate_verdict_object(obj: Any) -> list[str]:
    """Standard-library enforcement of schema-v1 semantics for review verdicts."""
    if not isinstance(obj, dict):
        return ["verdict must be a JSON object"]
    errors: list[str] = []

    for key in sorted(set(obj) - VERDICT_TOP_LEVEL_KEYS):
        errors.append(f"unknown property not allowed: {key}")
    for key in VERDICT_REQUIRED_KEYS:
        if key not in obj:
            errors.append(f"missing required property: {key}")

    if "schema_version" in obj and (not _is_integer(obj["schema_version"]) or obj["schema_version"] != 1):
        errors.append("schema_version must be the integer constant 1")
    if "stage_id" in obj and not _is_nonempty_string(obj["stage_id"]):
        errors.append("stage_id must be a non-empty string")
    if "role" in obj and obj["role"] not in ROLES:
        errors.append(f"role must be one of {sorted(ROLES)}")
    if "model" in obj and not _is_nonempty_string(obj["model"]):
        errors.append("model must be a non-empty string")
    if "verdict" in obj and obj["verdict"] not in VERDICTS:
        errors.append(f"verdict must be one of {sorted(VERDICTS)}")
    if "diff_fingerprint" in obj and not _is_nonempty_string(obj["diff_fingerprint"]):
        errors.append("diff_fingerprint must be a non-empty string")
    if "reviewer_prior_involvement" in obj and obj["reviewer_prior_involvement"] not in INVOLVEMENTS:
        errors.append(f"reviewer_prior_involvement must be one of {sorted(INVOLVEMENTS)}")
    if "reviewer_prior_involvement_notes" in obj and not _is_string(obj["reviewer_prior_involvement_notes"]):
        errors.append("reviewer_prior_involvement_notes must be a string")

    if "reviewed_artifacts" in obj:
        artifacts = obj["reviewed_artifacts"]
        if not isinstance(artifacts, list):
            errors.append("reviewed_artifacts must be an array")
        else:
            if len(artifacts) < 1:
                errors.append("reviewed_artifacts must have at least 1 item")
            for idx, item in enumerate(artifacts):
                if not _is_nonempty_string(item):
                    errors.append(f"reviewed_artifacts[{idx}] must be a non-empty string")

    if "findings" in obj:
        findings = obj["findings"]
        if not isinstance(findings, list):
            errors.append("findings must be an array")
        else:
            for idx, finding in enumerate(findings):
                errors.extend(_validate_finding(finding, f"findings[{idx}]"))

    for key in ("required_fixes", "residual_risks"):
        if key in obj:
            values = obj[key]
            if not isinstance(values, list):
                errors.append(f"{key} must be an array")
            else:
                for idx, item in enumerate(values):
                    if not _is_string(item):
                        errors.append(f"{key}[{idx}] must be a string")

    if "fix_start_prompt" in obj and not _is_nonempty_string(obj["fix_start_prompt"]):
        errors.append("fix_start_prompt must be a non-empty string")
    if obj.get("verdict") == "REWORK" and "fix_start_prompt" not in obj:
        errors.append("verdict REWORK requires fix_start_prompt")
    if "next_action" in obj and obj["next_action"] not in NEXT_ACTIONS:
        errors.append(f"next_action must be one of {sorted(NEXT_ACTIONS)}")

    return errors


def _validate_finding(finding: Any, prefix: str) -> list[str]:
    if not isinstance(finding, dict):
        return [f"{prefix} must be an object"]
    errors: list[str] = []
    for key in sorted(set(finding) - FINDING_KEYS):
        errors.append(f"{prefix}: unknown property not allowed: {key}")
    for key in FINDING_REQUIRED_KEYS:
        if key not in finding:
            errors.append(f"{prefix}: missing required property: {key}")
    if "severity" in finding and finding["severity"] not in SEVERITIES:
        errors.append(f"{prefix}.severity must be one of {sorted(SEVERITIES)}")
    for key in ("title", "evidence", "impact", "recommendation"):
        if key in finding and not _is_nonempty_string(finding[key]):
            errors.append(f"{prefix}.{key} must be a non-empty string")
    if "file" in finding and not _is_string(finding["file"]):
        errors.append(f"{prefix}.file must be a string")
    if "line" in finding:
        line = finding["line"]
        if line is not None and (not _is_integer(line) or line < 1):
            errors.append(f"{prefix}.line must be null or an integer >= 1")
    return errors


def review_base_name(kind: str, task_id: str | None = None) -> str:
    """Frozen protocol base name for a review kind.

    kind: 'review_1_serial', 'review_1_task' (requires task_id), 'review_2'."""
    if kind == "review_1_serial":
        return SERIAL_REVIEW_1_BASE
    if kind == "review_1_task":
        if not task_id or not _TASK_ID_RE.match(str(task_id)):
            raise ValueError(f"invalid task id for review artifact name: {task_id!r}")
        return f"{SERIAL_REVIEW_1_BASE}-{task_id}"
    if kind == "review_2":
        return REVIEW_2_BASE
    raise ValueError(f"unknown review artifact kind: {kind!r}")


def match_protocol_filename(name: str, kind: str, task_id: str | None, suffix: str) -> str | None:
    """Return the attempt label ('' for the base attempt, 'retry-N' for a
    retry) when `name` is exactly the frozen protocol filename for this review,
    else None."""
    base = review_base_name(kind, task_id)
    pattern = f"^{re.escape(base)}{_RETRY_RE}{re.escape(suffix)}$"
    match = re.match(pattern, name)
    if not match:
        return None
    retry = match.group("retry")
    return f"retry-{retry}" if retry else ""


def resolve_stage_local_artifact(
    root: Path,
    stage_dir: Path,
    value: Any,
    kind: str,
    task_id: str | None,
    suffix: str,
    field: str,
) -> tuple[Path | None, str | None, list[str]]:
    """Resolve a status-selected artifact path to a file inside the stage
    directory whose name is exactly the frozen protocol name or a positive
    `-retry-N` variant.

    Accepts a bare filename or the exact repo-relative stage path. Absolute
    paths, traversal, and any other directory are rejected.

    Returns (path, attempt_label, errors)."""
    if not _is_nonempty_string(value):
        return None, None, [f"{field} must be a non-empty string path"]
    text = str(value)
    if Path(text).is_absolute() or text.startswith("~"):
        return None, None, [f"{field} must be stage-local, got absolute path: {text}"]
    stage_rel = stage_dir.relative_to(root).as_posix()
    if "/" in text or "\\" in text:
        normalized = text.replace("\\", "/")
        prefix = f"{stage_rel}/"
        if not normalized.startswith(prefix) or "/" in normalized[len(prefix):]:
            return None, None, [f"{field} must stay inside the stage directory: {text}"]
        name = normalized[len(prefix):]
    else:
        name = text
    if name in ("", ".", ".."):
        return None, None, [f"{field} must name a stage-local file: {text}"]
    attempt = match_protocol_filename(name, kind, task_id, suffix)
    if attempt is None:
        return None, None, [
            f"{field} must match the frozen protocol name "
            f"'{review_base_name(kind, task_id)}[-retry-N]{suffix}', got {name!r}"
        ]
    path = stage_dir / name
    if path.resolve().parent != stage_dir.resolve():
        return None, None, [f"{field} escapes the stage directory: {text}"]
    return path, attempt, []


def load_and_parse_pair(
    raw_path: Path, verdict_path: Path, prefix: str
) -> tuple[dict[str, Any] | None, list[str]]:
    """Parse a raw/verdict pair and enforce the mechanical binding.

    Raw must decode as exactly one JSON object with transport whitespace only.
    Verdict bytes must equal the deterministic canonical serialization of the
    verdict's own decoded object (so no fences, prose, surrounding bytes, key
    reordering, or trailing newline). Both decoded objects must be equal, and
    the object must satisfy schema-v1.

    Returns (verdict_object, errors); verdict_object is None when the pair
    cannot be established."""
    errors: list[str] = []
    for label, path in ((f"{prefix} raw output", raw_path), (f"{prefix} verdict", verdict_path)):
        if not path.is_file():
            errors.append(f"{label} file does not exist: {path}")
    if errors:
        return None, errors

    raw_obj, raw_errors = parse_single_json_object(raw_path.read_bytes(), f"{prefix} raw output")
    errors.extend(raw_errors)

    verdict_bytes = verdict_path.read_bytes()
    verdict_obj, verdict_errors = parse_single_json_object(verdict_bytes, f"{prefix} verdict")
    errors.extend(verdict_errors)
    if verdict_obj is not None and verdict_bytes != canonical_verdict_bytes(verdict_obj):
        errors.append(
            f"{prefix} verdict bytes are not the deterministic canonical JSON serialization "
            "(sorted keys, minimal separators, UTF-8, no surrounding bytes or trailing newline)"
        )

    if raw_obj is None or verdict_obj is None:
        return None, errors
    if raw_obj != verdict_obj:
        errors.append(f"{prefix} raw output and verdict decode to different JSON objects")
        return None, errors

    schema_errors = validate_verdict_object(verdict_obj)
    errors.extend(f"{prefix} verdict schema-v1: {msg}" for msg in schema_errors)
    if errors:
        return None, errors
    return verdict_obj, []


def publish_bytes_no_clobber(path: Path, data: bytes) -> None:
    """Atomically publish `data` at `path`, failing if `path` already exists.

    Uses temp file + flush + fsync + hard link. The link itself is the atomic
    no-clobber publication, so a destination created concurrently between any
    two steps cannot be overwritten. The temp file is always cleaned up."""
    parent = path.parent
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.tmp-", dir=str(parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(tmp_name, path)
        except FileExistsError:
            raise CaptureError(
                f"refusing to overwrite existing verdict: {path} "
                "(use a new -retry-N attempt path)"
            ) from None
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def capture(args: argparse.Namespace) -> int:
    raw_path = Path(args.raw)
    verdict_path = Path(args.verdict)
    schema_path = Path(args.schema)
    failures: list[str] = []

    if not schema_path.is_file():
        failures.append(f"schema file does not exist: {schema_path}")
    else:
        try:
            json.loads(schema_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            failures.append(f"schema file is not valid JSON: {exc}")

    if args.producer_exit_status != 0:
        failures.append(
            f"producer exit status is {args.producer_exit_status}; the review attempt failed. "
            "The raw file is retained as attempt evidence; no verdict is published."
        )

    raw_bytes = b""
    if not raw_path.is_file():
        failures.append(f"raw output file does not exist: {raw_path}")
    else:
        raw_bytes = raw_path.read_bytes()
        if not raw_bytes.strip():
            failures.append(f"raw output file is empty: {raw_path}")

    obj: dict[str, Any] | None = None
    if not failures:
        obj, parse_errors = parse_single_json_object(raw_bytes, "raw output")
        failures.extend(parse_errors)
        if obj is not None:
            failures.extend(f"schema-v1: {msg}" for msg in validate_verdict_object(obj))

    if not failures and verdict_path.exists():
        failures.append(
            f"refusing to overwrite existing verdict: {verdict_path} "
            "(use a new -retry-N attempt path)"
        )

    verdict_bytes = b""
    if not failures and obj is not None:
        verdict_bytes = canonical_verdict_bytes(obj)
        try:
            publish_bytes_no_clobber(verdict_path, verdict_bytes)
        except (CaptureError, OSError) as exc:
            failures.append(str(exc))

    if failures:
        print("CAPTURE FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("CAPTURE OK")
    print(f"raw_path={raw_path}")
    print(f"raw_bytes={len(raw_bytes)}")
    print(f"raw_sha256={sha256_hex(raw_bytes)}")
    print(f"verdict_path={verdict_path}")
    print(f"verdict_bytes={len(verdict_bytes)}")
    print(f"verdict_sha256={sha256_hex(verdict_bytes)}")
    print(f"schema={schema_path}")
    print("schema_v1_semantics=PASS")
    print(f"producer_exit_status={args.producer_exit_status}")
    assert obj is not None
    print(f"stage_id={obj.get('stage_id')}")
    print(f"verdict={obj.get('verdict')}")
    print(f"session_id={args.session_id or 'unavailable (not provided by operator)'}")
    print(f"session_id_source={args.session_id_source or 'unavailable'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Protocol-v1 review artifact capture helper")
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture_parser = subparsers.add_parser(
        "capture",
        help="normalize one already-captured raw review output into a canonical verdict file",
    )
    capture_parser.add_argument("--raw", required=True, help="already-captured raw stdout file")
    capture_parser.add_argument("--verdict", required=True, help="canonical verdict output path")
    capture_parser.add_argument("--schema", required=True, help="schemas/review-verdict.schema.json")
    capture_parser.add_argument(
        "--producer-exit-status",
        required=True,
        type=int,
        help="exit status of the human-launched review adapter, captured by the operator",
    )
    capture_parser.add_argument("--session-id", default=None, help="operator-verified session id, if any")
    capture_parser.add_argument(
        "--session-id-source", default=None, help="session id source per docs/model-adapters.md"
    )
    args = parser.parse_args(argv)
    if args.command == "capture":
        return capture(args)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
