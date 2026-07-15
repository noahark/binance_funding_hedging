# Development Breakdown And Pre-Implementation Design Review

## Breakdown Author Identity

- Role: development breakdown author 兼实现前设计审查者（非本轮 formal review-1/review-2）
- Provider: Anthropic Claude
- Model: `opus4.8`（fallback；`claude-fable-5` 配额耗尽，用户已在本次 dispatch 中确认改用 Opus4.8）
- Skill: `task_planner`
- Mode: documentation write only（不实现、不 commit、不改 status/handoff/初始设计/代码/schema/API samples）
- Prior involvement: Claude provider 参与本 stage 的 development breakdown，构成 review-2 的 design involvement（见 §12）。

本文件读取集：`AGENTS.md`、`workflows/templates/stage-delivery.yaml`(stage-design/development_breakdown 段)、`00-intake.md`、`00-task.md`、`10-design.md`、`11-adr.md`、`status.json`、`reports/api-samples/2026-07-bookticker-discovery-v1/20260715T0651Z/`(evidence-index/capture/normalized 及内含 raw BTC 现货/合约样本与 batch-probe headers)、`docs/product/PRD.md`、`docs/architecture/ARCHITECTURE.md`、`docs/development/DEVELOPMENT_GUIDE.md`、`schemas/api/public-market/snapshot.schema.json`、`schemas/api/public-market/symbol-snapshot.schema.json`、`backend/adapters/binance_public.py`、`backend/domain/snapshot.py`、`backend/services/snapshot_service.py`、相关 `backend/tests/`(尤其 `test_background_worker.py` 的 `_StubPublic`/`_SeamStubPublic`)、`frontend/index.html`、`frontend/self-check.js`、`frontend/fixture/public-market-snapshot.json`。

---

## Design Review Verdict

`READY`

`10-design.md` 与 `11-adr.md` 的契约、缓存失效语义、单位约定和向后兼容策略与冻结用户要求、原始公开样本一致，可直接进入实现。所有 finding 均为 `P2` 级实现约束/澄清，不构成对冻结要求的 P0/P1 矛盾，无需 human decision 改写冻结语义。实现方必须在编码时消化本文件 §5–§9 的全部 P2 约束；否则会在 formal review 阶段暴露为缺陷。

---

## Design Review Findings

按 `P0/P1/P2` 排列。每项给出证据锚点、风险、可执行修订。

### P0

None。

### P1

None。冻结要求内部自洽：正向/反向公式方向、分子分母、两位小数展示、公开 always-on 边界、无交易副作用均无相互矛盾。

### P2

**P2-1 Decimal 运算顺序与 context 必须与测试 oracle 逐位一致（否则 `1.01` 舍入向量会漂）。**
- 证据：`10-design.md` §D6 rounding vector「spot ask `100`, futures bid `101.005` -> forward `1.01`」；公式 `(futures_bid - spot_ask) / spot_ask * 100`，除法在乘法之前。
- 风险：`(28.90 / 64925.10)` 一类除法是无限小数，Decimal 默认 context 截到 28 位有效数字后再 `* 100` 再 `quantize`。若 oracle 用 `float`、或改变运算分组（例如先 `* 100` 再除）、或改变 quantize 时机，`1.005` 边界会因 `ROUND_HALF_UP` 方向不同而产生 `1.00` vs `1.01` 偏差。
- 修订：Task A 的纯函数必须严格按 `(bid - ask) / ask * 100` 顺序在 `Decimal` 上求值，最后一步且仅最后一步 `quantize(Decimal("0.01"), ROUND_HALF_UP)`；测试 oracle 用完全相同的表达式构造期望值，不得用 float 或手算字符串。`quantize` 前 `-0.00` 归一为 `0.00`。默认 `decimal` context（28 位）已足够；不要新建/收窄 context。

**P2-2 book_ticker_pair 新 source seam 必须走 capability check，避免打断 legacy stub bootstrap。**
- 证据：`backend/services/snapshot_service.py` `_refresh_due_sources` 已有 `has_seams = hasattr(self.client, "fetch_premium_index") and hasattr(self.client, "fetch_exchange_info_group_b")` 的 legacy fallback；`backend/tests/test_background_worker.py` 的 `_StubPublic`(line 63) 与 `_SeamStubPublic`(line 139) 均无 book ticker seam。
- 风险：若生产代码无条件 `self.client.fetch_book_ticker_pair()`，所有沿用旧 stub 的既有 worker/endpoint 测试会 `AttributeError`，破坏 `10-design.md` §Risk「Existing stub compatibility」与验收项「首次无缓存不阻塞其他公开快照发布」。
- 修订：Task A 用 `hasattr(self.client, "fetch_book_ticker_pair")` 独立门控 book_ticker_pair 刷新；缺 seam 时该 source 保持 never-succeeded，行 `opening_quotes.status="unavailable"`，其余快照照常发布。给需要覆盖 pair 行为的测试在 `_SeamStubPublic`（及必要时 `_StubPublic`）加 `fetch_book_ticker_pair` seam。

