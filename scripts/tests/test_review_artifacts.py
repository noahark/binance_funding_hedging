#!/usr/bin/env python3
"""Focused fixtures for review-artifact protocol v1.

Covers, per the frozen Task H1 contract and the negative-test checklist in
reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/21-bookkeeper-reconciliation.md:

- schema-v1 corpus over every constraint, with an optional `jsonschema` oracle
  comparing the stdlib implementation against the canonical schema file;
- raw single-JSON-object parsing (fences, narrative, empty, extra data, BOM);
- canonical verdict byte enforcement (key order, whitespace, trailing newline);
- frozen serial/task/Review-2 artifact names, -retry-N variants, and stage
  containment (absolute/traversal/foreign paths);
- protocol resolution: live-missing vs cold-legacy via explicit ACTIVE.json
  evidence, unknown values fail closed;
- phase timing: pre-review+review_1 needs no result pair, pre-review+review_2
  needs Review-1 pairs, pre-accept needs Review-1 and Review-2 pairs;
- stage/provider identity binding (stage_id, role, model, fingerprint,
  normalized provider isolation incl. alias self-review);
- conditional embedded review (default-off pass, enabled-incomplete fail,
  per-round PASS|BLOCKER result);
- dispatch-ready human_operator executor rule (executor self rejected);
- capture CLI behavior (producer exit, empty/fenced raw, refuse overwrite) and
  the atomic no-clobber publication primitive;
- doc sweep: no surviving model-side self-dispatch tokens in the normative
  Harness files, and manifest/template registration of the new protocol.

Standard library only; `jsonschema` is used solely as an optional test oracle.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SCRIPTS_DIR.parent
PROTOCOL_V1 = "raw-plus-strict-json/v1"


def _load(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ra = _load("review_artifacts", SCRIPTS_DIR / "review_artifacts.py")
vs = _load("validate_stage", SCRIPTS_DIR / "validate-stage.py")

SCHEMA_PATH = REPO_ROOT / "schemas" / "review-verdict.schema.json"

try:
    import jsonschema  # type: ignore

    HAVE_JSONSCHEMA = True
except ImportError:  # pragma: no cover
    HAVE_JSONSCHEMA = False


def valid_verdict(**overrides) -> dict:
    obj = {
        "schema_version": 1,
        "stage_id": "stage-v1",
        "role": "first_reviewer",
        "model": "kimi-2.7",
        "verdict": "ACCEPT",
        "diff_fingerprint": "headsha:0000",
        "reviewer_prior_involvement": "none",
        "reviewed_artifacts": ["00-task.md"],
        "findings": [],
        "required_fixes": [],
        "next_action": "continue",
    }
    obj.update(overrides)
    return obj


def full_finding(**overrides) -> dict:
    finding = {
        "severity": "P1",
        "title": "t",
        "file": "a.py",
        "line": 3,
        "evidence": "e",
        "impact": "i",
        "recommendation": "r",
    }
    finding.update(overrides)
    return finding


def _without(obj: dict, key: str) -> dict:
    out = copy.deepcopy(obj)
    out.pop(key, None)
    return out


def schema_corpus() -> list[tuple[str, dict, bool]]:
    """(name, object, expect_valid) covering every schema-v1 constraint."""
    base = valid_verdict()
    cases: list[tuple[str, dict, bool]] = [
        ("valid minimal", base, True),
        (
            "valid all optionals",
            valid_verdict(
                reviewer_prior_involvement_notes="disclosed",
                residual_risks=["risk"],
                fix_start_prompt="do the fix",
                findings=[full_finding(), full_finding(line=None)],
            ),
            True,
        ),
        (
            "valid REWORK with fix_start_prompt",
            valid_verdict(verdict="REWORK", fix_start_prompt="fix it", next_action="fix"),
            True,
        ),
        ("valid BLOCKED", valid_verdict(verdict="BLOCKED", next_action="human_escalation_required"), True),
        (
            "valid finding without optional file/line",
            valid_verdict(findings=[_without(_without(full_finding(), "file"), "line")]),
            True,
        ),
    ]
    for key in ra.VERDICT_REQUIRED_KEYS:
        cases.append((f"missing required {key}", _without(base, key), False))
    cases += [
        ("unknown top-level property", valid_verdict(extra_field="x"), False),
        ("schema_version 2", valid_verdict(schema_version=2), False),
        ("schema_version string", valid_verdict(schema_version="1"), False),
        ("schema_version bool", valid_verdict(schema_version=True), False),
        ("stage_id empty", valid_verdict(stage_id=""), False),
        ("stage_id non-string", valid_verdict(stage_id=5), False),
        ("role outside enum", valid_verdict(role="code_reviewer"), False),
        ("role non-string", valid_verdict(role=1), False),
        ("model empty", valid_verdict(model=""), False),
        ("verdict outside enum", valid_verdict(verdict="PASS"), False),
        ("diff_fingerprint empty", valid_verdict(diff_fingerprint=""), False),
        ("involvement outside enum", valid_verdict(reviewer_prior_involvement="implementation"), False),
        ("notes non-string", valid_verdict(reviewer_prior_involvement_notes=5), False),
        ("reviewed_artifacts empty", valid_verdict(reviewed_artifacts=[]), False),
        ("reviewed_artifacts non-array", valid_verdict(reviewed_artifacts="00-task.md"), False),
        ("reviewed_artifacts empty item", valid_verdict(reviewed_artifacts=[""]), False),
        ("reviewed_artifacts non-string item", valid_verdict(reviewed_artifacts=[1]), False),
        ("findings non-array", valid_verdict(findings="none"), False),
        ("finding non-object", valid_verdict(findings=[1]), False),
        ("finding unknown property", valid_verdict(findings=[full_finding(extra="x")]), False),
        ("finding severity outside enum", valid_verdict(findings=[full_finding(severity="P4")]), False),
        ("finding title empty", valid_verdict(findings=[full_finding(title="")]), False),
        ("finding evidence empty", valid_verdict(findings=[full_finding(evidence="")]), False),
        ("finding impact empty", valid_verdict(findings=[full_finding(impact="")]), False),
        ("finding recommendation empty", valid_verdict(findings=[full_finding(recommendation="")]), False),
        ("finding file non-string", valid_verdict(findings=[full_finding(file=1)]), False),
        ("finding line zero", valid_verdict(findings=[full_finding(line=0)]), False),
        ("finding line string", valid_verdict(findings=[full_finding(line="3")]), False),
        ("finding line bool", valid_verdict(findings=[full_finding(line=True)]), False),
        ("required_fixes non-array", valid_verdict(required_fixes="x"), False),
        ("required_fixes non-string item", valid_verdict(required_fixes=[1]), False),
        ("residual_risks non-string item", valid_verdict(residual_risks=[2]), False),
        ("fix_start_prompt empty", valid_verdict(fix_start_prompt=""), False),
        ("REWORK missing fix_start_prompt", valid_verdict(verdict="REWORK", next_action="fix"), False),
        ("next_action outside enum", valid_verdict(next_action="stop"), False),
        ("next_action empty", valid_verdict(next_action=""), False),
    ]
    for key in ra.FINDING_REQUIRED_KEYS:
        cases.append(
            (f"finding missing required {key}", valid_verdict(findings=[_without(full_finding(), key)]), False)
        )
    return cases


class TestSchemaV1(unittest.TestCase):
    def test_corpus(self):
        for name, obj, expect_valid in schema_corpus():
            errors = ra.validate_verdict_object(obj)
            with self.subTest(case=name):
                if expect_valid:
                    self.assertEqual(errors, [], f"{name}: unexpected errors {errors}")
                else:
                    self.assertTrue(errors, f"{name}: expected schema errors, got none")

    def test_non_object_rejected(self):
        self.assertTrue(ra.validate_verdict_object(["not", "an", "object"]))
        self.assertTrue(ra.validate_verdict_object(None))


@unittest.skipUnless(HAVE_JSONSCHEMA, "jsonschema not installed; stdlib corpus still enforced")
class TestJsonschemaOracle(unittest.TestCase):
    """Compare the stdlib schema-v1 implementation with the canonical schema
    file through the optional `jsonschema` package (test oracle only)."""

    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.validator = jsonschema.Draft202012Validator(cls.schema)

    def test_parity(self):
        for name, obj, _expected in schema_corpus():
            stdlib_valid = not ra.validate_verdict_object(obj)
            oracle_valid = not list(self.validator.iter_errors(obj))
            with self.subTest(case=name):
                self.assertEqual(
                    stdlib_valid,
                    oracle_valid,
                    f"{name}: stdlib={stdlib_valid} oracle={oracle_valid}",
                )


class TestRawParsing(unittest.TestCase):
    def _parse(self, data: bytes):
        return ra.parse_single_json_object(data, "raw")

    def test_transport_whitespace_ok(self):
        obj, errors = self._parse(b'\n \t{"a": 1}\r\n \n')
        self.assertEqual(errors, [])
        self.assertEqual(obj, {"a": 1})

    def test_markdown_fence_rejected(self):
        obj, errors = self._parse(b'```json\n{"a": 1}\n```')
        self.assertIsNone(obj)
        self.assertTrue(errors)

    def test_narrative_before_rejected(self):
        obj, errors = self._parse(b'Here is my verdict:\n{"a": 1}')
        self.assertIsNone(obj)
        self.assertTrue(errors)

    def test_trailing_narrative_rejected(self):
        obj, errors = self._parse(b'{"a": 1}\nthanks')
        self.assertIsNone(obj)
        self.assertTrue(errors)

    def test_two_documents_rejected(self):
        obj, errors = self._parse(b'{"a": 1}{"b": 2}')
        self.assertIsNone(obj)
        self.assertTrue(errors)

    def test_empty_rejected(self):
        obj, errors = self._parse(b"")
        self.assertIsNone(obj)
        self.assertTrue(errors)

    def test_whitespace_only_rejected(self):
        obj, errors = self._parse(b"  \n ")
        self.assertIsNone(obj)
        self.assertTrue(errors)

    def test_array_root_rejected(self):
        obj, errors = self._parse(b"[1, 2]")
        self.assertIsNone(obj)
        self.assertTrue(errors)

    def test_bom_rejected(self):
        obj, errors = self._parse("﻿{\"a\": 1}".encode("utf-8"))
        self.assertIsNone(obj)
        self.assertTrue(errors)


class PairFixture(unittest.TestCase):
    """Shared temp-stage plumbing for pair/protocol tests."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="review-artifacts-test-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "docs").mkdir()
        (self.root / "docs" / "parallel-development-mode.md").write_text("contract\n")
        (self.root / "agents").mkdir()
        (self.root / "agents" / "registry.yaml").write_text(
            "adapters:\n"
            "  claude_glm:\n"
            "    embedded_read_only_review_command: \"cmd\"\n"
            "  kimi:\n"
            "    embedded_read_only_review_command: \"cmd\"\n"
            "model_policies:\n"
            "  review_1_selection_rules:\n"
            "    implementer_provider_claude_glm: kimi\n"
            "    implementer_provider_kimi: claude_glm\n"
            "    default_preference: [kimi, claude_glm]\n"
        )
        self.runs = self.root / "reports" / "agent-runs"
        self.runs.mkdir(parents=True)

    def make_stage(self, stage_id: str) -> Path:
        stage_dir = self.runs / stage_id
        stage_dir.mkdir()
        return stage_dir

    def set_active(self, stage_id: str | None):
        (self.runs / "ACTIVE.json").write_text(
            json.dumps({"active": {"stage_id": stage_id} if stage_id else None})
        )

    def write_pair(
        self,
        stage_dir: Path,
        obj: dict,
        base: str,
        *,
        raw_bytes: bytes | None = None,
        verdict_bytes: bytes | None = None,
        retry: str = "",
    ) -> tuple[str, str]:
        raw_name = f"{base}{retry}.raw-output.md"
        verdict_name = f"{base}{retry}.verdict.json"
        raw = raw_bytes if raw_bytes is not None else json.dumps(obj, indent=2).encode() + b"\n"
        verdict = verdict_bytes if verdict_bytes is not None else ra.canonical_verdict_bytes(obj)
        (stage_dir / raw_name).write_bytes(raw)
        (stage_dir / verdict_name).write_bytes(verdict)
        return raw_name, verdict_name

    def serial_status(self, stage_id: str, record: dict | None, status: str = "review_2") -> dict:
        return {
            "stage_id": stage_id,
            "status": status,
            "review_artifact_protocol": PROTOCOL_V1,
            "parallel_mode": {"enabled": False},
            "implementer": {"provider": "claude_glm"},
            "review_1": record,
            "review_2": None,
        }

    def serial_record(self, raw_name: str, verdict_name: str, obj: dict) -> dict:
        return {
            "reviewer": "kimi",
            "provider": "kimi",
            "model": obj["model"],
            "verdict": obj["verdict"],
            "diff_fingerprint": obj["diff_fingerprint"],
            "raw_output_path": raw_name,
            "verdict_path": verdict_name,
        }


