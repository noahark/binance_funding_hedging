# Design: 2026-07-public-market-ui-cn-v1

Author: Fable5 (anthropic/claude-fable-5), designer/breakdown author.
细则以本文件为准；边界与验收以 `00-task.md` 为准。

## 1. 「资金费率/结算时间」列（Task B 核心）

替换现第 4 列「最近更新的资金费率」与第 5 列「下一次结算时间 (北京)」。

**列头**：`资金费率/结算时间`（可加 title="本周期实时预估 / 北京时间"）。

**单元格内容**：`{rate}% / {HH:mm}`，如 `+0.01% / 16:00`。

### 费率格式化算法（必须逐条实现，self-check 断言）

输入是 API 的十进制字符串（如 `"0.00010000"`、`"-0.00005000"`），输出百分比：

1. **字符串移位**：小数点右移 2 位得到百分数字符串。禁止
   `parseFloat(x) * 100` / `Number(x) * 100`（浮点伪影：`0.0001*100 =
   0.010000000000000002`）。实现建议：按 `-?\d+\.?\d*` 拆符号/整数/小数，
   小数部分前 2 位并入整数部分（不足补 0）。
2. **裁尾零**：小数部分去尾部 `0`，若剩空则去掉小数点。`0.0100`→`0.01`，
   `0.0050`→`0.005`。
3. **符号**：正值加 `+` 前缀；负值保留 `-`；**归一负零**：裁剪后数值为 0
   时输出 `0%`（不得出现 `-0%`、`+0%`）。
4. 缺失/异常输入（空串、非数字）→ `—`。后端缺 premium 时默认 `"0"`，正常
   走规则 3 输出 `0%`。

样例表（self-check 用例最小集）：

| 输入 | 输出 |
|---|---|
| `"0.00010000"` | `+0.01%` |
| `"-0.00005000"` | `-0.005%` |
| `"0.00000000"` | `0%` |
| `"-0.00000000"` | `0%` |
| `"0"` | `0%` |
| `"0.00008556"` | `+0.008556%` |
| `""` / `null` | `—` |

### 时间格式化

- `next_funding_time`（ms）→ 北京时间 `HH:mm`（`Asia/Shanghai`）。
- `next_funding_time === 0`（缺失）→ `—`（整格显示 `{rate}% / —`）。
- tooltip（`title` 属性）：`北京时间 YYYY-MM-DD HH:mm:ss 结算 · 原始费率
  {raw} · 预估值，结算时最终确定`。

## 2. 提示标记（原「UI 标记」列）

| ui_flags 值 | 展示 |
|---|---|
| `MARGIN_PUBLIC_UNVERIFIED` | **不做行内 badge**（全行恒真）。页面级说明一条：「杠杆可借性未经私有验证（当前为公开数据阶段）」，放数据说明区或摘要区。 |
| `PERP_ONLY_NO_SPOT_LEG` | badge「无现货腿」（muted） |
| `TRADIFI_BSTOCK` | badge「bStock」（accent） |
| 未知值（向前兼容） | 原样 badge，muted |

列头改「提示标记」。原始枚举值放 badge 的 title。

## 3. 数据说明区（原 warnings 展示）

- 观感中性（信息样式，非红色报错），标题「数据说明」。
- 固定中文文案三条（与后端 warnings 数组一一对应；Task A 的 warnings[1]
  新文案确定后按其翻译）：
  1. 「杠杆交易对官方清单需 API key（Phase 1 无 key），杠杆可借性未经私有
     验证；候选判断使用公开现货 isMarginTradingAllowed 字段。」
  2. 「表中资金费率为本周期实时预估值，将于所示结算时间收取，结算前会漂移；
     已结算历史以 /fapi/v1/fundingRate 为准。」
  3. 「bStock（美股）合约的现货腿按 baseAsset+B+quoteAsset 别名连接（如
     TSLAUSDT → TSLABUSDT）；质押率动态未知，未做任何硬编码。」
- 英文原文（API warnings 原值）放 `<details>` 折叠展示，保持可审计。
- 中英文对应关系加 self-check 断言（数组长度一致即可，不逐字比对）。

## 4. 中文化清单（Task B）

- `<title>`：`资金费率对冲工作台`；页头同名，副标题可留「公开数据 · 只读」。
- 英文残留替换：Public Only→「公开数据」，Read-only→「只读」，
  Manual Refresh→「手动刷新」，Funding Hedge Workstation→「资金费率对冲
  工作台」。
- 「PM 现货候选」→「杠杆现货候选」（route badge 文案统一）。
- 保留技术词：USDT、bStock、API、HTTP 状态码、symbol 原文。
- 枚举原值一律进 title/tooltip，不在主表直出。

## 5. Task A 措辞（合约层，英文）

`CONTRACT_WARNINGS[1]` 与合约文档段落的精确文本见 `00-task.md` Task A 节。
证据：`reports/api-samples/2026-07-public-market-ui-cn-v1/20260704T044945Z/`
（evidence-index.md + verify-funding-semantics.py PASS：周期中段
ETHUSDT/SOLUSDT 预估值 ≠ 已结算值；15 分钟内可观察漂移）。

语义要点（措辞不得偏离）：
- 是「本周期实时预估值」，于 `nextFundingTime` 结算收取；
- 结算前会漂移，**不是**已锁定的下次收取值，也**不是**已结算历史；
- 已结算历史唯一来源是 `/fapi/v1/fundingRate`；
- 不得把预估值展示为已结算/已确定值。

本地北京时间: 2026-07-04 12:55 CST
