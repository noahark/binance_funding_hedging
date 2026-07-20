#!/usr/bin/env python3
"""Deterministic tests for the human-operator/v1 dispatch-protocol checks in
``scripts/validate-stage.py`` (2026-07-20 dispatch/review reform, proposal
reports/agent-runs/_proposals/2026-07-20-harness-dispatch-review-reform.md
DRAFT-2 section 3.5 / test plan 3.9).

The validator is loaded via importlib because ``validate-stage.py`` has a
hyphen filename (not a valid Python identifier). Every fixture stage is built
under tmp_path with its own minimal ``agents/registry.yaml`` and a copy of the
real ``schemas/review-verdict.schema.json``; the tmp root is ``git init``-ed
so validator code paths that probe git behave deterministically (an empty
repo makes ``git rev-parse HEAD`` fail, which the validator already tolerates
when no authorized_exceptions records exist).

Coverage (proposal 3.9 groups 1-9):
  * dispatch-ready executor flip: new protocol rejects ``self`` and the
    abolished ``manual_user_handoff_allowed`` field, accepts
    ``human_operator``; legacy stages keep the old ``self`` rule untouched;
  * verdict parsing gate: missing artifact / unparseable JSON / fenced +
    footer extraction / status.json cross-check mismatch;
  * receipt sanity: ``adapter_cmd: n/a`` with ``status: done`` is rejected,
    a model recorded as executor is rejected;
  * preamble marker grep: dispatch prompt without
    ``[HARNESS-EXECUTOR-CONTRACT v1]`` fails dispatch-ready;
  * embedded pre-review opt-in: off-book artifacts when disabled fail, an
    empty opt-in reason fails;
  * dynamic required-files: parallel stages expand to task-level
    ``30-review-1-<task-id>.md`` and no longer require the unsuffixed file;
  * ``json_schema_valid`` abolition: a false status field no longer fails
    pre-accept when the artifact parses, and a true field cannot rescue an
    unparseable artifact;
  * session_id discipline: empty / bare ``unavailable`` rejected,
    ``unavailable:<reason>`` accepted, artifact/receipt mismatch rejected;
  * legacy stages (no ``dispatch_protocol``) bypass every new check.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent
REPO_ROOT = _SCRIPTS.parent

_spec = importlib.util.spec_from_file_location("validate_stage", _SCRIPTS / "validate-stage.py")
vs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vs)

REGISTRY_TEXT = """\
adapters:
  kimi:
    embedded_read_only_review_command: "kimi --model kimi-code/kimi-for-coding -p fixture"
  claude_glm:
    embedded_read_only_review_command: "claude-glm --model glm-5.2 -p fixture"
rotation:
  review_1:
    selection:
      implementer_provider_claude_glm: kimi
      implementer_provider_kimi: claude_glm
      default_preference: [kimi, claude_glm]