class TestCanonicalPairBinding(PairFixture):
    def check_pair(self, stage_dir, raw_name, verdict_name, prefix="review_1"):
        return ra.load_and_parse_pair(stage_dir / raw_name, stage_dir / verdict_name, prefix)

    def test_happy_pair(self):
        stage = self.make_stage("stage-v1")
        obj = valid_verdict()
        raw, verdict = self.write_pair(stage, obj, "30-review-1")
        parsed, errors = self.check_pair(stage, raw, verdict)
        self.assertEqual(errors, [])
        self.assertEqual(parsed, obj)

    def test_verdict_trailing_newline_rejected(self):
        stage = self.make_stage("stage-v1")
        obj = valid_verdict()
        raw, verdict = self.write_pair(
            stage, obj, "30-review-1", verdict_bytes=ra.canonical_verdict_bytes(obj) + b"\n"
        )
        parsed, errors = self.check_pair(stage, raw, verdict)
        self.assertIsNone(parsed)
        self.assertTrue(any("canonical" in e for e in errors))

    def test_verdict_leading_whitespace_rejected(self):
        stage = self.make_stage("stage-v1")
        obj = valid_verdict()
        raw, verdict = self.write_pair(
            stage, obj, "30-review-1", verdict_bytes=b" " + ra.canonical_verdict_bytes(obj)
        )
        _, errors = self.check_pair(stage, raw, verdict)
        self.assertTrue(any("canonical" in e for e in errors))

    def test_verdict_pretty_printed_rejected(self):
        stage = self.make_stage("stage-v1")
        obj = valid_verdict()
        raw, verdict = self.write_pair(
            stage, obj, "30-review-1", verdict_bytes=json.dumps(obj, indent=2).encode()
        )
        _, errors = self.check_pair(stage, raw, verdict)
        self.assertTrue(any("canonical" in e for e in errors))

    def test_verdict_unsorted_keys_rejected(self):
        stage = self.make_stage("stage-v1")
        obj = valid_verdict()
        unsorted_bytes = json.dumps(obj, ensure_ascii=False, sort_keys=False, separators=(",", ":")).encode()
        self.assertNotEqual(unsorted_bytes, ra.canonical_verdict_bytes(obj))
        raw, verdict = self.write_pair(stage, obj, "30-review-1", verdict_bytes=unsorted_bytes)
        _, errors = self.check_pair(stage, raw, verdict)
        self.assertTrue(any("canonical" in e for e in errors))

    def test_raw_verdict_object_mismatch_rejected(self):
        stage = self.make_stage("stage-v1")
        obj = valid_verdict()
        other = valid_verdict(model="glm-5.2")
        raw, verdict = self.write_pair(
            stage, obj, "30-review-1", verdict_bytes=ra.canonical_verdict_bytes(other)
        )
        parsed, errors = self.check_pair(stage, raw, verdict)
        self.assertIsNone(parsed)
        self.assertTrue(any("different JSON objects" in e for e in errors))

    def test_missing_files_rejected(self):
        stage = self.make_stage("stage-v1")
        _, errors = self.check_pair(stage, "30-review-1.raw-output.md", "30-review-1.verdict.json")
        self.assertEqual(len([e for e in errors if "does not exist" in e]), 2)

    def test_schema_invalid_pair_rejected(self):
        stage = self.make_stage("stage-v1")
        obj = valid_verdict(verdict="MAYBE")
        raw, verdict = self.write_pair(stage, obj, "30-review-1")
        parsed, errors = self.check_pair(stage, raw, verdict)
        self.assertIsNone(parsed)
        self.assertTrue(any("schema-v1" in e for e in errors))

    def test_fenced_raw_rejected(self):
        stage = self.make_stage("stage-v1")
        obj = valid_verdict()
        raw, verdict = self.write_pair(
            stage, obj, "30-review-1",
            raw_bytes=b"```json\n" + json.dumps(obj).encode() + b"\n```\n",
        )
        parsed, errors = self.check_pair(stage, raw, verdict)
        self.assertIsNone(parsed)
        self.assertTrue(any("raw output" in e for e in errors))


