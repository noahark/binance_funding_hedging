[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于
   claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出
   ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条
   执行记录都必须对应你本会话内真实发生的动作。
3. 你的依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的文件。

# Boundary C Canonical Breakdown — Targeted Consistency Amendment

你是用户明确选择的 development-breakdown author：Claude Opus 4.8。本轮不是
重新设计，也不是实现；只修正 canonical breakdown 内四处机械冲突。

## 必读

1. `AGENTS.md`
2. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/12-development-breakdown.md`
3. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/12-development-breakdown.bookkeeper-audit.md`
4. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/status.json` 中
   `tasks[0].id`
5. `reports/api-samples/2026-07-real-borrow-boundary-c-v1/20260720T150836Z/evidence-index.md`
6. 同一 evidence capture 的四份 `raw/*.md`
7. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/10-design.md`

## 唯一允许的写入

只修改：
`reports/agent-runs/2026-07-real-borrow-boundary-c-v1/12-development-breakdown.md`

不得修改代码、测试、schema、status、handoff、其他 stage artifact 或 canonical
docs；不得生成 implementation prompt；不得运行 live/authenticated Binance 请求。

## 必须完成的四项修正

1. §1 的 machine task id 改回 `C`；`boundary-c-live-borrow` 可以作为 name，
   不能替换 `status.json.tasks[0].id`。
2. §5.1 删除“empty known-rejection allowlist 仍是当前可交付选择”的句子。
   当前冻结集合只能是 `-51006/-51014/-51061`，其他 4xx 保持 `unknown`。
3. 重写 §8 的 closure/fallback 表述，使其与 evidence index 一致：
   - POST 参数/签名/body contract 与 POST weight 100 是已经满足的 hard
     preconditions，不是仍打开的 blocker；
   - PM IP budget 6000/min 是本次官方公开 capture 已验证事实，不是 inference；
   - cadence floor 2s 已冻结，不再称 interim；
   - 只有 `Retry-After` 表示、loan-history propagation SLA、per-asset
     precision/minimum、其他 limit-family accounting 等未被公开文档保证的内容
     保留 fail-closed/default 标签。
4. §5.3 删除“loan-record field names 尚未归档”的陈述。`txId`、`asset`、
   `principal`、`timestamp`、`status` 已验证；未验证的是 propagation SLA，
   dispatch-anchored window width 是本地保守策略，不是 Binance 保证。

保持其余内容、作者身份和架构冻结不变。完成后检查文档不再同时出现互斥答案，
并更新末尾 footer：Session ID 只能来自当前运行时证据；本地北京时间必须来自
本会话 `date` 命令；原始输出路径仍是 canonical breakdown 自身。

最终回复只报告修改路径、四项冲突均已消除以及任何 blocker。不要声称开始实现。

当前 Session ID: unavailable (current bookkeeper runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/development-breakdown-amendment.prompt.md
本地北京时间: 2026-07-21 07:05:16 CST
下一步模型: human operator → Claude Opus 4.8
下一步任务: apply the four mechanical corrections to canonical 12-development-breakdown.md; do not implement