"""

FINGERPRINT = "deadbeef:" + "0" * 64


@pytest.fixture
def harness(tmp_path):
    """Minimal Harness repo: registry + real verdict schema + one stage dir."""
    root = tmp_path / "repo"
    (root / "agents").mkdir(parents=True)
    (root / "agents" / "registry.yaml").write_text(REGISTRY_TEXT)
    (root / "schemas").mkdir()
    shutil.copy(
        REPO_ROOT / "schemas" / "review-verdict.schema.json",
        root / "schemas" / "review-verdict.schema.json",
    )
    (root / "docs").mkdir()
    (root / "docs" / "parallel-development-mode.md").write_text("# parallel mode\n")
    stage_dir = root / "reports" / "agent-runs" / "fixture-stage"
    stage_dir.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    return root, stage_dir


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _checklist(task_id, owner, executor, *, embedded, protocol_new):
    reviewer = "kimi" if owner == "claude_glm" else "claude_glm"
    checklist = {
        "task_prompt_path": f"task-{task_id}.prompt.md",
        "self_tests_command": "pytest -q",
        "pass_branch": "report PASS and stop for bookkeeper",
        "blocker_branch": "scope-contained fix then rerun self-tests",
        "next_dispatch_executor": executor,
        "unavailable_branch": {
            "failure_classes": ["model_unavailable"],
            "escalation_artifact": f"embedded-review-{task_id}-round1.dispatch.md",
        },
    }
    if embedded:
        checklist.update(
            {
                "embedded_review_prompt_path": f"embedded-review-{task_id}-round1.prompt.md",
                "diff_patch_command": "git diff -- . > x.diff.patch",
                "diff_patch_path": f"embedded-review-{task_id}-round1.diff.patch",
                "cross_review_adapter": reviewer,
                "cross_review_command_ref": (
                    f"agents/registry.yaml#adapters.{reviewer}.embedded_read_only_review_command"
                ),
                "cross_review_raw_output_path": f"embedded-review-{task_id}-round1.raw-output.md",
                "cross_review_dispatch_path": f"embedded-review-{task_id}-round1.dispatch.md",
                "max_rounds": 2,
            }
        )
    if not protocol_new:
        checklist["manual_user_handoff_allowed"] = False
    return checklist


def _parallel_status(*, protocol, executor, embedded_opt_in="legacy"):
    """embedded_opt_in: "legacy" (old protocol, embedded always active), None
    (new protocol, not opted in), or a dict (new protocol, opted in)."""
    protocol_new = protocol is not None
    embedded = embedded_opt_in == "legacy" or isinstance(embedded_opt_in, dict)
    tasks = []
    for task_id, owner in (("A", "claude_glm"), ("B", "kimi")):
        tasks.append(
            {
                "id": task_id,
                "owner": owner,
                "r10_checklist": _checklist(
                    task_id, owner, executor, embedded=embedded, protocol_new=protocol_new
                ),
            }
        )
    status = {
        "stage_id": "fixture-stage",
        "status": "implementing",
        "parallel_mode": {
            "enabled": True,
            "r10_dispatch_tail_required": True,
            "r4_diff_reconciliation_required": True,
        },
        "tasks": tasks,
    }
    if protocol is not None:
        status["dispatch_protocol"] = protocol
    if isinstance(embedded_opt_in, dict):
        status["parallel_mode"]["embedded_review"] = embedded_opt_in
    return status


def _write_prompt(stage_dir, name, *, marker=True):
    body = (vs.EXECUTOR_CONTRACT_MARKER + "\n") if marker else ""
    (stage_dir / name).write_text(body + "任务正文\n")


def _setup_dispatch_ready(stage_dir, status, *, marker=True):
    for name in ("00-task.md", "10-design.md", "11-adr.md"):
        (stage_dir / name).write_text(f"# {name}\n")
    for task in status["tasks"]:
        checklist = task["r10_checklist"]
        _write_prompt(stage_dir, checklist["task_prompt_path"], marker=marker)
        if "embedded_review_prompt_path" in checklist:
            _write_prompt(stage_dir, checklist["embedded_review_prompt_path"], marker=marker)


def _verdict_json(verdict="ACCEPT", *, role="first_reviewer", model="kimi-2.7"):
    payload = {
        "schema_version": 1,
        "stage_id": "fixture-stage",
        "role": role,
        "model": model,
        "verdict": verdict,
        "diff_fingerprint": FINGERPRINT,
        "reviewer_prior_involvement": "none",
        "reviewed_artifacts": ["reports/agent-runs/fixture-stage/20-implementation.md"],
        "findings": [],
        "required_fixes": [],
        "next_action": "continue",
    }
    if verdict == "REWORK":
        payload["fix_start_prompt"] = "Fix the findings above within scope."
        payload["next_action"] = "fix"
    return json.dumps(payload, indent=2)


def _write_review_artifact(
    stage_dir, name, verdict_text, *, session_id="session_abc123", fenced=True
):
    text = "# review narrative\n\n"
    text += ("```json\n" + verdict_text + "\n```\n") if fenced else (verdict_text + "\n")
    text += (
        f"\n当前 Session ID: {session_id}\n"
        "Session ID 来源: cli_output\n"
        f"原始输出路径: {name}\n"
        "本地北京时间: 2026-07-20 20:00:00 CST\n"
        "下一步模型: human\n"
        "下一步任务: n/a\n"
    )
    (stage_dir / name).write_text(text)


def _write_dispatch(
    stage_dir,
    name,
    *,
    status="done",
    adapter_cmd='kimi --model kimi-code/kimi-for-coding -p "$(cat prompt.md)"',
    session_id="session_abc123",
    executor="human_operator",
    started="2026-07-20T10:00:00+08:00",
    completed="2026-07-20T10:05:00+08:00",
    marker=True,
):
    receipt = (
        "<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====\n"
        f"status:        {status}\n"
        "target_model:  kimi/kimi-2.7\n"
        f"adapter_cmd:   {adapter_cmd}\n"
        f"executor:      {executor}\n"
        f"started_at:    {started}\n"
        f"completed_at:  {completed}\n"
        f"session_id:    {session_id}\n"
        "outputs:       30-review-1.md\n"
        "next_dispatch: none\n"
        "===== END RECEIPT ===== -->\n\n"
    )
    body = "<!-- ===== PROMPT BODY（immutable） ===== -->\n"
    if marker:
        body += vs.EXECUTOR_CONTRACT_MARKER + "\n"
    (stage_dir / name).write_text(receipt + body)


def _single_review_status(*, verdict="ACCEPT", dispatch_path="review-1.dispatch.md"):
    return {
        "stage_id": "fixture-stage",
        "status": "review_2",
        "dispatch_protocol": vs.HUMAN_OPERATOR_DISPATCH_PROTOCOL,
        "review_1": {"verdict": verdict, "reviewer": "kimi", "dispatch_path": dispatch_path},
    }


def _ok_single_review_fixture(stage_dir, *, status_verdict="ACCEPT"):
    _write_review_artifact(stage_dir, "30-review-1.md", _verdict_json("ACCEPT"))
    _write_dispatch(stage_dir, "review-1.dispatch.md")
    return _single_review_status(verdict=status_verdict)


# ---------------------------------------------------------------------------
# Group 1+2: dispatch-ready executor flip + legacy regression protection
# ---------------------------------------------------------------------------


class TestDispatchReadyExecutorFlip:
    def test_new_protocol_rejects_self_executor(self, harness):
        root, stage_dir = harness
        status = _parallel_status(
            protocol=vs.HUMAN_OPERATOR_DISPATCH_PROTOCOL, executor="self", embedded_opt_in=None
        )
        _setup_dispatch_ready(stage_dir, status)
        errors = vs.validate_dispatch_ready(root, stage_dir, status)
        assert any("human_operator" in err for err in errors)

    def test_new_protocol_accepts_human_operator(self, harness):
        root, stage_dir = harness
        status = _parallel_status(
            protocol=vs.HUMAN_OPERATOR_DISPATCH_PROTOCOL,
            executor="human_operator",
            embedded_opt_in=None,
        )
        _setup_dispatch_ready(stage_dir, status)
        assert vs.validate_dispatch_ready(root, stage_dir, status) == []

    def test_new_protocol_rejects_manual_user_handoff_field(self, harness):
        root, stage_dir = harness
        status = _parallel_status(
            protocol=vs.HUMAN_OPERATOR_DISPATCH_PROTOCOL,
            executor="human_operator",
            embedded_opt_in=None,
        )
        for task in status["tasks"]:
            task["r10_checklist"]["manual_user_handoff_allowed"] = False
        _setup_dispatch_ready(stage_dir, status)
        errors = vs.validate_dispatch_ready(root, stage_dir, status)
        assert any("manual_user_handoff_allowed is abolished" in err for err in errors)

    def test_new_protocol_embedded_opt_in_still_checks_embedded_fields(self, harness):
        root, stage_dir = harness
        status = _parallel_status(
            protocol=vs.HUMAN_OPERATOR_DISPATCH_PROTOCOL,
            executor="human_operator",
            embedded_opt_in={"enabled": True, "reason": "high-risk contract change"},
        )
        _setup_dispatch_ready(stage_dir, status)
        assert vs.validate_dispatch_ready(root, stage_dir, status) == []

    def test_legacy_protocol_keeps_self_executor_rule(self, harness):
        root, stage_dir = harness
        status = _parallel_status(protocol=None, executor="self", embedded_opt_in="legacy")
        _setup_dispatch_ready(stage_dir, status)
        assert vs.validate_dispatch_ready(root, stage_dir, status) == []

    def test_legacy_protocol_rejects_human_operator_executor(self, harness):
        root, stage_dir = harness
        status = _parallel_status(
            protocol=None, executor="human_operator", embedded_opt_in="legacy"
        )
        _setup_dispatch_ready(stage_dir, status)
        errors = vs.validate_dispatch_ready(root, stage_dir, status)
        assert any("next_dispatch_executor must be 'self'" in err for err in errors)


# ---------------------------------------------------------------------------
# Group 5: preamble marker grep
# ---------------------------------------------------------------------------


class TestPreambleMarker:
    def test_missing_marker_line_fails_dispatch_ready(self, harness):
        root, stage_dir = harness
        status = _parallel_status(
            protocol=vs.HUMAN_OPERATOR_DISPATCH_PROTOCOL,
            executor="human_operator",
            embedded_opt_in=None,
        )
        _setup_dispatch_ready(stage_dir, status, marker=False)
        errors = vs.validate_dispatch_ready(root, stage_dir, status)
        assert any(vs.EXECUTOR_CONTRACT_MARKER in err for err in errors)

    def test_legacy_protocol_does_not_grep_marker(self, harness):
        root, stage_dir = harness
        status = _parallel_status(protocol=None, executor="self", embedded_opt_in="legacy")
        _setup_dispatch_ready(stage_dir, status, marker=False)
        assert vs.validate_dispatch_ready(root, stage_dir, status) == []


# ---------------------------------------------------------------------------
# Group 3: verdict parsing gate
# ---------------------------------------------------------------------------


class TestVerdictParsingGate:
    def test_missing_review_artifact_fails(self, harness):
        root, stage_dir = harness
        _write_dispatch(stage_dir, "review-1.dispatch.md")
        status = _single_review_status()
        errors = vs.validate_review_artifacts(root, stage_dir, status, "pre-review")
        assert any("does not exist" in err for err in errors)

    def test_unparseable_artifact_fails(self, harness):
        root, stage_dir = harness
        (stage_dir / "30-review-1.md").write_text("全是叙述文字，没有任何 JSON。\n")
        _write_dispatch(stage_dir, "review-1.dispatch.md")
        status = _single_review_status()
        errors = vs.validate_review_artifacts(root, stage_dir, status, "pre-review")
        assert any("no parseable JSON verdict object" in err for err in errors)

    def test_fenced_verdict_with_footer_extracts(self, harness):
        root, stage_dir = harness
        status = _ok_single_review_fixture(stage_dir)
        assert vs.validate_review_artifacts(root, stage_dir, status, "pre-review") == []

    def test_verdict_mismatch_with_status_fails(self, harness):
        root, stage_dir = harness
        status = _ok_single_review_fixture(stage_dir, status_verdict="REWORK")
        errors = vs.validate_review_artifacts(root, stage_dir, status, "pre-review")
        assert any("does not match status.json verdict" in err for err in errors)

    def test_recorded_verdict_requires_dispatch_path(self, harness):
        root, stage_dir = harness
        _write_review_artifact(stage_dir, "30-review-1.md", _verdict_json("ACCEPT"))
        status = _single_review_status(dispatch_path=None)
        errors = vs.validate_review_artifacts(root, stage_dir, status, "pre-review")
        assert any("dispatch_path must be recorded" in err for err in errors)

    def test_legacy_protocol_bypasses_parsing_gate(self, harness):
        root, stage_dir = harness
        status = _single_review_status()
        del status["dispatch_protocol"]
        assert vs.validate_review_artifacts(root, stage_dir, status, "pre-review") == []


# ---------------------------------------------------------------------------
# Group 4: receipt sanity
# ---------------------------------------------------------------------------


class TestReceiptSanity:
    def test_placeholder_adapter_cmd_with_done_status_fails(self, harness):
        root, stage_dir = harness
        _write_review_artifact(stage_dir, "30-review-1.md", _verdict_json("ACCEPT"))
        _write_dispatch(stage_dir, "review-1.dispatch.md", adapter_cmd="n/a")
        status = _single_review_status()
        errors = vs.validate_review_artifacts(root, stage_dir, status, "pre-review")
        assert any("real executed adapter_cmd" in err for err in errors)

    def test_pending_adapter_cmd_with_done_status_fails(self, harness):
        root, stage_dir = harness
        _write_review_artifact(stage_dir, "30-review-1.md", _verdict_json("ACCEPT"))
        _write_dispatch(stage_dir, "review-1.dispatch.md", adapter_cmd="pending")
        status = _single_review_status()
        errors = vs.validate_review_artifacts(root, stage_dir, status, "pre-review")
        assert any("real executed adapter_cmd" in err for err in errors)

    def test_model_as_executor_fails(self, harness):
        root, stage_dir = harness
        _write_review_artifact(stage_dir, "30-review-1.md", _verdict_json("ACCEPT"))
        _write_dispatch(stage_dir, "review-1.dispatch.md", executor="claude-glm")
        status = _single_review_status()
        errors = vs.validate_review_artifacts(root, stage_dir, status, "pre-review")
        assert any("must be the human operator" in err for err in errors)

    def test_unparseable_timestamp_fails(self, harness):
        root, stage_dir = harness
        _write_review_artifact(stage_dir, "30-review-1.md", _verdict_json("ACCEPT"))
        _write_dispatch(stage_dir, "review-1.dispatch.md", started="soon")
        status = _single_review_status()
        errors = vs.validate_review_artifacts(root, stage_dir, status, "pre-review")
        assert any("ISO-8601" in err for err in errors)

    def test_pending_receipt_skips_field_checks(self, harness):
        root, stage_dir = harness
        _write_review_artifact(stage_dir, "30-review-1.md", _verdict_json("ACCEPT"))
        _write_dispatch(
            stage_dir,
            "review-1.dispatch.md",
            status="pending",
            adapter_cmd="n/a",
            session_id="",
            started="",
            completed="",
        )
        status = _single_review_status()
        assert vs.validate_review_artifacts(root, stage_dir, status, "pre-review") == []


# ---------------------------------------------------------------------------
# Group 9: session_id discipline
# ---------------------------------------------------------------------------


class TestSessionIdDiscipline:
    def test_empty_session_id_fails(self, harness):
        root, stage_dir = harness
        _write_review_artifact(stage_dir, "30-review-1.md", _verdict_json("ACCEPT"))
        _write_dispatch(stage_dir, "review-1.dispatch.md", session_id="")
        status = _single_review_status()
        errors = vs.validate_review_artifacts(root, stage_dir, status, "pre-review")
        assert any("session_id is required" in err for err in errors)

    def test_bare_unavailable_session_id_fails(self, harness):
        root, stage_dir = harness
        _write_review_artifact(stage_dir, "30-review-1.md", _verdict_json("ACCEPT"))
        _write_dispatch(stage_dir, "review-1.dispatch.md", session_id="unavailable")
        status = _single_review_status()
        errors = vs.validate_review_artifacts(root, stage_dir, status, "pre-review")
        assert any("must carry a reason" in err for err in errors)

    def test_unavailable_with_reason_passes(self, harness):
        root, stage_dir = harness
        _write_review_artifact(
            stage_dir,
            "30-review-1.md",
            _verdict_json("ACCEPT"),
            session_id="unavailable（Kimi Work 桌面运行时未暴露）",
        )
        _write_dispatch(
            stage_dir,
            "review-1.dispatch.md",
            session_id="unavailable: kimi work desktop exposes no provider-native id",
        )
        status = _single_review_status()
        assert vs.validate_review_artifacts(root, stage_dir, status, "pre-review") == []

    def test_artifact_receipt_session_mismatch_fails(self, harness):
        root, stage_dir = harness
        _write_review_artifact(
            stage_dir, "30-review-1.md", _verdict_json("ACCEPT"), session_id="session_other"
        )
        _write_dispatch(stage_dir, "review-1.dispatch.md", session_id="session_abc123")
        status = _single_review_status()
        errors = vs.validate_review_artifacts(root, stage_dir, status, "pre-review")
        assert any("does not match dispatch receipt session_id" in err for err in errors)


# ---------------------------------------------------------------------------
# Group 6: embedded pre-review opt-in
# ---------------------------------------------------------------------------


class TestEmbeddedReviewOptIn:
    def _status(self, *, embedded_review=None, embedded_reviews=None):
        parallel_mode = {
            "enabled": True,
            "r10_dispatch_tail_required": True,
            "r4_diff_reconciliation_required": True,
        }
        if embedded_review is not None:
            parallel_mode["embedded_review"] = embedded_review
        status = {
            "stage_id": "fixture-stage",
            "status": "implementing",
            "dispatch_protocol": vs.HUMAN_OPERATOR_DISPATCH_PROTOCOL,
            "parallel_mode": parallel_mode,
        }
        if embedded_reviews is not None:
            status["embedded_reviews"] = embedded_reviews
        return status

    def test_disabled_with_recorded_embedded_reviews_fails(self, harness):
        root, stage_dir = harness
        status = self._status(embedded_reviews={"A": {"task_id": "A"}})
        errors = vs.validate_parallel_mode(root, stage_dir, status, "checkpoint")
        assert any("must be empty" in err for err in errors)

    def test_disabled_with_stray_raw_output_artifact_fails(self, harness):
        root, stage_dir = harness
        (stage_dir / "embedded-review-A-round1.raw-output.md").write_text("账外评审\n")
        status = self._status()
        errors = vs.validate_parallel_mode(root, stage_dir, status, "checkpoint")
        assert any("not enabled but embedded-review raw-output artifacts exist" in err for err in errors)

    def test_disabled_clean_passes(self, harness):
        root, stage_dir = harness
        status = self._status()
        assert vs.validate_parallel_mode(root, stage_dir, status, "checkpoint") == []

    def test_enabled_with_empty_reason_fails(self, harness):
        root, stage_dir = harness
        status = self._status(embedded_review={"enabled": True, "reason": ""})
        errors = vs.validate_parallel_mode(root, stage_dir, status, "checkpoint")
        assert any("requires a non-empty reason" in err for err in errors)

    def test_legacy_protocol_still_requires_embedded_reviews(self, harness):
        root, stage_dir = harness
        status = self._status(embedded_reviews={})
        del status["dispatch_protocol"]
        errors = vs.validate_parallel_mode(root, stage_dir, status, "pre-review")
        assert any("requires at least one embedded_reviews entry" in err for err in errors)


# ---------------------------------------------------------------------------
# Group 7: dynamic required-files expansion (+ per-task parse coverage)
# ---------------------------------------------------------------------------


class TestDynamicRequiredFiles:
    def _base_files(self, stage_dir):
        for name in (
            "00-task.md",
            "10-design.md",
            "11-adr.md",
            "20-implementation.md",
            "60-test-output.txt",
            "70-handoff.md",
        ):
            (stage_dir / name).write_text(f"# {name}\n")

    def _parallel_accept_status(self):
        return {
            "stage_id": "fixture-stage",
            "status": "stage_accepted_waiting_user",
            "dispatch_protocol": vs.HUMAN_OPERATOR_DISPATCH_PROTOCOL,
            "tasks": [
                {"id": "backend", "review_1": {"verdict": "ACCEPT"}},
                {"id": "frontend", "review_1": {"verdict": "ACCEPT"}},
            ],
        }

    def test_parallel_task_level_files_pass(self, harness):
        root, stage_dir = harness
        self._base_files(stage_dir)
        (stage_dir / "30-review-1-backend.md").write_text("x\n")
        (stage_dir / "30-review-1-frontend.md").write_text("x\n")
        (stage_dir / "50-review-2.md").write_text("x\n")
        status = self._parallel_accept_status()
        assert vs.validate_required_files(stage_dir, status, "pre-accept") == []

    def test_parallel_missing_one_task_file_fails(self, harness):
        root, stage_dir = harness
        self._base_files(stage_dir)
        (stage_dir / "30-review-1-backend.md").write_text("x\n")
        (stage_dir / "30-review-1.md").write_text("unsuffixed must not help\n")
        (stage_dir / "50-review-2.md").write_text("x\n")
        status = self._parallel_accept_status()
        errors = vs.validate_required_files(stage_dir, status, "pre-accept")
        assert errors == ["missing required stage file: 30-review-1-frontend.md"]

    def test_single_task_keeps_unsuffixed_name(self, harness):
        root, stage_dir = harness
        self._base_files(stage_dir)
        (stage_dir / "30-review-1.md").write_text("x\n")
        (stage_dir / "50-review-2.md").write_text("x\n")
        status = {
            "stage_id": "fixture-stage",
            "dispatch_protocol": vs.HUMAN_OPERATOR_DISPATCH_PROTOCOL,
            "tasks": [{"id": "only", "review_1": {"verdict": "ACCEPT"}}],
        }
        assert vs.validate_required_files(stage_dir, status, "pre-accept") == []

    def test_parallel_per_task_verdict_parsing(self, harness):
        root, stage_dir = harness
        for task_id, session in (("backend", "session_a"), ("frontend", "session_b")):
            _write_review_artifact(
                stage_dir, f"30-review-1-{task_id}.md", _verdict_json("ACCEPT"), session_id=session
            )
            _write_dispatch(stage_dir, f"review-1-{task_id}.dispatch.md", session_id=session)
        status = self._parallel_accept_status()
        for task_id, session in (("backend", "session_a"), ("frontend", "session_b")):
            for task in status["tasks"]:
                if task["id"] == task_id:
                    task["review_1"]["dispatch_path"] = f"review-1-{task_id}.dispatch.md"
        assert vs.validate_review_artifacts(root, stage_dir, status, "pre-accept") == []


# ---------------------------------------------------------------------------
# Group 8: json_schema_valid abolition at the pre-accept terminal gate
# ---------------------------------------------------------------------------


class TestJsonSchemaValidAbolition:
    def _status(self, *, json_schema_valid):
        return {
            "stage_id": "fixture-stage",
            "status": "stage_accepted_waiting_user",
            "dispatch_protocol": vs.HUMAN_OPERATOR_DISPATCH_PROTOCOL,
            "diff_fingerprint": FINGERPRINT,
            "tests": {"status": "pass"},
            "implementer": "claude_glm",
            "designer": "fable5",
            "review_1": {
                "verdict": "ACCEPT",
                "diff_fingerprint": FINGERPRINT,
                "reviewer": "kimi",
                "json_schema_valid": json_schema_valid,
                "dispatch_path": "review-1.dispatch.md",
            },
            "review_2": {
                "verdict": "ACCEPT",
                "diff_fingerprint": FINGERPRINT,
                "reviewer": "codex",
                "json_schema_valid": json_schema_valid,
                "dispatch_path": "review-2.dispatch.md",
            },
        }

    def _write_accept_evidence(self, stage_dir):
        _write_review_artifact(
            stage_dir, "30-review-1.md", _verdict_json("ACCEPT"), session_id="session_r1"
        )
        _write_dispatch(stage_dir, "review-1.dispatch.md", session_id="session_r1")
        _write_review_artifact(
            stage_dir,
            "50-review-2.md",
            _verdict_json("ACCEPT", role="final_reviewer", model="gpt-5.5"),
            session_id="session_r2",
        )
        _write_dispatch(stage_dir, "review-2.dispatch.md", session_id="session_r2")

    def test_false_field_no_longer_fails_when_artifact_parses(self, harness):
        root, stage_dir = harness
        self._write_accept_evidence(stage_dir)
        status = self._status(json_schema_valid=False)
        errors, applied = vs.validate_acceptance(root, stage_dir, status)
        assert errors == []
        assert applied == []

    def test_true_field_cannot_rescue_unparseable_artifact(self, harness):
        root, stage_dir = harness
        self._write_accept_evidence(stage_dir)
        (stage_dir / "30-review-1.md").write_text("verdict claimed in prose only\n")
        status = self._status(json_schema_valid=True)
        errors, _applied = vs.validate_acceptance(root, stage_dir, status)
        assert any("no parseable JSON verdict object" in err for err in errors)

    def test_legacy_protocol_still_asserts_json_schema_valid(self, harness):
        root, stage_dir = harness
        status = self._status(json_schema_valid=False)
        del status["dispatch_protocol"]
        errors, _applied = vs.validate_acceptance(root, stage_dir, status)
        assert "review_1.json_schema_valid must be true" in errors
        assert "review_2.json_schema_valid must be true" in errors


# ---------------------------------------------------------------------------
# Tolerant extraction unit checks (P6: fences + trailing bytes)
# ---------------------------------------------------------------------------


class TestTolerantExtraction:
    def test_last_json_object_wins_over_footer_braces(self):
        verdict = _verdict_json("ACCEPT")
        text = f"叙述\n```json\n{verdict}\n```\nfooter 提到 {{未闭合\n"
        assert vs.extract_last_json_object(text) is not None
        assert vs.extract_last_json_object(text)["verdict"] == "ACCEPT"

    def test_prose_only_returns_none(self):
        assert vs.extract_last_json_object("没有任何 JSON object\n") is None

    def test_rework_verdict_requires_fix_start_prompt(self, harness):
        root, _stage_dir = harness
        schema = vs.load_review_verdict_schema(root)
        payload = json.loads(_verdict_json("REWORK"))
        del payload["fix_start_prompt"]
        errors = vs._mini_schema_errors(payload, schema, schema)
        assert any("fix_start_prompt" in err for err in errors)
