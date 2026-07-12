#!/usr/bin/env python3
"""Stdlib-only tests for ``scripts/harness_stage_lib.py``.

This module also owns the shared helpers imported by the sibling test modules
(``test_stage_seal.py``, ``test_validate_stage_auto_review.py``):

- ``make_temp_repo`` — isolated throwaway git repository constructor;
- ``VALID_AUTH`` / ``VALID_RECEIPT`` / ``REVIEW_1_VALID_RECEIPTS`` — complete
  positive fixtures for the hand-written structural validators.

No ``conftest.py``, no ``__init__.py``, no separate fixtures module (the shared
helper lives here, per the T2 writable set).
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import harness_stage_lib as lib  # noqa: E402

REPO_ROOT = _SCRIPTS.parent


# ---------------------------------------------------------------------------
# shared helpers / fixtures (imported by sibling test modules)
# ---------------------------------------------------------------------------

def make_temp_repo():
    """Return ``(root, git)`` for an isolated throwaway git repository.

    Isolation: ``GIT_CONFIG_NOSYSTEM=1``, ``HOME`` redirected under the temp
    dir, no network (``GIT_TERMINAL_PROMPT=0``), and a deterministic identity
    via explicit ``-c user.name/user.email`` on every command.
    """
    tmp = tempfile.mkdtemp(prefix="harness-test-")
    root = Path(tmp)
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["HOME"] = str(root / "home")
    (root / "home").mkdir()
    env["GIT_TERMINAL_PROMPT"] = "0"

    def git(*args):
        result = subprocess.run(
            ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", *args],
            cwd=str(root), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        if result.returncode != 0:
            raise AssertionError(
                "git " + " ".join(args) + " failed: " + result.stderr.strip()
            )
        return result.stdout

    git("init", "-q")
    git("commit", "-q", "--allow-empty", "-m", "init")
    return root, git


VALID_AUTH = {
    "schema_version": 1,
    "stage_id": "2026-07-auto-review-pipeline-v1",
    "stage_branch": "stage/2026-07-auto-review-pipeline-v1",
    "contract_version": "auto-review-pipeline/v1",
    "authorized_by": "human",
    "approval_evidence_path": "reports/agent-runs/2026-07-auto-review-pipeline-v1/05-authorization.md",
    "approval_recorded_by": "operator",
    "authorized_at": "2026-07-11T00:00:00Z",
    "expires_at": None,
    "scope": {
        "task_ids": ["T1"],
        "allowed_pathspecs": ["scripts/x.py"],
        "forbidden_pathspecs": ["secrets/y.env"],
    },
    "budgets": {
        "max_model_calls": 20,
        "max_auto_code_changes": 2,
    },
    "supersedes": None,
}

VALID_RECEIPT = {
    "schema_version": 1,
    "stage_id": "2026-07-auto-review-pipeline-v1",
    "sequence": 1,
    "node": "implementation",
    "attempt": 1,
    "review_unit_id": "T1",
    "task_id": "T1",
    "adapter": {
        "id": "claude_glm",
        "registry_command_ref": "agents/registry.yaml#adapters.claude_glm.noninteractive_command",
    },
    "prompt_path": "reports/agent-runs/2026-07-auto-review-pipeline-v1/task-T1.prompt.md",
    "raw_output_path": "reports/agent-runs/2026-07-auto-review-pipeline-v1/10-design.md",
    "verdict_path": None,
    "started_at": "2026-07-11T00:00:00Z",
    "completed_at": "2026-07-11T00:10:00Z",
    "exit_status": 0,
    "timeout": False,
    "call_budget": {"before": 20, "after": 19},
    "failure_class": None,
    "next_transition": "embedded_cross_check",
}


def _receipt_with(node, adapter_id, ref):
    r = copy.deepcopy(VALID_RECEIPT)
    r["node"] = node
    r["adapter"] = {"id": adapter_id, "registry_command_ref": ref}
    return r


REVIEW_1_VALID_RECEIPTS = [
    _receipt_with("review_1", "grok", "agents/registry.yaml#adapters.grok.optional_review_command"),
    _receipt_with("review_1", "kimi", "agents/registry.yaml#adapters.kimi.embedded_read_only_review_command"),
    _receipt_with("review_1", "claude_glm", "agents/registry.yaml#adapters.claude_glm.embedded_read_only_review_command"),
]


# ---------------------------------------------------------------------------
# diff fingerprint — double anchor regression
# ---------------------------------------------------------------------------

class DiffFingerprintTests(unittest.TestCase):
    def test_anchor_this_stage_t1_range(self):
        """Anchor 1: this stage's T1-sealed range, recomputed verbatim."""
        stage = REPO_ROOT / "reports/agent-runs/2026-07-auto-review-pipeline-v1"
        fp = lib.compute_diff_fingerprint(
            REPO_ROOT, stage,
            "a385c7ad77da1611c6e952b2219aee56b49f442f",
            "25383e86d0b10b3e8bd3e0f51254588826c9601b",
        )
        self.assertEqual(
            fp,
            "25383e86d0b10b3e8bd3e0f51254588826c9601b:"
            "242cff3040ac66e79ce2dbb5a13dab6bf92043765884ed9f0288cf8decc80486",
        )

    def test_anchor_historical_accepted_stage(self):
        """Anchor 2: a historical accepted stage with a complete status fingerprint.

        ``2026-07-borrow-cost-coverage-v2`` is accepted with matching stage-level
        base/head/fingerprint; recomputing must reproduce the recorded digest.
        """
        stage = REPO_ROOT / "reports/agent-runs/2026-07-borrow-cost-coverage-v2"
        fp = lib.compute_diff_fingerprint(
            REPO_ROOT, stage,
            "5bdfc4b3dc6843a8e52aeb86896c735500ed137a",
            "11c3935ec859320b5dad50d31c0068993b4bd8f5",
        )
        self.assertEqual(
            fp,
            "11c3935ec859320b5dad50d31c0068993b4bd8f5:"
            "2a73b681d0ae77f3d2d9d9eaed04f977be44dd1996a3bffef3ca8dfa52b7d401",
        )


