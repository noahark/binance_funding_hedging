#!/usr/bin/env python3
"""Stdlib-only integration tests for ``scripts/stage-seal.py``.

Uses the shared ``make_temp_repo`` / ``VALID_AUTH`` fixtures from the sibling
``test_harness_stage_lib`` module. ``stage-seal.py`` is loaded via importlib
(its filename contains a hyphen).

The seal flow's step 9 (``run_validator`` -> ``validate-stage --phase
pre-review``) is replaced with a fake that asserts its call contract (clean
worktree, the stage id). Building a status that *also* satisfies the full
manual pre-review contract is a separate concern exercised by
``test_validate_stage_auto_review.py`` and the frozen suite; here the focus is
the nine-step seal protocol itself: the two commits, the fingerprint landing
in status, fail-closed on blocking/bind, and crash recovery.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import harness_stage_lib as lib  # noqa: E402
from test_harness_stage_lib import make_temp_repo, VALID_AUTH  # noqa: E402


def _load_stage_seal():
    spec = importlib.util.spec_from_file_location(
        "stage_seal_under_test", _SCRIPTS / "stage-seal.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


STAGE_REL = "reports/agent-runs/test-stage"


def _make_seal_env(*, with_seen=True, dirty_code=True):
    """Build an isolated repo + stage dir ready for a nine-step seal.

    Returns (root, git, stage_dir, status_doc, unit). ``status_doc`` and
    ``unit`` share the review-unit object, so mutating ``unit`` then calling
    ``_rewrite_status`` propagates the change.
    """
    root, git = make_temp_repo()
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "a.py").write_text("x = 1\n", encoding="utf-8")
    git("add", "scripts/a.py")
    git("commit", "-q", "-m", "base")
    base_sha = git("rev-parse", "HEAD").strip()
    git("checkout", "-q", "-b", "stage/test")
    stage_dir = root / STAGE_REL
    stage_dir.mkdir(parents=True)
    for name in ("00-task.md", "10-design.md", "11-adr.md", "20-implementation.md", "60-test-output.txt", "70-handoff.md"):
        (stage_dir / name).write_text("stub\n", encoding="utf-8")
    auth = copy.deepcopy(VALID_AUTH)
    auth["stage_id"] = "test-stage"
    auth["stage_branch"] = "stage/test"
    auth["scope"]["allowed_pathspecs"] = ["scripts/**"]
    (stage_dir / "auth.json").write_text(json.dumps(auth), encoding="utf-8")
    # Commit the stage evidence so the seal preflight sees a clean evidence
    # tree: at seal time only code-scope changes (and freshly-written bind/
    # status artifacts under the stage dir) should be dirty. In a real stage
    # the evidence is already in the base commit; this mirrors that.
    git("add", STAGE_REL)
    git("commit", "-q", "-m", "stage-evidence")
    if dirty_code:
        (root / "scripts" / "a.py").write_text("x = 2\n", encoding="utf-8")
    seen_rel = STAGE_REL + "/seen.patch"
    if with_seen:
        seen_bytes = lib.capture_code_scope_patch(root, base_sha, ["scripts/a.py"])
        (root / seen_rel).write_bytes(seen_bytes)
    unit = {
        "id": "T1",
        "kind": "task",
        "base_sha": base_sha,
        "code_pathspecs": ["scripts/a.py"],
        "blocking_checks": {
            "commands": ["python3 -m py_compile scripts/a.py"],
            "evidence_exclude_pathspecs": [STAGE_REL + "/"],
            "first_pass": {"exit_status": 0, "ran_at": "2026-07-11T00:00:00Z"},
            "second_pass": {"exit_status": 0, "ran_after_cross_check": True, "ran_at": "2026-07-11T00:01:00Z"},
        },
        "embedded_cross_check": {
            "required_attempt": True,
            "status": "ran" if with_seen else "unavailable",
            "seen_patch_path": seen_rel if with_seen else None,
            "bind_status": "n/a",
        },
    }
    status_doc = {
        "stage_id": "test-stage",
        "stage_branch": {"name": "stage/test", "base": base_sha},
        "auto_review_pipeline": {
            "enabled": True,
            "authorization_path": STAGE_REL + "/auth.json",
            "review_units": [unit],
        },
    }
    lib.atomic_write_json(stage_dir / "status.json", status_doc)
    return root, git, stage_dir, status_doc, unit


class _SealTestBase(unittest.TestCase):
    def setUp(self):
        env = _make_seal_env()
        self.root, self.git, self.stage_dir, self.status_doc, self.unit = env
        self.base_sha = self.unit["base_sha"]
        self.seal = _load_stage_seal()
        self.validator_calls = []
        # step 9 is replaced with a contract-asserting no-op
        self.seal.run_validator = self._fake_validator

    def _fake_validator(self, root, stage_id):
        self.validator_calls.append(stage_id)
        dirty = self.seal._porcelain(root)
        assert not dirty, "worktree must be clean before validate-stage"

    def _rewrite_status(self):
        lib.atomic_write_json(self.stage_dir / "status.json", self.status_doc)


class SealHappyPathTests(_SealTestBase):
    def test_nine_step_seal_two_commits_and_fingerprint(self):
        result = self.seal.seal(self.root, self.stage_dir, "T1")
        self.assertFalse(result["recovered"])
        log = self.git("log", "--format=%s")
        self.assertEqual(log.count("H_snapshot"), 1)
        self.assertEqual(log.count("H_bind"), 1)
        status2 = lib.load_json(self.stage_dir / "status.json")
        unit2 = status2["auto_review_pipeline"]["review_units"][0]
        self.assertEqual(unit2["snapshot_commit"], result["head_sha"])
        self.assertEqual(unit2["diff_fingerprint"], result["diff_fingerprint"])
        self.assertEqual(unit2["embedded_cross_check"]["bind_status"], "bound")
        self.assertEqual(self.validator_calls, ["test-stage"])

    def test_extra_stage_evidence_does_not_change_bind(self):
        # an extra evidence file under the stage dir must not perturb the
        # code-scope bind (capture only walks code_pathspecs)
        (self.stage_dir / "99-extra-evidence.txt").write_text("noise\n", encoding="utf-8")
        result = self.seal.seal(self.root, self.stage_dir, "T1")
        self.assertFalse(result["recovered"])
        status2 = lib.load_json(self.stage_dir / "status.json")
        self.assertEqual(
            status2["auto_review_pipeline"]["review_units"][0]["embedded_cross_check"]["bind_status"],
            "bound",
        )

    def test_seal_receipt_is_not_a_runner_receipt(self):
        self.seal.seal(self.root, self.stage_dir, "T1")
        receipt = lib.load_json(self.stage_dir / "runner-1-seal.receipt.json")
        for forbidden in ("adapter", "node", "sequence", "attempt", "call_budget", "failure_class", "next_transition"):
            self.assertNotIn(forbidden, receipt)
        self.assertEqual(receipt["kind"], "seal")
        self.assertEqual(receipt["schema_version"], 1)
        self.assertIn("bind_status", receipt)
        self.assertIn("blocking_second_pass", receipt)


class SealBlockingStepTests(_SealTestBase):
    def test_first_pass_failed_refuses(self):
        self.unit["blocking_checks"]["first_pass"]["exit_status"] = 1
        self._rewrite_status()
        with self.assertRaises(self.seal.SealError):
            self.seal.seal(self.root, self.stage_dir, "T1")

    def test_embedded_cross_check_missing_refuses(self):
        self.unit.pop("embedded_cross_check")
        self._rewrite_status()
        with self.assertRaises(self.seal.SealError):
            self.seal.seal(self.root, self.stage_dir, "T1")

    def test_second_pass_missing_refuses(self):
        self.unit["blocking_checks"].pop("second_pass")
        self._rewrite_status()
        with self.assertRaises(self.seal.SealError):
            self.seal.seal(self.root, self.stage_dir, "T1")

    def test_second_pass_failed_refuses(self):
        self.unit["blocking_checks"]["second_pass"]["exit_status"] = 1
        self._rewrite_status()
        with self.assertRaises(self.seal.SealError):
            self.seal.seal(self.root, self.stage_dir, "T1")

    def test_second_pass_not_after_cross_check_refuses(self):
        self.unit["blocking_checks"]["second_pass"]["ran_after_cross_check"] = False
        self._rewrite_status()
        with self.assertRaises(self.seal.SealError):
            self.seal.seal(self.root, self.stage_dir, "T1")

    def test_evidence_exclude_missing_refuses(self):
        self.unit["blocking_checks"]["evidence_exclude_pathspecs"] = ["other/"]
        self._rewrite_status()
        with self.assertRaises(self.seal.SealError):
            self.seal.seal(self.root, self.stage_dir, "T1")


class SealBindTests(_SealTestBase):
    def test_bind_mismatch_fail_closed_no_status_hash(self):
        (self.root / (STAGE_REL + "/seen.patch")).write_bytes(b"not the real patch\n")
        with self.assertRaises(self.seal.SealError) as ctx:
            self.seal.seal(self.root, self.stage_dir, "T1")
        self.assertIn("bind", str(ctx.exception).lower())
        # no hash/fingerprint field may be written to status on mismatch
        status2 = lib.load_json(self.stage_dir / "status.json")
        unit2 = status2["auto_review_pipeline"]["review_units"][0]
        self.assertNotIn("diff_fingerprint", unit2)
        self.assertNotIn("snapshot_commit", unit2)

    def test_no_seen_patch_binds_na(self):
        env = _make_seal_env(with_seen=False)
        root, _git, stage_dir, _status_doc, _unit = env
        seal = _load_stage_seal()
        seal.run_validator = lambda *a, **k: None
        result = seal.seal(root, stage_dir, "T1")
        self.assertFalse(result["recovered"])
        status2 = lib.load_json(stage_dir / "status.json")
        self.assertEqual(
            status2["auto_review_pipeline"]["review_units"][0]["embedded_cross_check"]["bind_status"],
            "n/a",
        )


class SealCrashRecoveryTests(_SealTestBase):
    def test_fresh_seal_path_not_recovered(self):
        # unit has no snapshot_commit -> neither unbound nor sealed -> fresh seal
        self.assertFalse(self.seal.unit_is_unbound(self.unit))
        self.assertFalse(self.seal.unit_is_sealed(self.unit))
        result = self.seal.seal(self.root, self.stage_dir, "T1")
        self.assertFalse(result["recovered"])

    def test_unbound_snapshot_recovers_with_single_bind_commit(self):
        # simulate crash: H_snapshot landed, H_bind did not
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "harness-seal: H_snapshot review snapshot for task T1")
        snapshot_head = self.git("rev-parse", "HEAD").strip()
        self.unit["snapshot_commit"] = snapshot_head
        self.unit["head_sha"] = snapshot_head
        self._rewrite_status()
        before = int(self.git("rev-list", "--count", "HEAD"))
        result = self.seal.seal(self.root, self.stage_dir, "T1")
        self.assertTrue(result["recovered"])
        after = int(self.git("rev-list", "--count", "HEAD"))
        # exactly one new commit (H_bind); NEVER a second code commit
        self.assertEqual(after - before, 1)
        status2 = lib.load_json(self.stage_dir / "status.json")
        self.assertTrue(status2["auto_review_pipeline"]["review_units"][0]["diff_fingerprint"])

    def test_snapshot_crash_window_recovers_without_second_code_commit(self):
        # F6: the real H_snapshot crash window is between create_snapshot committing
        # H_snapshot and write_unit_and_receipt writing snapshot_commit/fingerprint
        # into status. Inject the crash by monkeypatching write_unit_and_receipt to
        # raise on its first call (AFTER the snapshot commit has landed), then prove
        # the second seal() recovers via the pending marker and adds NO second code
        # commit — only the H_bind.
        real_write = self.seal.write_unit_and_receipt
        calls = {"n": 0}

        def crashing_write(*a, **k):
            calls["n"] += 1
            # create_snapshot has already committed H_snapshot before we are called;
            # crash here, before the status write records snapshot_commit/fingerprint
            raise self.seal.SealError("injected crash: status write did not land")

        self.seal.write_unit_and_receipt = crashing_write
        try:
            with self.assertRaises(self.seal.SealError):
                self.seal.seal(self.root, self.stage_dir, "T1")
        finally:
            self.seal.write_unit_and_receipt = real_write
        self.assertEqual(calls["n"], 1)
        snapshot_head = self.git("rev-parse", "HEAD").strip()  # the committed H_snapshot
        # the pending marker must still be on disk (recovery detects the real point)
        self.assertTrue(self.seal._pending_marker_path(self.stage_dir, "T1").exists())

        before = int(self.git("rev-list", "--count", "HEAD"))
        result = self.seal.seal(self.root, self.stage_dir, "T1")  # recover via marker
        after = int(self.git("rev-list", "--count", "HEAD"))

        self.assertTrue(result["recovered"])
        self.assertEqual(result.get("crash_window"), "snapshot_committed_status_unwritten")
        self.assertEqual(result["head_sha"], snapshot_head)
        # exactly one new commit (H_bind); NEVER a second H_snapshot code commit
        self.assertEqual(after - before, 1)
        log = self.git("log", "--format=%s")
        self.assertEqual(log.count("H_snapshot"), 1)
        self.assertEqual(log.count("H_bind"), 1)
        # the marker is cleared once recovery completes
        self.assertFalse(self.seal._pending_marker_path(self.stage_dir, "T1").exists())
        status2 = lib.load_json(self.stage_dir / "status.json")
        unit2 = status2["auto_review_pipeline"]["review_units"][0]
        self.assertEqual(unit2["snapshot_commit"], snapshot_head)
        self.assertTrue(unit2["diff_fingerprint"])
        self.assertEqual(unit2["embedded_cross_check"]["bind_status"], "bound")

    def test_sealed_unit_refuses_reseal(self):
        # simulate post-H_bind state: unit fully sealed
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "snap")
        head = self.git("rev-parse", "HEAD").strip()
        self.unit["snapshot_commit"] = head
        self.unit["head_sha"] = head
        self.unit["diff_fingerprint"] = head + ":deadbeef"
        self._rewrite_status()
        with self.assertRaises(self.seal.SealError) as ctx:
            self.seal.seal(self.root, self.stage_dir, "T1")
        self.assertIn("already sealed", str(ctx.exception))


class EscalationArtifactTests(_SealTestBase):
    def test_write_escalation_artifact(self):
        name = self.seal.write_escalation(
            self.stage_dir, "bind_mismatch", {"stage_id": "test-stage", "task_id": "T1"}
        )
        text = (self.stage_dir / name).read_text(encoding="utf-8")
        self.assertIn("bind_mismatch", text)
        self.assertIn("Human action required", text)
        self.assertTrue(name.startswith("80-escalation-bind_mismatch-"))


if __name__ == "__main__":
    unittest.main()
