"""Shared helpers for the independent task-branch mode scripts.

Dependency-free (stdlib only), so that record-checkpoint, prepare-review-2, and
validate-stage.py can all pin the SAME canonical fingerprint invocation
(decision C: keep the canonical formula unchanged but pin the exact git call
across every recompute site).
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


class ItbmError(Exception):
    pass


def git(args: list[str], *, cwd: Path, text: bool = True) -> str | bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
    )
    if result.returncode != 0:
        err = result.stderr if text else result.stderr.decode("utf-8", "replace")
        raise ItbmError(f"git {' '.join(args)} failed:\n{err.strip()}")
    return result.stdout


def rev_parse(ref: str, *, cwd: Path) -> str:
    return str(git(["rev-parse", ref], cwd=cwd)).strip()


def status_rel(stage_id: str) -> str:
    return f"reports/agent-runs/{stage_id}/status.json"


def canonical_fingerprint(repo: Path, base: str, head: str, stage_id: str) -> str:
    """head_sha + ':' + sha256(canonical binary diff), status.json excluded.

    Pinned invocation (decision C): `git -c diff.renames=true diff --binary
    base..head -- . :(exclude)<top status.json>`. diff.renames=true is git's
    default, so this does not change existing recorded fingerprints; pinning it
    makes the three recompute sites byte-identical regardless of local config.
    """
    diff = git(
        [
            "-c",
            "diff.renames=true",
            "diff",
            "--binary",
            f"{base}..{head}",
            "--",
            ".",
            f":(exclude){status_rel(stage_id)}",
        ],
        cwd=repo,
        text=False,
    )
    return f"{head}:{hashlib.sha256(diff).hexdigest()}"


def product_rebind_hash(repo: Path, base: str, head: str, product_paths: list[str]) -> str:
    """Non-binding product-only hash for the integration rebind assertion.

    Uses --no-renames for byte-level reproducibility, restricted to the frozen
    product pathspecs. Never used as a gate fingerprint.
    """
    diff = git(
        ["diff", "--binary", "--no-renames", f"{base}..{head}", "--", *product_paths],
        cwd=repo,
        text=False,
    )
    return hashlib.sha256(diff).hexdigest()


def changed_files(repo: Path, base: str, head: str) -> list[str]:
    out = str(git(["diff", "--name-only", f"{base}..{head}"], cwd=repo))
    return [line.strip() for line in out.splitlines() if line.strip()]


def worktree_changed_files(worktree: Path) -> list[str]:
    """Uncommitted (staged + unstaged + untracked) paths in a worktree.

    --untracked-files=all lists individual untracked files instead of collapsing
    new directories, so scope checks see full file paths.
    """
    out = str(git(["status", "--porcelain", "--untracked-files=all"], cwd=worktree))
    files: list[str] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        # porcelain v1: XY <path> (or "orig -> path" for renames)
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append(path.strip())
    return files


PROTECTED_HARNESS_PATHS = (
    "AGENTS.md",
    "workflows/",
    "agents/registry.yaml",
    "docs/model-adapters.md",
    "docs/parallel-development-mode.md",
    "scripts/",
    "schemas/",
)


def hits_protected_path(path: str) -> bool:
    return any(path == p or path.startswith(p) for p in PROTECTED_HARNESS_PATHS)


def path_in_scope(path: str, product_paths: list[str], evidence_prefix: str) -> bool:
    if path.startswith(evidence_prefix):
        return True
    for p in product_paths:
        # product_paths are git pathspecs; support "dir" and "dir/**" forms.
        prefix = p[:-3] if p.endswith("/**") else p
        prefix = prefix.rstrip("/")
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return False