**P2-3 前端 self-check 实际加载的 fixture 不在 frontend 允许文件内；opening_quotes 覆盖必须在 self-check.js 内存注入，不得改后端 fixture。**
- 证据：`frontend/self-check.js` line 14 `fixturePath = .../backend/tests/fixtures/private-account-v1-design.json`；该文件既不在 Task A 也不在 Task B 的 allowed files；`frontend/fixture/public-market-snapshot.json`（Task B allowed）并不被 self-check 加载（仅供浏览器预览）。既有先例：self-check line 210–235 已在内存给设计期 fixture 补 `annualized_*`、`value_usdt` 等字段。
- 风险：实现方误改 `private-account-v1-design.json`（越界），或误以为更新 `frontend/fixture/public-market-snapshot.json` 就能让 self-check 覆盖 opening_quotes（实际不生效）。
- 修订：Task B 在 `self-check.js` 内对已加载的 `designFixture.rows` 内存注入 `opening_quotes`（fresh/incomplete/stale/unavailable/null-spread 各态），与既有 `annualized_*` 注入同法；`frontend/fixture/public-market-snapshot.json` 仅作为浏览器静态预览一并补 `opening_quotes`。两者都不触碰 `backend/tests/fixtures/**`。

**P2-4 列索引迁移是 self-check 的最大回归面：`negative_funding_status` 徽标从第 11 列迁入合并列（第 2 列），新增开单列在末两列。**
- 证据：`frontend/index.html` 现表头 12 列，`negative_funding_status` 在 col index 10、`提示标记` 在 col index 11；`self-check.js` 大量断言按数字列索引取单元格（如 #16/#34/#41 用 index 10 取负费率状态，#28 用 index 0，#6/#19/#31/#33 用 index 4/8）。目标布局（`10-design.md` §D8）：合并列在 index 1，`日净收益` 在 index 8，`正向开单`=index 10、`反向开单`=index 11，删除独立 `负费率状态`/`提示标记` 列。
- 风险：任何遗漏的列索引断言会静默取错单元格，产生假通过或假失败。
- 修订：Task B 系统性重编 self-check 所有 `getRowCell(..., N)` 索引；`badgeForNegativeFundingStatus` 的行感知六文案派生（见 memory `followup-negative-funding-status-ui-labels`）整体移入合并列上行，断言改取 index 1；新增开单列断言取 index 10/11。§5 acceptance 固化最终 12 列顺序与索引。

**P2-5 `fresh` 覆盖 0–120s 全部 last-good，无独立「aging」态；需 UI 文案兜住，避免评审误判为缺陷。**
- 证据：`10-design.md` §D5 状态表：usable age(`<2*ttl`) 且四价齐全 -> `fresh`；`11-adr.md` ADR-1「last-good 最多作为可用值保留两个刷新周期」。
- 风险：61–120s 的 last-good 仍标 `fresh`，可能被误读为「刚刷新」。
- 修订：非阻塞澄清。冻结要求只区分「可用/不可用（两周期）」，`fresh` 表示「在可用窗口内」符合冻结语义。Task B 必须在开单列头/单元格 title 明示「60 秒参考报价，非成交保证」，并展示 `updated_at`，让 operator 自行判断新旧。评审据此不将 `fresh` 命名判为缺陷。

**P2-6 `symbol-snapshot.schema.json` 无需修改即自动继承 `opening_quotes`（该文件被列为 forbidden，确认无需扩权）。**
- 证据：`schemas/api/public-market/symbol-snapshot.schema.json` line 48–51 `row` 用 `"$ref": "snapshot.schema.json#/$defs/row"`；`opening_quotes` 作为 row 可选 additive property 加入 `snapshot.schema.json#/$defs/row` 后，symbol-snapshot 与 selected-symbol click 投影自动带上，无需触碰 forbidden 文件。
- 风险：实现方误以为需改 symbol-snapshot schema 而请求扩权。
- 修订：确认 Task A 仅改 `snapshot.schema.json`；click 路径 `_handle_refresh_command` 复用同一 `_assemble`/`build_rows`，opening_quotes 自然投影，`get_symbol_snapshot` 用 `snapshot.schema.json` registry 校验通过（`snapshot_service.py` line 214–231 已注册）。§7 D7 无新增 HTTP。

