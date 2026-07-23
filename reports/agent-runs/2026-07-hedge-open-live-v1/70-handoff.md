# Handoff — Hedge Open Live v1 (stage 2)

## Recovery Header

- Active phase: `ACCEPTED + no-ff merged to local main` — round 1 complete.
- Final: user accepted round 1 (dry-run skeleton); no-ff merged to LOCAL main
  `1f65042` (NOT pushed). Product head `02bcc24` (base `6639b002`). review-1 both
  ACCEPT + review-2 Codex ACCEPT + pre-accept PASS. rework 2/3. Three cross-seam
  drifts caught+fixed (R4-001/F-001/F-007).
- **Next stage = the real-API round** (user: 直接上真实 api): rebuild the order-
  parameter model per DI-6 (spot market BUY = quoteOrderQty; DI-4/ADR-2 wrong for
  forward), real preflight/executor + APP_HEDGE_EXECUTOR=live + global Start +
  user margin/amount/count risk controls, smooth-open ws gate (DI-1),
  F-003..F-006, both-mismatched representation. Nothing real authorized yet.
  See `80-user-acceptance.md` + `design-inputs.md`.
- Both recon reports done and archived under
  `reports/api-samples/2026-07-hedge-open-live-v1/` (websocket → Sonnet;
  order-endpoints/filters → GPT); decisions locked into DI-1 (option B) and DI-4.
- Round-1 scope = immediate open only (1 fill/sec, no websocket), dry-run record
  transport. Design draft written: `00-task.md`, `10-design.md`, `11-adr.md`.
- Stage branch: `stage/2026-07-hedge-open-live-v1`, created from main
  `4253889c838baa67aa441807588df426a4db8c9d`. Not merged back.
- This is stage 2 of the hedge program: the **live backend open executor**.
  Direction is frozen (three-stage discussion + accepted stage-1 contracts);
  classification HIGH + user-approved lightweight route (no direction panel).
- Next action: human operator dispatches the two cross-review-1 packets —
  hedge-be→Kimi (`review-1-hedge-be-kimi.prompt.md`), hedge-fe→Claude-GLM
  (`review-1-hedge-fe-claude-glm.prompt.md`), each fresh + read-only, saving raw
  output to `30-review-1-<task>.md`. Bookkeeper intakes each verdict; on both
  ACCEPT → review-2 (Codex first, else Claude fallback with disclosure); any
  REWORK → route the reviewer `fix_start_prompt` to that task's implementer.
  Real orders remain gated (dry-run default; live needs `APP_HEDGE_EXECUTOR=live`
  + global Start + human first task, after review).
- Note: the unrelated untracked `scripts/check_symbol_mismatch.py` (a user tool,
  not this stage's) was moved to scratchpad to satisfy the clean-worktree gate;
  awaiting the user's decision on its home (commit to main / gitignore / keep in
  scratchpad).
- Read-set: `00-intake.md`, `api-recon-websocket.prompt.md`, `status.json`, and
  the stage-1 contracts (`reports/agent-runs/2026-07-hedge-open-fake-ui-v1/`
  `{10-design.md,11-adr.md,00-task.md}`).
- Do-not-read: credentials, `.env`, unrelated stages, any `history/`.

## Safety posture (locked at intake)

Real funds. No real Binance order, no production execution websocket, no
credential access, no push authorized yet. `APP_HEDGE_EXECUTOR=live`, the global
Start gate, and the first real task are human-only actions AFTER implementation
and review — same discipline as Boundary C. Order/filter/stream contract changes
require real public API samples under `reports/api-samples/`.

## Roles / routing (planned)

- Bookkeeper: Claude Opus 4.8 (anthropic).
- Implementers (planned split): backend Claude-GLM (`zhipu_glm`), frontend Kimi
  (`moonshot_kimi`); parallel-mode candidate, decided at breakdown time.
- review-1: cross-provider from each implementer. review-2: Codex/GPT first,
  else Claude fallback with disclosure (subject to quota; note the stage-1
  lesson that all decision models may be unavailable).

当前 Session ID: unavailable (Claude Code runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-v1/{00-intake.md,api-recon-websocket.prompt.md,status.json,70-handoff.md}
本地北京时间: 2026-07-22 21:40:33 CST
下一步模型: user-delegated recon model (websocket facts)
下一步任务: run api-recon-websocket.prompt.md, return raw recon; bookkeeper archives to reports/api-samples/ and writes stage design
