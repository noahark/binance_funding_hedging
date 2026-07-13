# Final Deadline-Gate Repair Dispatch Prompt

你是本阶段原 implementation author（实现作者）`claude_glm` / GLM-5.2。继续同一阶段
分支，使用 `minimal_change_engineer`（最小改动工程师）skill，修复 bookkeeper 在 BK-6
验收时发现的最后一个 deadline race（截止时间竞态）。这不是 formal review（正式审查）
REWORK（返工），不改变 `rework_count`；不得调用其他模型或 subagent（子代理）。

先读取：`AGENTS.md`、active workflow（当前工作流）、stage `status.json` /
`70-handoff.md`、`00-task.md`、`10-design.md`、`12-development-breakdown.md`、
`20-implementation.md`、`22-pre-review-atomicity-repair.prompt.md`、以及
`agents/skills/minimal-change-engineer.md`。保留全部工作区改动。

## 发现 BK-7（HIGH）

`backend/services/snapshot_service.py:_handle_refresh_command()` 当前顺序为：

```text
post-assemble deadline check → _validate(snapshot) → history-cache commit → _publish_validated
```

这解决了 BK-6 的 validation failure（校验失败）原子性，但 `_validate(snapshot)` 本身可
消耗时间。若它在 deadline 前开始、在 deadline 后结束，代码仍会在超时后写 history cache
并发布新 `PublishedState`。这违反冻结 timeout（超时）契约：**任何 domain cache commit
（领域缓存提交）或 publication（发布）之前都必须重新确认
`time.monotonic() < cmd.deadline_monotonic`。**

## 严格允许文件

- `backend/services/snapshot_service.py`
- `backend/tests/test_symbol_snapshot_endpoint.py`
- `reports/agent-runs/2026-07-history-background-refresh-v1/20-implementation.md`
- `reports/agent-runs/2026-07-history-background-refresh-v1/60-test-output.txt`（只追加）

不得修改其它文件；不得提交、推送、合并、rebase（变基）、修改 `status.json` /
`70-handoff.md`，或启动模型分发。

## 精确验收

- selected-click（选中行点击）路径在 `_validate(snapshot)` **成功返回后**、写
  `_funding_history_cache` 和调用 `_publish_validated` 前，加最终 deadline gate（截止
  时间闸门）。若已到期：`timeout`，旧 state/cache/private inputs 全部保留，不发布。
- 保留 BK-6 顺序：validation failure 仍必须在任何缓存提交/发布前失败。
- 增加一个确定性无网络测试：用可控 monotonic clock（单调时钟）和一个包装/monkeypatch
  的 `_validate`，使 validation 在开始时未超时、成功返回时已经超时；断言
  `refresh_status="timeout"`、旧 `PublishedState` 同一引用、history cache 同一旧对象、
  `_last_private_inputs` 同一引用，且不真实等待 30 秒。
- 将 `20-implementation.md` 中“deadline 检查仍先于所有 domain commit / publish”的
  说明更新为真实顺序，并记录 BK-7 测试。

运行并追加完整原始输出：

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider
python3 -m pytest backend/tests/test_symbol_snapshot_endpoint.py -v
node frontend/self-check.js
git diff --check
```

报告末尾使用本机 `date` 添加 Harness footer（页脚）。完成后只回复修改文件、测试、
BLOCKED、session ID。

本地北京时间: 2026-07-13 09:25:33 CST
下一步模型: claude_glm / GLM-5.2
下一步任务: 在 validation 成功后、缓存提交/发布前补最终 deadline 闸门及确定性测试
