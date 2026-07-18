# Claude-GLM Implementation Dispatch

You are the sole implementation author for LOW stage
`2026-07-tradable-spot-leg-v1` under provider identity `zhipu_glm`, model `glm-5.2`.
Use the repository `senior_developer` role skill. Do not invoke another model or subagent.

## Read First

Read these files completely before editing:

1. `AGENTS.md`
2. the implementation section of `workflows/templates/stage-delivery.yaml`
3. `agents/developer-discipline.md`
4. `agents/skills/senior-developer.md`
5. `reports/agent-runs/2026-07-tradable-spot-leg-v1/status.json`
6. `reports/agent-runs/2026-07-tradable-spot-leg-v1/00-task.md`
7. `reports/agent-runs/2026-07-tradable-spot-leg-v1/10-design.md`
8. `reports/agent-runs/2026-07-tradable-spot-leg-v1/11-adr.md`
9. `reports/agent-runs/2026-07-tradable-spot-leg-v1/05-live-sample-analysis.md`
10. `reports/api-samples/2026-07-tradable-spot-leg-v1/20260718T042314Z/`
11. the relevant implementation, tests, PRD, and API contract inside the allowed boundary

Before writing, verify the current branch is exactly
`stage/2026-07-tradable-spot-leg-v1`. Preserve all existing uncommitted bookkeeper artifacts.

## Role And Safety Boundary

- You are the implementation author only, not the bookkeeper or reviewer.
- Do not edit `status.json`, `70-handoff.md`, intake/design/ADR/dispatch files, raw samples,
  workflows, registry, schemas, adapters, frontend, private-account code, `.env`, or any other
  stage.
- Do not commit, push, merge, rebase, deploy, or execute another model dispatch.
- Do not inspect, print, store, or summarize credentials or expanded alias environments.
- No order, borrow, repay, transfer, close, or other trading execution is allowed.

## Required Change

Implement the approved resolver invariant in `backend/domain/normalize.py`:

- an exact spot record resolves only when `status == "TRADING"`;
- absent, missing-status, `BREAK`, `HALT`, and every other value fail closed;
- for `TRADIFI_PERPETUAL`, skip a non-trading exact record and continue to the B-suffix alias;
- the B-suffix alias also resolves only when its status is exactly `TRADING`;
- preserve the existing match-type strings and all existing behavior for tradable exact and alias
  records.

Keep the rule at `resolve_spot_leg` (or an equivalent private helper used by that resolver), not
only in a service-side index. Do not add a schema field or frontend workaround. When no usable
spot leg resolves, existing downstream logic must emit the current no-leg shape and
`PERP_ONLY_EXCLUDED` / `DISABLED_PERP_ONLY` behavior specified in `00-task.md`.

## Allowed Writes

- `backend/domain/normalize.py`
- `backend/tests/test_snapshot.py`
- `docs/product/PRD.md`
- `docs/api/public-market-contract.md`
- `reports/agent-runs/2026-07-tradable-spot-leg-v1/20-implementation.md`
- `reports/agent-runs/2026-07-tradable-spot-leg-v1/60-test-output.txt`

Everything else is forbidden. If correct implementation requires another file, stop and record a
blocker in `20-implementation.md`; do not expand scope yourself.

## Tests And Evidence

Add regression coverage for all of these cases:

1. exact `TRADING` remains eligible;
2. exact `BREAK` does not resolve and produces the expected excluded route shape;
3. exact `HALT` does not resolve;
4. a non-trading exact record does not block a `TRADING` B-suffix alias;
5. a non-trading B-suffix alias does not resolve;
6. missing or unknown status fails closed if not already directly covered by the cases above.

Update the PRD and API contract narrowly so “spot leg” / `spot.exists` means a currently tradable
resolved spot leg, while raw Binance history may still contain a non-trading symbol record. Cite
the frozen AERGOUSDT, XMRUSDT, and LITUSDT evidence path in `20-implementation.md`.

Run exactly these commands and append their complete, unedited output to `60-test-output.txt`:

```text
python3 -m pytest backend/tests/test_snapshot.py -q
python3 -m pytest backend/tests -q
node frontend/self-check.js
git diff --check
```

Do not run review gates or compute a diff fingerprint; the bookkeeper does that after inspection
and the evidence commit.

## Deliverables

Create `20-implementation.md` with:

- provider/model and verified provider-native Session ID, or an explicit unavailable reason;
- exact files changed and implementation summary;
- test matrix mapping and raw output path;
- frozen public sample path and what it proves;
- confirmation that schema/frontend/private/execution behavior did not change;
- current `git status --short`, any blocker, and no-commit/no-push/no-merge confirmation.

End both the implementation report and your final response with a local `date`-derived footer:

```text
当前 Session ID: <provider-native id | unavailable (reason)>
Session ID 来源: <runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable>
原始输出路径: reports/agent-runs/2026-07-tradable-spot-leg-v1/20-implementation.md
本地北京时间: YYYY-MM-DD HH:MM:SS CST
下一步模型: Codex bookkeeper
下一步任务: 核验实现边界和测试证据，创建本地 evidence commit 并准备 Kimi review-1
```

---
当前 Session ID: 019f734a-dd82-7a11-8367-93fc1a5e954c
Session ID 来源: runtime_env
原始输出路径: reports/agent-runs/2026-07-tradable-spot-leg-v1/08-dispatch-claude-glm-implementation.md
本地北京时间: 2026-07-18 12:29:25 CST
下一步模型: claude_glm
下一步任务: 由人类操作者在 Claude-GLM 终端执行本派工包
