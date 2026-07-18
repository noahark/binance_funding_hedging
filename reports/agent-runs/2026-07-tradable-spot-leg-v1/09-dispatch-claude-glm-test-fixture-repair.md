# Claude-GLM Mechanical Fixture Repair Dispatch

You are the continuing implementation author for LOW stage
`2026-07-tradable-spot-leg-v1` under provider identity `zhipu_glm`, model `glm-5.2`. This is a
scope-contained mechanical continuation of implementation session
`bb16025d-d15d-47d1-969a-0df4a2f4be14`, not a new design task or review. Do not invoke another
model or subagent.

## Read First

Read these files before editing:

1. `AGENTS.md`
2. `agents/developer-discipline.md`
3. `agents/skills/senior-developer.md`
4. `reports/agent-runs/2026-07-tradable-spot-leg-v1/00-task.md`
5. `reports/agent-runs/2026-07-tradable-spot-leg-v1/10-design.md`
6. `reports/agent-runs/2026-07-tradable-spot-leg-v1/11-adr.md`
7. `reports/agent-runs/2026-07-tradable-spot-leg-v1/07-scope-extension-authorization.md`
8. `reports/agent-runs/2026-07-tradable-spot-leg-v1/20-implementation.md`
9. `reports/agent-runs/2026-07-tradable-spot-leg-v1/60-test-output.txt`
10. `backend/tests/test_normalize.py`

Verify that the branch is exactly `stage/2026-07-tradable-spot-leg-v1`. Preserve every existing
uncommitted implementation and evidence change; do not restore, rewrite, or discard them.

## Authorized Repair — Exact Scope

Edit only `backend/tests/test_normalize.py` production-test fixtures as follows:

1. In `test_resolve_spot_leg_exact_symbol`, add `"status": "TRADING"` to the `BTCUSDT` spot
   record.
2. In `test_resolve_spot_leg_bstock_alias_for_tradifi`, add `"status": "TRADING"` to the
   `TSLABUSDT` spot record.
3. In `test_resolve_spot_leg_exact_beats_alias_for_tradifi`, add `"status": "TRADING"` to both
   the `TSLAUSDT` and `TSLABUSDT` spot records.

These four dictionary-field additions across three tests are the entire code/test repair. Do not
change assertions, test names, production code, documentation, or resolver semantics. Missing or
unknown status must continue to fail closed.

## Allowed Writes

- `backend/tests/test_normalize.py`
- `reports/agent-runs/2026-07-tradable-spot-leg-v1/20-implementation.md`
- `reports/agent-runs/2026-07-tradable-spot-leg-v1/60-test-output.txt`

Everything else is read-only. In particular, do not edit `status.json`, `70-handoff.md`, dispatch
files, raw samples, production code, schemas, frontend, other tests, workflows, registry, or any
other stage. Do not inspect credentials or expanded alias environments. Do not commit, push,
merge, rebase, deploy, or dispatch another model.

## Verification And Evidence

Run these commands and append their complete raw output and exit codes to `60-test-output.txt`:

```text
python3 -m pytest backend/tests/test_normalize.py -q
python3 -m pytest backend/tests/test_snapshot.py -q
python3 -m pytest backend/tests -q
node frontend/self-check.js
git diff --check
git status --short
```

Preserve the earlier failing run as audit evidence. Append a new clearly timestamped repair run;
do not delete, replace, summarize, or rewrite earlier test output.

Append a `Blocker Resolution` section to `20-implementation.md` that records the authorized file,
the exact fixture-only change, all command outcomes, and whether the full backend suite is green.
Do not erase the original blocker narrative. Record the verified provider-native Session ID from
Claude Code when visible; otherwise state the exact unavailable reason.

Finish with a local `date`-derived footer:

```text
当前 Session ID: <provider-native id | unavailable (reason)>
Session ID 来源: <runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable>
原始输出路径: reports/agent-runs/2026-07-tradable-spot-leg-v1/20-implementation.md
本地北京时间: YYYY-MM-DD HH:MM:SS CST
下一步模型: Codex bookkeeper
下一步任务: 核验 fixture-only 修复和全量测试，创建本地 evidence commit 并准备 Kimi review-1
```

---
当前 Session ID: 019f734a-dd82-7a11-8367-93fc1a5e954c
Session ID 来源: runtime_env
原始输出路径: reports/agent-runs/2026-07-tradable-spot-leg-v1/09-dispatch-claude-glm-test-fixture-repair.md
本地北京时间: 2026-07-18 13:43:26 CST
下一步模型: claude_glm
下一步任务: 机械补齐三个旧测试 fixture 的 TRADING 状态并重跑冻结测试
