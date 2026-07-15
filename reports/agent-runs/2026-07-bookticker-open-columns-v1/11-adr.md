# Stage ADR

## Status

`ACCEPTED FOR IMPLEMENTATION — Claude READY; Grok REVISE findings reconciled without changing frozen product semantics`

## Context

默认机会表目前只展示 mark/index price，不能表达按一档盘口实际进入“多现货/空合约”或“空现货/多合约”时的跨市场价差。同时，表内“提示标记”“资产标签”“负费率状态”和净收益子行存在重复信息。

本 stage 必须在现有只读 snapshot architecture 内解决该问题，并满足四个约束：

1. Binance bookTicker 是两个独立 REST 响应，不能声称交易所级原子快照。
2. 价差直接影响人工开单判断，不能把一端新缓存与另一端旧缓存静默混算。
3. 现有 frozen `public-market-snapshot/v1` fixtures 必须继续通过 schema。
4. bStock 的 spot leg symbol 可能与 futures symbol 不同，连接必须沿用既有 alias resolution。

事实证据来自 `reports/api-samples/2026-07-bookticker-discovery-v1/20260715T0651Z/`：现货/合约 full payload 均为公开无 key；futures `symbols=` probe 实际返回 full universe；spot payload 存在大量零盘口；价格均以 decimal string 表达。

用户在设计评审完成后又明确授权本 stage 集成 Harness Session ID 回执，
让随后的实现与审查立即输出可定位的会话元数据。该范围扩展不进入产品
runtime，也不赋予模型跨 provider 读取会话的能力。

## Decision

### ADR-1：本地配对原子缓存

把两次 full bookTicker 请求组合为一个 `book_ticker_pair` business source。只有两个请求和 map 校验都成功后才一次性推进 cache timestamp。两端不能独立替换可发布 pair。

该 source 复用 Group A `cache_ttl_seconds`（默认 60 秒），不阻塞冷启动快照；last-good 最多作为可用值保留两个刷新周期，age `>= 2*ttl` 时行契约进入 `stale` 并清空可用报价/价差。

### ADR-2：后端域层计算可执行一档百分比

Domain 使用 resolved leg symbols 连接四个价格，按用户冻结公式计算：

- forward：`(futures_bid - spot_ask) / spot_ask * 100`
- reverse：`(spot_bid - futures_ask) / futures_ask * 100`

使用 `Decimal`、`ROUND_HALF_UP`、两位 percentage points；frontend 不重复业务计算。

### ADR-3：行级 additive `opening_quotes`

在 row schema 增加可选 `opening_quotes` object；当前 producer 总是输出完整 object，legacy fixture 可缺失。对象封装 status、pair completion time、四个价格和两个已计算百分比。保持 wire version `v1`，不借机做 route/version cleanup。

### ADR-4：仅合并 presentation，不合并领域字段

Frontend 删除“提示标记”列并把借贷状态/资产标签上下合并，但 backend `ui_flags`、`asset_tag`、`negative_funding_status` 继续独立。max-borrowable 展示归入合并单元格，日净收益单元格只保留收益、借币成本和来源。

### ADR-5：Session ID 采用双层执行回执，不作为验收事实替代品

每个模型输出 footer 显示 provider-native Session ID、来源和 raw output
路径；runner/bookkeeper 将已验证值写入 `status.json.session_receipts`。模型
看不到运行时 ID 时必须写 `unavailable (reason)`，不得按最新 mtime 猜测。

各 provider 的查找与交叉验证顺序集中在 `docs/model-adapters.md`。Session
ID 只作人工恢复/定位：不同 provider 不能凭 ID 直接读取对方 transcript，
formal review 仍必须读取 stage 内 raw artifacts 和 committed diff。

## Alternatives Considered

### 每行或 watchlist 逐 symbol REST

- Why rejected：futures endpoint 不支持有效 multi-symbol batch；逐 symbol 增加 weight、延迟与行循环 HTTP，违反现有 fetch-once/map/join 约束。

### 现货与合约各自独立 source cache

- Benefit：一侧成功即可更新，数据局部更新更快。
- Why rejected：价差是跨市场派生值，独立提交会静默组合不同 refresh round；必须额外引入 timestamp skew policy。对 60 秒人工参考表而言，本地 pair atomic 更简单且更安全。

### 在 frontend 用 JavaScript `Number` 计算

- Benefit：backend contract 字段更少。
- Why rejected：复制价格方向语义，产生 decimal/rounding 第二实现，并增加百分比单位乘错 100 的风险。现有 backend 已把 funding/net 领域数学集中在 `Decimal`。

### 把 bid/ask 直接塞进 `futures` 和 `spot`

- Benefit：更接近上游字段结构。
- Why rejected：UI 仍需另找 freshness/status/derived spreads；`opening_quotes` 能把同一人工判断所需的数据和失效语义绑定在一个边界内，且 selected-symbol row 自动复用。

### 失败时无限展示 last-good 并加“旧”标签

- Benefit：页面永远有数。
- Why rejected：列名是“开单”，无限陈旧数据的误导成本高于空值。两个周期后必须停止作为可用值。

### bookTicker 失败阻塞整个 snapshot publication

- Benefit：所有发布快照始终带完整报价。
- Why rejected：开单报价是 additive read-only enrichment；不能让新公开 endpoint 降低现有 funding/history/account 工作台可用性。使用 `unavailable/stale` 明确降级。

