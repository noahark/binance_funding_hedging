# Task B Dispatch — Kimi（frontend，minimal_change_engineer）

（由 designer Fable5 预写的完整派工文案；controller 在 H_A 提交后原样发给
Kimi，不得删改技术约束。阶段 `2026-07-public-market-ui-cn-v1`，前置 Task A
已完成——warnings[1] 已是新文案。）

---

你是 Kimi（kimi-2.7），本任务角色 minimal_change_engineer。只做下面列出的
改动，不做任何其他"顺手优化"。

## 只允许写

- `frontend/**`（index.html、self-check.js、fixture/public-market-snapshot.json）
- `reports/agent-runs/2026-07-public-market-ui-cn-v1/20-implementation-frontend.md`（你的实现报告）

## 禁止

- `backend/**`、`schemas/**`、`docs/**`、`reports/api-samples/**`、
  `agents/**`、`workflows/**`、`scripts/**`
- 新增任何依赖、构建工具；页面保持单文件
- 任何直接调用 Binance；数据只来自同源 `/api/public-market/snapshot` 或
  本地 fixture
- 发明新的路由/分类逻辑（展示层只做映射）

## 改动 1：合并「资金费率/结算时间」列

删除现有第 4 列「最近更新的资金费率」与第 5 列「下一次结算时间 (北京)」，
替换为一列：

- 列头：`资金费率/结算时间`（title="本周期实时预估 / 北京时间"）
- 单元格：`{rate}% / {HH:mm}`，如 `+0.01% / 16:00`

### 费率格式化算法（逐条实现，禁止偏离）

输入是 API 十进制字符串（如 `"0.00010000"`）：

1. **字符串移位**：小数点右移 2 位。**禁止 `parseFloat(x)*100` /
   `Number(x)*100`**（浮点伪影 `0.0001*100 = 0.010000000000000002`）。
   按 `-?\d+\.?\d*` 拆符号/整数/小数，小数部分前 2 位并入整数（不足补 0）。
2. **裁尾零**：小数部分去尾部 `0`，剩空则去小数点。`0.0100`→`0.01`。
3. **符号**：正值加 `+`；负值保留 `-`；裁剪后为 0 时输出 `0%`（不得出现
   `-0%`/`+0%`）。
4. 空串/null/非数字 → `—`。

必测样例（写进 self-check.js）：

| 输入 | 输出 |
|---|---|
| `"0.00010000"` | `+0.01%` |
| `"-0.00005000"` | `-0.005%` |
| `"0.00000000"` | `0%` |
| `"-0.00000000"` | `0%` |
| `"0"` | `0%` |
| `"0.00008556"` | `+0.008556%` |
| `""` | `—` |

### 时间格式化

- `next_funding_time`（ms）→ 北京时间 `HH:mm`（Asia/Shanghai）
- `next_funding_time === 0` → `—`
- 单元格 title：`北京时间 YYYY-MM-DD HH:mm:ss 结算 · 原始费率 {原始字符串}
  · 预估值，结算时最终确定`

## 改动 2：提示标记（原「UI 标记」列）

列头改为 `提示标记`。映射：

| ui_flags 值 | 展示 |
|---|---|
| `MARGIN_PUBLIC_UNVERIFIED` | **不做行内 badge**（所有行恒真）。改为页面级说明一条：「杠杆可借性未经私有验证（当前为公开数据阶段）」，放数据说明区。 |
| `PERP_ONLY_NO_SPOT_LEG` | badge「无现货腿」（muted） |
| `TRADIFI_BSTOCK` | badge「bStock」（accent） |
| 未知值 | 原样 badge（muted），保证向前兼容 |

原始枚举值放 badge 的 title 属性。

## 改动 3：数据说明区（原 warnings 展示）

- 观感中性（信息样式，不得是红色报错观感），标题「数据说明」。
- 展示固定中文三条（与后端 warnings 数组一一对应）：
  1. 「杠杆交易对官方清单需 API key（当前无 key 阶段），杠杆可借性未经私有
     验证；候选判断使用公开现货 isMarginTradingAllowed 字段。」
  2. 「表中资金费率为本周期实时预估值，将于所示结算时间收取，结算前会漂移；
     已结算历史以 /fapi/v1/fundingRate 为准。」
  3. 「bStock（美股）合约的现货腿按 baseAsset+B+quoteAsset 别名连接（如
     TSLAUSDT → TSLABUSDT）；质押率动态未知，未做任何硬编码。」
- API 返回的英文原文放 `<details>` 折叠展示（可审计）。
- self-check 断言：中文条目数 === API warnings 数组长度。

## 改动 4：中文化清单

- `<title>` 与页头：`资金费率对冲工作台`；副标题「公开数据 · 只读」。
- 替换英文残留：Public Only→公开数据，Read-only→只读，
  Manual Refresh→手动刷新，Funding Hedge Workstation→资金费率对冲工作台。
- route badge 文案「PM 现货候选」→「杠杆现货候选」。
- 保留技术词：USDT、bStock、API、symbol 原文。
- 主表不得出现英文枚举直出；枚举原值一律进 title/tooltip。

## 改动 5：fixture 与 self-check 同步

- `fixture/public-market-snapshot.json`：warnings[1] 更新为后端 H_A 的新文案
  （从 `backend/domain/snapshot.py` 的 `CONTRACT_WARNINGS[1]` 原样复制）。
- `self-check.js`：新增上述格式化断言 + 数据说明条目数断言；既有断言全部
  保持通过。

## 完成后必跑

```bash
node frontend/self-check.js   # 全 PASS（含新增断言）
```

并在 `20-implementation-frontend.md` 记录：改动清单、格式化函数实现说明、
self-check 结果原文。

## 验收口径（review-1 将按此复核）

- 列合并后单元格与 tooltip 符合上述格式；7 个格式化样例全过。
- `MARGIN_PUBLIC_UNVERIFIED` 无逐行 badge；页面级说明存在。
- 数据说明区中性观感、三条中文、英文原文可折叠查看。
- 无英文枚举直出；英文残留清理完成。
- diff 仅触及 frontend/** 与你的报告文件；无新依赖；无直接 Binance 调用。