# ---------------------------------------------------------------------------
# code-scope patch capture / byte equality
# ---------------------------------------------------------------------------

class CodeScopePatchTests(unittest.TestCase):
    def setUp(self):
        self.root, self.git = make_temp_repo()
        (self.root / "scripts").mkdir()
        (self.root / "scripts" / "a.py").write_text("x = 1\n", encoding="utf-8")
        self.git("add", "scripts/a.py")
        self.git("commit", "-q", "-m", "base")
        self.base = self.git("rev-parse", "HEAD").strip()
        # working-tree change is the "seen" patch (not yet committed)
        (self.root / "scripts" / "a.py").write_text("x = 2\n", encoding="utf-8")

    def test_capture_then_regenerate_byte_equal(self):
        captured = lib.capture_code_scope_patch(self.root, self.base, ["scripts/a.py"])
        self.git("add", "scripts/a.py")
        self.git("commit", "-q", "-m", "change")
        head = self.git("rev-parse", "HEAD").strip()
        regenerated = lib.capture_code_scope_patch(
            self.root, self.base + ".." + head, ["scripts/a.py"]
        )
        self.assertTrue(lib.patches_byte_equal(captured, regenerated))

    def test_byte_equal_detects_difference(self):
        self.assertFalse(lib.patches_byte_equal(b"abc", b"abd"))
        self.assertTrue(lib.patches_byte_equal(b"abc", b"abc"))


# ---------------------------------------------------------------------------
# atomic JSON IO
# ---------------------------------------------------------------------------

class AtomicWriteTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def test_write_creates_valid_json(self):
        p = Path(self.dir) / "out.json"
        lib.atomic_write_json(p, {"a": 1})
        self.assertEqual(json.loads(p.read_text(encoding="utf-8")), {"a": 1})

    def test_write_replaces_existing(self):
        p = Path(self.dir) / "out.json"
        lib.atomic_write_json(p, {"old": True})
        lib.atomic_write_json(p, {"new": True})
        self.assertEqual(json.loads(p.read_text(encoding="utf-8")), {"new": True})


# ---------------------------------------------------------------------------
# provider identity normalization
# ---------------------------------------------------------------------------

class ProviderTests(unittest.TestCase):
    def test_identity_normalization_superset(self):
        self.assertEqual(lib.provider_identity("gemini"), "google")
        self.assertEqual(lib.provider_identity("claude_fable5"), "anthropic")
        self.assertEqual(lib.provider_identity("fable5"), "anthropic")
        self.assertEqual(lib.provider_identity("glm"), "zhipu_glm")
        self.assertEqual(lib.provider_identity("grok"), "xai_grok")
        self.assertEqual(lib.provider_identity("kimi"), "moonshot_kimi")

    def test_identity_passthrough_and_none(self):
        self.assertEqual(lib.provider_identity("unknown_vendor"), "unknown_vendor")
        self.assertIsNone(lib.provider_identity(None))

    def test_identity_from_dict(self):
        self.assertEqual(
            lib.provider_identity({"runtime_provider_identity": "kimi"}), "moonshot_kimi"
        )


# ---------------------------------------------------------------------------
# safe path resolution
# ---------------------------------------------------------------------------

