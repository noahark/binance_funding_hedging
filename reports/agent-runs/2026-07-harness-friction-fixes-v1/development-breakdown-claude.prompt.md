<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status:        pending
target_model:  claude / claude-fable-5 (fallback: claude-opus-4-8)
adapter_cmd:   claude --model claude-fable-5 --permission-mode plan -p "$(cat reports/agent-runs/2026-07-harness-friction-fixes-v1/development-breakdown-claude.prompt.md)"
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       reports/agent-runs/2026-07-harness-friction-fixes-v1/12-development-breakdown.md
next_dispatch: none
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable，设计期定稿后不得修改） ===== -->
You are the development breakdown author for Harness stage
`2026-07-harness-friction-fixes-v1`.

Read first:

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `docs/independent-task-branch-mode.md`
- `docs/model-adapters.md`
- `reports/agent-runs/README.md`
- `scripts/validate-stage.py`
- `scripts/record-checkpoint`
- `scripts/_itbm.py`
- `reports/agent-runs/_template/status.json`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/00-intake.md`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/00-task.md`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/10-design.md`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/11-adr.md`
- Prior-stage evidence:
  `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/70-handoff.md`,
  `30-review-1.md`, `50-review-2.md`, `status.json`

Task:

Create `reports/agent-runs/2026-07-harness-friction-fixes-v1/12-development-breakdown.md`.

Required contents:

- Recommended implementation owner and review-1 reviewer.
- Whether this should be one task or split into sub-tasks.
- Exact allowed files and forbidden files.
- Concrete implementation requirements for each friction point, especially:
  1. unselected review-2 preferred provider must not trigger designer-overlap;
  2. single-owner validator evidence must be inside or reconciled with the
     reviewed range;
  3. `record-checkpoint --single-owner` status metadata behavior must be
     implemented or documentation/template claims corrected;
  4. validator evidence capture must not dirty the worktree before clean check;
  5. delivery-anchored `head_sha` and validator fixed-point semantics must be
     documented;
  6. actual Claude fallback model must be recorded cleanly;
  7. `fix_start_prompt.next_action` must point to the true next step.
  8. a durable reporting-language preference must be added: Chinese-first
     user-facing reports and significant bookkeeper responses, with necessary
     English technical terms explained in Chinese on first use while preserving
     exact commands, paths, JSON/schema keys, model names, provider identities,
     and code identifiers.
- Test plan with exact commands and fixture expectations.
- Review focus for Kimi review-1 and final review-2.
- Explicit non-goals and rollback/REWORK triggers.

Constraints:

- Do not edit product code.
- Do not execute implementation.
- Do not modify files other than `12-development-breakdown.md` unless a brief
  evidence note is necessary.
- End with the standard Harness footer using local date output.

本地北京时间: 2026-07-09 13:42:58 CST
下一步模型: human
下一步任务: dispatch implementation after reviewing `12-development-breakdown.md`
