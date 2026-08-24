# Hyperliquid 费率对比行 v1 — Review-1 dispatch（grok）

## Identity

- task_id: `hyperliquid-funding-compare-review-1-grok`
- target_role: `Reviewer / Review-1`
- target_model: `grok`
- provider: `xai`
- status_revision: `6`
- required_skill: `agents/skills/code-reviewer.md`

## Goal

代码评审——实现是否以最小、安全、可恢复的方式落实 rev3 设计。**HIGH_RISK 独立只读评审。**

## 固定范围与 SHA

- base_sha：`25cc8fe4e31194261dd48415f085bc6f9fda062d`
- **delivery_sha：`6922bcebb4f18ba824125c46774fc5ad22bab806`**（`status.json.delivery_sha` 同值）
- 实现前控制点：`dc76e0c`
- **固定实现 diff**：`git diff dc76e0c..6922bcebb4f18ba824125c46774fc5ad22bab806`
- 分支：`2026-08-23-hyperliquid-funding-compare-v1`

**范围外**（针对它们的发现记为范围外）：

- `reports/agent-runs/.../status.json`（控制文件）
- `reports/agent-runs/.../evidence/hyperliquid-funding-compare-impl-claude-glm.handoff.md`（实现者自述，可作参考但不是受审代码）
- 任何在 delivery_sha **之后**的控制提交。`HEAD` 前移是预期的，一律以固定 delivery_sha 为准。

## 设计权威

`docs/planning/hyperliquid-funding-compare-v1.md` **rev3**，固定于
`fe91abb69e236e9ef110ca354b8773dfcb042773`，已过三轮 Codex 独立设计评审 `ACCEPT`，
Human 已确认全部决策点 D1–D8。**实现必须落实该设计，不多不少。**

评审设计本身的意见记为范围外——设计已定案。本轮只判断实现是否忠实、安全、可恢复。

## 隔离披露

- 实现作者：claude_glm / 智谱（provider `zhipu`）。
- 设计作者：Opus 5 / Anthropic。三轮设计评审：Codex / OpenAI。
- 本 Reviewer：grok / xai。与实现作者跨 provider，隔离成立。
- **Review-1（grok）与 Review-2（kimi）本轮并行执行**，互不知悉对方结论，独立出具 verdict。

## 必查项

**M1 失败语义（设计 §6.1，D6）**：main+xyz 原子组——任一 POST 失败 / shape 非法 /
任一 `funding` 无法转 Decimal → 整源失败、全行 `null`、`hyperliquid_data_time` 为 `null`、
**不投影 warm last-good**、币安四列首行照常显示、不阻断快照发布。
现有 Group A/B 是 success-only cache（`_refresh_due_sources` 原文 "Timestamps advance only
on success"），请确认实现没有让 HL 复用该语义而静默展示旧值。

**M2 匹配 fail-closed（设计 §3）**：DENY 先于 raw name → `isDelisted` 过滤 → exact →
**类别校验**（main 只配 `PERPETUAL`、xyz 只配 `TRADIFI_PERPETUAL`）。
请确认顺序正确且无绕过路径。注意：类别校验只承诺拦**跨类别**撞名，同类别同名不受保护。

**M3 IC-1 schema**：顶层 `additionalProperties: false`。`hyperliquid_data_time` 必须注册进
`properties` 但**不得**进顶层 `required`；行内 `hyperliquid` block 同理。
请确认既有 offline fixture 未被打挂。

**M4 IC-2 前端标红**：`isStaleTime(NaN)` 返回 **false**，所以"取不到"只调该函数**不会红**——
请确认实现显式把 unavailable 纳入了 `.stale-time` 条件。另确认红色**只作用于 HL 片段**，
没有把同一 meta 行里仍新鲜的币安时间一起染红。

**M5 零回归**：币安侧四列数值与本 stage 前**逐格不变**；`funding_interval_hours` 驱动的
折算未被改动（122 个 4h / 136 个 8h 各自正确，未统一成 8h）。

**M6 边界**：未触碰下单 / 保证金 / 借币 / 平仓路径；未改 `SPOT_SYMBOL_MAP` 现有条目；
未把 HL 加进「更新缓存」按钮的强制刷新集合；未给前端加直连或按需拉取。

**M7 验收真实性**：设计 §9 的 18 条（A1–A16 + A9b + A9c）是否**真的**被测试覆盖，
还是存在假绿（断言恒真、oracle 不唯一、mock 掉了被测逻辑）。
提醒：rev2 曾因"断言 warnings 非空"被判假绿——`CONTRACT_WARNINGS` 使该数组永远非空。
请用同样的怀疑审视新测试。

## 已知基线问题（不是本次引入，不必重复报告）

`backend/tests/test_private_client.py::test_urlopen_only_in_designated_http_clients` 失败，
原因是 `backend/services/public_ip_service.py` 调 `urlopen` 但未登记白名单。
Bookkeeper 已独立验证该失败在基线 `dd12833` 即存在，将记入后续项。
本次交付**新增**的 `hyperliquid_public.py` 已正确登记。

## 复现命令

```bash
.venv/bin/python -m pytest backend/tests/test_hyperliquid_compare.py -q   # 期望 22 passed
.venv/bin/python -m pytest backend/tests/ -q                              # 期望 2023 passed, 1 failed(基线)
node frontend/self-check.js                                               # 期望全部通过
```

Bookkeeper 已复现全部三条，结果与实现者自述一致。

## Allowed Files

Reviewer 完全只读，除下面唯一 create-only handoff 外零写入：

- **唯一允许新建**：
  `reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-review-1-grok.handoff.md`
- 该路径开始前不存在（Bookkeeper 预检 2026-08-23 CST：ABSENT）。
- 不得修改任何源码、测试、设计稿、`status.json`、`ACTIVE.json`、他人 handoff。
- **不得**运行会启停服务、下单、访问私有 API 或使用凭证的命令。上述复现命令为只读。

## Verdict

`ACCEPT` / `REJECT`，逐条对应 M1–M7。若 `REJECT`，给出最小修正建议，不扩大范围。

## Stop Point

写完 handoff 即停。不实现、不修复、不推进 stage 状态、不合并、不部署。

reply_to: claude
After emitting the normal console receipt, send that same receipt once to the
reply_to window per this file, then stop.
