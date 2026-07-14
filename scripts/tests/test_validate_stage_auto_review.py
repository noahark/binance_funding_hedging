#!/usr/bin/env python3
"""Stdlib-only tests for the ``auto_review_pipeline`` validation in
``scripts/validate-stage.py``.

Two groups:

1. **Manual regression matrix** — legacy status without a truthy
   ``auto_review_pipeline.enabled`` never triggers auto validation, so the
   manual path is byte-for-byte unchanged. Includes the real status snapshot
   of THIS bootstrap stage as one fixture.
2. **Auto positive + fail-closed faces** — a clean auto status passes, and
   each violation surface is reported in isolation.

``validate-stage.py`` is loaded via ``importlib.util.spec_from_file_location``
(its filename contains a hyphen). No new file is created.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import harness_stage_lib as lib  # noqa: E402
from test_harness_stage_lib import VALID_AUTH  # noqa: E402

REPO_ROOT = _SCRIPTS.parent
THIS_STAGE_DIR = REPO_ROOT / "reports" / "agent-runs" / "2026-07-auto-review-pipeline-v1"


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_stage_under_test", _SCRIPTS / "validate-stage.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_root_with_auth():
    tmp = tempfile.mkdtemp(prefix="auto-review-")
    root = Path(tmp)
    stage_dir = root / "reports" / "agent-runs" / "auto-stage"
    stage_dir.mkdir(parents=True)
    (stage_dir / "auth.json").write_text(json.dumps(VALID_AUTH), encoding="utf-8")
    return root, stage_dir


def _auto_status(auth_rel="reports/agent-runs/auto-stage/auth.json"):
    return {
        "stage_id": "auto-stage",
        "auto_review_pipeline": {
            "enabled": True,
            "schema_version": 1,
            "runner_version": "auto-review-pipeline/v1",
            "runner_host": {
                "id": "human_operator",
                "provider_identity": "human",
                "role": "runner_host",
                "switch_requires": "explicit_human_instruction",
                "session_isolation": "human_shell_start_and_watch_only",
            },
            "dispatch_mode": "auto_review",
            "runner_state": "running",
            "authorization_path": auth_rel,
            "budgets": {
                "model_calls_used": 0,
                "auto_code_changes_used": 0,
            },
            "mode_history": [
                {
                    "from": {"dispatch_mode": "human_dispatch", "runner_state": None},
                    "to": {"dispatch_mode": "auto_review", "runner_state": "authorized"},
                    "event": "new_human_authorization",
                },
                {
                    "from": {"dispatch_mode": "auto_review", "runner_state": "authorized"},
                    "to": {"dispatch_mode": "auto_review", "runner_state": "running"},
                    "event": "successful_full_preflight",
                },
            ],
            "review_units": [
                {
                    "id": "T1",
                    "kind": "task",
                    "required": True,
                    "author_provider_identities": [{"id": "claude_glm"}],
                    "diff_fingerprint": "h:d",
                    "review_1": {
                        "verdict": "ACCEPT",
                        "json_schema_valid": True,
                        "diff_fingerprint": "h:d",
                    },
                }
            ],
        },
    }


class ManualRegressionMatrixTests(unittest.TestCase):
    """Legacy status without enabled auto_review_pipeline stays manual."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_validator()

    def test_no_auto_field(self):
        self.assertFalse(self.mod.auto_review_enabled({}))
        self.assertFalse(self.mod.auto_review_enabled({"status": "checkpoint"}))

    def test_auto_disabled(self):
        self.assertFalse(
            self.mod.auto_review_enabled({"auto_review_pipeline": {"enabled": False}})
        )

    def test_auto_missing_enabled_key(self):
        self.assertFalse(
            self.mod.auto_review_enabled({"auto_review_pipeline": {"dispatch_mode": "auto_review"}})
        )

    def test_enabled_for_this_stage_alone_is_not_auto(self):
        # the bootstrap control does not by itself trigger auto validation
        self.assertFalse(
            self.mod.auto_review_enabled({"auto_review_pipeline": {"enabled_for_this_stage": True}})
        )

    def test_this_stage_real_snapshot_is_manual(self):
        status_path = THIS_STAGE_DIR / "status.json"
        if not status_path.exists():
            self.skipTest("this stage status.json not present")
        status = lib.load_json(status_path)
        self.assertFalse(self.mod.auto_review_enabled(status))

    def test_fingerprint_delegates_to_shared_lib(self):
        # compute_diff_fingerprint delegates behaviour to harness_stage_lib
        # (single implementation path): both must return the identical digest.
        base = "a385c7ad77da1611c6e952b2219aee56b49f442f"
        head = "25383e86d0b10b3e8bd3e0f51254588826c9601b"
        via_validator = self.mod.compute_diff_fingerprint(REPO_ROOT, THIS_STAGE_DIR, base, head)
        via_lib = lib.compute_diff_fingerprint(REPO_ROOT, THIS_STAGE_DIR, base, head)
        self.assertEqual(via_validator, via_lib)
        self.assertIn("25383e86d0b10b3e8bd3e0f51254588826c9601b:", via_validator)

    def test_manual_common_still_callable_on_legacy_status(self):
        errs = self.mod.validate_common(REPO_ROOT, THIS_STAGE_DIR, {"status": "bogus"}, "checkpoint")
        self.assertTrue(any("status is not allowed" in e for e in errs))

    def test_disabled_representation_enabled_false_human_dispatch_null(self):
        # the disabled machine representation must NOT read as auto-enabled
        status = {"auto_review_pipeline": {"enabled": False, "dispatch_mode": "human_dispatch", "runner_state": None}}
        self.assertFalse(self.mod.auto_review_enabled(status))


class AutoValidationPositiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_validator()

    def test_auto_positive_clean(self):
        root, stage_dir = _make_root_with_auth()
        status = _auto_status()
        errs = self.mod.validate_auto_review_pipeline(root, stage_dir, status, "pre-review")
        self.assertEqual(errs, [], msg="\n".join(errs))

    def test_human_dispatch_disabled_representation_passes(self):
        # enabled + human_dispatch + null runner_state is a valid disabled rep
        root, stage_dir = _make_root_with_auth()
        status = _auto_status()
        status["auto_review_pipeline"]["dispatch_mode"] = "human_dispatch"
        status["auto_review_pipeline"]["runner_state"] = None
        status["auto_review_pipeline"]["mode_history"] = []
        errs = self.mod.validate_auto_review_pipeline(root, stage_dir, status, "checkpoint")
        self.assertEqual(errs, [], msg="\n".join(errs))


class AutoValidationFailClosedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_validator()

    def _check(self, mutate_arp, phase="pre-review", mutate_status=None):
        root, stage_dir = _make_root_with_auth()
        status = _auto_status()
        mutate_arp(status["auto_review_pipeline"])
        if mutate_status is not None:
            mutate_status(status)
        return self.mod.validate_auto_review_pipeline(root, stage_dir, status, phase)

    def test_unknown_runner_state(self):
        errs = self._check(lambda a: a.__setitem__("runner_state", "teleporting"))
        self.assertTrue(any("runner_state" in e for e in errs))

    def test_unknown_transition(self):
        def mutate(a):
            a["mode_history"].append({
                "from": {"dispatch_mode": "auto_review", "runner_state": "running"},
                "to": {"dispatch_mode": "auto_review", "runner_state": "running"},
                "event": "bogus_event",
            })
        errs = self._check(mutate)
        self.assertTrue(any("transition set" in e for e in errs))

    def test_discontinuous_transition_history(self):
        def mutate(a):
            a["mode_history"].append({
                "from": {"dispatch_mode": "human_dispatch", "runner_state": None},
                "to": {"dispatch_mode": "auto_review", "runner_state": "authorized"},
                "event": "new_human_authorization",
            })
        errs = self._check(mutate)
        self.assertTrue(any("discontinuous" in e for e in errs))

    def test_history_final_state_must_match_current_state(self):
        errs = self._check(lambda a: a.__setitem__("runner_state", "awaiting_human"))
        self.assertTrue(any("final state" in e for e in errs))

    def test_budget_used_exceeds_max_auto(self):
        errs = self._check(lambda a: a["budgets"].__setitem__("auto_code_changes_used", 3))
        self.assertTrue(any("auto_code_changes_used" in e for e in errs))

    def test_status_budget_max_auto_is_unknown(self):
        # serial-only v1: caps live in the authorization; a status budgets copy
        # carrying max_auto_code_changes is rejected as an unknown field.
        errs = self._check(lambda a: a["budgets"].__setitem__("max_auto_code_changes", 3))
        self.assertTrue(any("max_auto_code_changes" in e for e in errs))

    def test_status_budget_max_stage_rework_is_unknown(self):
        # serial-only v1: max_stage_rework is a global invariant, not a status
        # budgets field; carrying it in status is rejected as an unknown field.
        errs = self._check(lambda a: a["budgets"].__setitem__("max_stage_rework", 4))
        self.assertTrue(any("max_stage_rework" in e for e in errs))

    def test_rework_count_exceeds_global_invariant(self):
        # max_stage_rework is enforced as a global invariant (3) on the
        # top-level rework_count ledger (shared with review-2 repair).
        errs = self._check(
            lambda a: None,
            mutate_status=lambda s: s.__setitem__("rework_count", 4),
        )
        self.assertTrue(any("rework_count" in e for e in errs))

    def test_mutex_with_parallel_mode(self):
        errs = self._check(
            lambda a: None,
            mutate_status=lambda s: s.__setitem__("parallel_mode", {"enabled": True}),
        )
        self.assertTrue(any("mutually exclusive" in e for e in errs))

    def test_missing_authorization_path(self):
        errs = self._check(lambda a: a.__setitem__("authorization_path", "reports/agent-runs/auto-stage/missing.json"))
        self.assertTrue(any("authorization_path" in e for e in errs))

    def test_schema_version_wrong(self):
        errs = self._check(lambda a: a.__setitem__("schema_version", 2))
        self.assertTrue(any("schema_version" in e for e in errs))

    def test_runner_version_wrong(self):
        errs = self._check(lambda a: a.__setitem__("runner_version", "v2"))
        self.assertTrue(any("runner_version" in e for e in errs))

    def test_runner_host_rejects_legacy_kimi_model_host(self):
        def use_legacy_kimi_host(arp):
            arp["runner_host"] = {
                "id": "kimi",
                "provider_identity": "moonshot_kimi",
                "role": "runner_host",
                "switch_requires": "explicit_human_instruction",
                "session_isolation": "host_only_no_implementation_fix_review",
            }

        errs = self._check(use_legacy_kimi_host)
        self.assertTrue(any("runner_host" in e and "human-operator" in e for e in errs))

    def test_dispatch_mode_invalid(self):
        errs = self._check(lambda a: a.__setitem__("dispatch_mode", "telepathy"))
        self.assertTrue(any("dispatch_mode" in e for e in errs))

    def test_review_unit_lacks_accept(self):
        def mutate(a):
            a["review_units"][0]["review_1"]["verdict"] = "REWORK"
        errs = self._check(mutate, phase="pre-review")
        self.assertTrue(any("ACCEPT" in e for e in errs))

    def test_review_unit_schema_invalid(self):
        def mutate(a):
            a["review_units"][0]["review_1"]["json_schema_valid"] = False
        errs = self._check(mutate, phase="pre-review")
        self.assertTrue(any("schema-valid" in e for e in errs))

    def test_review_unit_kind_invalid(self):
        def mutate(a):
            a["review_units"][0]["kind"] = "bogus"
        errs = self._check(mutate, phase="pre-review")
        self.assertTrue(any("kind" in e for e in errs))

    def test_authorization_doc_invalid(self):
        # authorization present but structurally invalid -> fail closed
        root, stage_dir = _make_root_with_auth()
        # overwrite auth.json with an invalid doc (bad contract_version)
        bad = json.loads((stage_dir / "auth.json").read_text(encoding="utf-8"))
        bad["contract_version"] = "wrong/v2"
        (stage_dir / "auth.json").write_text(json.dumps(bad), encoding="utf-8")
        status = _auto_status()
        errs = self.mod.validate_auto_review_pipeline(root, stage_dir, status, "pre-review")
        self.assertTrue(any("authorization:" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