class TestArtifactNames(PairFixture):
    def resolve(self, value, kind="review_1_serial", task_id=None, suffix=ra.RAW_SUFFIX):
        stage = self.runs / "stage-v1"
        if not stage.exists():
            stage.mkdir()
        return ra.resolve_stage_local_artifact(self.root, stage, value, kind, task_id, suffix, "field")

    def test_serial_base_ok(self):
        path, attempt, errors = self.resolve("30-review-1.raw-output.md")
        self.assertEqual(errors, [])
        self.assertEqual(attempt, "")
        self.assertEqual(path.name, "30-review-1.raw-output.md")

    def test_serial_retry_ok(self):
        _, attempt, errors = self.resolve("30-review-1-retry-2.raw-output.md")
        self.assertEqual(errors, [])
        self.assertEqual(attempt, "retry-2")

    def test_retry_zero_rejected(self):
        _, _, errors = self.resolve("30-review-1-retry-0.raw-output.md")
        self.assertTrue(errors)

    def test_retry_leading_zero_rejected(self):
        _, _, errors = self.resolve("30-review-1-retry-01.raw-output.md")
        self.assertTrue(errors)

    def test_task_name_ok(self):
        _, attempt, errors = self.resolve(
            "30-review-1-H1.raw-output.md", kind="review_1_task", task_id="H1"
        )
        self.assertEqual(errors, [])
        self.assertEqual(attempt, "")

    def test_task_name_wrong_task_rejected(self):
        _, _, errors = self.resolve(
            "30-review-1-H2.raw-output.md", kind="review_1_task", task_id="H1"
        )
        self.assertTrue(errors)

    def test_serial_name_rejected_for_task_kind(self):
        _, _, errors = self.resolve(
            "30-review-1.raw-output.md", kind="review_1_task", task_id="H1"
        )
        self.assertTrue(errors)

    def test_review_2_ok(self):
        _, _, errors = self.resolve(
            "50-review-2.verdict.json", kind="review_2", suffix=ra.VERDICT_SUFFIX
        )
        self.assertEqual(errors, [])

    def test_bare_narrative_name_rejected(self):
        _, _, errors = self.resolve("30-review-1.md")
        self.assertTrue(errors)

    def test_absolute_path_rejected(self):
        _, _, errors = self.resolve(str(self.root / "30-review-1.raw-output.md"))
        self.assertTrue(any("absolute" in e for e in errors))

    def test_traversal_rejected(self):
        _, _, errors = self.resolve("../stage-v1/30-review-1.raw-output.md")
        self.assertTrue(errors)

    def test_other_stage_rejected(self):
        _, _, errors = self.resolve("reports/agent-runs/other-stage/30-review-1.raw-output.md")
        self.assertTrue(errors)

    def test_exact_stage_relative_ok(self):
        _, _, errors = self.resolve("reports/agent-runs/stage-v1/30-review-1.raw-output.md")
        self.assertEqual(errors, [])

    def test_subdirectory_rejected(self):
        _, _, errors = self.resolve("sub/30-review-1.raw-output.md")
        self.assertTrue(errors)


