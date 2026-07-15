# Stage Design

## Summary

本 stage 沿用现有 layered snapshot（分层快照）结构，不引入新 scheduler 或抽象层：public adapter 全量拉取两个 bookTicker，background worker 把它们视为一个配对 Group A source，domain assembly 按已解析的 futures/spot leg symbol 连接并用 `Decimal` 计算开单价差，schema 以可选 additive field（增量字段）扩展，frontend 只格式化后端结果并调整表格布局。

```text
Binance spot full bookTicker ─┐
                              ├─ both succeed ─> book_ticker_pair cache
Binance futures full bookTicker┘                  (60s due, 120s max usable age)
                                                       │
exchangeInfo + premiumIndex ─> resolved row legs ──────┤
                                                       v
                                             opening_quotes per row
                                                       │
                                  snapshot schema validation + atomic publish
                                                       │
                                                       v
                              日净收益 / 借贷状态与资产 / 正向开单 / 反向开单
```

## Assumptions

- Raw capture `2026-07-bookticker-discovery-v1/20260715T0651Z` 是本次 Binance 字段与 payload shape 的事实依据。
- 现货、合约 full bookTicker 均为 public no-key；60 秒一次的 weight 和 payload 已被样本证明在当前本地工作台预算内。
- 两个 REST 请求无法形成交易所级同时快照；“原子”仅指本地缓存不会混合不同刷新轮次的两端结果。
- 现有 worker tick 默认 30 秒，因此 due source 会在 60 秒边界后的首个 tick 刷新；失效也在首个观察到 age `>= 2 * ttl` 的 tick 生效。
- 现有 `public-market-snapshot/v1` 已采用 additive optional fields 兼容旧冻结 fixture，本 stage 延续该策略，不借机清理历史 wire version。
- 当前系统是参考和人工规划界面，不是 execution quote（执行报价）系统。

## Design Decisions

### D1. 使用一个配对 source，而不是两个独立可发布 source

Discovery artifacts 中较早提出的 `spot_book_ticker` +
`futures_book_ticker` 双独立 source 草图已被本设计废止；唯一可发布的
业务 source 是 `book_ticker_pair`，两端不得跨轮独立提交。

Adapter 暴露一个配对 fetch seam，例如 `fetch_book_ticker_pair()`，内部顺序请求：

1. `GET /api/v3/ticker/bookTicker`
2. `GET /fapi/v1/ticker/bookTicker`

它返回：

```text
{
  "spot": {symbol: {"bid_price": str, "ask_price": str}},
  "futures": {symbol: {"bid_price": str, "ask_price": str}}
}
```

Service 只在两个 endpoint 请求、顶层 shape 校验和 map 归一化全部成功后写：

```text
_global_source_cache["book_ticker_pair"] = (
    completion_monotonic,
    {
      "updated_at": completion_utc_iso,
      "spot": spot_map,
      "futures": futures_map
    }
)
```

现货成功而合约失败（或反之）时不写任何部分结果，旧 pair 的时间戳也不推进。请求日志仍分别记为两个真实 endpoint。

### D2. 复用 Group A cadence，但不成为冷启动发布阻塞

- Due threshold：`Config.cache_ttl_seconds`，默认 60 秒。
- Max usable age：`2 * Config.cache_ttl_seconds`，默认 120 秒。
- 不新增 env/config 字段。
- pair source 独立于 `premium_index`、`group_b_public` 和所有 private source。
- `_compose_base_raw()` 仍只要求 premium + Group B public 才允许冷启动发布；没有 bookTicker 时照常发布，报价状态为 `unavailable`。
- pair cache age `< 2 * ttl` 时可用于 assembly；age `>= 2 * ttl` 时只传递 last success 的 `updated_at` 和 `stale` 状态，不传递可用价格。
- private channel 关闭或 classic reference 失败不得抑制该 source 的请求。

可用性不是 fetch-failure 分支的副作用，而是每次 assembly 的投影：

```text
pair_age = now_monotonic - pair_success_monotonic
usable = pair_entry exists and pair_age < 2 * ttl
stale = pair_entry exists and pair_age >= 2 * ttl
```

因此一次成功后，即使没有额外失败事件，age 从 `119.9` 跨到 `120.0`
也必须在下一次 assembly 进入 `stale`。

### D3. Payload shape 校验与 decimal discipline

