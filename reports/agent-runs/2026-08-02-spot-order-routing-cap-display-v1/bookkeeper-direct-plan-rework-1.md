# Bookkeeper direct plan rework — plan-rework-1

日期：2026-08-03

## Human 指令与处置

Human 明确决定跳过已准备但尚未启动的 Opus5 Planner 修订，要求 Codex 直接完成两项已定的
最小方案修正，并交由 DeepSeek 复审。`plan-rework-1.dispatch.md` 因此未执行，保留作审计记录。

本次仅修改 `docs/planning/spot-order-routing-v1.md`：

1. §3 现明确负费率/现货 `SELL` 不读取限制名单、不选 `regular_spot`，bStock 与名单命中仍
   保持 PAPI；正费率才读取名单。相应修正了 fail-closed 依赖范围与缓存条款的步骤引用。
2. §4 与 §8 列出受 `https://api.binance.com` 硬绑定的五条 exact allowlist 路径；§9 新增
   负费率路由和未登记路径被拒两条验收。

未修改代码、契约、schema、状态以外的运行配置、凭证或交易开关；未调用外部接口。
这属于 HIGH_RISK 计划评审的预实现修正，按 `AGENTS.md` §8 不增加 `rework_count`。