class TestProtocolResolutionAndPhaseTiming(PairFixture):
    def protocol_errors(self, stage_dir, status_doc, phase, active_id):
        return vs.validate_review_artifact_protocol(self.root, stage_dir, status_doc, phase, active_id)

    def test_missing_protocol_dispatch_ready_fails(self):
        stage = self.make_stage("stage-a")
        errors = self.protocol_errors(stage, {"stage_id": "stage-a"}, "dispatch-ready", None)
        self.assertTrue(any("review_artifact_protocol is required" in e for e in errors))

    def test_missing_protocol_active_stage_fails_pre_review_and_pre_accept(self):
        stage = self.make_stage("stage-a")
        for phase in ("pre-review", "pre-accept"):
            errors = self.protocol_errors(stage, {"stage_id": "stage-a"}, phase, "stage-a")
            self.assertTrue(any("fails closed" in e for e in errors), f"phase={phase}: {errors}")

    def test_missing_protocol_cold_stage_stays_legacy(self):
        stage = self.make_stage("stage-old")
        for phase in ("pre-review", "pre-accept", "checkpoint"):
            errors = self.protocol_errors(stage, {"stage_id": "stage-old"}, phase, "stage-a")
            self.assertEqual(errors, [], f"phase={phase}")

    def test_unknown_protocol_fails_closed_every_phase(self):
        stage = self.make_stage("stage-a")
        doc = {"stage_id": "stage-a", "review_artifact_protocol": "raw/v9"}
        for phase in ("checkpoint", "dispatch-ready", "pre-review", "pre-accept"):
            errors = self.protocol_errors(stage, doc, phase, None)
            self.assertTrue(any("unknown review_artifact_protocol" in e for e in errors), f"phase={phase}")

    def test_active_stage_id_reads_pointer(self):
        self.set_active("stage-a")
        self.assertEqual(vs.active_stage_id(self.root), "stage-a")
        self.set_active(None)
        self.assertIsNone(vs.active_stage_id(self.root))

    def test_malformed_active_pointer_fails_closed(self):
        (self.runs / "ACTIVE.json").write_text("{not json")
        with self.assertRaises(vs.ValidationError):
            vs.active_stage_id(self.root)

    def _valid_serial_setup(self, stage_id="stage-v1", status="review_2"):
        stage = self.make_stage(stage_id)
        obj = valid_verdict(stage_id=stage_id)
        raw, verdict = self.write_pair(stage, obj, "30-review-1")
        doc = self.serial_status(stage_id, self.serial_record(raw, verdict, obj), status=status)
        return stage, doc, obj

    def test_pre_review_status_review_1_requires_no_pair(self):
        stage = self.make_stage("stage-v1")
        doc = self.serial_status("stage-v1", record=None, status="review_1")
        errors = self.protocol_errors(stage, doc, "pre-review", "stage-v1")
        self.assertEqual(errors, [])

    def test_pre_review_status_review_2_requires_serial_pair(self):
        stage = self.make_stage("stage-v1")
        doc = self.serial_status("stage-v1", record=None, status="review_2")
        errors = self.protocol_errors(stage, doc, "pre-review", "stage-v1")
        self.assertTrue(any("review_1" in e for e in errors))

    def test_pre_review_status_review_2_with_valid_pair_passes(self):
        stage, doc, _obj = self._valid_serial_setup()
        errors = self.protocol_errors(stage, doc, "pre-review", "stage-v1")
        self.assertEqual(errors, [])

    def test_pre_accept_requires_review_2_pair(self):
        stage, doc, _obj = self._valid_serial_setup(status="stage_accepted_waiting_user")
        errors = self.protocol_errors(stage, doc, "pre-accept", "stage-v1")
        self.assertTrue(any(e.startswith("review_2") for e in errors))

    def test_pre_accept_with_both_pairs_passes(self):
        stage, doc, _obj = self._valid_serial_setup(status="stage_accepted_waiting_user")
        obj2 = valid_verdict(stage_id="stage-v1", role="final_reviewer", model="gpt-5.5")
        raw2, verdict2 = self.write_pair(stage, obj2, "50-review-2")
        record2 = self.serial_record(raw2, verdict2, obj2)
        record2.update({"reviewer": "codex", "provider": "codex", "model": "gpt-5.5"})
        doc["review_2"] = record2
        errors = self.protocol_errors(stage, doc, "pre-accept", "stage-v1")
        self.assertEqual(errors, [])

    def test_verdict_stage_id_mismatch_rejected(self):
        stage = self.make_stage("stage-v1")
        obj = valid_verdict(stage_id="some-other-stage")
        raw, verdict = self.write_pair(stage, obj, "30-review-1")
        doc = self.serial_status("stage-v1", self.serial_record(raw, verdict, obj))
        errors = self.protocol_errors(stage, doc, "pre-review", "stage-v1")
        self.assertTrue(any("stage_id" in e for e in errors))

    def test_wrong_role_rejected(self):
        stage = self.make_stage("stage-v1")
        obj = valid_verdict(role="final_reviewer")
        raw, verdict = self.write_pair(stage, obj, "30-review-1")
        doc = self.serial_status("stage-v1", self.serial_record(raw, verdict, obj))
        errors = self.protocol_errors(stage, doc, "pre-review", "stage-v1")
        self.assertTrue(any("role" in e for e in errors))

    def test_model_mismatch_rejected(self):
        stage = self.make_stage("stage-v1")
        obj = valid_verdict(model="glm-5.2")
        raw, verdict = self.write_pair(stage, obj, "30-review-1")
        record = self.serial_record(raw, verdict, obj)
        record["model"] = "kimi-2.7"
        doc = self.serial_status("stage-v1", record)
        errors = self.protocol_errors(stage, doc, "pre-review", "stage-v1")
        self.assertTrue(any("does not match status-recorded model" in e for e in errors))

    def test_missing_reviewer_provider_rejected(self):
        stage = self.make_stage("stage-v1")
        obj = valid_verdict()
        raw, verdict = self.write_pair(stage, obj, "30-review-1")
        record = self.serial_record(raw, verdict, obj)
        record.pop("provider")
        record.pop("reviewer")
        doc = self.serial_status("stage-v1", record)
        errors = self.protocol_errors(stage, doc, "pre-review", "stage-v1")
        self.assertTrue(any("reviewer provider" in e for e in errors))

    def test_provider_alias_self_review_rejected(self):
        stage = self.make_stage("stage-v1")
        obj = valid_verdict(model="claude-fable-5")
        raw, verdict = self.write_pair(stage, obj, "30-review-1")
        record = self.serial_record(raw, verdict, obj)
        record.update({"reviewer": "fable5", "provider": "fable5", "model": "claude-fable-5"})
        doc = self.serial_status("stage-v1", record)
        doc["implementer"] = {"provider": "claude"}
        errors = self.protocol_errors(stage, doc, "pre-review", "stage-v1")
        self.assertTrue(any("self-review is forbidden" in e for e in errors))

    def test_fingerprint_cache_mismatch_rejected(self):
        stage = self.make_stage("stage-v1")
        obj = valid_verdict()
        raw, verdict = self.write_pair(stage, obj, "30-review-1")
        record = self.serial_record(raw, verdict, obj)
        record["diff_fingerprint"] = "othersha:ffff"
        doc = self.serial_status("stage-v1", record)
        errors = self.protocol_errors(stage, doc, "pre-review", "stage-v1")
        self.assertTrue(any("diff_fingerprint" in e for e in errors))

    def test_review_1_pair_must_be_accept(self):
        stage = self.make_stage("stage-v1")
        obj = valid_verdict(verdict="REWORK", fix_start_prompt="fix", next_action="fix")
        raw, verdict = self.write_pair(stage, obj, "30-review-1")
        doc = self.serial_status("stage-v1", self.serial_record(raw, verdict, obj))
        errors = self.protocol_errors(stage, doc, "pre-review", "stage-v1")
        self.assertTrue(any("must be ACCEPT" in e for e in errors))

    def test_attempt_mismatch_rejected(self):
        stage = self.make_stage("stage-v1")
        obj = valid_verdict()
        self.write_pair(stage, obj, "30-review-1")
        self.write_pair(stage, obj, "30-review-1", retry="-retry-1")
        record = self.serial_record("30-review-1.raw-output.md", "30-review-1-retry-1.verdict.json", obj)
        doc = self.serial_status("stage-v1", record)
        errors = self.protocol_errors(stage, doc, "pre-review", "stage-v1")
        self.assertTrue(any("different attempts" in e for e in errors))

    def test_retry_pair_selected_by_status_passes(self):
        stage = self.make_stage("stage-v1")
        obj = valid_verdict()
        raw, verdict = self.write_pair(stage, obj, "30-review-1", retry="-retry-2")
        doc = self.serial_status("stage-v1", self.serial_record(raw, verdict, obj))
        errors = self.protocol_errors(stage, doc, "pre-review", "stage-v1")
        self.assertEqual(errors, [])

    def test_parallel_stage_requires_task_pairs(self):
        stage = self.make_stage("stage-v1")
        obj = valid_verdict(diff_fingerprint="taskhead:1234")
        raw, verdict = self.write_pair(stage, obj, "30-review-1-A")
        record = self.serial_record(raw, verdict, obj)
        doc = self.serial_status("stage-v1", None)
        doc["parallel_mode"] = {"enabled": True}
        doc["tasks"] = [
            {"id": "A", "owner": "claude_glm", "diff_fingerprint": "taskhead:1234", "review_1": record},
            {"id": "B", "owner": "kimi", "diff_fingerprint": "taskhead:5678", "review_1": None},
        ]
        errors = self.protocol_errors(stage, doc, "pre-review", "stage-v1")
        self.assertTrue(any("task B review_1" in e for e in errors))
        self.assertFalse(any("task A review_1" in e for e in errors))

    def test_task_pair_fingerprint_must_match_task(self):
        stage = self.make_stage("stage-v1")
        obj = valid_verdict(diff_fingerprint="wronghead:9999")
        raw, verdict = self.write_pair(stage, obj, "30-review-1-A")
        record = self.serial_record(raw, verdict, obj)
        doc = self.serial_status("stage-v1", None)
        doc["parallel_mode"] = {"enabled": True}
        doc["tasks"] = [
            {"id": "A", "owner": "claude_glm", "diff_fingerprint": "taskhead:1234", "review_1": record},
            {"id": "B", "owner": "kimi", "diff_fingerprint": "taskhead:5678", "review_1": record},
        ]
        errors = self.protocol_errors(stage, doc, "pre-review", "stage-v1")
        self.assertTrue(any("committed task fingerprint" in e for e in errors))


