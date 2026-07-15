# Handoff

This file is the stage's active handoff context. A new terminal session reads
it together with `status.json` and only the needed workflow section; it does
not read `history/` at startup.

## Recovery Header

- Active phase: `implementation`
- Next action: Human executes `task-a-backend-claude-glm.prompt.md`; Task A stops and returns to bookkeeper before Task B.
- Read-set: = `status.current_inputs`
- Open blockers: none
- Do-not-read: `reports/agent-runs/**/history/**`, other stages

## Current State

- Stage: `2026-07-bookticker-open-columns-v1`
- Status: `implementing` (Task A packet prepared; waiting for human execution)
- Branch: `stage/2026-07-bookticker-open-columns-v1`
- HEAD: `fea9fdc3ecce7675b34b01fe0a4b9de08811f939` (stage branch creation point; no stage commit yet)
- Git status: uncommitted design/Harness/API-evidence checkpoint; no backend/frontend/schema product runtime changes
- Bookkeeper: `codex / gpt-5 / codex_bookkeeper`, Session `019f639a-7890-7573-a04b-7a62debff633`; not implementer/fix author
- Designer: `codex / gpt-5 / software_architect`
- Breakdown author: Anthropic Claude `opus4.8`, Session `d313bb8a-6355-45b9-b546-5995bd320862`, verdict `READY`
- Advisory reviewer: Grok `grok-build`, Session `019f6457-54f7-7fd1-aba0-842c084fdde2`, raw verdict `REVISE`, fully reconciled
- Parallel mode: disabled; Task A committed/frozen backend contract precedes Task B

## User-Approved Scope Amendment

On 2026-07-15 the user explicitly asked this stage to include Harness Session
receipt v1 so later implementation and review outputs display the current
provider-native Session ID. This is the documented exception to the normal rule
against mixing unrelated Harness sync into a product stage: the current stage
needs the behavior immediately.

Implemented Harness surface:

- `AGENTS.md` six-field navigation footer and checkpoint receipt rule
- `docs/model-adapters.md` Codex/Claude/Claude-GLM/Grok/Kimi lookup and
  verification order
- `workflows/templates/stage-delivery.yaml` Session receipt contract
- `reports/agent-runs/_template/` model-facing footers and status ledger

Session IDs remain navigation metadata. Cross-provider review still consumes
stage raw artifacts, not another provider's ID.

## Frozen User Decisions

- “净收益”改为“日净收益”；删除默认表“提示标记”列。
- 合并资产标签与借贷状态的前端单元格，状态在上、资产标签在下；底层契约语义仍分离。
- bookTicker 以 60 秒 public Group A cadence 全量抓取并成对缓存，缺失/零值不计算，age `>=120s` 不发布可用开单价。
- 正向：上合约买一、下现货卖一，`(F_bid-S_ask)/S_ask*100`。
- 反向：上现货买一、下合约卖一，`(S_bid-F_ask)/F_ask*100`。
- 两方向正值都表示有利价差；后端 Decimal，两位 HALF_UP；前端独立 formatter，不复用 `formatFundingRate`。

## Review Reconciliation

- Claude: `READY`; seven P2 constraints incorporated through its breakdown.
- Grok: `REVISE`; three P1 and five P2 resolved in bounded design changes.
- Key amendments: stale recalculated every assembly; incomplete direction truth
  table; strict JSON-string prices; opening-spread formatter; 60s/120s UI
  wording; discovery double-source sketch superseded; public contract doc added.
- No unresolved P0/P1 and no product decision remains.

## Artifact Index

- Intake: `reports/agent-runs/2026-07-bookticker-open-columns-v1/00-intake.md`
- Task: `reports/agent-runs/2026-07-bookticker-open-columns-v1/00-task.md`
- Design: `reports/agent-runs/2026-07-bookticker-open-columns-v1/10-design.md`
- ADR: `reports/agent-runs/2026-07-bookticker-open-columns-v1/11-adr.md`
- Claude breakdown: `reports/agent-runs/2026-07-bookticker-open-columns-v1/12-development-breakdown.md`
- Grok raw export: `reports/agent-runs/2026-07-bookticker-open-columns-v1/13-design-review-grok.raw.md`
- Review reconciliation: `reports/agent-runs/2026-07-bookticker-open-columns-v1/14-design-review-reconciliation.md`
- Session method evidence: `reports/agent-runs/2026-07-bookticker-open-columns-v1/15-session-id-capture-evidence.md`
- Task A packet: `reports/agent-runs/2026-07-bookticker-open-columns-v1/task-a-backend-claude-glm.prompt.md`
- Task A implementation: pending at `20-implementation-task-a.md`
- Task B implementation: blocked on committed/frozen Task A contract
- Review 1 / fix / review 2: pending
- Test output: `reports/agent-runs/2026-07-bookticker-open-columns-v1/60-test-output.txt`; design/Harness mechanical checks passed, product tests not run
- Status JSON: `reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json`
- Public API evidence: `reports/api-samples/2026-07-bookticker-discovery-v1/20260715T0651Z/`

## Open Findings

- None at design gate. Product implementation has not started.

## Blockers

- None.

## Next Action

The human operator runs
`reports/agent-runs/2026-07-bookticker-open-columns-v1/task-a-backend-claude-glm.prompt.md`
in the existing Claude-GLM terminal. Claude-GLM may edit only the Task A allowed
backend/schema/test/doc files plus `20-implementation-task-a.md`; it does not
commit, modify stage state, start Kimi, or dispatch review. Its report and final
response must include the verified Session ID/source/raw-output footer.

当前 Session ID: 019f639a-7890-7573-a04b-7a62debff633
Session ID 来源: runtime_env (`CODEX_THREAD_ID`)
原始输出路径: reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md
本地北京时间: 2026-07-15 17:37:39 CST
下一步模型: claude_glm（由人工执行）
下一步任务: 执行 Task A 后端实现 packet，完成后交回 codex_bookkeeper 核验 diff 与测试