**P2-7 spot 全量 payload 含 2282 个零盘口；`"0.00000000"` 必须判为 incomplete，绝不作合法分母。**
- 证据：`normalized/bookticker-summary.json` `empty_or_zero_bidPrice=2282`；`10-design.md` §D3「raw `"0.00000000"` 属于缺失流动性」、§D6「该方向 denominator `<= 0` 或任一 operand 非法时该方向返回 null」。
- 风险：把 `"0"` 当分母产生除零/`InvalidOperation`，或产出误导性 `spread`。
- 修订：Task A 行级价格有效性判据 = 可解析 `Decimal` 且 `> 0`；四价任一无效 -> row `incomplete`；每个方向独立只校验自身两条 operand（见 §8）。

---

## Owner Split And Execution Order

顺序（serial，`parallel_mode.enabled=false`）：Task A 完成并在 stage 分支形成 committed backend contract 后，Task B 才开始，依赖已冻结的 `opening_quotes` wire 契约。

- **Task A** — backend/API/schema/domain/tests — owner `claude_glm`（provider `zhipu_glm`）。
- **Task B** — frontend/UI/fixture/self-check — owner `kimi`，依赖 Task A committed/frozen 契约。

Codex/Grok 不写交付代码；Codex 为 bookkeeper/review-2，Grok 为用户启用的 advisory 设计评审（§11）。

---

## Task A — Backend Contract, Cache, Decimal Semantics

Owner: `claude_glm`。

### A. Allowed files（仅这些可写）

- `backend/adapters/binance_public.py`
- `backend/domain/snapshot.py`
- `backend/services/snapshot_service.py`
- `schemas/api/public-market/snapshot.schema.json`
- `backend/tests/test_book_ticker.py`（新增）
- `backend/tests/test_background_worker.py`
- `backend/tests/test_snapshot.py`
- `backend/tests/test_negative_schema.py`
- `backend/tests/test_symbol_snapshot_endpoint.py`
- `docs/architecture/ARCHITECTURE.md`（仅同步已实现数据流）
- `docs/development/DEVELOPMENT_GUIDE.md`（仅同步公开 endpoint、缓存、验证命令）

### B. Forbidden / do-not-touch

- `backend/config.py`（不新增 config/env；pair 复用 `Config.cache_ttl_seconds`）
- `backend/services/private_client.py`、`backend/app/server.py`
- `schemas/api/public-market/symbol-snapshot.schema.json`、`funding-history.schema.json`
- `backend/tests/fixtures/**`（含 `private-account-v1-design.json`）
- `frontend/**`
- `docs/product/PRD.md`、`docs/planning/ROADMAP.md`、`docs/planning/DECISIONS.md`
- Harness：`AGENTS.md`、`workflows/**`、`agents/**`、`scripts/validate-stage.py`
- 既有 funding/history/borrow/private 语义：不改 1500s refresh-ahead、history cursor、每 tick ≤10 symbol、`-0.00030000` 门槛、coverage ledger、max-borrowable、borrow-rate cadence、private transport TTL、签名 GET、白名单、`price_map` 现有 gating。
- 不改 `/api/public-market/snapshot` 路由、不升级 `public-market-snapshot/v1`、不删/改 `ui_flags`/`asset_tag`/`negative_funding_status` 后端字段。

### C. Inputs

`00-task.md` frozen semantics、`10-design.md` D1–D7、`11-adr.md` ADR-1/2/3、raw 样本目录、本文件 §6 wire contract、§7 cache truth table、§8 formula/rounding/error vectors。

### D. Work items

1. **Adapter seam**（`binance_public.py`）：新增 `fetch_book_ticker_pair()`（live-only），顺序请求
   - `GET {spot_base_url}/api/v3/ticker/bookTicker`（无参数全量）
   - `GET {futures_base_url}/fapi/v1/ticker/bookTicker`（无参数全量）
   两个 endpoint 各 `_bump` 一次真实 URL key（request log 分开计数）。顶层必须非空 `list`；非 list/空 list -> 抛错或返回失败标记（由 service 判失败，保留 last-good）。归一化为 `{"spot": {SYM: {"bid_price": str, "ask_price": str}}, "futures": {...}}`；跳过非 dict/无 symbol row；`bidPrice`/`askPrice` 原样保留字符串（禁 `float`）；不携带 qty/`time`/`lastUpdateId`。offline 返回 `None` 或不暴露 seam（offline 无该 source）。