- 两个 full endpoint 顶层都必须是非空 list；否则视为失败并由 service 保留 last-good。
- 非 dict row、无 symbol row 可跳过；归一化后任一 market map 为空则整个 pair 失败。
- `bidPrice`、`askPrice` 只有在原始 JSON value 是 string 时才可进入 map；
  number 型 value 必须使该字段/row 不可用，禁止 `str(number)`。adapter、
  service 和 domain 不使用 `float`。
- qty、futures `time` 和 `lastUpdateId` 不进入本 stage contract。
- 行级有效价格必须是可解析 `Decimal` 且 `> 0`；raw `"0.00000000"` 属于缺失流动性，不属于可计算零价。

### D4. 连接使用已经解析的交易腿 symbol

- Futures lookup key：`row["futures"]["symbol"]`。
- Spot lookup key：`row["spot"]["symbol"]`，而不是 futures symbol 或 `{base_asset}USDT` 重构值。
- 因此 exact crypto pair 使用相同 symbol，bStock 自动复用既有 B-suffix alias，例如 `TSLAUSDT -> TSLABUSDT`。
- `row.spot.symbol is None` 时该行是 `incomplete`，不得猜测替代资产（例如 XAU 不得自动换成 PAXG）。

### D5. Wire contract 使用可选的行级 `opening_quotes`

`schemas/api/public-market/snapshot.schema.json` 的 row 增加可选 property；旧 frozen rows 没有它仍合法。当前 `build_rows` 对所有新行始终产生完整对象：

```json
{
  "opening_quotes": {
    "status": "fresh",
    "updated_at": "2026-07-15T06:51:57Z",
    "spot_bid_price": "64954.00000000",
    "spot_ask_price": "64954.01000000",
    "futures_bid_price": "64925.00",
    "futures_ask_price": "64925.10",
    "forward_spread_pct": "-0.04",
    "reverse_spread_pct": "0.04"
  }
}
```

字段定义：

| Field | Type | Meaning |
|---|---|---|
| `status` | enum | `fresh`, `incomplete`, `stale`, `unavailable` |
| `updated_at` | date-time or null | 最近一次完整 pair 成功写入的 UTC completion time |
| four `*_price` | decimal string or null | 对应市场的一档买/卖价格 |
| `forward_spread_pct` | decimal string or null | 已乘 100、`ROUND_HALF_UP` 到两位的正向百分数值，不含 `%` 字符 |
| `reverse_spread_pct` | decimal string or null | 已乘 100、`ROUND_HALF_UP` 到两位的反向百分数值，不含 `%` 字符 |

`opening_quotes` object 的所有上述子字段在对象存在时都 required，`additionalProperties=false`。row 层面的 `opening_quotes` 本身不加入 schema required list，以保持旧 fixture 兼容。`symbol-snapshot.schema.json` 已 `$ref` 同一 row definition，不需要修改。

状态规则：

| Pair cache | Row four prices | Row status | Published prices/rates |
|---|---|---|---|
| never succeeded | n/a | `unavailable` | all null, `updated_at=null` |
| age `>= 2*ttl` | n/a | `stale` | all null, retain last `updated_at` |
| usable age | any invalid/missing/zero | `incomplete` | preserve individually valid prices; compute each spread independently when that formula's two operands are valid |
| usable age | all valid `>0` | `fresh` | four prices + both spread fields |

`fresh` 与 `incomplete` 都保留 pair 的 `updated_at`；只有 never-succeeded
的 `unavailable` 使用 `updated_at=null`。`stale` 保留最后成功时间，但不发布
可用价格/价差。

最小 incomplete 真值表：

| Valid operands | Forward | Reverse | Status |
|---|---|---|---|
| only futures bid + spot ask | value | null | `incomplete` |
| only spot bid + futures ask | null | value | `incomplete` |
| all four | value | value | `fresh` |
| spot symbol missing / map miss / zero price | compute only unaffected direction | compute only unaffected direction | `incomplete` |
| pair never succeeded | null | null | `unavailable`, `updated_at=null` |

### D6. Backend owns both formulas and two-place rounding

Pure domain helper uses `Decimal` only：

```text
forward_pct = (futures_bid - spot_ask) / spot_ask * 100
reverse_pct = (spot_bid - futures_ask) / futures_ask * 100
```

- 使用 `Decimal("0.01")` 和 `ROUND_HALF_UP`。
- 量化后的 `-0.00` 规范化为 `0.00`。
- 每个方向独立校验自己的两个 operands；该方向 denominator `<= 0` 或任一 operand 非法时该方向返回 null。另一方向满足条件时仍可计算。四个价格未全部有效时 row status 为 `incomplete`。
- 存储的是 percentage points（百分数值），所以前端只添加正负号样式与 `%`，不得再次乘 100。前端必须使用独立的 opening-spread formatter，
  禁止复用 fractional funding rate 的 `formatFundingRate`。

