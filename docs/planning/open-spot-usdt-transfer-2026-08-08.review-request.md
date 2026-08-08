# 开仓 regular_spot 自动划转 USDT（v2.1，待 Review）

- **日期**：2026-08-08
- **状态**：待 Code Review
- **演变**：v1（dispatch 预划转+回流+豁免+缓冲进preflight）REWORK 5🔴 → v2（create_task 划转+不回流）REWORK 2🔴（建卡未备款仍下单裸空 / 划转无恢复链无幂等）→ **v2.1**：裸空防护靠 **dispatch 核验**（非 create 拒绝）；幂等/恢复链按 Human 决断不做。
- **实现**：`domain.py` / `service.py` / `frontend/index.html` / 3 个测试文件
- **实盘验证**：✅ 已通过（2026-08-08 TSTUSDT：划转 15.77 USDT → 启动后现货买 1000 + 合约空 1000 两腿成交 → done）

---

## 摘要

所有 USDT 放统一账户。`open+forward+regular_spot` 建仓时 `create_task` 内从统一账户一次性划转 `truncate(q×N×price×1.03)` USDT 到现货；失败不建卡 + 前端弹窗。preflight 对 regular_spot forward 放行。**dispatch 下单前核验：fresh 走 regular_spot 时建卡固化的 frozen route 必须也是 regular_spot（即已备款），否则暂停防裸空**。开完不回流，人工收尾。

## ⚠️ Human 已决断（请勿再作为缺陷/阻塞项提出）

以下均为 Human 明确拍板的权衡，review 时**不要**再当问题决策：

1. **不查统一账户余额**：下单时前端已校验、人工开单也验证金额；后端不做划转前的统一账户预查（划转本身的交易所拒绝即资金核验）。
2. **不做幂等 / 不落 tranId / 不做 funding intent 恢复链**：重复划转（网络超时二义性、前端连点）、划转成功后落库失败的孤儿，均不做系统级防重或可恢复记录，由 **Human 收尾核对**。
3. **不自动回流**：开仓完成后普通现货账户的残余 USDT（3% 缓冲 + 成交零头）不自动划回统一账户，Human 定期手动收尾。
4. **本轮不做前端防重**（连点多次建卡 → 多次划转）：后续前端实现。
5. **接受 1.03 缓冲外的极端波动单腿敞口**：MARKET+quantity 现货单固有，1.03 只覆盖常见波动，极端行情的现货拒单/合约成交风险由 Human 接受为市场风险。

> 裸空防护不靠"建卡时拒绝 snapshot None"，而是靠下面 dispatch 核验——因为"snapshot None 建卡 + dispatch 仍读不到 → 暂停"本身是安全行为，不该被 create 拒绝破坏。

## 改动文件

| 文件 | 改动 |
|---|---|
| `domain.py` | `OPEN_SPOT_BUFFER=1.03` + `truncate_usdt`；`compute_preflight` forward regular_spot **放行**，papi 校验不变、不加缓冲；`PAUSE_REASON_SPOT_ROUTE_CHANGED` + `SIGNAL_SPOT_ROUTE_CHANGED` |
| `service.py` | `create_task` 内划转（失败 `HedgeError` 弹窗、不建卡）；**dispatch 下单前备款/路由核验**（fresh=regular_spot 且 frozen≠regular_spot → 暂停）；worker round 接 `SIGNAL_SPOT_ROUTE_CHANGED` |
| `frontend/index.html` | `open_spot_transfer_failed` 弹窗 |
| 3 个测试 | create_task 划转三例 + dispatch 核验两例 + preflight 放行；2 个旧测试更新 |

## 核心机制

### create_task 划转（service.py）
preflight 后、落库前：`open+forward+regular_spot` → `universal_transfer("PORTFOLIO_MARGIN_MAIN", "USDT", truncate(q×N×price×1.03))`，不预查统一账户。失败 → `HedgeError(400, "open_spot_transfer_failed")` → 前端弹窗、不建卡。`snapshot is None`/dry-run 跳过划转（snapshot None 仍允许建卡，靠 dispatch 核验防裸空）。

### preflight 放行（domain.py）
`compute_preflight` forward：regular_spot → `balance_ok=True`（放行，不校验），`available` 填统一账户 USDT 展示；papi 保留校验；**不加缓冲**。reverse 不变。

### dispatch 备款/路由核验（service.py）—— 裸空防护
`_dispatch_one_for_task` 的 fresh preflight 后：open 任务若 `fresh spot_route==regular_spot 且 frozen spot_route≠regular_spot` → 暂停不发单（`SIGNAL_SPOT_ROUTE_CHANGED`）。frozen 来自建卡固化的 `task.preflight_snapshot`。
- 路由变化（建卡 PAPI → 下单 regular_spot）：frozen=papi → 暂停；
- 场景1（建卡 snapshot None 未备款 → 下单恢复 regular_spot）：frozen=None → 暂停；
- 已备款（frozen=regular_spot）/ papi 下单 / 多腿后续腿 → 不拦。

这一条使 `frozen=regular_spot` 成为"建卡时已划转备款"的间接证据——**无需持久化 tranId 即可判断备款**。

## 审查重点（请重点看）

1. **dispatch 核验的覆盖与误伤**：确认 `fresh==regular_spot and frozen!=regular_spot → 暂停` 覆盖了所有"未备款却走 regular_spot 下单"的入口（路由变化、snapshot None 建卡恢复），且不误伤已备款任务 / papi 下单 / 多腿后续腿。
2. **snapshot None 建卡仍允许**：有意为之（snapshot None 建卡 + dispatch 仍读不到 → preflight_incomplete 暂停，是安全行为）。裸空防护完全靠 dispatch 核验，不靠 create 拒绝。确认这条链路。
3. **划转 fail-closed**：划转失败不建卡（确认）。

## 测试

`test_hedge_*.py` 574 passed。create_task 划转（成功 / 失败弹窗 / papi 跳过）；dispatch 核验（路由变化暂停 / 未备款场景1暂停）；preflight 放行。dry-run 无法覆盖真实划转，靠实盘。

## 实盘验证记录（2026-08-08，已通过）

TSTUSDT forward open（target_n=1, single=1000, spot_route=regular_spot, est_price=0.01531）：
- [x] `create_task` 划转 `need=truncate(1000×1×0.01531×1.03)=15.77 USDT` 到现货（stderr `open_spot_transfer ok`）✓
- [x] 启动后两腿成交：spot 买 1000（花 14.96 USDT）+ perp 空 1000（0.01488），status=done ✓
- [x] 残余 ~0.81 USDT 留现货账户（人工收尾，符合预期）✓
- [ ] 统一账户不足弹窗 / papi 不划转 / 路由变化暂停：未自然触发（单测覆盖）

## 实盘验证清单（其他标的/场景，上实盘前）

- [ ] 统一账户不足：不建卡 + 前端弹窗（open_spot_transfer_failed）
- [ ] papi 开仓：不划转
- [ ] 建卡后路由/snapshot 变化导致下单需走 regular_spot 但未备款：暂停不发单