2. **Worker 接入**（`snapshot_service.py` `_refresh_due_sources`）：以 `hasattr(self.client, "fetch_book_ticker_pair")` 门控（P2-2）；`_source_due("book_ticker_pair", now, ttl_a)` 用 `Config.cache_ttl_seconds`。**原子提交**：仅两端请求 + 顶层校验 + 双 map 归一化全部成功后，一次性写 `self._global_source_cache["book_ticker_pair"] = (completion_monotonic, {"updated_at": iso_utc, "spot": spot_map, "futures": futures_map})`；任一侧失败/空 map 均不写、不推进时间戳（FR-2 completion-time 语义，与既有 sources 一致）。source 独立于 premium/group_b/private，不受 `private_channel_enabled`、classic_ref 影响。`_compose_base_raw` 冷启动条件不变（仍只需 premium+group_b）；无 pair 时不阻塞发布。
3. **Assembly / build_rows**（`domain/snapshot.py` + service）：按 `10-design.md` §D4 连接——futures map key = `row["futures"]["symbol"]`；spot map key = 已解析的 `row["spot"]["symbol"]`（bStock 自动复用 B 后缀 alias，如 futures `TSLAUSDT` -> spot `TSLABUSDT`）；`row.spot.symbol is None` -> incomplete，不猜替代资产。为每个当前行产出完整 `opening_quotes` 对象（§6）。pair cache 传入方式：在 assembly 层读取 `_global_source_cache["book_ticker_pair"]`，按 monotonic age 判 cold/stale/usable（§7）后投影到每行。**建议**：把「pair entry -> 单行 opening_quotes」实现为 `domain/snapshot.py` 纯函数（接受 spot_leg/futures_leg quote dict + status），便于单测，service 只负责取 cache + 判 age。
4. **Formula 纯函数**（`domain/snapshot.py`）：`Decimal` only，两个方向独立（§8）。新增 2 位 `ROUND_HALF_UP` quantize（不复用 8 位 `_quantize_rate`）；`-0.00` 归一 `0.00`；输出百分数值字符串（已 ×100，无 `%`）。
5. **Schema**（`snapshot.schema.json`）：在 `#/$defs/row/properties` 增可选 `opening_quotes`（§6 定义，`additionalProperties=false`，内部子字段全 required），**不**加入 row `required` 列表（旧 fixture 兼容）。
6. **Tests**：见 §9 单测/worker 测试清单，新增 `test_book_ticker.py`，扩展既有测试。
7. **Docs**：仅在 ARCHITECTURE/DEVELOPMENT_GUIDE 同步「已实现」的 bookTicker 数据流、两个公开 endpoint、复用 `cache_ttl_seconds`、120s 可用上限、验证命令。

### E. Acceptance criteria（Task A）

- 两 endpoint 均无参数全量、每 due 周期各一次；request log 按两真实 endpoint 分开计数；价格全程 decimal string，无 `float`。
- 非 list/空 payload/任一侧失败均不推进 pair 成功时间戳、不部分提交。
- pair source 独立 source id、复用 `cache_ttl_seconds`；成功时间戳在两请求+解析完成后写入。
- 首次无缓存不阻塞其他公开快照发布，行 `opening_quotes.status="unavailable"`、四价与两 spread 全 null、`updated_at=null`。
- last-good 在刷新失败后短暂可用；age `>= 2*cache_ttl_seconds` -> `stale`，四价与 spread 不再作为可用值发布，保留最后 `updated_at`。
- bookTicker 不受 `private_channel_enabled`/classic reference 影响。
- 连接：futures 按 `row.futures.symbol`；spot 按已解析 `row.spot.symbol`；bStock alias 正确（futures `TSLAUSDT` -> spot `TSLABUSDT`）。
- 四价任一缺失/非数字/空串/`<=0` -> 行 `incomplete`；正向与反向分别只检查各自公式所需两价，一方向缺失不连带清空另一可计算方向。
- 仅 `Decimal` 执行两冻结公式，两位 `ROUND_HALF_UP`，负零 -> `0.00`。
- 当前服务每行都含 `opening_quotes`；旧冻结快照可缺该可选字段并通过 schema。
- `opening_quotes.status ∈ {fresh, incomplete, stale, unavailable}`；对象与 schema 均禁未知属性。
- selected-symbol click 不新增 bookTicker HTTP，投影/复用最近发布 canonical row 报价。
- focused + full backend tests + `py_compile` + `git diff --check` 全绿并落 `60-test-output.txt`。

