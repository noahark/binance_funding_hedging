# Symbol Mismatch Analysis — 期现命名差异与对冲匹配

诊断脚本：`scripts/check_symbol_mismatch.py`（拉币安公共 exchangeInfo，随时可重跑
获取最新数据：`python scripts/check_symbol_mismatch.py [--quote USDT] [--json]`）。
本文件是问题记录 + 修复方向，**尚未实现**（未来工作项，独立于 hedge-open stage）。

## 问题
币安 USDⓈ-M 永续合约的部分交易对命名与现货市场不完全一致，系统在匹配现货对冲腿
时失败，把本可对冲的合约错误归类为 **PERP_ONLY（仅合约）**，从而漏掉套利机会。

## 两类命名差异

### 1. 数字倍率前缀（1000x）— **未修复**
- 合约 `baseAsset` 带 `1000` 前缀，现货不带。例：合约 `1000PEPEUSDT` ↔ 现货
  `PEPEUSDT`。
- 语义：`1000PEPE` 合约的 1 个下单单位代表 **1000 个 PEPE**（合约面值放大 1000 倍）。
- 已知 6 个此类合约：**BONK、FLOKI、LUNC、PEPE、SHIB、XEC**（`1000<BASE>USDT`）。
- 现状：`backend/domain/normalize.py` 未做前缀剥离，这 6 个被标为无法对冲，实际都有
  可交易的现货腿。

### 2. bStock B 后缀 — **已处理**
- 美股/ETF 类（`contractType == TRADIFI_PERPETUAL`）的现货 symbol 在 `baseAsset`
  后多一个字母 `B`。例：合约 `TSLAUSDT` ↔ 现货 `TSLABUSDT`。
- 现状：已在 `backend/domain/normalize.py` 的 `bstock_b_suffix_alias` 处理，覆盖
  约 36 个美股衍生品合约。

## 影响
第 1 类的 6 个合约在当前系统被误标 PERP_ONLY → 漏对冲机会。且对冲存在**数量换算**：
1 个 `1000PEPE` 合约单位 ↔ 1000 个现货 PEPE。**若忽略这个 1000 倍比例，两腿名义
不等 → 仓位错配**（与 hedge-open 的"共同网格取整/双腿等量"直接冲突，见
`reports/agent-runs/2026-07-hedge-open-live-v1/11-adr.md` ADR-2）。

## 修复方向（建议，未实现）
在 `backend/domain/normalize.py` 的 **exact 匹配与 bstock 之间**补一段数字倍率前缀
剥离：
- 识别 `^(1000+)<BASE>` 形式的合约 baseAsset，剥离数字前缀得到现货 baseAsset，
  匹配现货腿。
- 记录该合约的**倍率 `multiplier`（如 1000）**，供对冲数量换算使用。

**数量换算方向（实现时必须明确，避免仓位错配）：**
- 物理关系：`现货数量(个) = 合约下单单位数 × multiplier`（1 个 1000PEPE 单位 =
  1000 个 PEPE）。
- 用户问题说明写作"合约数量 × 1000 = 现货数量"；修复建议里写作"合约数量 ÷ 1000
  才是现货数量" —— 两处方向相反，**取决于系统内 quantity 字段的单位约定**（存的是
  "合约下单单位数"还是"展开后的 base 数量"）。实现时先钉死 quantity 字段单位，再
  确定乘/除方向，并加双向测试（用真实的 1000PEPE 合约面值样本验证），因为算错直接
  导致对冲两腿名义不等。

## 数据来源
`scripts/check_symbol_mismatch.py`（诊断，公共只读 API）。分类：1000/10000/100000
前缀、bStock B 后缀、PERP_ONLY、其他命名不一致。