class TestEmbeddedReviewConditional(PairFixture):
    def parallel_status(self, stage_id: str, *, embedded_review=None, embedded_reviews=None) -> dict:
        parallel = {
            "enabled": True,
            "contract": "docs/parallel-development-mode.md",
            "r10_dispatch_tail_required": True,
            "r4_diff_reconciliation_required": True,
        }
        if embedded_review is not None:
            parallel["embedded_review"] = embedded_review
        return {
            "stage_id": stage_id,
            "status": "review_1",
            "parallel_mode": parallel,
            "embedded_reviews": embedded_reviews if embedded_reviews is not None else {},
            "tasks": [],
        }

    def embedded_entry(self, stage_dir: Path, *, result="PASS", include_result=True) -> dict:
        for name in (
            "embedded-review-A.prompt.md",
            "embedded-review-A-round1.dispatch.md",
            "embedded-review-A-round1.diff.patch",
            "embedded-review-A-round1.raw-output.md",
        ):
            (stage_dir / name).write_text("x\n")
        artifact = {
            "round": 1,
            "dispatch_path": "embedded-review-A-round1.dispatch.md",
            "worktree_diff_path": "embedded-review-A-round1.diff.patch",
            "raw_output_path": "embedded-review-A-round1.raw-output.md",
            "fix_report_path": None,
        }
        if include_result:
            artifact["result"] = result
        return {
            "task_id": "A",
            "scope": ["backend/**"],
            "implementer": {"provider": "claude_glm"},
            "reviewer": {"provider": "kimi"},
            "prompt_path": "embedded-review-A.prompt.md",
            "rounds": 1,
            "round_artifacts": [artifact],
        }

    def test_default_off_requires_no_embedded_entries(self):
        stage = self.make_stage("stage-p")
        doc = self.parallel_status("stage-p")
        errors = vs.validate_parallel_mode(self.root, stage, doc, "pre-review")
        self.assertEqual(errors, [])

    def test_enabled_requires_reason(self):
        stage = self.make_stage("stage-p")
        doc = self.parallel_status("stage-p", embedded_review={"enabled": True, "reason": ""})
        errors = vs.validate_parallel_mode(self.root, stage, doc, "checkpoint")
        self.assertTrue(any("non-empty reason" in e for e in errors))

    def test_enabled_requires_entries_at_pre_review(self):
        stage = self.make_stage("stage-p")
        doc = self.parallel_status("stage-p", embedded_review={"enabled": True, "reason": "high risk"})
        errors = vs.validate_parallel_mode(self.root, stage, doc, "pre-review")
        self.assertTrue(any("at least one embedded_reviews entry" in e for e in errors))

    def test_enabled_complete_round_passes(self):
        stage = self.make_stage("stage-p")
        doc = self.parallel_status(
            "stage-p",
            embedded_review={"enabled": True, "reason": "high risk"},
            embedded_reviews={"A": self.embedded_entry(stage)},
        )
        errors = vs.validate_parallel_mode(self.root, stage, doc, "pre-review")
        self.assertEqual(errors, [])

    def test_enabled_round_missing_result_fails(self):
        stage = self.make_stage("stage-p")
        doc = self.parallel_status(
            "stage-p",
            embedded_review={"enabled": True, "reason": "high risk"},
            embedded_reviews={"A": self.embedded_entry(stage, include_result=False)},
        )
        errors = vs.validate_parallel_mode(self.root, stage, doc, "pre-review")
        self.assertTrue(any("result must be one of" in e for e in errors))

    def test_enabled_round_formal_verdict_value_rejected(self):
        stage = self.make_stage("stage-p")
        doc = self.parallel_status(
            "stage-p",
            embedded_review={"enabled": True, "reason": "high risk"},
            embedded_reviews={"A": self.embedded_entry(stage, result="ACCEPT")},
        )
        errors = vs.validate_parallel_mode(self.root, stage, doc, "pre-review")
        self.assertTrue(any("result must be one of" in e for e in errors))

    def test_legacy_recorded_entries_without_opt_in_still_validated(self):
        stage = self.make_stage("stage-p")
        entry = self.embedded_entry(stage, include_result=False)
        doc = self.parallel_status("stage-p", embedded_reviews={"A": entry})
        errors = vs.validate_parallel_mode(self.root, stage, doc, "pre-review")
        self.assertEqual(errors, [])
        (stage / "embedded-review-A-round1.diff.patch").unlink()
        errors = vs.validate_parallel_mode(self.root, stage, doc, "pre-review")
        self.assertTrue(any("worktree_diff_path does not exist" in e for e in errors))