class SafePathTests(unittest.TestCase):
    def test_reject_absolute(self):
        self.assertFalse(lib.is_safe_repo_relative_path("/etc/passwd"))

    def test_reject_traversal(self):
        self.assertFalse(lib.is_safe_repo_relative_path("../x"))
        self.assertFalse(lib.is_safe_repo_relative_path("a/../b"))

    def test_reject_control_chars(self):
        self.assertFalse(lib.is_safe_repo_relative_path("a\nb"))
        self.assertFalse(lib.is_safe_repo_relative_path("a\tb"))

    def test_accept_normal(self):
        self.assertTrue(lib.is_safe_repo_relative_path("scripts/a.py"))

    def test_nullable_none(self):
        self.assertTrue(lib.is_safe_repo_relative_path(None, nullable=True))
        self.assertFalse(lib.is_safe_repo_relative_path(None, nullable=False))

    def test_resolve_raises_on_traversal(self):
        with self.assertRaises(lib.HarnessError):
            lib.resolve_safe_path(REPO_ROOT, "../outside")

    def test_resolve_returns_path(self):
        resolved = lib.resolve_safe_path(REPO_ROOT, "scripts/a.py")
        self.assertEqual(resolved, (REPO_ROOT / "scripts" / "a.py").resolve())


# ---------------------------------------------------------------------------
# ISO8601 parsing
# ---------------------------------------------------------------------------

class Iso8601Tests(unittest.TestCase):
    def test_z_suffix_and_offset(self):
        self.assertTrue(lib.is_iso8601("2026-07-11T00:00:00Z"))
        self.assertTrue(lib.is_iso8601("2026-07-11T00:00:00+08:00"))

    def test_invalid(self):
        self.assertFalse(lib.is_iso8601("not-a-date"))
        self.assertFalse(lib.is_iso8601(None))


# ---------------------------------------------------------------------------
# authorization structural validator
# ---------------------------------------------------------------------------

class AuthorizationValidatorTests(unittest.TestCase):
    def test_positive(self):
        self.assertEqual(lib.validate_authorization_doc(copy.deepcopy(VALID_AUTH)), [])

    def test_expires_at_null_ok(self):
        d = copy.deepcopy(VALID_AUTH)
        d["expires_at"] = None
        self.assertEqual(lib.validate_authorization_doc(d), [])

    def test_missing_expires_at(self):
        d = copy.deepcopy(VALID_AUTH)
        d.pop("expires_at")
        errs = lib.validate_authorization_doc(d)
        self.assertTrue(any("expires_at" in e for e in errs))

    def test_expires_at_bad_timestamp(self):
        d = copy.deepcopy(VALID_AUTH)
        d["expires_at"] = "tomorrow"
        errs = lib.validate_authorization_doc(d)
        self.assertTrue(any("expires_at" in e for e in errs))

    def test_absolute_approval_evidence_path(self):
        d = copy.deepcopy(VALID_AUTH)
        d["approval_evidence_path"] = "/etc/passwd"
        errs = lib.validate_authorization_doc(d)
        self.assertTrue(any("approval_evidence_path" in e for e in errs))

    def test_traversal_approval_evidence_path(self):
        d = copy.deepcopy(VALID_AUTH)
        d["approval_evidence_path"] = "../escape.md"
        errs = lib.validate_authorization_doc(d)
        self.assertTrue(any("approval_evidence_path" in e for e in errs))

    def test_newline_approval_evidence_path(self):
        d = copy.deepcopy(VALID_AUTH)
        d["approval_evidence_path"] = "a\nb.md"
        errs = lib.validate_authorization_doc(d)
        self.assertTrue(any("approval_evidence_path" in e for e in errs))

    def test_empty_task_ids(self):
        d = copy.deepcopy(VALID_AUTH)
        d["scope"]["task_ids"] = []
        errs = lib.validate_authorization_doc(d)
        self.assertTrue(any("task_ids" in e for e in errs))

    def test_auto_changes_over_two(self):
        d = copy.deepcopy(VALID_AUTH)
        d["budgets"]["max_auto_code_changes"] = 3
        errs = lib.validate_authorization_doc(d)
        self.assertTrue(any("max_auto_code_changes" in e for e in errs))

    def test_authorized_by_not_human(self):
        d = copy.deepcopy(VALID_AUTH)
        d["authorized_by"] = "model"
        errs = lib.validate_authorization_doc(d)
        self.assertTrue(any("authorized_by" in e for e in errs))

    def test_contract_version_wrong(self):
        d = copy.deepcopy(VALID_AUTH)
        d["contract_version"] = "wrong/v2"
        errs = lib.validate_authorization_doc(d)
        self.assertTrue(any("contract_version" in e for e in errs))

    # serial-v1 slim shape: every withdrawn field must fail as unknown
    # (additionalProperties: false). There is no compatibility-normalization
    # path because v1 has not been accepted, merged, or piloted.
    def test_removed_authorized_flag_is_unknown(self):
        d = copy.deepcopy(VALID_AUTH)
        d["authorized"] = True
        errs = lib.validate_authorization_doc(d)
        self.assertTrue(any("authorized" in e for e in errs))

    def test_removed_allowed_adapters_is_unknown(self):
        d = copy.deepcopy(VALID_AUTH)
        d["allowed_adapters"] = ["claude_glm"]
        errs = lib.validate_authorization_doc(d)
        self.assertTrue(any("allowed_adapters" in e for e in errs))

    def test_removed_review_1_provider_is_unknown(self):
        d = copy.deepcopy(VALID_AUTH)
        d["review_1_provider"] = "kimi"
        errs = lib.validate_authorization_doc(d)
        self.assertTrue(any("review_1_provider" in e for e in errs))

    def test_removed_auto_high_end_dispatch_allowed_is_unknown(self):
        d = copy.deepcopy(VALID_AUTH)
        d["auto_high_end_dispatch_allowed"] = False
        errs = lib.validate_authorization_doc(d)
        self.assertTrue(any("auto_high_end_dispatch_allowed" in e for e in errs))

    def test_removed_scope_topology_is_unknown(self):
        d = copy.deepcopy(VALID_AUTH)
        d["scope"]["topology"] = "serial"
        errs = lib.validate_authorization_doc(d)
        self.assertTrue(any("topology" in e for e in errs))

    def test_removed_wall_clock_seconds_is_unknown(self):
        d = copy.deepcopy(VALID_AUTH)
        d["budgets"]["wall_clock_seconds"] = 3600
        errs = lib.validate_authorization_doc(d)
        self.assertTrue(any("wall_clock_seconds" in e for e in errs))

    def test_removed_max_stage_rework_is_unknown(self):
        d = copy.deepcopy(VALID_AUTH)
        d["budgets"]["max_stage_rework"] = 3
        errs = lib.validate_authorization_doc(d)
        self.assertTrue(any("max_stage_rework" in e for e in errs))

    def test_removed_invalid_json_max_attempts_is_unknown(self):
        d = copy.deepcopy(VALID_AUTH)
        d["budgets"]["invalid_json_max_attempts_per_model"] = 2
        errs = lib.validate_authorization_doc(d)
        self.assertTrue(any("invalid_json_max_attempts_per_model" in e for e in errs))


