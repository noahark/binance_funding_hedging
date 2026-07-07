# 00-task：2026-07-borrow-cost-coverage-v2

## 目标

修复 UI 大量负费率资产"日借币利率 = -"。根因两条（均有实盘证据）：
- ① next-hourly 单次 assets 硬上限 20（Gate B），服务发 50 → HTTP500 → 静默降级 tier② rate_history（仅 1 资产）。
- ② `borrow_check_max_calls=50` 把利率覆盖与 maxBorrowable 预算错误绑定（Gate A：66>50，截断 16）。

## 范围（单一原子交付物 H）

next-hourly 分批（batch_size=15）+ 预算解耦（rate_probe / borrowability_probe）+ `borrow_validation` 契约变更（`borrowability_not_probed`，截断保留利率）+ 下游收口（frontend 徽章 / self-check / contract 文档 / warning）+ 测试。

## 非目标

- per-asset tier synthesis / interestRateHistory 逐资产补源（根因B）→ defer `per-asset-cost-leg-v1`。
- maxBorrowable rotating queue、WebSocket、下单/借还/划转、bStock 负费率借币。

## 权威文档

设计 `10-design.md`（=DRAFT-4）；breakdown `12-development-breakdown.md`（=stage-plan §3）；证据 `gate-a-live.md` / `gate-b-endpoint-recon.md §9`。

## 红线

只读私有通道；零下单/借还/划转；Decimal 无 float；key 零片段；bStock 仍禁用；单一写者。
