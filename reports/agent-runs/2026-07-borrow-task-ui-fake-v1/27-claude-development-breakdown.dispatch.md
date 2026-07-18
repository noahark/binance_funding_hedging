# Development Breakdown Dispatch — Fake Borrow-Task v2

You are the development-breakdown author for a MEDIUM fake-UI amendment plus a narrow existing-contract extension. Work read/write only in the stage evidence directory; do not modify application source, tests, backend, API contracts, schemas, fixtures, documents outside the stage evidence, credentials, or any external service.

Repository: `/Users/ark/Desktop/ai code/funding_hedging`

Read these raw artifacts before writing:

- `AGENTS.md`
- `agents/developer-discipline.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/00-intake.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/00-task.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/10-design.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/11-adr.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/13-scope-amendment-v2.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/14-user-min-borrow-contract-amendment.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/30-review-1.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/status.json`

Write `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/12-development-breakdown.md`. It must define two dependency-ordered implementation tasks: Claude-GLM owns the backend/schema/raw-sample contract amendment; Kimi owns the frontend task-state/filter/edit UI and consumes the new field after the backend contract lands. It must include:

- allowed and forbidden files;
- the task status model (`borrowing`, `paused`, `deleted`, `completed`), exact start/pause/delete transition and button-enable rules;
- soft deletion and filter semantics (全部 includes deleted);
- task-list edit input/validation/update rules;
- the completed-state limitation (no scheduler or UI simulation trigger);
- no-fetch/no-timer/no-persistence/non-backend boundaries;
- self-check cases, manual visual checks, risks, and review focus;
- treatment of the old review-1 ACCEPT as superseded by the user scope amendment.
- the exact `allAssets[].userMinBorrow → classic_ref.user_min_borrow_by_name → rows[].borrow_validation.classic_margin.user_min_borrow` mapping, plus `user_min_borrow_value_usdt`; null/pair-listed gates matching `asset_borrowable`; raw-string preservation; same stablecoin/price routing as the maximum-borrow calculation; `Decimal` `ROUND_HALF_UP` quantization to exactly two decimal places for the new value; the existing eight-decimal `max_borrowable_value_usdt` unchanged; schema/fixture/test requirements; and the required raw public sample copy under `reports/api-samples/2026-07-borrow-task-ui-fake-v1/`;
- the market operation amount input placeholder rule `最小借币量 <value> (≈ <two-decimal-value> USDT)` / `最小借币量 <value> (≈ — USDT)` / `最小借币量 —`, including that the input value stays empty and task-list edit inputs are not changed by this rule.

Do not make up a new backend endpoint, retry behavior, storage model, simulated-success button, fake HOME market row, or a nonzero raw `userMinBorrow` sample. Retain the two P3 notes from old review-1 as optional review inputs, not mandatory work unless your breakdown identifies a direct conflict.

Then update only this stage's `status.json` to record you as `breakdown_author` and append a session receipt with verified provider-native Session ID or explicit unavailable reason. Update `70-handoff.md` with the next action. Include the mandatory footer in the breakdown report.

当前 Session ID: unavailable (to be captured by Claude/operator after execution)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-borrow-task-ui-fake-v1/27-claude-development-breakdown.dispatch.md
本地北京时间: 2026-07-18 22:01:37 CST
下一步模型: Claude
下一步任务: 输出 12-development-breakdown.md，供 Kimi 实现 fake UI v2