从 raw BTC 样本得到的确定性向量：

- spot bid `64954.00000000`, spot ask `64954.01000000`
- futures bid `64925.00`, futures ask `64925.10`
- forward `-0.04`
- reverse `0.04`

额外 rounding vector：spot ask `100`, futures bid `101.005` -> forward `1.01`；spot bid `101.005`, futures ask `100` -> reverse `1.01`。

### D7. Selected-symbol refresh 不新增 bookTicker I/O

手动点击仍只执行既有 selected-symbol premium/history/private refresh。`opening_quotes` 来自 worker 最近发布的 canonical row/base cache：

- 不新增 single-symbol spot/futures bookTicker 调用。
- click response 的 row 继续与 published snapshot 使用同一 row schema。
- timeout/partial click 不得制造比 canonical published state 更“新”的报价语义。

### D8. 前端保持 12 列并合并重复信息

最终列顺序：

1. 标的
2. 借贷状态 / 资产
3. 资金费率
4. 结算时间
5. 日费率
6. 年化 24h
7. 年化 7D
8. 年化 30D
9. 日净收益
10. 标记价格 / 指数价格
11. 正向开单
12. 反向开单

变化说明：12 个旧列减去“提示标记”、再合并资产/状态，新增两个开单列，净列数仍为 12；empty-state colspan 不变。

合并单元格：

- 第一行：借贷状态 badge。已探测额度时包含 `可借 <amount>` 与约合 USDT；零额度保持 `可借 0(已借完)`。
- 第二行：`CRYPTO(加密货币)` / `METAL(金属)` / `BSTOCK(美股代币)` / `UNKNOWN(未知)`。
- 日净收益单元格保留净百分比、borrow-rate source 和日借币成本；删除重复 max-borrowable 子行。

开单单元格使用价格 stack + 右侧百分比的两列布局：

```text
正向开单                     反向开单
合约买一  64925.00  -0.04%    现货买一  64954.00  +0.04%
现货卖一  64954.01            合约卖一  64925.10
```

百分比为正使用 success 色、负使用 danger 色、零/缺失使用 muted。title
明示“约 60 秒刷新；失败时 last-good 最多约两个周期（默认 120 秒）后
停用；非成交保证”并解释 `stale`/`incomplete`。

### D9. 旧后端与缺失字段优雅降级

- 不把 `opening_quotes` 加入 frontend `REQUIRED_ROW_FIELDS`。
- 字段整体缺失时两个开单列均渲染 `—`，其他列与抽屉正常工作。
- `ui_flags` 继续留在 `REQUIRED_ROW_FIELDS`，只是默认表不再显示。
- `badgeForUiFlag` 和行内 `uiFlags` 渲染逻辑可删除，底层 snapshot 不变。

## Task Breakdown

### Task A — Backend contract, cache and decimal semantics

Owner: `claude_glm`。

- 增加 full bookTicker adapter seam 与严格 map 归一化。
- 将 pair source 接入 Group A worker，完成 atomic success、retry、120s stale projection。
- 扩展 `build_rows`/assembly，加入 alias-aware quote join 和 Decimal formulas。
- 添加可选 `opening_quotes` schema definition。
- 覆盖 adapter、domain、worker、schema、click projection 测试。
- 必要时只同步 ARCHITECTURE/DEVELOPMENT_GUIDE 中已落地事实。
- 同步 `docs/api/public-market-contract.md` 的 additive `opening_quotes`
  字段、percentage-point 单位和兼容规则。

Task A 完成并形成 committed backend contract 后，Task B 才开始。

### Task B — Frontend contract integration and table compaction

Owner: `kimi`。

- 更新 fixture 到冻结 `opening_quotes` contract。
- 调整表头、combined cell、日净收益内容和两列开单布局。
- 保留旧后端 graceful degradation。
- 更新 self-check 的列索引、12 列断言、显示顺序、百分比与 stale/missing cases。

### Bookkeeper/review work

- Codex 只维护 stage 状态、证据、commits、dispatch 与 handoff，不写交付代码。
- Review-1 按 task provider 交叉：Claude-GLM 后端由 Kimi review，Kimi 前端由 Claude-GLM review。
- Review-2 优先 Codex；Claude 因 development breakdown 属于 prior design involvement，仅在满足 strong-reviewer override 时可回退。
- 用户启用的 Grok 设计评审是 advisory evidence（补充证据），不替代 formal review-1/2。
- 用户授权 bookkeeper 在本 stage 集成 Session receipt v1：更新 Harness
  footer、适配器方法、workflow/templates，并让 Task A/Task B/正式 reviews
  从本 stage 起输出 provider-native Session ID 或明确 unavailable reason。

