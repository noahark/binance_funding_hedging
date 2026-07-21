[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于
   claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出
   ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条
   执行记录都必须对应你本会话内真实发生的动作。
3. 你的依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的文件。

# Task C — Bookkeeper Intake Micro Fix 3（测试证据机械修正）

你是 Task C 原实现者：`claude_glm` / provider identity `zhipu_glm` /
`glm-5.2[1m]`。fix 2 的产品代码行为已经通过 bookkeeper 复审；本轮不允许修改
任何产品 source，只恢复一个被严格 row contract 意外弱化的必测场景。

## 必读

1. `AGENTS.md`
2. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/12-development-breakdown.md`（§5.3 / §9.10）
3. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/20-implementation-bookkeeper-audit.md`（Fix 2 Re-audit）
4. `backend/tests/test_live_borrow_executor.py`

## 唯一修改

在 `test_reconcile_multiple_confirmed_not_matched` 中，让第二条 CONFIRMED row
也携带 contract-valid `timestamp`，并保持两条记录的 asset 与 exact Decimal
principal 都匹配当前 task、`txId` 不同、`total == 2`。断言继续是
`matched is False`。

这条测试必须明确证明：两个**完整合法**的匹配候选因为 ambiguity 而不能证明
success，而不是因为任一 row malformed 被更早 fail-closed。不要删除或合并独立
的 malformed-row regression。

## Allowed Files

- `backend/tests/test_live_borrow_executor.py`
- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/20-implementation.md`
- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/60-test-output.txt`（append only）
- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-bookkeeper-fix-3.dispatch.md`
  （只回填 Receipt）

禁止修改任何产品 source、其它 test、`status.json`、`70-handoff.md`、`ACTIVE.json`、
bookkeeper audit、设计/规范/Harness、unrelated stage 或 `_proposals/**`。不 commit/
push/merge，不 dispatch reviewer。

## 验证

```text
python3 -m pytest backend/tests/test_live_borrow_executor.py -q
python3 -m pytest \
  backend/tests/test_portfolio_margin_borrow_client.py \
  backend/tests/test_live_borrow_executor.py -q
python3 -m pytest backend/tests -q
node frontend/self-check.js
python3 -m py_compile backend/services/live_borrow_executor.py
git diff --check
```

真实输出追加到 `60-test-output.txt`。在 `20-implementation.md` 增加
`Bookkeeper intake micro fix 3 — multiple-candidate evidence`，说明仅补 timestamp、
产品代码零改动、合法 multiple 与 malformed 两个测试均保留。只回填 dispatch 的
Receipt 与六行页脚，然后停止等待 bookkeeper；不得宣称 review 或 acceptance。

当前 Session ID: unavailable (prompt preparation session; target runtime must record its own verified ID or exact unavailable reason)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-bookkeeper-fix-3.prompt.md
本地北京时间: 2026-07-21 10:12:03 CST
下一步模型: human operator → Claude-GLM / GLM-5.2
下一步任务: execute this micro fix-3 packet, restore the contract-valid multiple-candidate ambiguity test, rerun fake-only checks, and stop for bookkeeper
