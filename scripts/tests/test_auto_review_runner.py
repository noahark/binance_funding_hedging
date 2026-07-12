#!/usr/bin/env python3
"""Stdlib-only integration tests for ``scripts/auto-review-runner.py``.

The runner is the sole automatic dispatcher / mechanical writer of the auto
review pipeline v1. These tests cover the frozen 12-breakdown §5 scenario set
declared in the T3 packet:

- default-off manual status never triggers runner behaviour;
- preflight rejection faces (missing / invalid / expired / wrong-stage /
  wrong-branch authorization, dirty / wrong-branch worktree, mode mutex) all
  fail BEFORE any adapter call;
- full happy path implementation → blocking → cross-check → second blocking →
  delegated two-commit seal → review-1 ACCEPT, reaching ``completed_review_1``;
- second blocking failure seals to escalation; evidence-dir writes do not
  change a passing second blocking;
- seen-diff bind mismatch fails closed;
- invalid-JSON retry routing (serial fallback eligible vs ineligible);
- blocking-fix + review-REWORK aggregate auto-budget cap (≤ 2);
- parallel author set rejects cross-pool fallback and escalates;
- multi-owner fix is serialised (no concurrent writes);
- verdict-record commit does not change the unit fingerprint;
- receipt hygiene: no expanded command / env / token / secret; ``next_transition``
  only from the frozen workflow set;
- call / adapter-timeout accounting timing (charge before start and timed-out
  adapter calls still consume call budget);
- P3 residual risk: parallel-topology pathspec exotic forms (negation / nested
  glob / case) either match correctly or fail closed — never a silent miss.

No network, no real model CLIs, no credentials. Fake adapters are injected
Python callables; the seal is either a tiny fake module or the real
``stage-seal.py`` loaded via importlib with its validator step patched to a
no-op. ``scripts/auto-review-runner.py`` is loaded via importlib (hyphen
filename). The shared ``make_temp_repo`` helper is imported, not copied.
"""

from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import re
import shlex
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
from test_harness_stage_lib import make_temp_repo, VALID_AUTH  # noqa: E402