class TestDispatchReady(PairFixture):
    def default_checklist(self, task_id: str, adapter: str, stage_dir: Path) -> dict:
        prompt = f"task-{task_id}.prompt.md"
        (stage_dir / prompt).write_text("prompt\n")
        return {
            "task_prompt_path": prompt,
            "self_tests_command": "python3 -m pytest",
            "formal_review_raw_output_path": f"30-review-1-{task_id}.raw-output.md",
            "formal_review_verdict_path": f"30-review-1-{task_id}.verdict.json",
            "cross_review_adapter": adapter,
            "next_dispatch_executor": "human_operator",
        }

    def dispatch_status(self, stage_dir: Path, *, embedded_review=None) -> dict:
        for name in ("00-task.md", "10-design.md", "11-adr.md"):
            (stage_dir / name).write_text("x\n")
        parallel = {
            "enabled": True,
            "contract": "docs/parallel-development-mode.md",
            "r10_dispatch_tail_required": True,
            "r4_diff_reconciliation_required": True,
        }
        if embedded_review is not None:
            parallel["embedded_review"] = embedded_review
        return {
            "stage_id": stage_dir.name,
            "status": "implementing",
            "review_artifact_protocol": PROTOCOL_V1,
            "parallel_mode": parallel,
            "embedded_reviews": {},
            "complexity": {"classification": "LOW"},
            "tasks": [
                {"id": "A", "owner": "claude_glm", "r10_checklist": self.default_checklist("A", "kimi", stage_dir)},
                {"id": "B", "owner": "kimi", "r10_checklist": self.default_checklist("B", "claude_glm", stage_dir)},
            ],
        }

    def test_default_packet_passes_without_embedded_fields(self):
        stage = self.make_stage("stage-d")
        doc = self.dispatch_status(stage)
        errors = vs.validate_dispatch_ready(self.root, stage, doc)
        self.assertEqual(errors, [])

    def test_executor_self_rejected(self):
        stage = self.make_stage("stage-d")
        doc = self.dispatch_status(stage)
        doc["tasks"][0]["r10_checklist"]["next_dispatch_executor"] = "self"
        errors = vs.validate_dispatch_ready(self.root, stage, doc)
        self.assertTrue(any("'self' is forbidden" in e for e in errors))

    def test_executor_other_value_rejected(self):
        stage = self.make_stage("stage-d")
        doc = self.dispatch_status(stage)
        doc["tasks"][0]["r10_checklist"]["next_dispatch_executor"] = "bookkeeper"
        errors = vs.validate_dispatch_ready(self.root, stage, doc)
        self.assertTrue(any("must be 'human_operator'" in e for e in errors))

    def test_manual_user_handoff_false_rejected(self):
        stage = self.make_stage("stage-d")
        doc = self.dispatch_status(stage)
        doc["tasks"][0]["r10_checklist"]["manual_user_handoff_allowed"] = False
        errors = vs.validate_dispatch_ready(self.root, stage, doc)
        self.assertTrue(any("manual_user_handoff_allowed=false is forbidden" in e for e in errors))

    def test_wrong_formal_review_path_rejected(self):
        stage = self.make_stage("stage-d")
        doc = self.dispatch_status(stage)
        doc["tasks"][0]["r10_checklist"]["formal_review_raw_output_path"] = "30-review-1.md"
        errors = vs.validate_dispatch_ready(self.root, stage, doc)
        self.assertTrue(any("frozen protocol name" in e for e in errors))

    def test_same_provider_reviewer_rejected(self):
        stage = self.make_stage("stage-d")
        doc = self.dispatch_status(stage)
        doc["tasks"][0]["r10_checklist"]["cross_review_adapter"] = "claude_glm"
        errors = vs.validate_dispatch_ready(self.root, stage, doc)
        self.assertTrue(any("cross_review_adapter must be 'kimi'" in e for e in errors))

    def test_embedded_enabled_incomplete_checklist_fails(self):
        stage = self.make_stage("stage-d")
        doc = self.dispatch_status(stage, embedded_review={"enabled": True, "reason": "high risk"})
        errors = vs.validate_dispatch_ready(self.root, stage, doc)
        self.assertTrue(any("embedded_review_prompt_path" in e for e in errors))
        self.assertTrue(any("max_rounds" in e for e in errors))

    def test_embedded_enabled_complete_checklist_passes(self):
        stage = self.make_stage("stage-d")
        doc = self.dispatch_status(stage, embedded_review={"enabled": True, "reason": "high risk"})
        for task, adapter in (("A", "kimi"), ("B", "claude_glm")):
            prompt = f"embedded-review-{task}.prompt.md"
            (stage / prompt).write_text("prompt\n")
            checklist = next(t for t in doc["tasks"] if t["id"] == task)["r10_checklist"]
            checklist.update(
                {
                    "embedded_review_prompt_path": prompt,
                    "diff_patch_command": "git diff -- x > y",
                    "diff_patch_path": f"embedded-review-{task}-round1.diff.patch",
                    "cross_review_command_ref": f"agents/registry.yaml#adapters.{adapter}.embedded_read_only_review_command",
                    "cross_review_raw_output_path": f"embedded-review-{task}-round1.raw-output.md",
                    "cross_review_dispatch_path": f"embedded-review-{task}-round1.dispatch.md",
                    "max_rounds": 2,
                    "pass_branch": "report PASS and stop for bookkeeper",
                    "blocker_branch": "scope fix then round 2",
                    "unavailable_branch": {
                        "failure_classes": ["model_unavailable"],
                        "escalation_artifact": f"embedded-review-{task}-round1.dispatch.md",
                    },
                }
            )
        errors = vs.validate_dispatch_ready(self.root, stage, doc)
        self.assertEqual(errors, [])