---

## Task B — Frontend Contract Integration And Table Compaction

Owner: `kimi`。依赖 Task A committed/frozen 契约。

### A. Allowed files

- `frontend/index.html`
- `frontend/self-check.js`
- `frontend/fixture/public-market-snapshot.json`

### B. Forbidden / do-not-touch

- 一切 backend/schema/docs/tests/Harness/`backend/tests/fixtures/**`。
- `REQUIRED_ROW_FIELDS` 中的 `ui_flags`、`route_class` 校验保留（不得移除）。
- 不改 selected-symbol click 的 HTTP 行为、drawer/抽屉、私有面板、隐私开关、既有过滤器语义、自动刷新计时器逻辑。
- 前端不做业务计算：opening spread 百分数已由后端 ×100，前端只加正负号样式与 `%`，**禁止再乘 100**（`_pct` 字段命名 + schema description 是护栏）。

### C. Inputs

Task A 冻结的 `opening_quotes` wire 契约（§6）、`10-design.md` §D8/D9、`00-task.md` Frontend acceptance、本文件 §5 列布局与索引。

### D. Work items

1. **表头文案**：`净收益` -> `日净收益`；sort-basis 文案 `净收益优先` -> `日净收益优先`（`sortBasisLabel` 中 `net_daily_yield` 分支）。
2. **删「提示标记」列**：移除该 `<th>` 与单元格渲染（`renderRowHtml` 末列 `uiFlags`）；`REQUIRED_ROW_FIELDS` 仍保留 `ui_flags`；`badgeForUiFlag`/行内 uiFlags 渲染逻辑可删（底层 snapshot 不变）。
3. **合并列「借贷状态 / 资产」**（新 index 1，替换原「资产标签」列）：上行 = 原 `badgeForNegativeFundingStatus(row)` 的行感知派生徽标（保留 memory `followup-negative-funding-status-ui-labels` 的六文案：已验证可借 / 可借 0(已借完) / 杠杆交易对未列出 / 资产不可借 / 有利率·可借性未探测 / 未探测(限速预算) / 需私有验证，结构禁用行保留结构文案），并把 max-borrowable 数量 + 约合 USDT 从日净收益格迁入此处（零额度保持 `可借 0(已借完)`）；下行 = `badgeForAssetTag(row.asset_tag)`（CRYPTO/METAL/BSTOCK/UNKNOWN 中文优先，METAL 中性徽章）。
4. **日净收益格（index 8）**：保留净百分比、borrow-rate source 徽标、日借币成本子行（memory `followup-borrow-rate-on-row`：仅 `borrow_rate_source != null` 行展示日息子行）；**删除**重复的 max-borrowable 可借子行（已迁入合并列）。
5. **两个开单列**（index 10 正向、index 11 反向）：价格 stack + 右侧百分比布局（`10-design.md` §D8）：
   - 正向：上「合约买一 = futures_bid_price」、下「现货卖一 = spot_ask_price」、右 `forward_spread_pct`。
   - 反向：上「现货买一 = spot_bid_price」、下「合约卖一 = futures_ask_price」、右 `reverse_spread_pct`。
   - 百分比：正 -> success 色、负 -> danger 色、零/缺失 -> muted；固定两位小数展示（后端字符串直接展示 + `%`，不再运算）。
6. **降级**（§D9）：`opening_quotes` 整体缺失 / `stale` / `unavailable` / spread 为 null -> 两开单列或对应百分比显示 `—`，不白屏；`incomplete` 展示存在的单腿价格，每方向缺自身任一 operand 时该方向百分比 `—`，另一方向可独立显示有效值。`opening_quotes` **不**加入 `REQUIRED_ROW_FIELDS`。
7. **文案**：开单列头或单元格 title 明示「60 秒参考报价，非成交保证」，并解释 `stale`/`incomplete`。
8. **fixture**：`frontend/fixture/public-market-snapshot.json` 各行补 `opening_quotes`（覆盖 fresh + 至少一 incomplete + 一 stale/unavailable）供浏览器预览。
9. **self-check**：见 §9 前端断言清单；系统更新所有列索引（P2-4），新增 opening_quotes 各态断言（内存注入，P2-3），断言最终 12 列顺序、empty-state `colspan=12`、行点击/键盘抽屉不受影响。

