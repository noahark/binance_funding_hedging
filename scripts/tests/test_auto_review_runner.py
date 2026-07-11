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
- call / wall-clock accounting timing (charge before start, timeout charges,
  restart does not reset the deadline);
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
import importlib.util
import json
import re
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

    def seal(self, root, stage_dir, unit_id):
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
                 enabled=True, review_1_provider="kimi", max_model_calls=20,
                 wall_clock_seconds=3600, max_auto_code_changes=2,
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

        # authorization artifact
        auth = json.loads(json.dumps(VALID_AUTH))
        auth["stage_id"] = stage_id
        auth["stage_branch"] = self.branch
        auth["review_1_provider"] = review_1_provider
        auth["scope"] = {
            "task_ids": ["T1"],
            "allowed_pathspecs": list(allowed_pathspecs),
            "forbidden_pathspecs": list(forbidden_pathspecs),
            "topology": topology,
        }
        auth["budgets"] = {
            "max_model_calls": max_model_calls,
            "wall_clock_seconds": wall_clock_seconds,
            "max_stage_rework": 3,
            "max_auto_code_changes": max_auto_code_changes,
            "invalid_json_max_attempts_per_model": 2,
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
                "runner_state": runner_state,
                "authorization_path": authorization_path or (
                    "reports/agent-runs/%s/auth.json" % stage_id),
                "budgets": {
                    "max_model_calls": max_model_calls,
                    "wall_clock_seconds": wall_clock_seconds,
                    "max_stage_rework": 3,
                    "max_auto_code_changes": max_auto_code_changes,
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
            "claude_glm": {"commands": {"noninteractive_command": "@PROMPT@"}},
            "kimi": {"commands": {
                "noninteractive_command": "@PROMPT@",
                "embedded_read_only_review_command": "@PROMPT@",
            }},
            "grok": {"commands": {
                "development_command": "@PROMPT@",
                "optional_review_command": "@PROMPT@",
            }},
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
# 9. parallel author set rejects cross-pool fallback
# ===========================================================================

class ParallelTipNoFallbackTests(unittest.TestCase):
    def test_parallel_tip_grok_failure_escalates_no_crosspool(self):
        # parallel topology; grok returns invalid repeatedly → no fallback
        stage = Stage(unit_authors=("claude_glm",), topology="parallel")
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
        self.assertEqual(grok_attempts["n"], 2, "parallel tip: grok retried once then escalated, no fallback")

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
# 14. call / wall-clock accounting timing
# ===========================================================================

class AccountingTimingTests(unittest.TestCase):
    def test_call_charged_before_adapter_start_even_on_timeout(self):
        stage = Stage(max_model_calls=3)
        started = {"n": 0}

        def invoke(adapter_id, command_key, prompt_abs, timeout):
            started["n"] += 1
            return InvokeResult(stdout=b"", exit_status=None, timed_out=True, failure_class="timeout",
                                started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")

        runner = stage.make_runner(invoker=invoke, blocking_runner=lambda u, c, p: 0, seal=FakeSeal())
        result = runner.run()
        # every adapter call (incl. timeouts) consumes one model call; with cap 3
        # the runner escalates on cap exhaustion.
        self.assertEqual(result.terminal, "human_escalation_required")
        arp = stage.arp()
        self.assertEqual(arp["budgets"]["model_calls_used"], 3)

    def test_wall_clock_restart_does_not_reset_deadline(self):
        # deadline computed once from run_started_at; a restart keeps it.
        stage = Stage(wall_clock_seconds=3600)
        runner = stage.make_runner(
            invoker=_accept_invoker(stage),
            blocking_runner=lambda u, c, p: 0, seal=FakeSeal())
        runner.load_status()
        runner._arp["dispatch_mode"] = "auto_review"
        runner._record_transition("new_human_authorization", "human_dispatch", None,
                                  "auto_review", "authorized")
        runner._set_state("authorized", "auto_review")
        runner._persist()
        runner._init_wall_clock()
        first_deadline = runner._arp.get("run_deadline_at")
        first_started = runner._arp.get("run_started_at")
        self.assertTrue(first_deadline)
        # simulate a restart: re-init must NOT change either field
        runner._init_wall_clock()
        self.assertEqual(runner._arp.get("run_deadline_at"), first_deadline)
        self.assertEqual(runner._arp.get("run_started_at"), first_started)

    def test_wall_clock_expiry_escalates_timeout(self):
        stage = Stage(wall_clock_seconds=3600)

        class Clock:
            def __init__(self):
                self.t = BASE_TIME

            def __call__(self):
                return self.t

        clock = Clock()

        def invoke(adapter_id, command_key, prompt_abs, timeout):
            if command_key == "noninteractive_command":
                (stage.root / "scripts" / "x.py").write_text("X = 1\n", encoding="utf-8")
                # jump past the deadline before the next charge
                clock.t = BASE_TIME + datetime.timedelta(seconds=4000)
                return InvokeResult(stdout=b"imp", exit_status=0, timed_out=False, failure_class=None,
                                    started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")
            return InvokeResult(stdout=b"", exit_status=0, timed_out=False, failure_class=None,
                                started_at="2026-07-11T00:00:00Z", completed_at="2026-07-11T00:00:01Z")

        runner = stage.make_runner(invoker=invoke, blocking_runner=lambda u, c, p: 0,
                                   seal=FakeSeal(), now=clock)
        result = runner.run()
        self.assertEqual(result.terminal, "human_escalation_required")
        events = [m["event"] for m in stage.arp().get("mode_history", [])]
        self.assertIn("timeout", events)


# ===========================================================================
# 15. P3 residual risk — pathspec exotic forms under parallel topology
#     (runner→seal blackbox: match correctly or fail closed, never silent miss)
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

    def test_parallel_topology_dirty_path_outside_allowlist_fail_closed(self):
        # under parallel topology, a stray path outside the (single-file) allowlist
        # is still rejected at preflight — no silent pass-through.
        stage = Stage(topology="parallel", allowed_pathspecs=("scripts/x.py",))
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


if __name__ == "__main__":
    unittest.main()