class TestCaptureCLI(PairFixture):
    def run_capture(self, raw: Path, verdict: Path, producer_exit=0, schema: Path | None = None):
        return ra.main(
            [
                "capture",
                "--raw", str(raw),
                "--verdict", str(verdict),
                "--schema", str(schema or SCHEMA_PATH),
                "--producer-exit-status", str(producer_exit),
            ]
        )

    def make_raw(self, obj: dict, name="30-review-1.raw-output.md", data: bytes | None = None) -> Path:
        stage = self.runs / "stage-c"
        stage.mkdir(exist_ok=True)
        raw = stage / name
        raw.write_bytes(data if data is not None else json.dumps(obj).encode() + b"\n")
        return raw

    def test_happy_capture(self):
        obj = valid_verdict()
        raw = self.make_raw(obj)
        verdict = raw.with_name("30-review-1.verdict.json")
        code = self.run_capture(raw, verdict)
        self.assertEqual(code, 0)
        self.assertEqual(verdict.read_bytes(), ra.canonical_verdict_bytes(obj))
        # raw keeps the transport newline; canonical verdict has no trailing newline
        self.assertTrue(raw.read_bytes().endswith(b"\n"))
        self.assertFalse(verdict.read_bytes().endswith(b"\n"))
        leftovers = [p.name for p in raw.parent.iterdir() if ".tmp-" in p.name]
        self.assertEqual(leftovers, [])

    def test_nonzero_producer_exit_fails_and_keeps_raw(self):
        obj = valid_verdict()
        raw = self.make_raw(obj)
        verdict = raw.with_name("30-review-1.verdict.json")
        code = self.run_capture(raw, verdict, producer_exit=1)
        self.assertEqual(code, 1)
        self.assertFalse(verdict.exists())
        self.assertTrue(raw.exists())

    def test_empty_raw_fails(self):
        raw = self.make_raw({}, data=b"")
        verdict = raw.with_name("30-review-1.verdict.json")
        self.assertEqual(self.run_capture(raw, verdict), 1)
        self.assertFalse(verdict.exists())

    def test_fenced_raw_fails(self):
        obj = valid_verdict()
        raw = self.make_raw(obj, data=b"```json\n" + json.dumps(obj).encode() + b"\n```\n")
        verdict = raw.with_name("30-review-1.verdict.json")
        self.assertEqual(self.run_capture(raw, verdict), 1)
        self.assertFalse(verdict.exists())

    def test_schema_invalid_raw_fails(self):
        raw = self.make_raw(valid_verdict(verdict="MAYBE"))
        verdict = raw.with_name("30-review-1.verdict.json")
        self.assertEqual(self.run_capture(raw, verdict), 1)
        self.assertFalse(verdict.exists())

    def test_refuses_overwrite_and_preserves_prior_verdict(self):
        obj = valid_verdict()
        raw = self.make_raw(obj)
        verdict = raw.with_name("30-review-1.verdict.json")
        prior = b'{"prior": "verdict"}'
        verdict.write_bytes(prior)
        self.assertEqual(self.run_capture(raw, verdict), 1)
        self.assertEqual(verdict.read_bytes(), prior)

    def test_missing_schema_file_fails(self):
        obj = valid_verdict()
        raw = self.make_raw(obj)
        verdict = raw.with_name("30-review-1.verdict.json")
        code = self.run_capture(raw, verdict, schema=self.root / "nope.schema.json")
        self.assertEqual(code, 1)
        self.assertFalse(verdict.exists())