### E. Acceptance criteria（Task B）

- `日净收益` 表头与 sort-basis 文案生效。
- 默认表不再渲染「提示标记」表头/单元格，`REQUIRED_ROW_FIELDS` 仍含 `ui_flags`。
- 合并列标题「借贷状态 / 资产」，状态在上、资产在下；max-borrowable 数量+约合 USDT 只在合并列出现，不在日净收益格重复。
- 正向列上合约买一、下现货卖一；反向列上现货买一、下合约卖一；百分比两位小数、色/号正确、位于两行价格右侧。
- `opening_quotes` 缺失/`stale`/`unavailable`/spread null -> `—`，不白屏；`incomplete` 单腿独立展示。
- 列头/单元格 title 明示「60 秒参考报价，非成交保证」。
- 最终 12 列，empty-state `colspan` 正确，行点击/键盘抽屉/私有面板/自动刷新照常。
- `node frontend/self-check.js` 全绿并落 `60-test-output.txt`。

---

## Wire Contract — `opening_quotes`（逐字段冻结）

row 级 **可选 additive** 对象；当前 producer 对每个当前行始终输出完整对象；旧冻结快照可缺失并仍通过 schema。加入 `snapshot.schema.json#/$defs/row/properties`，**不**加入 row `required`；`symbol-snapshot.schema.json` 经 `$ref` 自动继承（P2-6，不改该文件）。对象 `additionalProperties=false`，对象存在时以下 8 子字段全部 required。

| 字段 | 类型 | 可空 | 语义 |
|---|---|---|---|
| `status` | enum | 否 | 只允许 `fresh` / `incomplete` / `stale` / `unavailable` |
| `updated_at` | date-time 或 null | 是 | 最近一次完整 pair 成功写入的 UTC completion time；`unavailable` 时 null，`stale` 时保留最后成功值 |
| `spot_bid_price` | decimal string 或 null | 是 | 现货买一（反向公式分子左项） |
| `spot_ask_price` | decimal string 或 null | 是 | 现货卖一（正向公式分母/减项） |
| `futures_bid_price` | decimal string 或 null | 是 | 合约买一（正向公式被减项） |
| `futures_ask_price` | decimal string 或 null | 是 | 合约卖一（反向公式分母/减项） |
| `forward_spread_pct` | decimal string 或 null | 是 | 已 ×100、`ROUND_HALF_UP` 两位的正向百分数值，**不含** `%` |
| `reverse_spread_pct` | decimal string 或 null | 是 | 已 ×100、`ROUND_HALF_UP` 两位的反向百分数值，**不含** `%` |

- 单位：`*_spread_pct` 是**百分数值**（如 `-0.04` 表示 `-0.04%`），与 fractional funding-rate 字段单位不同；命名 `_pct` + schema description 双重护栏，前端禁止二次 ×100。
- 决定性 fresh 样例（raw BTC 样本，`normalized/bookticker-summary.json` `btc_cross_market`）：
  ```json
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
  ```
- Backward compatibility：schema `$defs/row` 现有 `required`（line 99–114）不含 `opening_quotes`；`frontend/fixture/public-market-snapshot.json` 与既有冻结 fixture 无该字段仍合法。schema 单独不能证明「current producer 始终 present」，由 Task A deterministic 测试补足。

---

## Cache Lifecycle Truth Table

age = `now_monotonic - pair_success_monotonic`；`ttl = Config.cache_ttl_seconds`（默认 60）；hard usable 上限 = `2*ttl`（默认 120）。判 due/stale 用 monotonic age；wire `updated_at` 仅供人读，不参与 due 判定。

| # | pair cache 状态 | 行四价 | `status` | published 价格/百分比 | `updated_at` |
|---|---|---|---|---|---|
| 1 | cold（never succeeded） | n/a | `unavailable` | 四价 null，两 spread null | null |
| 2 | fresh commit，age `< 2*ttl`，四价全有效 `>0` | 全有效 | `fresh` | 四价 + 两 spread | 最近成功值 |
| 3 | one-side failure（本轮单边失败） | — | 不推进时间戳；沿用上一次成功 entry，按其 age 落入行 #2/#4/#5 | 依 last-good | 依 last-good |
| 4 | retry 成功（双端复原） | 全有效 | `fresh` | 四价 + 两 spread（新 `updated_at`） | 新成功值 |
| 5 | usable age（`< 2*ttl`），某价缺失/非数字/空/`<=0` | 有缺 | `incomplete` | 保留各自有效价；每方向 operand 齐则算该方向 spread，缺则该方向 null | 最近成功值 |
| 6 | age `>= 2*ttl` | n/a | `stale` | 四价 null，两 spread null | 保留最后成功值 |
| 7 | recovery（stale 后再次双端成功） | 全有效 | `fresh` | 四价 + 两 spread | 新成功值 |