## Test Strategy

### Unit tests

- Adapter correct URLs, request log, full-list shape, string preservation, empty/malformed rejection。
- Pure formula direction, two-place HALF_UP, negative zero, invalid/zero denominator。
- Exact and bStock alias join；perp-only/missing/zero price incomplete。
- Schema accepts full object and legacy missing object；rejects unknown status/property/number-valued prices。

### Worker/integration tests

- Cold pair success; `<60s` no call; `>=60s` one pair refresh。
- Either-side failure does not advance pair cache timestamp or partially replace maps。
- Last-good remains usable below 120s; at `>=120s` publishes stale/null quote values。
- 一次成功后直接推进 monotonic 到 `119.9`/`120.0`，不注入额外失败事件，
  分别断言 usable/stale。
- bookTicker runs with private channel disabled。
- Existing premium/Group B/private/history cadence call counts remain unchanged except the two new public calls。
- Selected-symbol refresh performs no bookTicker HTTP and preserves canonical quote object。

### Frontend self-check

- Header text and exact 12-column order。
- No “提示标记” cell; combined cell status-before-asset。
- Borrow amount appears only in combined cell, not day-net cell。
- Forward and reverse top/bottom labels and prices exactly match frozen order。
- Backend percent strings display exactly two decimal places with correct color/sign。
- 独立 formatter 锁定 `"-0.04" -> "-0.04%"`、`"0.00" -> "0.00%"`；
  断言没有调用/复用 `formatFundingRate` 的 100 倍 fractional 语义。
- missing whole object, stale, unavailable, incomplete all degrade without blank screen；incomplete 的两个方向独立显示可用结果。
- Existing filters, row click, keyboard open, drawer, account panels and auto-refresh checks continue passing。

### Exact commands to be finalized by development breakdown

```text
pytest backend/tests/test_book_ticker.py backend/tests/test_snapshot.py backend/tests/test_background_worker.py backend/tests/test_symbol_snapshot_endpoint.py backend/tests/test_negative_schema.py -q
pytest backend/tests -q
node frontend/self-check.js
python3 -m py_compile backend/adapters/binance_public.py backend/domain/snapshot.py backend/services/snapshot_service.py
git diff --check
```

## Risks

- Cross-market REST skew：pair commit 防止跨轮混用，但无法让两个交易所响应同时；UI 必须保持参考报价文案。
- Stale misrepresentation：last-good 若无限发布会误导开单；120 秒 hard usability cutoff 是验收重点。
- bStock misjoin：若按 futures symbol 查 spot 会使 bStock 全部缺失；必须复用 `row.spot.symbol`。
- Percent unit double conversion：backend 字段已经乘 100；frontend 再乘会放大 100 倍。字段名、schema description 和测试必须同时锁定。
- Existing stub compatibility：旧测试 client 没有新 seam；service 必须用 capability check/optional path，不能破坏 legacy stub bootstrap。
- Table indexing：合并/新增后仍为 12 列，但既有 self-check 大量使用数字列索引，必须系统更新并验证。
- Review identity：Claude breakdown 会构成 design involvement；不得在没有 override 证据时直接作为 review-2 fallback。

## Raw Artifact Requirements For Review

- `reports/agent-runs/2026-07-bookticker-open-columns-v1/00-intake.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/00-task.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/10-design.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/11-adr.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/12-development-breakdown.md`
- Claude/Grok raw design review outputs when captured
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/14-design-review-reconciliation.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/15-session-id-capture-evidence.md`
- `reports/api-samples/2026-07-bookticker-discovery-v1/20260715T0651Z/evidence-index.md`
- raw JSON + headers + normalized summary under that sample directory
- exact committed git diff/fingerprint
- implementation/fix reports and `60-test-output.txt`
- relevant source, schema and fixture files

当前 Session ID: 019f639a-7890-7573-a04b-7a62debff633
Session ID 来源: runtime_env (`CODEX_THREAD_ID`)
原始输出路径: reports/agent-runs/2026-07-bookticker-open-columns-v1/10-design.md
本地北京时间: 2026-07-15 17:34:26 CST
下一步模型: claude_glm（由人工执行）
下一步任务: 按已 reconciliation 的设计完成 Task A，禁止开始 frontend Task B