class TestAtomicNoClobber(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="no-clobber-test-")
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def test_publish_success_exact_bytes(self):
        target = self.dir / "v.json"
        ra.publish_bytes_no_clobber(target, b"payload")
        self.assertEqual(target.read_bytes(), b"payload")
        self.assertEqual([p.name for p in self.dir.iterdir()], ["v.json"])

    def test_existing_destination_collision_fails_without_damage(self):
        target = self.dir / "v.json"
        target.write_bytes(b"earlier valid verdict")
        with self.assertRaises(ra.CaptureError):
            ra.publish_bytes_no_clobber(target, b"attacker payload")
        self.assertEqual(target.read_bytes(), b"earlier valid verdict")
        self.assertEqual([p.name for p in self.dir.iterdir()], ["v.json"])

    def test_failed_publish_leaves_no_partial_file(self):
        target = self.dir / "missing-dir" / "v.json"
        with self.assertRaises(OSError):
            ra.publish_bytes_no_clobber(target, b"payload")
        self.assertFalse(target.exists())
        self.assertEqual(list(self.dir.iterdir()), [])


class TestHarnessTextContracts(unittest.TestCase):
    """The frozen contract requires that no model-side child-dispatch semantics
    survive in the normative Harness files, and that the new protocol ships."""

    NORMATIVE_FILES = [
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / "docs" / "parallel-development-mode.md",
        REPO_ROOT / "docs" / "model-adapters.md",
        REPO_ROOT / "workflows" / "templates" / "stage-delivery.yaml",
        REPO_ROOT / "reports" / "agent-runs" / "_template" / "status.json",
        SCRIPTS_DIR / "validate-stage.py",
    ]

    def test_no_surviving_self_dispatch_tokens(self):
        for path in self.NORMATIVE_FILES:
            text = path.read_text(encoding="utf-8")
            for token in ("executor: self", "executor:self", '"next_dispatch_executor": "self"'):
                self.assertNotIn(token, text, f"{path}: surviving token {token!r}")
            self.assertNotIn(
                "manual_user_handoff_allowed: false",
                text,
                f"{path}: surviving manual_user_handoff_allowed:false semantics",
            )

    def test_template_defaults_protocol_v1_and_embedded_off(self):
        template = json.loads(
            (REPO_ROOT / "reports" / "agent-runs" / "_template" / "status.json").read_text()
        )
        self.assertEqual(template.get("review_artifact_protocol"), PROTOCOL_V1)
        embedded = template["parallel_mode"]["embedded_review"]
        self.assertIs(embedded["enabled"], False)
        self.assertIn("raw_output_path", template["review_1"])
        self.assertIn("verdict_path", template["review_2"])

    def test_manifest_registers_helper_and_tests(self):
        manifest = (REPO_ROOT / "harness-manifest.yaml").read_text(encoding="utf-8")
        for entry in (
            "scripts/review_artifacts.py",
            "scripts/validate-all-stages.py",
            "scripts/tests/test_review_artifacts.py",
        ):
            self.assertIn(f"- {entry}", manifest)

    def test_capture_helper_never_dispatches(self):
        helper = (SCRIPTS_DIR / "review_artifacts.py").read_text(encoding="utf-8")
        for token in ("import subprocess", "from subprocess", "os.system(", "os.exec", "Popen("):
            self.assertNotIn(token, helper)


if __name__ == "__main__":
    unittest.main(verbosity=2)