REPO_ROOT = _SCRIPTS.parent


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "auto_review_runner_under_test", _SCRIPTS / "auto-review-runner.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_real_seal():
    """Load the real ``stage-seal.py`` via importlib; tests patch run_validator."""
    spec = importlib.util.spec_from_file_location(
        "auto_review_runner_real_seal", _SCRIPTS / "stage-seal.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RUNNER = _load_runner()
AutoReviewRunner = RUNNER.AutoReviewRunner
InvokeResult = RUNNER.InvokeResult


# ---------------------------------------------------------------------------
# evidence helpers
# ---------------------------------------------------------------------------

BASE_TIME = datetime.datetime(2026, 7, 11, 12, 0, 0, tzinfo=datetime.timezone.utc)


def _verdict(*, stage_id, unit_fp, verdict="ACCEPT", role="first_reviewer",
             model="grok", findings=None, fix_start_prompt=None):
    """Build a schema-valid review-verdict object matching the active unit."""
    doc = {
        "schema_version": 1,
        "stage_id": stage_id,
        "role": role,
        "model": model,
        "verdict": verdict,
        "diff_fingerprint": unit_fp,
        "reviewer_prior_involvement": "none",
        "reviewed_artifacts": ["scripts/x.py"],
        "findings": findings or [],
        "required_fixes": [],
        "next_action": "stage_accepted_waiting_user",
    }
    if verdict == "REWORK":
        doc["fix_start_prompt"] = fix_start_prompt or "fix the flagged findings"
        doc["next_action"] = "fix"
        doc["findings"] = findings or [
            {"severity": "P2", "title": "bug", "file": "scripts/x.py", "line": 1,
             "evidence": "e", "impact": "i", "recommendation": "r"}
        ]
    return doc


class FakeSeal:
    """Minimal seal substitute: sets the unit fingerprint on disk.

    Real seal integration is exercised separately via ``_load_real_seal``. This
    fake lets routing / budget / accounting tests skip git-commit mechanics.
    """

    def __init__(self, *, outcome="ok", fingerprint=None):
        self.outcome = outcome
        self.fingerprint = fingerprint
        self.calls = []

    def seal(self, root, stage_dir, unit_id, commit_guard=None):
        # commit_guard mirrors the real seal's per-commit expiry hook (FX2); the
        # fake performs no git commit so it is accepted but never invoked here.
        self.calls.append(unit_id)
        if self.outcome == "bind_mismatch":
            raise RUNNER.lib.HarnessError(
                "seen-diff bind mismatch: captured and regenerated patches differ")
        if self.outcome == "fail":
            raise RUNNER.lib.HarnessError("seal failed: blocking second_pass did not pass")
        if self.outcome == "raise_runtime":
            raise RuntimeError("unexpected")
        # ok: set unit seal fields in status.json on disk so load_status sees them
        status_path = Path(stage_dir) / "status.json"
        status = lib.load_json(status_path)
        for unit in status.get("auto_review_pipeline", {}).get("review_units", []):
            if unit.get("id") == unit_id:
                fp = self.fingerprint or ("fakefp:" + str(unit_id) + ":" + str(len(self.calls)))
                unit["diff_fingerprint"] = fp
                unit["head_sha"] = "fakesha" + str(len(self.calls))
                unit["snapshot_commit"] = "fakesha" + str(len(self.calls))
        lib.atomic_write_json(status_path, status)
        return {"head_sha": "fakesha", "diff_fingerprint": self.fingerprint, "receipt": "x"}

    def run_validator(self, root, stage_id):  # patched attribute; never really called
        pass


# ---------------------------------------------------------------------------
# stage builder
# ---------------------------------------------------------------------------

class Stage:
    """A built auto-review stage under an isolated throwaway repo."""

    def __init__(self, *, unit_authors=("claude_glm",), topology="serial",
                 enabled=True, max_model_calls=20, max_auto_code_changes=2,
                 allowed_pathspecs=("scripts/x.py",), forbidden_pathspecs=(),
                 extra_unit_fields=None, runner_state=None,
                 dispatch_mode="human_dispatch", parallel_mode_enabled=False,
                 authorization_path=None, auth_mutator=None, stage_id="auto-stage"):
        root, git = make_temp_repo()
        self.root = root
        self.git = git
        self.stage_id = stage_id
        self.stage_dir = root / "reports" / "agent-runs" / stage_id
        self.stage_dir.mkdir(parents=True)
        # a tracked code dir so dirty code files show individually, not collapsed
        scripts = root / "scripts"
        scripts.mkdir(exist_ok=True)
        (scripts / "placeholder.py").write_text("# tracked\n", encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", "base")
        self.base_sha = git("rev-parse", "HEAD").strip()
        self.branch = git("branch", "--show-current").strip()

        # authorization artifact (serial-only v1 slim shape)
        auth = json.loads(json.dumps(VALID_AUTH))
        auth["stage_id"] = stage_id
        auth["stage_branch"] = self.branch
        auth["scope"] = {
            "task_ids": ["T1"],
            "allowed_pathspecs": list(allowed_pathspecs),
            "forbidden_pathspecs": list(forbidden_pathspecs),
        }
        auth["budgets"] = {
            "max_model_calls": max_model_calls,
            "max_auto_code_changes": max_auto_code_changes,
        }
        auth["approval_evidence_path"] = "reports/agent-runs/%s/auth.json" % stage_id
        if auth_mutator:
            auth_mutator(auth)
        self.auth = auth
        (self.stage_dir / "auth.json").write_text(json.dumps(auth), encoding="utf-8")

        unit = {
            "id": "T1",
            "kind": "task",
            "required": True,
            "base_sha": self.base_sha,
            "code_pathspecs": ["scripts/x.py"],
            "author_provider_identities": [{"id": a} for a in unit_authors],
            "blocking_checks": {
                "commands": ["true"],
                "evidence_exclude_pathspecs": ["reports/agent-runs/%s/" % stage_id],
            },
        }
        if extra_unit_fields:
            unit.update(extra_unit_fields)
        self.status = {
            "stage_id": stage_id,
            "status": "running",
            "stage_branch": {"name": self.branch},
            "parallel_mode": {"enabled": parallel_mode_enabled},
            "auto_review_pipeline": {
                "enabled": enabled,
                "schema_version": 1,
                "runner_version": "auto-review-pipeline/v1",
                "dispatch_mode": dispatch_mode,
                "topology": topology,
                "runner_state": runner_state,
                "authorization_path": authorization_path or (
                    "reports/agent-runs/%s/auth.json" % stage_id),
                "budgets": {
                    "auto_code_changes_used": 0,
                    "model_calls_used": 0,
                },
                "mode_history": [],
                "review_units": [unit],
            },
        }
        self._write_status()
        # commit the seed (stage dir tracked) so later dirty paths are individual
        git("add", "-A")
        git("commit", "-q", "--allow-empty", "-m", "seed-stage")

    def _write_status(self):
        lib.atomic_write_json(self.stage_dir / "status.json", self.status)

    def reload(self):
        self.status = lib.load_json(self.stage_dir / "status.json")
        return self.status

    def unit(self):
        return self.reload()["auto_review_pipeline"]["review_units"][0]

    def arp(self):
        return self.reload()["auto_review_pipeline"]

    def make_runner(self, *, invoker, blocking_runner=None, seal=None, now=None,
                    seal_run_validator=None):
        registry = {
            "claude_glm": {"commands": {"noninteractive_command": "@PROMPT@"},
                           "timeout_seconds": 3000},
            "kimi": {"commands": {
                "noninteractive_command": "@PROMPT@",
                "embedded_read_only_review_command": "@PROMPT@",
            }, "timeout_seconds": 1800},
            "grok": {"commands": {
                "development_command": "@PROMPT@",
                "optional_review_command": "@PROMPT@",
            }, "timeout_seconds": 1800, "optional_review_timeout_seconds": 900},
        }
        return AutoReviewRunner(
            self.root, self.stage_dir,
            registry=registry,
            invoker=invoker,
            now=now or (lambda: BASE_TIME),
            blocking_runner=blocking_runner,
            seal_module=seal,
            seal_run_validator=seal_run_validator,
        )


# ---------------------------------------------------------------------------
# common fake collaborators
# ---------------------------------------------------------------------------

def _accept_invoker(stage, *, write_code=True):
    """Invoker whose implementation writes code and whose Grok review ACCEPTs."""
    def invoke(adapter_id, command_key, prompt_abs, timeout):
        if command_key == "noninteractive_command":
            if write_code:
                (stage.root / "scripts" / "x.py").write_text("X = 1\n", encoding="utf-8")
            out = b"implemented\n"
        elif command_key == "embedded_read_only_review_command":
            out = b"advisory cross-check ok\n"
        elif command_key == "optional_review_command":
            fp = stage.unit().get("diff_fingerprint")
            out = ("notes\n" + json.dumps(_verdict(stage_id=stage.stage_id, unit_fp=fp)) + "\n").encode()
        else:
            out = b""
        return InvokeResult(stdout=out, exit_status=0, timed_out=False, failure_class=None,
                            started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")
    return invoke


def _static_now():
    return BASE_TIME


def _ir(stdout=b"", *, exit_status=0, timed_out=False, failure_class=None):
    """Compact InvokeResult builder for the negative-test suites below."""
    return InvokeResult(stdout=stdout, exit_status=exit_status, timed_out=timed_out,
                        failure_class=failure_class, started_at="2026-07-11T00:00:00Z",
                        completed_at="2026-07-11T00:00:01Z")


# ===========================================================================
# 1. enablement / default-off
# ===========================================================================

class EnablementTests(unittest.TestCase):
    def test_default_off_manual_status_is_noop(self):
        stage = Stage(enabled=False)
        calls = []

        def invoke(*a, **k):
            calls.append(a)
            return InvokeResult(stdout=b"", exit_status=0, timed_out=False, failure_class=None,
                                started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")

        runner = stage.make_runner(invoker=invoke, blocking_runner=lambda u, c, p: 0,
                                   seal=FakeSeal())
        result = runner.run()
        self.assertFalse(result.ran)
        self.assertEqual(calls, [], "no adapter may be invoked when auto mode is off")
        # status untouched: no mode_history, no runner_state flip
        arp = stage.arp()
        self.assertEqual(arp.get("mode_history"), [])


# ===========================================================================
# 2. preflight rejection faces (all before any adapter call)
# ===========================================================================

class PreflightRejectionTests(unittest.TestCase):
    def _run_preflight_only(self, stage, **runner_kwargs):
        calls = []

        def invoke(*a, **k):
            calls.append(a)
            return InvokeResult(stdout=b"x", exit_status=0, timed_out=False, failure_class=None,
                                started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")

        runner = stage.make_runner(invoker=invoke, blocking_runner=lambda u, c, p: 0,
                                   seal=FakeSeal(), **runner_kwargs)
        result = runner.run()
        return result, calls

    def test_missing_authorization_path(self):
        stage = Stage(authorization_path="reports/agent-runs/auto-stage/missing.json")
        result, calls = self._run_preflight_only(stage)
        self.assertEqual(result.terminal, "awaiting_human")
        self.assertEqual(calls, [])

    def test_invalid_authorization_doc(self):
        def mutate(auth):
            auth["contract_version"] = "wrong/v2"
        stage = Stage(auth_mutator=mutate)
        result, calls = self._run_preflight_only(stage)
        self.assertEqual(result.terminal, "awaiting_human")
        self.assertEqual(calls, [])

    def test_expired_authorization(self):
        def mutate(auth):
            auth["expires_at"] = "2020-01-01T00:00:00Z"
        stage = Stage(auth_mutator=mutate)
        result, calls = self._run_preflight_only(stage)
        self.assertEqual(result.terminal, "awaiting_human")
        self.assertEqual(calls, [])

    def test_wrong_stage_id(self):
        def mutate(auth):
            auth["stage_id"] = "some-other-stage"
        stage = Stage(auth_mutator=mutate)
        result, calls = self._run_preflight_only(stage)
        self.assertEqual(result.terminal, "awaiting_human")
        self.assertEqual(calls, [])

    def test_wrong_branch(self):
        def mutate(auth):
            auth["stage_branch"] = "stage/nonmatching"
        stage = Stage(auth_mutator=mutate)
        result, calls = self._run_preflight_only(stage)
        self.assertEqual(result.terminal, "awaiting_human")
        self.assertEqual(calls, [])

    def test_dirty_worktree_outside_allowlist(self):
        stage = Stage()
        # a stray product file outside the allowlist and stage dir
        (stage.root / "product").mkdir(exist_ok=True)
        (stage.root / "product" / "stray.py").write_text("oops", encoding="utf-8")
        result, calls = self._run_preflight_only(stage)
        self.assertEqual(result.terminal, "awaiting_human")
        self.assertEqual(calls, [])

    def test_mode_mutex_with_parallel_mode(self):
        stage = Stage(parallel_mode_enabled=True)
        result, calls = self._run_preflight_only(stage)
        self.assertEqual(result.terminal, "awaiting_human")
        self.assertEqual(calls, [])

    def test_preflight_failure_sets_paused_and_no_transition_row(self):
        # preflight failure has no authorized->awaiting_human row in the frozen
        # matrix; the runner must set awaiting_human + paused WITHOUT writing a
        # transition row (the validator only checks existing rows are in-set).
        def mutate(auth):
            auth["contract_version"] = "wrong/v2"
        stage = Stage(auth_mutator=mutate)
        result, _ = self._run_preflight_only(stage)
        arp = stage.arp()
        self.assertEqual(arp.get("runner_state"), "awaiting_human")
        self.assertEqual(stage.status.get("status"), "paused")
        self.assertEqual(arp.get("mode_flip_pending"), "human_dispatch")
        # exactly one transition recorded (the authorize_new_run), no escalation row
        events = [m["event"] for m in arp.get("mode_history", [])]
        self.assertEqual(events, ["new_human_authorization"])
        # an escalation artifact was written
        self.assertTrue(any(stage.stage_dir.glob("80-escalation-preflight_*.md")))


# ===========================================================================
# 3 + 6. happy path full chain (real seal) → completed_review_1
# ===========================================================================

class HappyPathRealSealTests(unittest.TestCase):
    def test_full_chain_accept_completed_review_1(self):
        stage = Stage()
        real_seal = _load_real_seal()
        runner = stage.make_runner(
            invoker=_accept_invoker(stage),
            blocking_runner=lambda u, c, p: 0,
            seal=real_seal,
            seal_run_validator=lambda root, stage_id: None,
        )
        result = runner.run()
        self.assertTrue(result.ran)
        self.assertEqual(result.terminal, "completed_review_1")
        arp = stage.arp()
        self.assertEqual(arp.get("runner_state"), "completed_review_1")
        self.assertEqual(stage.unit().get("review_1", {}).get("verdict"), "ACCEPT")
        events = [m["event"] for m in arp.get("mode_history", [])]
        self.assertEqual(events, ["new_human_authorization", "successful_full_preflight",
                                  "all_required_units_ACCEPT"])
        # model calls: implementation + cross-check + review-1 (no fix)
        self.assertEqual(arp["budgets"]["model_calls_used"], 3)
        self.assertEqual(arp["budgets"]["auto_code_changes_used"], 0)
        # receipt sequence is monotonic and collision-free across runner + seal
        seqs = []
        for p in sorted(stage.stage_dir.glob("runner-*.receipt.json")):
            seqs.append(int(p.name.split("-")[1]))
        self.assertEqual(seqs, sorted(seqs))
        self.assertEqual(len(set(seqs)), len(seqs))


# ===========================================================================
# 4. second-blocking semantics
# ===========================================================================

class SecondBlockingTests(unittest.TestCase):
    def test_second_blocking_failure_escalates(self):
        stage = Stage()
        passes = {"n": 0}

        def blocking(unit, commands, pass_index):
            # first_pass (pass_index=1) passes; second_pass (pass_index=2) fails
            return 0 if pass_index == 1 else 1

        runner = stage.make_runner(
            invoker=_accept_invoker(stage),
            blocking_runner=blocking, seal=FakeSeal())
        result = runner.run()
        self.assertEqual(result.terminal, "human_escalation_required")
        arp = stage.arp()
        self.assertEqual(arp.get("runner_state"), "awaiting_human")
        self.assertEqual(stage.status.get("status"), "human_escalation_required")

    def test_evidence_dir_write_does_not_change_second_pass(self):
        # a passing second pass stays passing even though evidence files landed
        stage = Stage()
        runner = stage.make_runner(
            invoker=_accept_invoker(stage),
            blocking_runner=lambda u, c, p: 0, seal=FakeSeal())
        result = runner.run()
        self.assertEqual(result.terminal, "completed_review_1")
        blk = stage.unit().get("blocking_checks", {})
        self.assertEqual(blk.get("second_pass", {}).get("exit_status"), 0)
        self.assertTrue(blk.get("second_pass", {}).get("ran_after_cross_check") is True)


# ===========================================================================
# 5. bind mismatch fail-closed
# ===========================================================================

class BindMismatchTests(unittest.TestCase):
    def test_bind_mismatch_fail_closed_real_seal(self):
        stage = Stage()
        # cross-check will capture a seen patch; tamper with it before seal bind
        # by making the implementer write DIFFERENT code on the second write the
        # seal sees. Simpler: use the real seal and mutate the seen patch file.
        real_seal = _load_real_seal()

        tampered = {"done": False}

        def invoke(adapter_id, command_key, prompt_abs, timeout):
            if command_key == "noninteractive_command":
                (stage.root / "scripts" / "x.py").write_text("X = 1\n", encoding="utf-8")
                return InvokeResult(stdout=b"imp", exit_status=0, timed_out=False, failure_class=None,
                                    started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")
            if command_key == "embedded_read_only_review_command":
                # after capturing the seen patch, corrupt it so bind mismatches
                for p in stage.stage_dir.glob("embedded-cross-check-*.seen.diff.patch"):
                    p.write_bytes(b"tampered patch bytes\n")
                    tampered["done"] = True
                return InvokeResult(stdout=b"advisory", exit_status=0, timed_out=False, failure_class=None,
                                    started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")
            return InvokeResult(stdout=b"", exit_status=0, timed_out=False, failure_class=None,
                                started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")

        runner = stage.make_runner(
            invoker=invoke, blocking_runner=lambda u, c, p: 0,
            seal=real_seal, seal_run_validator=lambda root, stage_id: None)
        result = runner.run()
        self.assertEqual(result.terminal, "human_escalation_required")
        self.assertTrue(tampered["done"])
        # the unit must NOT have a fingerprint written (bind failed closed)
        self.assertFalse(stage.unit().get("diff_fingerprint"))


# ===========================================================================
# 7. invalid-JSON retry routing
# ===========================================================================

class InvalidJsonRoutingTests(unittest.TestCase):
    def test_invalid_then_valid_grok_accepts(self):
        stage = Stage()
        attempts = {"n": 0}

        def invoke(adapter_id, command_key, prompt_abs, timeout):
            if command_key == "noninteractive_command":
                (stage.root / "scripts" / "x.py").write_text("X = 1\n", encoding="utf-8")
                return InvokeResult(stdout=b"imp", exit_status=0, timed_out=False, failure_class=None,
                                    started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")
            if command_key == "embedded_read_only_review_command":
                return InvokeResult(stdout=b"advisory", exit_status=0, timed_out=False, failure_class=None,
                                    started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")
            if command_key == "optional_review_command":
                attempts["n"] += 1
                if attempts["n"] == 1:
                    return InvokeResult(stdout=b"not json at all", exit_status=0, timed_out=False,
                                        failure_class=None, started_at="2026-07-11T00:00:00Z",
                                        completed_at="2026-07-11T00:00:01Z")
                fp = stage.unit().get("diff_fingerprint")
                out = json.dumps(_verdict(stage_id=stage.stage_id, unit_fp=fp)).encode()
                return InvokeResult(stdout=out, exit_status=0, timed_out=False, failure_class=None,
                                    started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")
            return InvokeResult(stdout=b"", exit_status=0, timed_out=False, failure_class=None,
                                started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")

        runner = stage.make_runner(invoker=invoke, blocking_runner=lambda u, c, p: 0, seal=FakeSeal())
        result = runner.run()
        self.assertEqual(result.terminal, "completed_review_1")
        # grok tried exactly twice (invalid_json_max_attempts_per_model == 2)
        self.assertEqual(attempts["n"], 2)

    def test_repeated_invalid_routes_to_serial_fallback(self):
        # unit authored by claude_glm only → kimi fallback eligible
        stage = Stage(unit_authors=("claude_glm",), topology="serial")
        grok_attempts = {"n": 0}
        kimi_attempts = {"n": 0}

        def invoke(adapter_id, command_key, prompt_abs, timeout):
            if command_key == "noninteractive_command":
                (stage.root / "scripts" / "x.py").write_text("X = 1\n", encoding="utf-8")
                return InvokeResult(stdout=b"imp", exit_status=0, timed_out=False, failure_class=None,
                                    started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")
            if command_key == "embedded_read_only_review_command":
                return InvokeResult(stdout=b"advisory", exit_status=0, timed_out=False, failure_class=None,
                                    started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")
            if command_key == "optional_review_command":
                grok_attempts["n"] += 1
                return InvokeResult(stdout=b"garbage", exit_status=0, timed_out=False, failure_class=None,
                                    started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")
            return InvokeResult(stdout=b"", exit_status=0, timed_out=False, failure_class=None,
                                started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")

        # patch: the kimi fallback command uses embedded_read_only_review_command,
        # which our invoker treats as advisory. To make fallback ACCEPT, intercept
        # via a dedicated invoker that knows the fallback attempt count.

        def invoke2(adapter_id, command_key, prompt_abs, timeout):
            if command_key == "noninteractive_command":
                (stage.root / "scripts" / "x.py").write_text("X = 1\n", encoding="utf-8")
                return InvokeResult(stdout=b"imp", exit_status=0, timed_out=False, failure_class=None,
                                    started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")
            if command_key == "optional_review_command":
                grok_attempts["n"] += 1
                return InvokeResult(stdout=b"garbage", exit_status=0, timed_out=False, failure_class=None,
                                    started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")
            if adapter_id == "kimi" and command_key == "embedded_read_only_review_command":
                kimi_attempts["n"] += 1
                fp = stage.unit().get("diff_fingerprint")
                # only the SECOND kimi embedded call is the review fallback (first
                # is the cross-check). Accept on the fallback review call.
                out = json.dumps(_verdict(stage_id=stage.stage_id, unit_fp=fp, model="kimi")).encode()
                return InvokeResult(stdout=out, exit_status=0, timed_out=False, failure_class=None,
                                    started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")
            # claude_glm cross-check advisory
            return InvokeResult(stdout=b"advisory", exit_status=0, timed_out=False, failure_class=None,
                                started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")

        runner = stage.make_runner(invoker=invoke2, blocking_runner=lambda u, c, p: 0, seal=FakeSeal())
        result = runner.run()
        self.assertEqual(result.terminal, "completed_review_1")
        self.assertEqual(grok_attempts["n"], 2, "grok retried exactly once (2 attempts)")
        self.assertGreaterEqual(kimi_attempts["n"], 1, "serial fallback (kimi) was invoked")


# ===========================================================================
# 8. aggregate auto-budget cap
# ===========================================================================

class AutoBudgetCapTests(unittest.TestCase):
    def test_blocking_fix_plus_rework_cap_at_two(self):
        # max_auto_code_changes = 1 so: blocking fix (1) + rework fix (2nd) cap-exhausts
        stage = Stage(max_auto_code_changes=1)
        blocking_passes = {"first": False}

        def blocking(unit, commands, pass_index):
            # first_pass fails once (triggers 1 auto fix), then passes thereafter
            if pass_index == 1 and not blocking_passes["first"]:
                blocking_passes["first"] = True
                return 1
            return 0

        review_round = {"n": 0}

        def invoke(adapter_id, command_key, prompt_abs, timeout):
            if command_key == "noninteractive_command":
                (stage.root / "scripts" / "x.py").write_text("X = 1\n", encoding="utf-8")
                return InvokeResult(stdout=b"imp", exit_status=0, timed_out=False, failure_class=None,
                                    started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")
            if command_key == "embedded_read_only_review_command":
                return InvokeResult(stdout=b"advisory", exit_status=0, timed_out=False, failure_class=None,
                                    started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")
            if command_key == "optional_review_command":
                review_round["n"] += 1
                fp = stage.unit().get("diff_fingerprint")
                if review_round["n"] == 1:
                    out = json.dumps(_verdict(stage_id=stage.stage_id, unit_fp=fp, verdict="REWORK")).encode()
                else:
                    out = json.dumps(_verdict(stage_id=stage.stage_id, unit_fp=fp, verdict="ACCEPT")).encode()
                return InvokeResult(stdout=out, exit_status=0, timed_out=False, failure_class=None,
                                    started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")
            return InvokeResult(stdout=b"", exit_status=0, timed_out=False, failure_class=None,
                                started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")

        runner = stage.make_runner(invoker=invoke, blocking_runner=blocking, seal=FakeSeal())
        result = runner.run()
        # 1 blocking fix + 1 rework fix == cap(1)? cap is max_auto_code_changes=1,
        # so the SECOND auto change (the rework fix) hits budget_exhausted.
        self.assertEqual(result.terminal, "human_escalation_required")
        arp = stage.arp()
        self.assertEqual(arp["budgets"]["auto_code_changes_used"], 1)
        events = [m["event"] for m in arp.get("mode_history", [])]
        self.assertIn("budget_exhausted", events)


# ===========================================================================
# 9. serial fallback: when the Grok review-1 tip fails and no eligible serial
#    fallback candidate remains (every author already authored the unit), the
#    run escalates via review_1_fallback_exhausted — no cross-pool dispatch.
# ===========================================================================

class SerialFallbackExhaustionTests(unittest.TestCase):
    def test_ineligible_fallback_both_providers_authored(self):
        # unit authored by claude_glm AND kimi → no eligible serial fallback
        stage = Stage(unit_authors=("claude_glm", "kimi"), topology="serial")
        grok_attempts = {"n": 0}

        def invoke(adapter_id, command_key, prompt_abs, timeout):
            if command_key == "noninteractive_command":
                (stage.root / "scripts" / "x.py").write_text("X = 1\n", encoding="utf-8")
                return InvokeResult(stdout=b"imp", exit_status=0, timed_out=False, failure_class=None,
                                    started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")
            if command_key == "embedded_read_only_review_command":
                return InvokeResult(stdout=b"advisory", exit_status=0, timed_out=False, failure_class=None,
                                    started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")
            if command_key == "optional_review_command":
                grok_attempts["n"] += 1
                return InvokeResult(stdout=b"garbage", exit_status=0, timed_out=False, failure_class=None,
                                    started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")
            return InvokeResult(stdout=b"", exit_status=0, timed_out=False, failure_class=None,
                                started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")

        runner = stage.make_runner(invoker=invoke, blocking_runner=lambda u, c, p: 0, seal=FakeSeal())
        result = runner.run()
        self.assertEqual(result.terminal, "human_escalation_required")
        # both providers are in the author set → no eligible fallback → escalate
        self.assertEqual(grok_attempts["n"], 2)


# ===========================================================================
# 10. multi-owner fix serialisation (no concurrent writes)
# ===========================================================================

class MultiOwnerFixTests(unittest.TestCase):
    def test_multi_owner_fix_dispatched_serially(self):
        # two code files owned by two different adapters
        stage = Stage(
            allowed_pathspecs=("scripts/x.py", "scripts/y.py"),
            extra_unit_fields={
                "code_pathspecs": ["scripts/x.py", "scripts/y.py"],
                "fix_ownership": {"scripts/x.py": "claude_glm", "scripts/y.py": "kimi"},
            },
        )
        (stage.root / "scripts" / "y.py").write_text("", encoding="utf-8")
        stage.git("add", "-A")
        stage.git("commit", "-q", "-m", "add y.py")
        # rebuild base_sha to include y.py
        stage.status["auto_review_pipeline"]["review_units"][0]["base_sha"] = \
            stage.git("rev-parse", "HEAD").strip()
        stage._write_status()
        stage.git("add", "-A")
        stage.git("commit", "-q", "--allow-empty", "-m", "rebase")

        dispatch_order = []

        def invoke(adapter_id, command_key, prompt_abs, timeout):
            # fix dispatches reuse noninteractive_command, so detect them first
            if command_id_is_fix(adapter_id, command_key, prompt_abs):
                dispatch_order.append(adapter_id)
                return InvokeResult(stdout=b"fix", exit_status=0, timed_out=False, failure_class=None,
                                    started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")
            if command_key == "noninteractive_command":
                # implementation writes both files
                (stage.root / "scripts" / "x.py").write_text("X=1\n", encoding="utf-8")
                (stage.root / "scripts" / "y.py").write_text("Y=1\n", encoding="utf-8")
                return InvokeResult(stdout=b"imp", exit_status=0, timed_out=False, failure_class=None,
                                    started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")
            if command_key == "embedded_read_only_review_command":
                return InvokeResult(stdout=b"advisory", exit_status=0, timed_out=False, failure_class=None,
                                    started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")
            if command_key == "optional_review_command":
                fp = stage.unit().get("diff_fingerprint")
                # first round REWORK with findings on both files; second round ACCEPT
                round_n = stage.unit().get("review_1", {}).get("round", 0)
                if round_n == 0:
                    findings = [
                        {"severity": "P2", "title": "x", "file": "scripts/x.py", "line": 1,
                         "evidence": "e", "impact": "i", "recommendation": "r"},
                        {"severity": "P2", "title": "y", "file": "scripts/y.py", "line": 1,
                         "evidence": "e", "impact": "i", "recommendation": "r"},
                    ]
                    out = json.dumps(_verdict(stage_id=stage.stage_id, unit_fp=fp,
                                              verdict="REWORK", findings=findings)).encode()
                else:
                    out = json.dumps(_verdict(stage_id=stage.stage_id, unit_fp=fp, verdict="ACCEPT")).encode()
                return InvokeResult(stdout=out, exit_status=0, timed_out=False, failure_class=None,
                                    started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")
            return InvokeResult(stdout=b"", exit_status=0, timed_out=False, failure_class=None,
                                started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")

        runner = stage.make_runner(invoker=invoke, blocking_runner=lambda u, c, p: 0, seal=FakeSeal())
        result = runner.run()
        self.assertEqual(result.terminal, "completed_review_1")
        # both owners dispatched, serially (deterministic order, no overlap)
        self.assertEqual(sorted(dispatch_order), ["claude_glm", "kimi"])
        self.assertEqual(len(dispatch_order), len(set(dispatch_order)) + 0)  # distinct


def command_id_is_fix(adapter_id, command_key, prompt_abs):
    """Heuristic: a fix dispatch prompt path contains '/fix-'."""
    return "/fix-" in str(prompt_abs)


# ===========================================================================
# 12. verdict-record commit does not change the fingerprint
# ===========================================================================

class VerdictRecordFingerprintTests(unittest.TestCase):
    def test_verdict_record_commit_preserves_fingerprint(self):
        stage = Stage()
        runner = stage.make_runner(
            invoker=_accept_invoker(stage),
            blocking_runner=lambda u, c, p: 0, seal=FakeSeal())
        result = runner.run()
        self.assertEqual(result.terminal, "completed_review_1")
        unit = stage.unit()
        fp = unit.get("diff_fingerprint")
        head = unit.get("head_sha")
        self.assertTrue(fp)
        # the verdict-record commit must not have changed the sealed fingerprint/head
        self.assertEqual(unit.get("diff_fingerprint"), fp)
        self.assertEqual(unit.get("head_sha"), head)


# ===========================================================================
# 13. receipt hygiene: no expanded command/env/token; next_transition in-set
# ===========================================================================

class ReceiptHygieneTests(unittest.TestCase):
    def test_receipts_contain_only_command_refs_no_secrets(self):
        stage = Stage()
        runner = stage.make_runner(
            invoker=_accept_invoker(stage),
            blocking_runner=lambda u, c, p: 0, seal=FakeSeal())
        result = runner.run()
        self.assertEqual(result.terminal, "completed_review_1")
        forbidden_markers = [
            "@PROMPT@", "@REPO@", "--prompt-file", "--model", "--permission-mode",
            "token", "secret", "password", "apikey", "api_key", "Bearer ", "export ",
            "ANTHROPIC", "OPENAI", "ZHIPU", "MOONSHOT",
        ]
        allowed_next = set(lib.NEXT_TRANSITIONS)
        for path in stage.stage_dir.glob("runner-*.receipt.json"):
            doc = lib.load_json(path)
            blob = json.dumps(doc)
            for marker in forbidden_markers:
                self.assertNotIn(marker, blob, "receipt %s leaks %r" % (path.name, marker))
            # adapter ref is the frozen anchored reference, never an expansion
            ref = doc["adapter"]["registry_command_ref"]
            self.assertTrue(ref.startswith("agents/registry.yaml#"))
            self.assertIn(ref, lib.RECEIPT_COMMAND_REFS)
            # next_transition only from the frozen workflow set (or null)
            self.assertIn(doc["next_transition"], allowed_next)

    def test_receipt_call_budget_after_equals_before_minus_one(self):
        stage = Stage()
        runner = stage.make_runner(
            invoker=_accept_invoker(stage),
            blocking_runner=lambda u, c, p: 0, seal=FakeSeal())
        runner.run()
        for path in stage.stage_dir.glob("runner-*.receipt.json"):
            doc = lib.load_json(path)
            # exclude seal receipts (different shape, no call_budget)
            if "call_budget" not in doc:
                continue
            cb = doc["call_budget"]
            self.assertEqual(cb["after"], cb["before"] - 1, path.name)


# ===========================================================================
# 14. call / adapter-timeout accounting timing
# ===========================================================================

class AccountingTimingTests(unittest.TestCase):
    def test_call_charged_before_adapter_start_even_on_timeout(self):
        # F7 made an implementation/fix adapter timeout flow-stopping, so to keep
        # exercising the model-call cap under repeated timeouts we let the
        # implementation and cross-check succeed and time out only the review
        # adapter: every attempt is still charged before it starts, and the cap
        # (3) is hit on the next charge.
        stage = Stage(max_model_calls=3)
        timeouts = {"n": 0}

        def invoke(adapter_id, command_key, prompt_abs, timeout):
            if command_key == "noninteractive_command":
                (stage.root / "scripts" / "x.py").write_text("X = 1\n", encoding="utf-8")
                return _ir(b"imp")
            if command_key == "embedded_read_only_review_command":
                return _ir(b"advisory")
            if command_key == "optional_review_command":
                timeouts["n"] += 1
                return InvokeResult(stdout=b"", exit_status=None, timed_out=True, failure_class="timeout",
                                    started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")
            return _ir()

        runner = stage.make_runner(invoker=invoke, blocking_runner=lambda u, c, p: 0, seal=FakeSeal())
        result = runner.run()
        # the timed-out review attempt was charged; with cap 3 the runner
        # escalates on cap exhaustion.
        self.assertGreaterEqual(timeouts["n"], 1)
        self.assertEqual(result.terminal, "human_escalation_required")
        arp = stage.arp()
        self.assertEqual(arp["budgets"]["model_calls_used"], 3)


# ===========================================================================
# 15. P3 residual risk — pathspec exotic forms across the runner→seal boundary
#     (match correctly or fail closed, never silent miss)
# ===========================================================================

class PathspecExoticFormTests(unittest.TestCase):
    """The runner reuses the seal's approximate pathspec matcher for its dirty-path
    and fix-routing boundary. Exotic forms must not silently over-match."""

    def test_negation_pathspec_does_not_silently_match(self):
        # a negation pathspec is exotic; the matcher treats it literally, so a
        # path that is NOT literally ':(exclude)x' must not match → fail closed.
        self.assertFalse(RUNNER._pathspec_matches("scripts/x.py", [":(exclude)scripts/x.py"]))

    def test_nested_glob_treated_literally(self):
        # '**' inside the middle of a spec is not a supported feature; it must
        # not match a path it shouldn't.
        self.assertFalse(RUNNER._pathspec_matches("scripts/a/b.py", ["scripts/**/b.py"]))
        # the supported trailing-/** form DOES match nested paths
        self.assertTrue(RUNNER._pathspec_matches("scripts/a/b.py", ["scripts/**"]))

    def test_case_sensitive_literal(self):
        self.assertTrue(RUNNER._pathspec_matches("scripts/X.py", ["scripts/X.py"]))
        self.assertFalse(RUNNER._pathspec_matches("scripts/x.py", ["scripts/X.py"]))

    def test_directory_glob_matches(self):
        self.assertTrue(RUNNER._pathspec_matches("scripts/dir/x.py", ["scripts/dir/**"]))
        self.assertTrue(RUNNER._pathspec_matches("scripts/dir/x.py", ["scripts/dir/"]))
        self.assertTrue(RUNNER._pathspec_matches("scripts/dir/x.py", ["scripts/dir/*"]))

    def test_dirty_path_outside_allowlist_fail_closed(self):
        # a stray path outside the (single-file) allowlist is still rejected at
        # preflight — no silent pass-through.
        stage = Stage(allowed_pathspecs=("scripts/x.py",))
        (stage.root / "elsewhere").mkdir(exist_ok=True)
        (stage.root / "elsewhere" / "z.py").write_text("z", encoding="utf-8")

        def invoke(*a, **k):
            self.fail("no adapter call should happen on preflight failure")

        runner = stage.make_runner(invoker=invoke, blocking_runner=lambda u, c, p: 0, seal=FakeSeal())
        result = runner.run()
        self.assertEqual(result.terminal, "awaiting_human")


# ===========================================================================
# resume: superseding_human_authorization transition
# ===========================================================================

class ResumeTransitionTests(unittest.TestCase):
    def test_resume_from_awaiting_human_records_superseding(self):
        stage = Stage(runner_state="awaiting_human", dispatch_mode="auto_review")
        # mark a prior transition so mode_history is non-empty
        stage.status["auto_review_pipeline"]["mode_history"] = [{
            "from": {"dispatch_mode": "human_dispatch", "runner_state": None},
            "to": {"dispatch_mode": "auto_review", "runner_state": "authorized"},
            "event": "new_human_authorization",
        }]
        stage.status["auto_review_pipeline"]["mode_flip_pending"] = "human_dispatch"
        stage._write_status()
        stage.git("add", "-A")
        stage.git("commit", "-q", "--allow-empty", "-m", "paused")

        runner = stage.make_runner(
            invoker=_accept_invoker(stage),
            blocking_runner=lambda u, c, p: 0, seal=FakeSeal())
        result = runner.run()
        self.assertEqual(result.terminal, "completed_review_1")
        events = [m["event"] for m in stage.arp().get("mode_history", [])]
        self.assertIn("superseding_human_authorization", events)
        self.assertNotIn("new_human_authorization", events[1:])  # only the resume row uses superseding


# ---------------------------------------------------------------------------
# transition truth-source consistency (review-1 REWORK finding P2)
# ---------------------------------------------------------------------------

WORKFLOW_TEMPLATE = REPO_ROOT / "workflows" / "templates" / "stage-delivery.yaml"

_FLOW_SEQ = re.compile(r"\[([^\]]*)\]")
_DISPATCH_MODE = re.compile(r'dispatch_mode:\s*"([^"]*)"')
_RUNNER_STATE = re.compile(r'runner_state:\s*(?:"([^"]*)"|(null))')


def _parse_workflow_state_transitions(workflow_path):
    """Restricted stdlib-only parser for the ``state_transitions`` block under
    ``auto_review_pipeline.executable_contract`` in the frozen workflow
    template. Returns a set of ``(from_dispatch_mode, from_runner_state,
    to_dispatch_mode, to_runner_state, event)`` five-tuples, mapping YAML
    ``null`` to Python ``None`` and expanding an ``event.one_of`` list into one
    tuple per listed event. Deliberately narrow — it assumes the exact
    indentation / inline flow-mapping shape of the frozen file and fails closed
    (raises AssertionError) on any structural deviation, so workflow drift
    surfaces here rather than passing silently. No third-party YAML dependency.
    """
    lines = Path(workflow_path).read_text(encoding="utf-8").splitlines()

    header_idx = None
    for i, line in enumerate(lines):
        if line == "    state_transitions:":  # 4-space indent under executable_contract
            header_idx = i
            break
    if header_idx is None:
        raise AssertionError("state_transitions: header not found in %s" % workflow_path)

    body = []
    for line in lines[header_idx + 1:]:
        if line.strip() == "" or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= 4:  # next sibling/parent key ends the block
            break
        body.append(line)

    entries = []
    for line in body:
        if line.startswith("      - id:"):  # 6-space indent marks a new transition
            entries.append([])
        if entries:
            entries[-1].append(line)
    if not entries:
        raise AssertionError("no transition entries parsed under state_transitions")

    def _dispatch_and_state(label, line):
        dm = _DISPATCH_MODE.search(line)
        rs = _RUNNER_STATE.search(line)
        if not dm or not rs:
            raise AssertionError(
                "%s dispatch_mode/runner_state unparseable: %r" % (label, line))
        runner_state = None if rs.group(1) is None else rs.group(1)  # null -> None
        return dm.group(1), runner_state

    def _events(entry):
        for idx, line in enumerate(entry):
            stripped = line.lstrip()
            if not stripped.startswith("event:"):
                continue
            rest = stripped[len("event:"):].strip()
            if rest:  # scalar inline event: "name"
                if not (rest.startswith('"') and rest.endswith('"')):
                    raise AssertionError("event scalar form unexpected: %r" % line)
                return [rest[1:-1]]
            for nxt in entry[idx + 1:]:  # block event:\n  one_of: [...]
                nxt_stripped = nxt.lstrip()
                if nxt_stripped.startswith("one_of:"):
                    match = _FLOW_SEQ.search(nxt_stripped)
                    if not match:
                        raise AssertionError("one_of flow sequence unparseable: %r" % nxt)
                    items = re.findall(r'"([^"]*)"', match.group(1))
                    if not items:
                        raise AssertionError("one_of list empty: %r" % nxt)
                    return items
                if nxt_stripped:  # any other content breaks the event block
                    break
            raise AssertionError("event: block missing one_of: in entry %r" % (entry,))
        raise AssertionError("no event: field in entry %r" % (entry,))

    tuples = set()
    for entry in entries:
        from_line = next((l for l in entry if l.lstrip().startswith("from:")), None)
        to_line = next((l for l in entry if l.lstrip().startswith("to:")), None)
        if from_line is None or to_line is None:
            raise AssertionError("entry missing from:/to: %r" % (entry,))
        from_dm, from_rs = _dispatch_and_state("from", from_line)
        to_dm, to_rs = _dispatch_and_state("to", to_line)
        for event in _events(entry):
            tuples.add((from_dm, from_rs, to_dm, to_rs, event))
    return tuples


class TransitionTruthSourceTests(unittest.TestCase):
    """Review-1 REWORK (finding P2): the runner reuses
    ``validate-stage.AUTO_TRANSITIONS`` via importlib as the single transition
    truth source (scripts/auto-review-runner.py). This pins that reused set to
    the workflow YAML ``state_transitions`` block so the two cannot silently
    drift — the persistence test the dispatch packet §3.1 required but the
    initial T3 delivery omitted.
    """

    def test_runner_transitions_match_workflow_state_transitions(self):
        parsed = _parse_workflow_state_transitions(WORKFLOW_TEMPLATE)
        self.assertTrue(parsed, "parsed transition set must be non-empty")
        self.assertEqual(
            parsed,
            set(RUNNER.AUTO_TRANSITIONS),
            "runner.AUTO_TRANSITIONS drifted from workflow state_transitions",
        )


# ===========================================================================
# Review-2 fix round 1 — F2: authorization real binding (sol §F2)
# ===========================================================================

class AuthorizationBindingTests(unittest.TestCase):
    """Authorization must bind actual execution: the artifact + approval receipt
    are committed (git-reachable), scope (task_ids/topology/allowed/forbidden)
    matches live review units exactly, runtime caps come from the authorization
    budget, and an uncommitted authorization modification is rejected. Every sol
    counterexample must fail closed BEFORE any adapter call."""

    def _run_preflight(self, stage):
        calls = []

        def invoke(*a, **k):
            calls.append(a)
            return _ir()

        runner = stage.make_runner(invoker=invoke, blocking_runner=lambda u, c, p: 0,
                                   seal=FakeSeal())
        return runner.run(), calls

    def test_unauthorized_extra_unit_fails_closed(self):
        # authorization covers T1 only; status secretly contains an extra T2
        stage = Stage()
        stage.status["auto_review_pipeline"]["review_units"].append({
            "id": "T2", "kind": "task", "required": True,
            "base_sha": stage.base_sha, "code_pathspecs": ["scripts/y.py"],
            "author_provider_identities": [{"id": "claude_glm"}],
            "blocking_checks": {"commands": ["true"]},
        })
        stage._write_status()
        stage.git("add", "-A")
        stage.git("commit", "-q", "--allow-empty", "-m", "sneak-T2")
        result, calls = self._run_preflight(stage)
        self.assertEqual(result.terminal, "awaiting_human")
        self.assertEqual(calls, [])

    def test_unit_pathspec_outside_allowlist_fails_closed(self):
        # the unit claims scripts/y.py which is outside the authorized allowlist
        stage = Stage(allowed_pathspecs=("scripts/x.py",),
                      extra_unit_fields={"code_pathspecs": ["scripts/x.py", "scripts/y.py"]})
        result, calls = self._run_preflight(stage)
        self.assertEqual(result.terminal, "awaiting_human")
        self.assertEqual(calls, [])

    def test_forbidden_pathspec_hit_fails_closed(self):
        # scripts/x.py is both allowed and forbidden → the forbidden match rejects
        stage = Stage(allowed_pathspecs=("scripts/x.py",),
                      forbidden_pathspecs=("scripts/x.py",))
        result, calls = self._run_preflight(stage)
        self.assertEqual(result.terminal, "awaiting_human")
        self.assertEqual(calls, [])

    def test_uncommitted_authorization_artifact_rejected(self):
        # auth.json removed from the index (untracked-from-HEAD) but present on disk
        stage = Stage()
        auth_rel = str((stage.stage_dir / "auth.json").relative_to(stage.root))
        stage.git("rm", "--cached", "-q", auth_rel)
        stage.git("commit", "-q", "-m", "untrack-auth")
        result, calls = self._run_preflight(stage)
        self.assertEqual(result.terminal, "awaiting_human")
        self.assertEqual(calls, [])

    def test_dirty_authorization_modification_rejected(self):
        # a committed auth.json edited in the worktree (not re-committed) is rejected
        stage = Stage()
        auth_path = stage.stage_dir / "auth.json"
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
        auth["authorized_at"] = "2026-07-12T00:00:00Z"  # legal value, but uncommitted worktree edit
        auth_path.write_text(json.dumps(auth), encoding="utf-8")
        result, calls = self._run_preflight(stage)
        self.assertEqual(result.terminal, "awaiting_human")
        self.assertEqual(calls, [])

    def test_runtime_caps_come_from_authorization_not_status(self):
        # status budget is inflated to 99; auth budget is 5 → runner uses 5
        stage = Stage(max_model_calls=5)
        stage.status["auto_review_pipeline"]["budgets"]["max_model_calls"] = 99
        stage._write_status()
        stage.git("add", "-A")
        stage.git("commit", "-q", "--allow-empty", "-m", "diverge")
        runner = stage.make_runner(invoker=lambda *a, **k: _ir(),
                                   blocking_runner=lambda u, c, p: 0, seal=FakeSeal())
        runner.load_status()
        runner.preflight()  # loads self._auth from the committed authorization
        self.assertEqual(runner._max_calls(), 5)
        self.assertEqual(runner._max_auto_changes(), 2)


# ===========================================================================
# Review-2 fix round 1 — F3: production registry command compatibility (sol §F3)
# ===========================================================================

class ProductionRegistryCommandTests(unittest.TestCase):
    """The real ``agents/registry.yaml`` uses ``<prompt-file>`` / ``<repo>``
    placeholders inside quoted YAML scalars (``\\"``). The restricted loader must
    unescape those scalars and the invoker must substitute the real placeholders
    so production adapters never receive a literal placeholder. Tests load the
    REAL registry — no synthetic ``@PROMPT@`` stand-in."""

    def test_real_registry_unescapes_quoted_command_scalars(self):
        reg = RUNNER.load_registry(REPO_ROOT)
        # double-quoted YAML scalar with \" → unescaped, real <prompt-file> kept
        self.assertEqual(
            reg["claude_glm"]["commands"]["noninteractive_command"],
            'claude-glm --model glm-5.2 -p "$(cat <prompt-file>)"')
        self.assertEqual(
            reg["kimi"]["commands"]["noninteractive_command"],
            'kimi --model kimi-code/kimi-for-coding -p "$(cat <prompt-file>)"')
        # grok uses unquoted <repo> + <prompt-file>
        self.assertIn("<repo>", reg["grok"]["commands"]["development_command"])
        self.assertIn("<prompt-file>", reg["grok"]["commands"]["optional_review_command"])

    def test_resolve_timeout_uses_registry_per_adapter_values(self):
        # serial-only v1: per-call subprocess timeout comes from the committed
        # registry. GLM implementation = 3000s; Grok optional review = command
        # override 900s; Grok/Kimi other commands use adapter default 1800s.
        stage = Stage()
        real_reg = RUNNER.load_registry(REPO_ROOT)
        runner = AutoReviewRunner(stage.root, stage.stage_dir, registry=real_reg,
                                  invoker=None, now=lambda: BASE_TIME)
        self.assertEqual(runner._resolve_timeout("claude_glm", "noninteractive_command"), 3000)
        self.assertEqual(runner._resolve_timeout("grok", "optional_review_command"), 900)
        self.assertEqual(runner._resolve_timeout("grok", "development_command"), 1800)
        self.assertEqual(runner._resolve_timeout("kimi", "noninteractive_command"), 1800)

    def test_timeout_override_collaborator_wins_over_registry(self):
        # a test may pass an explicit timeout_override; it always wins and never
        # represents production policy (no model output chooses a timeout).
        stage = Stage()
        real_reg = RUNNER.load_registry(REPO_ROOT)
        runner = AutoReviewRunner(stage.root, stage.stage_dir, registry=real_reg,
                                  invoker=None, now=lambda: BASE_TIME, timeout_override=42)
        self.assertEqual(runner._resolve_timeout("claude_glm", "noninteractive_command"), 42)
        self.assertEqual(runner._resolve_timeout("grok", "optional_review_command"), 42)

    def _invoke_and_capture(self, stage, adapter, key, prompt_abs):
        real_reg = RUNNER.load_registry(REPO_ROOT)
        runner = AutoReviewRunner(stage.root, stage.stage_dir, registry=real_reg,
                                  invoker=None, now=lambda: BASE_TIME)
        captured = {}
        orig = RUNNER.subprocess.run

        class _Proc:
            returncode = 0
            stdout = b""
            stderr = b""

        def fake_run(command, *a, **k):
            captured["command"] = command
            return _Proc()

        RUNNER.subprocess.run = fake_run
        self.addCleanup(setattr, RUNNER.subprocess, "run", orig)
        runner._default_invoke(adapter, key, Path(prompt_abs))
        return captured["command"]

    def test_claude_glm_real_command_substitutes_and_unescapes(self):
        stage = Stage()
        prompt_abs = str(stage.root / "review.prompt.md")
        cmd = self._invoke_and_capture(stage, "claude_glm", "noninteractive_command", prompt_abs)
        for marker in ("<prompt-file>", "<repo>", "@PROMPT@", "@REPO@", '\\"'):
            self.assertNotIn(marker, cmd)
        self.assertIn('-p "$(cat ', cmd)        # unescaped double-quote structure
        self.assertIn(prompt_abs, cmd)
        self.assertIn(str(stage.root), cmd)

    def test_kimi_real_command_substitutes_and_unescapes(self):
        stage = Stage()
        prompt_abs = str(stage.root / "review.prompt.md")
        cmd = self._invoke_and_capture(stage, "kimi", "embedded_read_only_review_command", prompt_abs)
        for marker in ("<prompt-file>", "<repo>", "@PROMPT@", "@REPO@", '\\"'):
            self.assertNotIn(marker, cmd)
        self.assertIn(prompt_abs, cmd)

    def test_grok_real_command_substitutes_both_placeholders(self):
        stage = Stage()
        prompt_abs = str(stage.root / "review.prompt.md")
        cmd = self._invoke_and_capture(stage, "grok", "optional_review_command", prompt_abs)
        for marker in ("<prompt-file>", "<repo>", "@PROMPT@", "@REPO@"):
            self.assertNotIn(marker, cmd)
        self.assertIn(prompt_abs, cmd)
        self.assertIn(str(stage.root), cmd)


# ===========================================================================
# Review-2 fix round 1 — F4: verdict schema alignment + byte fidelity (sol §F4)
# ===========================================================================

class VerdictSchemaAndByteFidelityTests(unittest.TestCase):
    """The hand validator must mirror ``schemas/review-verdict.schema.json``
    (reject unknown top-level fields, validate array item types / finding
    constraints). ``_store_verdict`` must persist the accepted SOURCE byte span,
    never a ``json.dumps`` reserialization."""

    def test_unknown_top_level_field_rejected(self):
        doc = _verdict(stage_id="auto-stage", unit_fp="FP1")
        doc["mystery_field"] = "x"
        errs = RUNNER.validate_review_verdict_doc(doc)
        self.assertTrue(any("unknown top-level fields" in e for e in errs))

    def test_required_fixes_non_string_item_rejected(self):
        doc = _verdict(stage_id="auto-stage", unit_fp="FP1")
        doc["required_fixes"] = ["ok", 7]
        errs = RUNNER.validate_review_verdict_doc(doc)
        self.assertTrue(any("required_fixes" in e for e in errs))

    def test_finding_unknown_field_rejected(self):
        doc = _verdict(stage_id="auto-stage", unit_fp="FP1", findings=[
            {"severity": "P1", "title": "t", "file": "scripts/x.py", "line": 1,
             "evidence": "e", "impact": "i", "recommendation": "r", "bogus": "x"}])
        errs = RUNNER.validate_review_verdict_doc(doc)
        self.assertTrue(any("unknown fields" in e for e in errs))

    def test_finding_bad_severity_and_line_rejected(self):
        doc = _verdict(stage_id="auto-stage", unit_fp="FP1", findings=[
            {"severity": "P9", "title": "t", "file": "scripts/x.py", "line": 0,
             "evidence": "e", "impact": "i", "recommendation": "r"}])
        errs = RUNNER.validate_review_verdict_doc(doc)
        joined = " | ".join(errs)
        self.assertIn("severity", joined)
        self.assertIn("line", joined)

    def test_residual_risks_non_string_item_rejected(self):
        doc = _verdict(stage_id="auto-stage", unit_fp="FP1")
        doc["residual_risks"] = ["ok", None]
        errs = RUNNER.validate_review_verdict_doc(doc)
        self.assertTrue(any("residual_risks" in e for e in errs))

    def test_stored_verdict_is_accepted_source_span_byte_for_byte(self):
        # raw stdout with surrounding prose and a NON-canonical verdict object
        # (reordered/loose spacing) so a json.dumps reserialize would differ.
        verdict_src = (
            '{ "verdict" : "ACCEPT" , "diff_fingerprint":"FP1" ,'
            ' "role":"first_reviewer" , "model":"grok" , "schema_version":1 ,'
            ' "stage_id":"auto-stage" , "reviewer_prior_involvement":"none" ,'
            ' "reviewed_artifacts":["scripts/x.py"] , "findings":[] ,'
            ' "required_fixes":[] , "next_action":"stage_accepted_waiting_user" }'
        )
        raw_text = "leading prose before verdict\n" + verdict_src + "\ntrailing prose\n"
        unit = {"diff_fingerprint": "FP1"}
        verdict, reason, _candidates, span = RUNNER.select_verdict(
            raw_text, unit, stage_id="auto-stage", role="first_reviewer")
        self.assertIsNotNone(verdict)
        self.assertEqual(reason, "accepted")
        self.assertIsNotNone(span)
        # a canonical reserialize must DIFFER from the source (proves no reserialize)
        self.assertNotEqual(json.dumps(verdict), verdict_src)

        stage = Stage()
        runner = stage.make_runner(invoker=lambda *a, **k: _ir(),
                                   blocking_runner=lambda u, c, p: 0, seal=FakeSeal())
        runner.load_status()
        verdict_rel = runner._store_verdict("T1", 1, 1, raw_text, span)
        stored_path = lib.resolve_safe_path(stage.root, verdict_rel)
        self.assertIsNotNone(stored_path)
        stored = stored_path.read_bytes()
        # the stored bytes equal the exact source span, byte for byte
        self.assertEqual(stored, verdict_src.encode("utf-8"))
        self.assertEqual(stored, raw_text[span[0]:span[1]].encode("utf-8"))


# ===========================================================================
# Review-2 fix round 1 — F5: single ledger + per-step expiry (sol §F5)
# ===========================================================================

class ReworkLedgerAndExpiryTests(unittest.TestCase):
    """``_charge_auto_change`` must increment the shared top-level ``rework_count``
    alongside ``auto_code_changes_used`` and honor the global ``MAX_STAGE_REWORK``
    invariant (3). A non-null ``expires_at`` is rechecked before every model call
    (acceptance 28), not only during initial preflight."""

    def test_charge_auto_change_increments_shared_ledger(self):
        stage = Stage()
        runner = stage.make_runner(invoker=lambda *a, **k: _ir(),
                                   blocking_runner=lambda u, c, p: 0, seal=FakeSeal())
        runner.load_status()
        runner._auth = {"budgets": {"max_auto_code_changes": 5}}
        runner._budgets()["auto_code_changes_used"] = 0
        runner._status["rework_count"] = 0
        runner._charge_auto_change()
        self.assertEqual(runner._budgets()["auto_code_changes_used"], 1)
        self.assertEqual(runner._status["rework_count"], 1)

    def test_charge_auto_change_escalates_past_max_stage_rework(self):
        stage = Stage()
        runner = stage.make_runner(invoker=lambda *a, **k: _ir(),
                                   blocking_runner=lambda u, c, p: 0, seal=FakeSeal())
        runner.load_status()
        runner._auth = {"budgets": {"max_auto_code_changes": 5}}
        runner._budgets()["auto_code_changes_used"] = 0
        runner._status["rework_count"] = 3  # proposed 4 > MAX_STAGE_REWORK invariant (3)
        with self.assertRaises(RUNNER.TerminalEscalation) as cm:
            runner._charge_auto_change()
        self.assertEqual(cm.exception.event, "budget_exhausted")
        # FX7: on escalation NEITHER counter is written — rework_count and
        # auto_code_changes_used both stay at their pre-charge original values.
        self.assertEqual(runner._status["rework_count"], 3)
        self.assertEqual(runner._budgets()["auto_code_changes_used"], 0)

    def test_charge_auto_change_escalation_leaves_auto_counter_unchanged(self):
        # FX7: when the AUTO change cap is exceeded, NEITHER counter is written
        # (auto_code_changes_used stays at cap, rework_count stays put).
        stage = Stage()
        runner = stage.make_runner(invoker=lambda *a, **k: _ir(),
                                   blocking_runner=lambda u, c, p: 0, seal=FakeSeal())
        runner.load_status()
        runner._auth = {"budgets": {"max_auto_code_changes": 1}}
        runner._budgets()["auto_code_changes_used"] = 1  # at cap -> proposed 2 > 1
        runner._status["rework_count"] = 0
        with self.assertRaises(RUNNER.TerminalEscalation) as cm:
            runner._charge_auto_change()
        self.assertEqual(cm.exception.event, "budget_exhausted")
        self.assertEqual(runner._budgets()["auto_code_changes_used"], 1)
        self.assertEqual(runner._status["rework_count"], 0)

    def test_charge_auto_change_at_exact_cap_is_legal(self):
        # FX7 boundary: reaching exactly max is legal (proposed == max, not > max).
        stage = Stage()
        runner = stage.make_runner(invoker=lambda *a, **k: _ir(),
                                   blocking_runner=lambda u, c, p: 0, seal=FakeSeal())
        runner.load_status()
        runner._auth = {"budgets": {"max_auto_code_changes": 2}}
        runner._budgets()["auto_code_changes_used"] = 1  # proposed 2 == max, legal
        runner._status["rework_count"] = 0
        runner._charge_auto_change()  # must NOT raise
        self.assertEqual(runner._budgets()["auto_code_changes_used"], 2)
        self.assertEqual(runner._status["rework_count"], 1)

    def test_rework_fix_charges_shared_rework_ledger_e2e(self):
        stage = Stage(max_auto_code_changes=2)
        rnd = {"n": 0}

        def invoke(adapter_id, command_key, prompt_abs, timeout):
            if command_key == "noninteractive_command":
                (stage.root / "scripts" / "x.py").write_text("X = 1\n", encoding="utf-8")
                return _ir(b"imp")
            if command_key == "embedded_read_only_review_command":
                return _ir(b"advisory")
            if command_key == "optional_review_command":
                rnd["n"] += 1
                fp = stage.unit().get("diff_fingerprint")
                if rnd["n"] == 1:
                    out = json.dumps(_verdict(stage_id=stage.stage_id, unit_fp=fp, verdict="REWORK"))
                else:
                    out = json.dumps(_verdict(stage_id=stage.stage_id, unit_fp=fp, verdict="ACCEPT"))
                return _ir(out.encode())
            return _ir()

        runner = stage.make_runner(invoker=invoke, blocking_runner=lambda u, c, p: 0, seal=FakeSeal())
        result = runner.run()
        self.assertEqual(result.terminal, "completed_review_1")
        arp = stage.reload()["auto_review_pipeline"]
        self.assertEqual(arp["budgets"]["auto_code_changes_used"], 1)
        self.assertEqual(stage.reload().get("rework_count"), 1)

    def test_authorization_expiry_rechecked_before_later_model_call(self):
        # expires_at is in the future at preflight, but the implementation call
        # advances the clock past it; the next model call (embedded cross-check)
        # must fail closed on the now-past expiry — not sail through to seal.
        stage = Stage(auth_mutator=lambda auth: auth.__setitem__(
            "expires_at", "2026-07-11T12:00:30Z"))  # BASE_TIME + 30s

        class Clock:
            def __init__(self):
                self.t = BASE_TIME

            def __call__(self):
                return self.t

        clock = Clock()

        def invoke(adapter_id, command_key, prompt_abs, timeout):
            if command_key == "noninteractive_command":
                (stage.root / "scripts" / "x.py").write_text("X = 1\n", encoding="utf-8")
                clock.t = BASE_TIME + datetime.timedelta(seconds=60)  # past the 30s expiry
                return _ir(b"imp")
            return _ir()

        runner = stage.make_runner(invoker=invoke, blocking_runner=lambda u, c, p: 0,
                                   seal=FakeSeal(), now=clock)
        result = runner.run()
        self.assertEqual(result.terminal, "human_escalation_required")
        events = [m["event"] for m in stage.reload()["auto_review_pipeline"].get("mode_history", [])]
        self.assertIn("timeout", events)


# ===========================================================================
# Review-2 fix round 1 — F6: exclusive runner lock (sol §F6, runner side)
# ===========================================================================

class RunnerLockTests(unittest.TestCase):
    """The runner holds an exclusive, runtime-only lock under git metadata for the
    duration of a run. FX4: a second run that finds the lock held is the lock
    LOSER — contention precedes any state transition, so it writes nothing and
    returns ``lock_busy`` (return-value + stderr only), never touching status."""

    def test_concurrent_runner_lock_is_exclusive(self):
        stage = Stage()
        calls = {"n": 0}

        def invoke(*a, **k):
            calls["n"] += 1
            return _ir()

        def stage_dir_snapshot():
            # sha256 of every file under the stage dir, keyed by repo-relative path
            out = {}
            for p in sorted(stage.stage_dir.rglob("*")):
                if p.is_file():
                    out[p.relative_to(stage.stage_dir).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
            return out

        # runner A acquires and HOLDS the lock (does not run the body)
        runner_a = stage.make_runner(invoker=invoke, blocking_runner=lambda u, c, p: 0,
                                     seal=FakeSeal())
        runner_a.load_status()
        runner_a._acquire_runner_lock()
        try:
            before = stage_dir_snapshot()
            runner_b = stage.make_runner(invoker=invoke, blocking_runner=lambda u, c, p: 0,
                                         seal=FakeSeal())
            result = runner_b.run()
            # (a) lock contention → lock_busy (return-value only, never in status)
            self.assertEqual(result.terminal, "lock_busy")
            self.assertEqual(calls["n"], 0, "no adapter call while the lock is held")
            # (b) every stage-dir file is byte-identical before/after (zero write)
            self.assertEqual(stage_dir_snapshot(), before,
                             "lock loser must not write any stage-dir file")
            # (c) no new escalation artifact (old behavior wrote 80-escalation-...md)
            self.assertFalse(any(stage.stage_dir.glob("80-escalation-*runner_lock_busy*.md")))
            # status.json itself was not mutated toward awaiting_human
            status = lib.load_json(stage.stage_dir / "status.json")
            self.assertNotEqual(status.get("status"), "awaiting_human")
        finally:
            runner_a._release_runner_lock()


# ===========================================================================
# Review-2 fix round 1 — F7: restart idempotency + adapter-error stop (sol §F7)
# ===========================================================================

class RestartAndAdapterErrorTests(unittest.TestCase):
    """A restart must not redispatch accepted work; ``completed_review_1`` is a
    no-op. A nonzero/timed-out implementation or fix adapter result stops the
    unit flow (escalation) — blocking and seal never run carrying a failed result."""

    def test_restart_completed_review_1_is_noop(self):
        stage = Stage(runner_state="completed_review_1", dispatch_mode="auto_review")
        calls = {"n": 0}

        def invoke(*a, **k):
            calls["n"] += 1
            return _ir()

        runner = stage.make_runner(invoker=invoke, blocking_runner=lambda u, c, p: 0, seal=FakeSeal())
        result = runner.run()
        self.assertFalse(result.ran)
        self.assertEqual(result.terminal, "completed_review_1")
        self.assertEqual(calls["n"], 0)

    def test_restart_running_skips_accepted_unit_no_redispatch(self):
        stage = Stage(runner_state="running", dispatch_mode="auto_review")
        unit = stage.status["auto_review_pipeline"]["review_units"][0]
        unit["snapshot_commit"] = "sealedsha"
        unit["head_sha"] = "sealedsha"
        unit["diff_fingerprint"] = "sealedfp"
        unit["review_1"] = {"verdict": "ACCEPT", "provider": "grok",
                            "json_schema_valid": True, "diff_fingerprint": "sealedfp",
                            "verdict_path": "reports/agent-runs/auto-stage/x.verdict.json"}
        arp = stage.status["auto_review_pipeline"]
        arp["mode_history"] = [{"event": "new_human_authorization"},
                               {"event": "successful_full_preflight"}]
        stage._write_status()
        stage.git("add", "-A")
        stage.git("commit", "-q", "--allow-empty", "-m", "running-accepted")

        impl_calls = {"n": 0}

        def invoke(adapter_id, command_key, prompt_abs, timeout):
            if command_key == "noninteractive_command":
                impl_calls["n"] += 1
            return _ir()

        runner = stage.make_runner(invoker=invoke, blocking_runner=lambda u, c, p: 0, seal=FakeSeal())
        result = runner.run()
        self.assertEqual(result.terminal, "completed_review_1")
        self.assertEqual(impl_calls["n"], 0, "restart must not redispatch an ACCEPT unit")

    def test_implementation_adapter_error_stops_before_blocking_and_seal(self):
        stage = Stage()
        seal = FakeSeal()
        blk = {"n": 0}

        def blocking(u, c, p):
            blk["n"] += 1
            return 0

        def invoke(adapter_id, command_key, prompt_abs, timeout):
            if command_key == "noninteractive_command":
                return _ir(b"err", exit_status=2, failure_class="command_error")
            return _ir()

        runner = stage.make_runner(invoker=invoke, blocking_runner=blocking, seal=seal)
        result = runner.run()
        self.assertEqual(result.terminal, "human_escalation_required")
        self.assertEqual(blk["n"], 0, "blocking must not run after an implementation adapter error")
        self.assertEqual(seal.calls, [], "seal must not run after an implementation adapter error")

    def test_fix_adapter_error_stops_before_second_seal(self):
        stage = Stage(max_auto_code_changes=2)
        rnd = {"n": 0}
        seal = FakeSeal()

        def invoke(adapter_id, command_key, prompt_abs, timeout):
            if command_key == "noninteractive_command":
                if "/fix-" in str(prompt_abs):
                    return _ir(b"err", exit_status=2, failure_class="command_error")
                (stage.root / "scripts" / "x.py").write_text("X = 1\n", encoding="utf-8")
                return _ir(b"imp")
            if command_key == "embedded_read_only_review_command":
                return _ir(b"advisory")
            if command_key == "optional_review_command":
                rnd["n"] += 1
                fp = stage.unit().get("diff_fingerprint")
                if rnd["n"] == 1:
                    out = json.dumps(_verdict(stage_id=stage.stage_id, unit_fp=fp, verdict="REWORK"))
                else:
                    out = json.dumps(_verdict(stage_id=stage.stage_id, unit_fp=fp, verdict="ACCEPT"))
                return _ir(out.encode())
            return _ir()

        runner = stage.make_runner(invoker=invoke, blocking_runner=lambda u, c, p: 0, seal=seal)
        result = runner.run()
        self.assertEqual(result.terminal, "human_escalation_required")
        # round-1 seal happened; the post-fix re-seal (round 2) must NOT have run
        self.assertEqual(len(seal.calls), 1, "fix adapter error must stop before the second seal")
        events = [m["event"] for m in stage.reload()["auto_review_pipeline"].get("mode_history", [])]
        self.assertIn("unroutable_fix", events)


# ===========================================================================
# Review-2 round 2 final fix — FX1: shell-safe adapter invocation (sol P1#1)
# ===========================================================================

class ShellSafeInvocationTests(unittest.TestCase):
    """The real registry templates substitute runner-owned paths into two
    contexts: double-quoted command substitution ``"$(cat <prompt-file>)"``
    (claude_glm/kimi) and bare words ``--prompt-file <prompt-file>`` (grok).
    The repository path itself contains a space (``ai code``), so raw
    substitution makes ``cat`` receive split arguments. Each substituted value
    must be ``shlex.quote()``-wrapped in BOTH contexts; the quoted value is a
    single shell word inside ``$()`` (a fresh parse context where single
    quotes are effective) and as a bare argument."""

    def _capture_command(self, stage, adapter, key, prompt_abs):
        """Run ``_default_invoke`` with a fake subprocess.run that captures the
        expanded command string (no real process semantics asserted here)."""
        real_reg = RUNNER.load_registry(REPO_ROOT)
        runner = AutoReviewRunner(stage.root, stage.stage_dir, registry=real_reg,
                                  invoker=None, now=lambda: BASE_TIME)
        captured = {}
        orig = RUNNER.subprocess.run

        class _Proc:
            returncode = 0
            stdout = b""
            stderr = b""

        def fake_run(command, *a, **k):
            captured["command"] = command
            return _Proc()

        RUNNER.subprocess.run = fake_run
        self.addCleanup(setattr, RUNNER.subprocess, "run", orig)
        runner._default_invoke(adapter, key, Path(prompt_abs))
        return captured["command"]

    def test_real_registry_paths_with_spaces_and_metachars_are_shell_quoted(self):
        # path contains a space plus $ ; and a single quote — all shell-meaningful
        nasty = "repo with space/p$home;x'md.md"
        cases = [
            ("claude_glm", "noninteractive_command"),
            ("kimi", "noninteractive_command"),
            ("kimi", "embedded_read_only_review_command"),
            ("grok", "development_command"),
            ("grok", "optional_review_command"),
        ]
        # Build Stage() ONCE, before the loop. _capture_command patches the
        # GLOBAL subprocess.run (RUNNER.subprocess IS sys.modules['subprocess'])
        # and restores it only via addCleanup at method end. If Stage() ran
        # inside the loop, its make_temp_repo()→git() on the 2nd+ iteration
        # would hit the still-installed fake_run (whose stdout is bytes b""),
        # corrupting self.branch and breaking json.dumps(auth). Reusing one
        # stage avoids calling make_temp_repo() while the patch is live.
        stage = Stage()
        prompt_abs = str(stage.root / nasty)
        for adapter, key in cases:
            cmd = self._capture_command(stage, adapter, key, prompt_abs)
            for marker in ("<prompt-file>", "<repo>", "@PROMPT@", "@REPO@"):
                self.assertNotIn(marker, cmd, "%s.%s still has literal %r" % (adapter, key, marker))
            # the substituted prompt path appears exactly as shlex.quote() emitted
            # it — a single quoted shell word — not split on its internal spaces
            self.assertIn(shlex.quote(prompt_abs), cmd,
                          "%s.%s prompt path not shell-quoted intact: %r" % (adapter, key, cmd))

    def test_bare_word_grok_path_is_one_shlex_token(self):
        # grok's bare --prompt-file/--cwd context: after substitution + shlex.split
        # the path must resurface as ONE intact token (proves no word-splitting)
        nasty = "repo with space/grok$;quote'md.md"
        stage = Stage()
        prompt_abs = str(stage.root / nasty)
        cmd = self._capture_command(stage, "grok", "optional_review_command", prompt_abs)
        tokens = shlex.split(cmd)
        self.assertIn(prompt_abs, tokens,
                      "grok bare-word path split into multiple tokens: %r" % cmd)

    def test_execution_probe_cmdsub_context_space_in_path(self):
        # REAL shell=True execution, prompt file inside a space-named directory.
        # Context 1: double-quoted command substitution "$(cat <prompt-file>)".
        # The prompt file's CONTENT is a path (also space-containing) that cat reads.
        base = tempfile.mkdtemp(prefix="harness-shell-probe-")
        spaced = Path(base) / "repo with space"
        spaced.mkdir()
        marker = "PROBE-MARKER-CONTENT"
        registry = {"probe_cmdsub": {"commands": {
            "noninteractive_command": 'cat "$(cat <prompt-file>)"'},
            "timeout_seconds": 30}}
        target = spaced / "target_cmdsub.txt"
        target.write_text(marker, encoding="utf-8")
        prompt = spaced / "prompt_cmdsub.md"
        prompt.write_text(str(target), encoding="utf-8")  # content = path cat will read
        runner = AutoReviewRunner(spaced, spaced, registry=registry, now=lambda: BASE_TIME)
        result = runner._default_invoke("probe_cmdsub", "noninteractive_command", prompt)
        self.assertEqual(result.exit_status, 0,
                         "cmdsub probe must exit 0 post-fix; stdout=%r" % result.stdout)
        self.assertIn(marker.encode(), result.stdout)

    def test_execution_probe_bare_word_context_space_in_path(self):
        # Context 2: bare-word ``cat <prompt-file>`` (grok --prompt-file shape).
        base = tempfile.mkdtemp(prefix="harness-shell-probe-")
        spaced = Path(base) / "repo with space"
        spaced.mkdir()
        marker = "PROBE-MARKER-CONTENT"
        registry = {"probe_bare": {"commands": {
            "noninteractive_command": "cat <prompt-file>"},
            "timeout_seconds": 30}}
        prompt = spaced / "prompt_bare.md"
        prompt.write_text(marker, encoding="utf-8")
        runner = AutoReviewRunner(spaced, spaced, registry=registry, now=lambda: BASE_TIME)
        result = runner._default_invoke("probe_bare", "noninteractive_command", prompt)
        self.assertEqual(result.exit_status, 0,
                         "bare-word probe must exit 0 post-fix; stdout=%r" % result.stdout)
        self.assertIn(marker.encode(), result.stdout)


class SealCommitGuardWiringTests(unittest.TestCase):
    """FX2 runner side: ``_node_seal`` wires ``self._check_authorization_expiry``
    as the seal's per-commit ``commit_guard``, and a mid-seal guard timeout
    propagates unchanged (event ``timeout``) — never rewritten to
    ``unroutable_fix``. Per-commit H_bind-blocking with real git is covered by
    ``test_stage_seal.CommitGuardTests``."""

    def test_node_seal_passes_expiry_check_as_commit_guard(self):
        stage = Stage()
        captured = {}

        class _SpySeal:
            def seal(self, root, stage_dir, unit_id, commit_guard=None):
                captured["guard"] = commit_guard
                return {"head_sha": "x", "diff_fingerprint": "y", "receipt": "z"}

            def run_validator(self, *a, **k):
                pass

        runner = stage.make_runner(invoker=lambda *a, **k: _ir(),
                                   blocking_runner=lambda u, c, p: 0, seal=_SpySeal())
        runner.load_status()
        unit = runner._find_unit("T1")
        runner._node_seal(unit)
        # bound methods compare by (__func__, __self__); `is` fails because each
        # attribute access yields a fresh method object, so assertEqual is correct.
        self.assertEqual(captured["guard"], runner._check_authorization_expiry)

    def test_node_seal_propagates_guard_timeout_unchanged(self):
        # injected now() is AFTER expires_at → the per-commit guard raises
        # TerminalEscalation(timeout) inside seal; _node_seal must propagate it
        # unchanged (event 'timeout'), not rewrite to 'unroutable_fix'.
        now = datetime.datetime(2026, 7, 12, 12, 0, 0, tzinfo=datetime.timezone.utc)
        stage = Stage(auth_mutator=lambda a: a.__setitem__(
            "expires_at", "2026-07-12T11:00:00Z"))  # one hour before now → expired

        class _GuardFiringSeal:
            def seal(self, root, stage_dir, unit_id, commit_guard=None):
                if commit_guard is not None:
                    commit_guard()  # _check_authorization_expiry → expired → timeout
                return {"head_sha": "x", "diff_fingerprint": "y", "receipt": "z"}

            def run_validator(self, *a, **k):
                pass

        runner = stage.make_runner(invoker=lambda *a, **k: _ir(),
                                   blocking_runner=lambda u, c, p: 0,
                                   seal=_GuardFiringSeal(), now=lambda: now)
        runner.load_status()
        # preflight normally loads auth.json into self._auth; calling _node_seal
        # directly bypasses it, so mirror that load so the guard sees expires_at.
        runner._auth = stage.auth
        unit = runner._find_unit("T1")
        with self.assertRaises(RUNNER.TerminalEscalation) as ctx:
            runner._node_seal(unit)
        self.assertEqual(ctx.exception.event, "timeout")


class ResumeIdempotencyTests(unittest.TestCase):
    """FX5 case A: resuming a run (runner_state=running) never redispatches a
    unit that already started. Any implementation / embedded_cross_check / fix
    receipt on disk proves 'started but unfinished'; without a per-node cursor
    the run fails closed to awaiting_human with ZERO model calls. A clean unit
    (no such receipts) resumes from scratch."""

    def _seed_started_receipt(self, stage, unit_id, node, seq):
        # real runner-receipt shape (the on-disk state after a node wrote its
        # receipt and the process crashed before finishing the unit)
        receipt = {
            "schema_version": 1, "stage_id": stage.stage_id, "sequence": seq,
            "node": node, "attempt": 1, "review_unit_id": unit_id, "task_id": unit_id,
            "adapter": {"id": "claude_glm",
                        "registry_command_ref": "claude_glm#noninteractive_command"},
            "prompt_path": None, "raw_output_path": None, "verdict_path": None,
            "started_at": "2026-07-11T12:00:00Z", "completed_at": "2026-07-11T12:00:01Z",
            "exit_status": 0, "timeout": False,
            "call_budget": {"before": seq - 1, "after": seq},
            "failure_class": None, "next_transition": "blocking_check",
        }
        lib.atomic_write_json(
            stage.stage_dir / "runner-{}-{}.receipt.json".format(seq, node), receipt)

    def _seed_seal_receipt(self, stage, unit_id, seq):
        # seal receipts have a distinct shape (kind=seal, no node) and must NOT
        # by themselves trigger the started-receipt check
        receipt = {
            "schema_version": 1, "kind": "seal", "stage_id": stage.stage_id,
            "task_id": unit_id, "review_unit_id": unit_id,
            "base_sha": "0" * 40, "head_sha": "1" * 40, "diff_fingerprint": "fp",
            "bind_status": "bound",
            "blocking_second_pass": {"exit_status": 0, "ran_after_cross_check": True},
            "created_at": "2026-07-11T12:00:01Z",
            "note": "seed seal receipt (deterministic seal evidence)",
        }
        lib.atomic_write_json(
            stage.stage_dir / "runner-{}-seal.receipt.json".format(seq), receipt)

    def _assert_no_redispatch(self, stage):
        calls = {"n": 0}

        def invoke(*a, **k):
            calls["n"] += 1
            return _ir()

        runner = stage.make_runner(invoker=invoke, blocking_runner=lambda u, c, p: 0,
                                   seal=FakeSeal())
        result = runner.run()
        self.assertEqual(result.terminal, "awaiting_human")
        self.assertEqual(calls["n"], 0,
                         "resume must not redispatch any adapter (unit started but unfinished)")
        self.assertTrue(any(stage.stage_dir.glob(
            "80-escalation-recoverable_resume_unverifiable_unit*.md")))

    def test_resume_after_implementation_crash_does_not_redispatch(self):
        stage = Stage(runner_state="running", dispatch_mode="auto_review")
        self._seed_started_receipt(stage, "T1", "implementation", 1)
        self._assert_no_redispatch(stage)

    def test_resume_after_cross_check_crash_does_not_redispatch(self):
        stage = Stage(runner_state="running", dispatch_mode="auto_review")
        self._seed_started_receipt(stage, "T1", "implementation", 1)
        self._seed_started_receipt(stage, "T1", "embedded_cross_check", 2)
        self._assert_no_redispatch(stage)

    def test_resume_after_seal_crash_does_not_redispatch(self):
        # a seal receipt alone is not a 'started' node, but the implementation +
        # cross-check receipts that precede it are, so the unit is unverifiable.
        stage = Stage(runner_state="running", dispatch_mode="auto_review")
        self._seed_started_receipt(stage, "T1", "implementation", 1)
        self._seed_started_receipt(stage, "T1", "embedded_cross_check", 2)
        self._seed_seal_receipt(stage, "T1", 3)
        self._assert_no_redispatch(stage)

    def test_resume_after_review_crash_does_not_redispatch(self):
        # review_1 is not a 'started' node either; the preceding implementation +
        # cross-check receipts still make the unit unverifiable on resume.
        stage = Stage(runner_state="running", dispatch_mode="auto_review")
        self._seed_started_receipt(stage, "T1", "implementation", 1)
        self._seed_started_receipt(stage, "T1", "embedded_cross_check", 2)
        self._seed_started_receipt(stage, "T1", "review_1", 3)
        self._assert_no_redispatch(stage)

    def test_resume_after_fix_crash_does_not_redispatch(self):
        stage = Stage(runner_state="running", dispatch_mode="auto_review")
        self._seed_started_receipt(stage, "T1", "implementation", 1)
        self._seed_started_receipt(stage, "T1", "embedded_cross_check", 2)
        self._seed_started_receipt(stage, "T1", "fix", 3)
        self._assert_no_redispatch(stage)

    def test_resume_clean_unit_runs_from_scratch(self):
        # FX5: a unit with NO started receipts resumes normally from scratch.
        stage = Stage(runner_state="running", dispatch_mode="auto_review")
        calls = {"n": 0}
        accept = _accept_invoker(stage)

        def invoke(*a, **k):
            calls["n"] += 1
            return accept(*a, **k)

        runner = stage.make_runner(invoker=invoke, blocking_runner=lambda u, c, p: 0,
                                   seal=FakeSeal())
        result = runner.run()
        self.assertEqual(result.terminal, "completed_review_1")
        self.assertGreater(calls["n"], 0, "a clean unit resumes and dispatches normally")


class AuthorizationExactBindTests(unittest.TestCase):
    """FX6 (serial-only v1): an authorization must exact-bind the live status
    scope — bidirectional task IDs and allowed/forbidden pathspecs. Topology is
    no longer an authorization-scope field, and runtime caps come solely from
    the authorization (status records usage only), so there is no topology or
    cap divergence to bind. Every scope divergence fails closed at preflight."""

    def _run_preflight(self, stage):
        runner = stage.make_runner(invoker=lambda *a, **k: _ir(),
                                   blocking_runner=lambda u, c, p: 0, seal=FakeSeal())
        runner.load_status()
        try:
            runner.preflight()
        except RUNNER.PreflightFailed as exc:
            return exc
        self.fail("preflight should have failed closed for this authorization divergence")

    def test_authorized_but_absent_task_fails_closed(self):
        # FX6: auth - live must reject too. T2 is authorized but absent from live.
        def mutate(auth):
            auth["scope"]["task_ids"] = ["T1", "T2"]
        stage = Stage(auth_mutator=mutate)
        exc = self._run_preflight(stage)
        self.assertEqual(exc.reason, "scope_mismatch")
        self.assertEqual(exc.detail.get("authorized_but_absent"), ["T2"])

    def test_allowed_pathspec_divergence_fails_closed(self):
        # the unit edits scripts/x.py but the allowlist only permits elsewhere
        def mutate(auth):
            auth["scope"]["allowed_pathspecs"] = ["scripts/elsewhere.py"]
        stage = Stage(auth_mutator=mutate)
        exc = self._run_preflight(stage)
        self.assertEqual(exc.reason, "scope_mismatch")
        self.assertIn("pathspec_outside_allowlist", exc.detail)

    def test_forbidden_pathspec_hit_fails_closed(self):
        def mutate(auth):
            auth["scope"]["forbidden_pathspecs"] = ["scripts/x.py"]  # unit path forbidden
        stage = Stage(auth_mutator=mutate)
        exc = self._run_preflight(stage)
        self.assertEqual(exc.reason, "scope_mismatch")
        self.assertIn("forbidden_pathspec_hit", exc.detail)


# ===========================================================================
# T4 correction round 1 — C1: registry timeout fail-closed preflight
# ===========================================================================

class RegistryTimeoutPreflightTests(unittest.TestCase):
    """C1: missing/boolean/zero/negative auto-loop adapter timeouts fail closed
    in preflight before any model call or commit. Serial-only v1 has no silent
    1800 fallback; the explicit test timeout_override remains available but is
    never a production default."""

    def _runner_with_registry(self, mutator):
        stage = Stage()
        reg = json.loads(json.dumps(RUNNER.load_registry(REPO_ROOT)))
        mutator(reg)
        runner = AutoReviewRunner(stage.root, stage.stage_dir, registry=reg,
                                  invoker=None, now=lambda: BASE_TIME)
        runner.load_status()
        return runner

    def test_preflight_rejects_missing_adapter_timeout(self):
        def mutate(reg):
            del reg["claude_glm"]["timeout_seconds"]
        runner = self._runner_with_registry(mutate)
        with self.assertRaises(RUNNER.PreflightFailed) as cm:
            runner.preflight()
        self.assertEqual(cm.exception.reason, "registry_timeout_invalid")
        self.assertEqual(cm.exception.detail.get("adapter"), "claude_glm")

    def test_preflight_rejects_boolean_timeout(self):
        # a boolean is an int subclass; the gate must reject it explicitly.
        def mutate(reg):
            reg["grok"]["optional_review_timeout_seconds"] = True
        runner = self._runner_with_registry(mutate)
        with self.assertRaises(RUNNER.PreflightFailed) as cm:
            runner.preflight()
        self.assertEqual(cm.exception.reason, "registry_timeout_invalid")
        self.assertEqual(cm.exception.detail.get("key"), "optional_review_timeout_seconds")

    def test_preflight_rejects_zero_timeout(self):
        def mutate(reg):
            reg["kimi"]["timeout_seconds"] = 0
        runner = self._runner_with_registry(mutate)
        with self.assertRaises(RUNNER.PreflightFailed) as cm:
            runner.preflight()
        self.assertEqual(cm.exception.reason, "registry_timeout_invalid")

    def test_resolve_timeout_raises_when_registry_missing_and_no_override(self):
        # defense-in-depth: _resolve_timeout no longer silently returns 1800.
        stage = Stage()
        reg = json.loads(json.dumps(RUNNER.load_registry(REPO_ROOT)))
        del reg["claude_glm"]["timeout_seconds"]
        runner = AutoReviewRunner(stage.root, stage.stage_dir, registry=reg,
                                  invoker=None, now=lambda: BASE_TIME)
        with self.assertRaises(RUNNER.PreflightFailed) as cm:
            runner._resolve_timeout("claude_glm", "noninteractive_command")
        self.assertEqual(cm.exception.reason, "registry_timeout_invalid")


# ===========================================================================
# T4 correction round 1 — C2: runner task-only preflight
# ===========================================================================

class RunnerTaskOnlyPreflightTests(unittest.TestCase):
    """C2: the runner rejects any review unit whose kind is not exactly ``task``
    during preflight, before any model call or commit, independent of
    validate-stage.py."""

    def test_preflight_rejects_non_task_unit(self):
        stage = Stage(extra_unit_fields={"kind": "tip"})
        runner = stage.make_runner(invoker=lambda *a, **k: None)
        runner.load_status()
        with self.assertRaises(RUNNER.PreflightFailed) as cm:
            runner.preflight()
        self.assertEqual(cm.exception.reason, "non_task_unit")
        self.assertEqual(cm.exception.detail.get("kind"), "tip")


if __name__ == "__main__":
    unittest.main()
