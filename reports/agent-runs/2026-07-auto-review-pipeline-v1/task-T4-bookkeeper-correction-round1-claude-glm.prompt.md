<!-- DISPATCH RECEIPT
status: pending
target: existing Claude-GLM / GLM-5.2 implementation session
executor: human
rework_charge: 0 (pre-review completion correction)
next_dispatch: none; return to Codex bookkeeper inspection
-->

# T4 bookkeeper correction round 1

继续当前 T4 实现会话。读取并严格执行：

1. `AGENTS.md`
2. `18-bookkeeper-inspection-T4.md`
3. 原始 `task-serial-v1-slimming-claude-glm.prompt.md`

不要读取 `history/`。不要 dispatch、commit、push、联网或修改
`status.json`、`70-handoff.md`、seal、review、verdict、history、产品路径。

## Required fixes

### C1 registry timeout fail-closed

- 删除生产运行期缺失/非法 timeout 时静默回退统一 1800 秒的行为。
- runner preflight 验证自动环实际使用的 adapter timeout：
  `claude_glm.timeout_seconds`、`kimi.timeout_seconds`、
  `grok.timeout_seconds`，以及 Grok review-1 的
  `optional_review_timeout_seconds`。
- 值必须是正整数且不能是 boolean；缺失、非法、零、负数都应在任何模型
  调用或 commit 前 fail closed。
- Grok `optional_review_command` 仍优先使用 900 秒 command override；其他
  调用使用 adapter timeout。
- 显式 test collaborator `timeout_override` 可以保留，但不得成为生产默认。
- 添加缺失、非法、零值 preflight negative tests，并保留 3000/1800/900
  正面测试。

### C2 runner task-only preflight

- runner 自身在 preflight 拒绝任何 `kind != task` 的 review unit。
- 拒绝发生在模型调用与 commit 之前，增加 focused negative test。
- 不依赖操作者先单独运行 `validate-stage.py` 才安全。

### C3 remove live tip event semantics

- 将活跃事件 `tip_once_grok_failure` 在 runner、workflow、validator、docs、
  tests 中一致重命名为 `review_1_fallback_exhausted` 或等价的纯串行名称。
- 保留相同的 fail-closed escalation 路线，不新增兼容别名或第二协议。
- 迁移/设计描述可以说明 tip/integration 已 deferred，但活跃状态机、运行期
  代码和当前测试名称不得再使用 tip-once 语义。

### C4 docs cleanup

- `docs/auto-review-pipeline.md` 的授权 supersession 规则删除 `adapters`：
  只保留 scope、budgets、expiry 等仍属授权的内容。
- 删除串行步骤中重复的 `2. implementer writes allowed paths`。

### Evidence

- 在 `20-implementation.md` append correction mapping，不改写原报告。
- 在 `60-test-output.txt` append 原始输出：完整 163+ suite、py_compile、
  checkpoint validator、diff check、正确的未提交工作树产品路径扫描、timeout
  missing/invalid tests、non-task runner rejection test、活跃
  `tip_once_grok_failure` residue scan（预期无运行期/规范匹配）。
- 工作树仍只能包含原 T4 writable set、两个 append evidence，以及由
  bookkeeper 创建的 inspection/correction/status/handoff 文件；不要修改后四类。

完成后只报告结果，不启动 Kimi。

本地北京时间: 2026-07-12 12:30:23 CST
下一步模型: Codex bookkeeper
下一步任务: 复验 C1-C4，完成 evidence commit 与 Kimi review-1 packet