要点：单边失败**不**产生新可发布 pair、**不**推进时间戳（#3）；age 从最后一次完整成功持续增长，最终越过 `2*ttl` -> `stale`（#6）；`fresh` 覆盖 0–120s 全部 last-good（P2-5，靠 UI 文案+`updated_at` 兜底）。

---

## Formula Vectors, Rounding/Error Vectors, Independence

### 冻结公式

```
forward_pct = (futures_bid_price - spot_ask_price) / spot_ask_price * 100
reverse_pct = (spot_bid_price  - futures_ask_price) / futures_ask_price * 100
```
两方向正值均表示该方向存在有利价差。`Decimal` only，运算顺序严格如上（P2-1），末步 `quantize(Decimal("0.01"), ROUND_HALF_UP)`，`-0.00` -> `0.00`。

### Deterministic vectors（oracle 用同表达式在 Decimal 上求值）

| 输入 | forward | reverse |
|---|---|---|
| spot_bid `64954.00000000`, spot_ask `64954.01000000`, fut_bid `64925.00`, fut_ask `64925.10` | `-0.04` | `0.04` |
| rounding：spot_ask `100`, fut_bid `101.005` | `1.01`（`1.005` HALF_UP 进位） | — |
| rounding：spot_bid `101.005`, fut_ask `100` | — | `1.01` |
| 相等：所有四价相等 | `0.00`（负零归一） | `0.00` |

### Error / incomplete vectors（每方向独立）

- 正向仅依赖 `futures_bid_price` 与 `spot_ask_price`；反向仅依赖 `spot_bid_price` 与 `futures_ask_price`。
- `spot_ask_price` 缺失/`"0.00000000"`/`<=0`/非数字 -> `forward_spread_pct=null`，但若 `spot_bid_price` 与 `futures_ask_price` 有效则 `reverse_spread_pct` 仍计算（**不连带清空**）。
- 对称：`futures_ask_price` 无效 -> reverse null，forward 可独立计算。
- 四价任一无效 -> row `status="incomplete"`（即使某一方向仍可算出 spread，row 级仍是 incomplete；两方向都能算且四价全 `>0` 才 `fresh`）。
- 分母 `<= 0` 视为该方向不可计算（返回 null），绝不除零（P2-7）。
- `"0.00000000"` = 缺失流动性，非合法零价。

---

## Exact Test Commands And Evidence Path

实现方在 stage 分支运行，输出汇入 `reports/agent-runs/2026-07-bookticker-open-columns-v1/60-test-output.txt`：

```text
pytest backend/tests/test_book_ticker.py backend/tests/test_snapshot.py backend/tests/test_background_worker.py backend/tests/test_symbol_snapshot_endpoint.py backend/tests/test_negative_schema.py -q
pytest backend/tests -q
node frontend/self-check.js
python3 -m py_compile backend/adapters/binance_public.py backend/domain/snapshot.py backend/services/snapshot_service.py
git diff --check
```

（若 `python` 别名不可用，用 `python3`，与 `status.json.tests.note` 一致。）

### Task A 测试要点（`test_book_ticker.py` 新增 + 既有扩展）

- Adapter：正确 URL（spot `api.binance.com/api/v3/ticker/bookTicker`、futures `fapi.binance.com/fapi/v1/ticker/bookTicker`）、无参数全量、request log 两 endpoint 各 +1、full-list shape、字符串保留、非 list/空 list 拒绝。
- 纯公式：方向、两位 HALF_UP、负零、`1.005` 进位向量、分母 `<=0`/无效 operand 返回 null、两方向独立。
- 连接：exact crypto 同 symbol、bStock alias（`TSLAUSDT`->`TSLABUSDT`）、perp-only/`spot.symbol=None`/零价 -> incomplete。
- Schema：接受完整 `opening_quotes` 对象、接受缺该可选对象的 legacy row；拒绝未知 status、未知子属性、number 值价格。
- Worker（扩 `test_background_worker.py`，`_SeamStubPublic`/`_StubPublic` 加 `fetch_book_ticker_pair` seam）：cold pair success；`<60s` 不再调；`>=60s` 一次 pair 刷新；任一侧失败不推进时间戳/不部分替换 map；last-good `<120s` 可用、`>=120s` 发布 stale/null；`private_channel_enabled=False` 下仍请求 bookTicker；除两新增公开调用外，premium/group_b/private/history cadence 调用计数不变；无 `fetch_book_ticker_pair` seam 的 legacy stub 走 unavailable 且不 `AttributeError`。
- Click（`test_symbol_snapshot_endpoint.py`）：selected-symbol refresh 不发 bookTicker HTTP、投影复用 canonical row `opening_quotes`、schema 校验过。

