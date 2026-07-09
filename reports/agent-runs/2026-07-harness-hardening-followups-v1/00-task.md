# Task

## Scope

Fix the 5 non-blocking P2 hardening findings from review-2 of
`2026-07-harness-friction-fixes-v1`. This is a Harness-only stage.

## Acceptance Criteria

1. `scripts/validate-stage.py` handles `--evidence-out` write failures with a
   clear Harness-style error instead of an uncaught Python traceback.
2. `scripts/record-checkpoint` rejects `--dry-run` when `--single-owner` is not
   present, so users cannot accidentally run the double-owner mutation path
   while believing it is a preview.
3. `scripts/validate-stage.py` pins `-c diff.renames=true` in
   `compute_diff_fingerprint`, matching `scripts/_itbm.py` canonical
   fingerprint behavior.
4. `reports/agent-runs/_template/status.json` supports `review_1.actual_model`,
   mirroring the review-2 actual-model evidence pattern.
5. `workflows/templates/stage-delivery.yaml` records explicit fix return
   guidance for review-1 versus review-2, so a fix can route back to the
   originating review gate mechanically.

## Allowed Files

```text
scripts/validate-stage.py
scripts/record-checkpoint
scripts/tests/itbm_dry_run.py
scripts/tests/test_validate_stage.py
reports/agent-runs/_template/status.json
workflows/templates/stage-delivery.yaml
reports/agent-runs/README.md
reports/agent-runs/2026-07-harness-hardening-followups-v1/20-implementation.md
reports/agent-runs/2026-07-harness-hardening-followups-v1/60-test-output.txt
```

## Forbidden Files

```text
backend/**
frontend/**
docs/product/**
docs/architecture/**
reports/api-samples/**
AGENTS.md
agents/registry.yaml
schemas/**
prototypes/**
.env
.env.example
reports/agent-runs/2026-07-harness-friction-fixes-v1/**
```

## Required Evidence

The implementer must run and preserve output for:

```bash
python3 scripts/tests/itbm_dry_run.py
python3 -m py_compile scripts/validate-stage.py scripts/_itbm.py
python3 scripts/tests/test_validate_stage.py
python3 scripts/validate-stage.py 2026-07-harness-hardening-followups-v1 --phase checkpoint
git diff --check
```

If a finding cannot be covered by a deterministic test without excessive
fixture cost, record the reason in `20-implementation.md` and include a static
or behavioral check instead.

## Non-goals

- Do not change the Harness fingerprint protocol.
- Do not change provider identity rules beyond the 5 listed findings.
- Do not alter old accepted review artifacts.
- Do not touch product code.
- Do not push, merge, rebase, or mark the stage accepted.

本地北京时间: 2026-07-09 21:10:45 CST
下一步模型: claude_glm
下一步任务: implement the 5 Harness hardening acceptance criteria
