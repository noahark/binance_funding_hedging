# Bookkeeper verification — plan-review-1

日期：2026-08-02

## 结论

收到并封存 DeepSeek 的原始只读评审回执：
`evidence/plan-review-1.deepseek.raw.md`。回执结构完整，正式结论为
`REWORK（返工）`；其两项失败均标为 `in-range`，因此不能进入实现。

Bookkeeper 复核结论：两项发现均成立。

1. `backend/hedge_open_tasks/domain.py:625-646` 明确规定正向为现货 `BUY`、反向为现货
   `SELL`；而方案 §3 第 4 步无方向条件地可选择 `regular_spot`。这与方案 §1.2 禁止
   普通现货 `SELL` 的边界相冲突。
2. `backend/services/hedge_open_live_client.py:53-65` 的 deny-by-default `ALLOWLIST` 目前
   只登记 PAPI 路径。方案若按原文增加 `restricted-asset` 和普通现货端点，将被该 client
   拒绝，或迫使实现绕开该安全边界。

两项 Human 裁定均已作为本阶段正式输入记录在
`docs/planning/2026-08-02-decisions-routing-and-cap-display.md` 的 Bookkeeper 补充裁定中。
计划评审的返工属于预实现 packet 修正，按 `AGENTS.md` §8 不增加 `rework_count`；本阶段
仍为 `0`。基线经 `git rev-parse HEAD` 复核为
`1a55781a5f80ee5b3e15d7124003af2dda73f0d5`，未产生交付 SHA、未调用凭证或交易端点。