### Wire version bump 或 API route rename

- Benefit：可以清理历史 public/private 混合命名。
- Why rejected：超出本 stage；已有 additive compatibility precedent，用户也未授权 API cleanup。

### 使用 WebSocket

- Benefit：更接近可执行盘口，降低跨市场时间差。
- Why rejected：本 stage 明确是 60 秒 REST 参考层；WebSocket lifecycle、重连、序列和 depth 属于后续人工开单 hardening。

## Tradeoffs

- Tradeoff：pair atomic 会在单边故障时放弃另一边的成功响应。
  - Benefit：不会产生跨刷新轮次的伪价差。
  - Cost：单边故障期间报价整体更旧，最终变成 stale；weight 很低，因此下个 tick 重试双方可接受。

- Tradeoff：每行重复 `updated_at` 和 quote status。
  - Benefit：full snapshot 与 selected-symbol payload 都自包含，不需要新增顶层 metadata contract。
  - Cost：JSON 有少量重复；对本地几百行表可忽略。

- Tradeoff：schema field optional，但当前 producer 保证 presence。
  - Benefit：旧 fixtures 和旧消费者继续兼容。
  - Cost：frontend 必须继续处理字段整体缺失，schema 单独不能证明 current producer presence，需 deterministic tests 补足。

- Tradeoff：百分数字段已乘 100。
  - Benefit：frontend 只需显示固定两位，无浮点业务运算。
  - Cost：与现有 fractional funding-rate 字段单位不同；必须通过 `_pct` 命名、description 和测试防止二次乘 100。

- Tradeoff：两个 REST 请求顺序执行。
  - Benefit：实现小、复用现有 urllib client，无线程/async 生命周期。
  - Cost：两端响应存在网络时间差；UI 必须明确“参考报价，非成交保证”。

## Edge Cases Or Constraints

- Spot full payload 中零 bid/ask 很多；`0` 是 incomplete，不是合法 denominator。
- `incomplete` 是行级状态，不要求两个方向一起为空；每个方向只由自身两条 operand 决定是否可计算。
- Futures 有 dated/other quote symbols；只按现有 eligible rows 与 exact futures symbol join，不创建新 universe。
- bStock 使用 `spot.symbol` 的 B-suffix alias；不得用 futures symbol 查 spot map。
- METAL 没有 exact spot leg 时保持 incomplete；不得用 PAXG 等经济近似资产替代。
- pair payload wrong top-level shape、空 list、归一化空 map均不推进 timestamp。
- source fetch failure 不得影响 premium/history/private source 的独立 retry timestamp。
- stale cutoff 采用 monotonic age，wire `updated_at` 只用于人类可读 freshness，不用于 due 判断。
- selected-symbol click 不强制 bookTicker single-symbol refresh。
- `opening_quotes` 缺失的旧后端必须继续可渲染；unknown nested property 必须被 schema 拒绝。
- 最终表仍为 12 列，但 opening cells 可能更宽；使用现有横向滚动，不重做响应式布局。

## Links To Prior Direction

- User-approved intake: `reports/agent-runs/2026-07-bookticker-open-columns-v1/00-intake.md`
- Direction synthesis: skipped under user-approved lightweight `MEDIUM` route
- Product: `docs/product/PRD.md`
- Architecture: `docs/architecture/ARCHITECTURE.md`
- Development guide: `docs/development/DEVELOPMENT_GUIDE.md`
- Raw sample index: `reports/api-samples/2026-07-bookticker-discovery-v1/20260715T0651Z/evidence-index.md`
- Capture feasibility: `reports/api-samples/2026-07-bookticker-discovery-v1/20260715T0651Z/capture.md`

## Reviewer Notes

- “原子”仅指本地 pair cache commit，不应被评审者或 UI 文案扩大为 exchange-time atomic。
- `opening_quotes` 在 schema row required list 之外是刻意的 backward compatibility；当前 producer presence 由测试保证。
- `forward_spread_pct` / `reverse_spread_pct` 已经是百分数值，不是 fractional rate。
- Opening spread 前端必须使用独立 formatter；`formatFundingRate` 的
  fractional 语义不适用于 `*_spread_pct`。
- `stale` 状态下保留 `updated_at` 但所有价格/rates 为 null 是刻意的：让 operator 看见上次成功时间，但不能把旧值当开单价。
- stale age 在每次 assembly 由 monotonic clock 重算，不要求 fetch 再失败一次。
- 删除提示列不授权删除 `ui_flags` API 字段。
- Claude 的 development breakdown 属于 prior design involvement；若未来 Claude 参与 review-2，必须遵守 strong-reviewer disclosure override。Grok 本轮只做用户启用的 advisory design review，不替代正式 gate。
- Grok 原始 verdict 为 `REVISE`；其 P1/P2 均已在 `00-task.md`、
  `10-design.md` 和 `14-design-review-reconciliation.md` 有界处理，无需改变
  用户冻结公式、120 秒 cutoff 或产品边界。

当前 Session ID: 019f639a-7890-7573-a04b-7a62debff633
Session ID 来源: runtime_env (`CODEX_THREAD_ID`)
原始输出路径: reports/agent-runs/2026-07-bookticker-open-columns-v1/11-adr.md
本地北京时间: 2026-07-15 17:34:26 CST
下一步模型: claude_glm（由人工执行）
下一步任务: 执行已冻结的配对缓存、Decimal 和 additive contract 决策
