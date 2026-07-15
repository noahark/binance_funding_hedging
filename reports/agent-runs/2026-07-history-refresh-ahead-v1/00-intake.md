# Stage Intake

## Stage

- Stage ID: `2026-07-history-refresh-ahead-v1`
- Workflow: `stage-delivery`
- Branch: `stage/2026-07-history-refresh-ahead-v1`
- Created from local `main`:
  `12b8e1c1ea5d86bf692bbba2183de08ee9429af4`
- Complexity: `LOW`
- Parallel mode: disabled

## User-Approved Lightweight Route

The user approved one bounded correction after live acceptance observation:

- funding history becomes refresh-due at 1500 seconds;
- the existing 1800-second publication expiry remains unchanged;
- borrow-rate, max-borrowable, Group B, private transport TTLs, and the
  `-0.00030000` threshold exit/re-entry behavior remain unchanged;
- no frontend, API, schema, or trading behavior changes.

The user explicitly approved the lightweight route. The existing cache scheduler
design covers the surrounding architecture, so no direction panel or development
breakdown is required for this LOW stage.

## Routing

- Designer/bookkeeper: Codex / OpenAI; no delivery-code authorship.
- Implementation owner: Claude-GLM / `zhipu_glm` (backend).
- Review-1: fresh read-only Kimi session.
- Review-2: fresh read-only Claude provider session because Codex is the stage
  designer; Claude has no implementation or design authorship in this stage.
- All model dispatch is human-executed from prepared prompt files.

本地北京时间: 2026-07-15 10:44:33 CST
下一步模型: codex_bookkeeper
下一步任务: 冻结最小设计并准备 Claude-GLM 实现派发包
