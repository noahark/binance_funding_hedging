# Final Pre-Review Atomicity Repair Dispatch Prompt

你是本阶段原 implementation author（实现作者）`claude_glm` / GLM-5.2。继续同一阶段
分支，使用 `minimal_change_engineer`（最小改动工程师）skill，修复 bookkeeper 在 21 号
修复验收后的最后一个 cache/publication atomicity（缓存/发布原子性）缺口。这不是 formal
review（正式审查）REWORK（返工），不改变 `rework_count`；不得调用其他模型或 subagent
（子代理）。

先读取：`AGENTS.md`、active workflow（当前工作流）、本 stage 的 `status.json` /
`70-handoff.md`、`00-task.md`、`10-design.md`、`12-development-breakdown.md`、
`20-implementation.md`、`21-pre-review-repair.prompt.md`、以及
`agents/skills/minimal-change-engineer.md`。保留全部工作区改动。

## 发现 BK-6（HIGH）

`backend/services/snapshot_service.py:_handle_refresh_command()` 当前在 post-assemble
deadline gate（组装后截止时间闸门）通过后，先写 `_funding_history_cache[symbol]`，再调用
`_publish()`；而 `_publish()` 内部才执行 `jsonschema.validate()`。若 schema validation
（模式校验）失败，旧 `PublishedState` 保留，但新的 domain cache（领域缓存）已经提交。
这违反冻结契约：组装/校验均在未发布局部变量完成；任何 assembly/validation failure（组装/
校验失败）都不得提交本次 history cache、`_last_private_inputs` 或 `PublishedState`。

## 严格允许文件

- `backend/services/snapshot_service.py`
- `backend/tests/test_symbol_snapshot_endpoint.py`
- `reports/agent-runs/2026-07-history-background-refresh-v1/20-implementation.md`
- `reports/agent-runs/2026-07-history-background-refresh-v1/60-test-output.txt`（只追加）

不得改其它文件；不得提交、推送、合并、rebase（变基）、修改 `status.json` / `70-handoff.md`
或启动模型分发。

## 精确验收

- 把 schema validation 移到 history-cache commit（历史缓存提交）和 `PublishedState`
  replacement（替换）之前，且保持 deadline 检查在所有 domain commit / publish 之前。
- 不要依靠“当前 `_assemble` 理应产生有效 schema”来省略这条保证；代码必须在 validation
  failure 时明确保留旧 state、旧 history cache、旧 `_last_private_inputs`。
- 避免双重昂贵校验或重新引入 deadline race（截止时间竞态）。若需要重构 `_publish` 为
  “已验证发布”私有 helper（辅助函数），保持变更局部、命名清晰、scheduled tick（定时刷新）
  同样先验证后发布。
- 新增一个确定性无网络测试：让 selected click 的 schema validation 在发布前失败，断言
  `refresh_status="timeout"`、`_published_state` 同一引用、`_funding_history_cache[symbol]`
  同一旧对象、`_last_private_inputs` 未变。测试不得真实等待 30 秒。

运行并追加完整原始输出：

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider
python3 -m pytest backend/tests/test_symbol_snapshot_endpoint.py -v
node frontend/self-check.js
git diff --check
```

在 `20-implementation.md` 的 Pre-review repair（审查前修复）章节增加 BK-6 映射、测试
结果与零 residual（剩余风险）声明。报告末尾用本机 `date` 添加 Harness footer（页脚）。
完成后只回复修改文件、测试、BLOCKED、session ID。

本地北京时间: 2026-07-13 09:10:33 CST
下一步模型: claude_glm / GLM-5.2
下一步任务: 最小修复 schema-validation failure 时的 history-cache 原子性
