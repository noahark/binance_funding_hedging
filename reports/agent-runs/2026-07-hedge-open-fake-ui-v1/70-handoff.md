# Handoff — Hedge Open Fake UI v1

## Recovery Header

- Active phase: `design_and_breakdown_complete_waiting_human_dispatch_to_kimi`.
- Stage branch: `stage/2026-07-hedge-open-fake-ui-v1`, created from main
  `e6b836831391da8b98101d9c6a85353e9fa8273e`. Not merged back.
- Next action: the human operator dispatches the Kimi implementation packet
  (`task-hedge-open-fake-ui-kimi.dispatch.md`). The bookkeeper does not launch
  Kimi. After Kimi stops, the bookkeeper collects `20-implementation.md` +
  `60-test-output.txt`, creates a local evidence commit, computes the standard
  `diff_fingerprint`, runs `scripts/validate-stage.py 2026-07-hedge-open-fake-ui-v1
  --phase pre-review`, then dispatches review-1 (Claude-GLM).
- Read-set: `00-task.md`, `10-design.md`, `11-adr.md`,
  `12-development-breakdown.md`, `status.json`.
- Do-not-read: credentials, `.env`, unrelated stages, any `history/`.

## Scope recap

Pure front-end fake prototype of the hedge OPEN surface. No backend, no real
websocket, no order path, no credentials. Three deliverables (market-table
columns, 开单任务 page, private-account fake position table) — see `00-task.md`.
Real order execution + live basis gating + durable tasks are deferred to
`stage/2026-07-hedge-open-live-v1`; close is `stage/2026-07-hedge-close-v1`.

## Roles / routing

- Bookkeeper: Claude Opus 4.8 (anthropic). Also breakdown author (design
  involvement disclosed); NOT implementer or fix author.
- Implementer: Kimi (`moonshot_kimi`), front-end only. Dispatch packet prepared,
  human-executed.
- review-1: Claude-GLM (`zhipu_glm`), cross-provider isolation from Kimi.
- review-2: GPT/Codex first; reported no quota this round → planned Claude
  (`anthropic`) strong-reviewer fallback with design-involvement disclosure,
  contingent on a runner-level unavailability check being recorded first.

## Boundary C note (prior active stage)

`2026-07-real-borrow-boundary-c-v1` was merged to local main (`7d0c925`) under
user release authorization; its remaining items are operator-side (user sets
`APP_BORROW_EXECUTOR=live` + non-secret aliases in `.env`, restarts service,
then read-only online preflight before任务删除). Those are preserved in that
stage's own `70-handoff.md` and `ACTIVE.json` last_completed note; they are not
blocked by this stage.

当前 Session ID: unavailable (Claude Code runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-fake-ui-v1/{00-intake.md,00-task.md,10-design.md,11-adr.md,12-development-breakdown.md,status.json,70-handoff.md,task-hedge-open-fake-ui-kimi.prompt.md,task-hedge-open-fake-ui-kimi.dispatch.md}
本地北京时间: 2026-07-22 18:51:35 CST
下一步模型: Kimi (human-operator-dispatched implementation)
下一步任务: implement the hedge open fake UI within frontend/index.html + frontend/self-check.js, run node frontend/self-check.js green, write 20-implementation.md + 60-test-output.txt, stop for bookkeeper
