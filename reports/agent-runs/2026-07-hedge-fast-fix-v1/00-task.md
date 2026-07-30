# 00-task：2026-07-hedge-fast-fix-v1

## 模式

Human 口述/粘贴发现的**小问题**；本会话（Grok）按最小改动直接修复并回报。

不是大需求设计 stage。默认不扩 scope、不加抽象、不顺手重构。

## 范围（默认可改）

- 对冲开单持仓/任务 UI 展示（精度、文案、格式）
- 持仓聚合展示相关的前端格式化
- 仅当 Human 点名且明确授权时：后端 `open_basis_rate` 等小字段实算
- 对应自测（frontend self-check / 相关 pytest）

## 明确非目标

- 真实下单、改 Start 闸门、动凭据、改 live 任务 DB
- 自动平仓 / 补腿 / 借还币
- Harness 流程改造
- 大范围重构

## 风险分级（按条）

- **LOW_RISK**：纯展示/文案/前端格式，不改成交/仓位/金额语义 → 可单次独立终审或 Human 直接验收
- **HIGH_RISK**：触及成交均价语义、价差率公式、记账、闸门、订单路径 → 按 AGENTS §8 走 review-1 + review-2

## 工作约定

1. Human 报一条（或一小批）问题，可给复现步骤/截图描述。
2. 本会话最小修复 → 自测 → 说明改了什么、为何安全。
3. 默认不 commit；Human 要求时再提交。
4. 合 main / 部署 / 开 live 仍需 Human 明确授权。

## 已知待办线索（开场上下文，非本 stage 自动承诺）

- 持仓均价 UI `formatMockPrice` 全局 `toFixed(4)` 会抹小平价差可读性
- `open_basis_rate` 后端仍为占位 `"0"`，库内 quote/base 仍是完整精度
- 价差率应用完整均价计算；4 位应留给**百分比**展示，而非均价本身

以上条目仅在 Human 明确点名后才改。