### Task B 测试要点（`self-check.js`）

- 12 列顺序与列头（含「日净收益」「借贷状态 / 资产」「正向开单」「反向开单」；无「提示标记」「负费率状态」独立列）、`colspan=12`。
- 合并列上状态下资产、状态六文案行感知派生、max-borrowable 仅现于合并列。
- 日净收益格保留净值/来源/日借币，不含可借额度重复。
- 正/反向列上下腿标签与价格严格匹配冻结顺序；后端百分数直接两位展示、色/号正确、无二次 ×100。
- opening_quotes 缺失/`stale`/`unavailable`/spread null -> `—` 且不白屏；`incomplete` 两方向独立（一方向 `—`、另一方向有效）。
- 既有过滤/行点击/键盘/抽屉/私有面板/自动刷新断言继续通过（列索引已迁移）。

---

## Formal Review Focus And Cross-Review Routing

### Formal review focus（review-1/review-2 必查）

schema 向后兼容（缺 `opening_quotes` 的 legacy row 仍过）、双请求原子性、单边失败不推进时间戳、120s 失效清空可用价、bStock alias 连接、两冻结公式方向、两位小数与负零、`_pct` 单位不二次 ×100、incomplete 两方向独立、click 无新增 bookTicker HTTP、legacy stub 不被新 seam 打断、最终 12 列与 empty-state colspan、`ui_flags` 契约字段保留。

### Cross-review routing（provider isolation）

- Review-1 交叉：Task A（`claude_glm`=`zhipu_glm`）由 **Kimi** review-1；Task B（Kimi）由 **Claude-GLM** review-1。reviewer 不得是被审任务的 implementer/fix author（硬禁，无 override）。
- Task-specific：后端契约/缓存/decimal 走 backend reviewer；前端布局/降级/单位走 frontend reviewer。
- Review-2 最终 gate：优先 **Codex/GPT**。Claude 因本 development breakdown 属 prior design involvement，只有在无 unrelated decision model 且满足 strong-reviewer disclosure override（记录 `reviewer_prior_involvement`、fallback 原因、evidence 路径）时才可回退，且 Claude 用 Fable5 优先、配额耗尽后 Opus4.8（同 Anthropic provider identity）。不得在 Codex 出具有效 verdict 后再找 Claude 二次意见。

---

## Grok Advisory Review Note

用户显式启用 Grok 对本 stage 初始设计做补充只读评审（`design-review-grok.prompt.md` -> `13-design-review-grok.raw.md`，`status.json.design_review_dispatch.grok.formal_review_gate=false`）。Grok 产出是 **advisory evidence（补充证据）**，**不替代** formal review-1/review-2，也不获准写交付代码。Grok 若提出实质 finding，由 bookkeeper 记录并交人工/正式 gate 处置，不自动改冻结语义。

---

## Prior Involvement Note（review-2 disclosure）

Claude provider（本文件 Opus4.8）已参与本 stage 的 development breakdown，构成 review-2 的 design involvement。未来若 Claude 作 review-2 fallback，必须走 strong-reviewer disclosure override：仅在 unrelated decision model（Codex/GPT）runner-level 可用性检查失败（quota/auth/service/timeout/重复 invalid verdict）后允许；verdict 须含 `reviewer_prior_involvement`，`status.json` 须记 fallback 原因与 evidence 文件；review-2 prompt 须以用户批准的方向/PRD/产品文档为最高要求，design 与 breakdown 仅作被审证据；`scripts/validate-stage.py` 缺字段即 fail acceptance。该 override 只适用于 direction/breakdown/design involvement，**绝不**适用于 implementation/fix authorship。

---

本地北京时间: 2026-07-15 16:56:39 CST
下一步模型: codex（bookkeeper）
下一步任务: 记录 breakdown_author 与 verdict 到 status.json、准备 Task A(`claude_glm`) 实现 dispatch packet；Grok advisory 评审可并行由人工执行，二者均不替代 formal gate；实现按 serial 顺序 Task A -> Task B。