# ---------------------------------------------------------------------------
# receipt structural validator
# ---------------------------------------------------------------------------

class ReceiptValidatorTests(unittest.TestCase):
    def test_positive_implementation(self):
        self.assertEqual(lib.validate_receipt_doc(copy.deepcopy(VALID_RECEIPT)), [])

    def test_review_1_three_valid_pairs(self):
        for r in REVIEW_1_VALID_RECEIPTS:
            self.assertEqual(lib.validate_receipt_doc(r), [], msg=str(r["adapter"]))

    def test_review_1_mismatched_pair(self):
        d = copy.deepcopy(VALID_RECEIPT)
        d["node"] = "review_1"
        d["adapter"] = {
            "id": "grok",
            "registry_command_ref": "agents/registry.yaml#adapters.claude_glm.embedded_read_only_review_command",
        }
        errs = lib.validate_receipt_doc(d)
        self.assertTrue(any("review_1" in e for e in errs))

    def test_call_budget_mismatch(self):
        d = copy.deepcopy(VALID_RECEIPT)
        d["call_budget"] = {"before": 20, "after": 18}
        errs = lib.validate_receipt_doc(d)
        self.assertTrue(any("call_budget" in e for e in errs))

    def test_bookkeeper_decision_unknown_field_rejected(self):
        # bookkeeper_decision is not a schema property; additionalProperties
        # is false, so the validator must reject it as unknown.
        d = copy.deepcopy(VALID_RECEIPT)
        d["bookkeeper_decision"] = "accept"
        errs = lib.validate_receipt_doc(d)
        self.assertTrue(any("unknown" in e for e in errs))

    def test_node_invalid(self):
        d = copy.deepcopy(VALID_RECEIPT)
        d["node"] = "bogus"
        errs = lib.validate_receipt_doc(d)
        self.assertTrue(any("node" in e for e in errs))

    def test_next_transition_invalid(self):
        d = copy.deepcopy(VALID_RECEIPT)
        d["next_transition"] = "teleport"
        errs = lib.validate_receipt_doc(d)
        self.assertTrue(any("next_transition" in e for e in errs))

    def test_embedded_cross_check_valid(self):
        d = copy.deepcopy(VALID_RECEIPT)
        d["node"] = "embedded_cross_check"
        d["adapter"] = {
            "id": "claude_glm",
            "registry_command_ref": "agents/registry.yaml#adapters.claude_glm.embedded_read_only_review_command",
        }
        self.assertEqual(lib.validate_receipt_doc(d), [])


if __name__ == "__main__":
    unittest.main()
