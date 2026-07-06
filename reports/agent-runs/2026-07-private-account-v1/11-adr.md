# ADR — 2026-07-private-account-v1

本 stage 的架构/设计决策记录。完整规格与论证见 `10-design.md`（含 §2.A
附录：冻结权重/预算/字段矩阵/脱敏表/链命中）；本文件记录决策点、状态与
后果。按 stage-delivery required-file 约定落档。决策源自方向基线
（`docs/private-account-v1-direction-draft.md` @7168266，用户批准含 ADR-3
sort revision）+ 10-design + Task A/B 实现报告（§2 决策表）。

## ADR-1：单一 HMAC 出口扩展（白名单 4→12，纪律不变）

- **决策**：`private_client.py` 仍是仓库级唯一 HMAC-SHA256 出口；deny-by-default
  `(method, exact-path)` 白名单由 phase2 的 4 项扩展至 status.json
  `endpoint_whitelist` 12 项（sapi/papi/account 三池）；GET-only；门控在签名
  构造**之前** raise；base_url 按 §2.A.1 逐端点冻结（sapi/api→api.binance.com，
  papi→papi.binance.com）；新增 dual-TTL 缓存（§1.6：账户级 60s fast / 1h std）。
- **状态**：ACCEPTED（hard_constraint；POST/PUT/DELETE、交易语义、websocket/
  listenKey 含铺垫代码永久禁止）。
- **后果**：未来私有端点须扩白名单 + 同一出口；grep 单测锁定单一出口
  （`test_single_hmac_exit_*`）；E1/E1b 登记但不被任何 fetcher 调用（discovery-only）。

## ADR-2：成本腿四级链 = 快照级单一命中 tier（§1.3）

- **决策**：链判定在快照级做一次（非逐行）：tier① next_hourly（E2，`assets=`
  逗号拼接，`isIsolated=false`）→ ② rate_history（E2b，单数 `asset`，A1 假设
  仅 probed_assets[0] 探一次）→ ③ cross_margin_tier（W3+E5）→ ④ vip0_reference；
  命中 tier 的查表取利率逐资产装配；命中 tier 表内缺失该资产 → 该行
  borrow rate/net/source=null。
- **状态**：ACCEPTED（§1.3 字面 + §3.2「不逐行探测利率端点」）。
- **后果**：设计期 fixture 的逐行混合 source（AUSDT=next_hourly / BUSDT=
  cross_margin_tier）是 design-time synthetic 形状示例（其 note 自声明 ALL
  values fabricated），非运行时语义；运行时全候选从单一命中 tier 取利率。
  实测命中 tier 1（next_hourly）。tier② E2b 全候选覆盖受限（见 ADR-9）。

## ADR-3：sort_basis 双基准（net_daily_yield 优先 / abs Phase2 回归）

- **决策**：`sort_rows(rows, basis)` 双基准——`net_daily_yield`（当
  `classic_ref ≠ None 且 cost_leg.chain_hit_tier ∈ {1..4}`）优先；否则回退
  `abs_daily_funding_rate`（phase2 全序：abs daily 降序 + null 末尾 + symbol
  升序 tie-break）。chain 全断（tier None，极罕见）→ abs。前端按 payload
  顺序渲染（零客户端排序）。
- **状态**：ACCEPTED（方向基线 ADR-3 sort revision，用户批准）。
- **后果**：sort_basis 快照级单一（§1.2）；§3.5 net-reversal 核心断言
  （AUSDT net 0.0004 排 BUSDT net 0.0001 前，尽管 BUSDT abs daily 更大）在测。

## ADR-4：net_daily_yield 定义（§1.1，Decimal 禁 float，六向量）

- **决策**：`net = daily_funding_rate - daily_interest_account`（当两者可计算）；
  `Decimal` 运算，`quantize(1E-8)`，负零归一化；缺失/不可计算 → null。
  hourly×24 归一化（`compute_daily_from_hourly`）。§3.4 六向量逐一在测。
- **状态**：ACCEPTED（decimal-string 纪律，延续 phase2 ADR-2）。
- **后果**：前端展示仅 string-shift（parseFloat/Number×100 禁止）。

## ADR-5：private_account 三态 + 防重复计算（§1.4）

- **决策**：顶层 `private_account` 块恒输出，三态语义同 borrow_validation：
  verified=true（总览/统一余额/现货余额/UM 持仓）/ disabled（env 缺失或
  classic_ref=None 或 unified+spot 双失败 → verified=false、三数组空、
  total null、error 填原因）/ error（单源失败 → 该数组空、块仍 verified=true）。
  防重复计算：`totalWalletBalance` 已含 um/cm/crossMargin，`um_positions` 是
  敞口视图（非余额），不重复加总。价格 map（P5 `/api/v3/ticker/price` 公开
  全量一次）折算 total_value_usdt。
- **状态**：ACCEPTED（§1.4 + round2 fix B：`classic_ref is None` 时跳过
  E3/E4/E6 + price_map 令 private_account 进 disabled 三态）。
- **后果**：防重复计算两条硬规则有测试断言（`test_assemble_private_account_anti_double_count`
  等）；`classic_ref=None` 门控回归测试（`test_private_account_disabled_when_classic_ref_none_even_if_accounts_return`）。

## ADR-6：coverage/warnings 截断语义（§1.5，上限 50 可配）

- **决策**：借币探测范围 = `neg ∧ MARGIN_SPOT_CANDIDATE ∧ CRYPTO`（不含
  asset_borrowable，解耦）；上限 `borrow_check_max_calls=50`（§1.5，可配，
  取代 phase2 N=10）；截断行标 `not_probed_this_round` + verified=false
  （禁静默 verified）；`coverage.skipped>0` 时顶层 warnings 追加
  `borrow_validation: N candidate(s) truncated by rate_limit_budget`。
- **状态**：ACCEPTED（§1.5 + round2 fix A：`assemble_snapshot` 由
  `coverage.skipped>0` 驱动追加 warning，分层到纯函数）。
- **后果**：`daily_interest_account` 不门控 `asset_borrowable`（独立信号）；
  截断 warning 仅 skipped>0 触发，offline（skipped=0）不触发。

## ADR-7：schema v0.3 additive（wire schema_version 不变）

- **决策**：顶层 `sort_basis`/`private_account`/`borrow_validation`（聚合
  `$defs/borrow_validation_summary`）+ 行 `net_daily_yield`/`borrow_rate_source`
  均 optional；`classic_margin.daily_interest_account` 恒供给故 required。
  wire `schema_version` = `public-market-snapshot/v1` 不变。contract v0.3
  amendment 引 H_intake 证据路径。
- **状态**：ACCEPTED（additive；v0.1 frozen fixture + v0.2 offline 快照均仍通过）。
- **后果**：旧后端/前端优雅降级（缺失字段→`—`/不渲染，不白屏）。

## ADR-8：设计期 fixture synthetic 性质

- **决策**：`backend/tests/fixtures/private-account-v1-design.json` 是设计期
  合成 fixture（6 行 A-F USDT 覆盖 §3.4/§3.5 向量 + private_account 三态），
  ALL values fabricated（其 `_design_fixture_note` 自声明）；账户级金额
  `<AMOUNT>`，{uid,vipLevel}→`<ID>`。Task A 后端测试验证真实输出，不
  schema-validate 该 fixture；Task B 渲染该 fixture 不做 schema 校验。
- **状态**：ACCEPTED（设计期 unblock 用途；含 `_design_fixture_*` 元键非 wire 输出）。
- **后果**：fixture 行序（AUSDT/BUSDT/CUSDT）与 §1.2 net 严格降序
  （应为 AUSDT/CUSDT/BUSDT）有偏差——合成数据问题，运行时排序由后端
  `sort_rows` 保证（§3.5 断言顺序），Task B 前端零排序按 payload 渲染。
  交 review-1 核查运行时排序正确性（非实现缺陷）。

## ADR-9：tier② E2b 单资产探针（A1 假设，R3 升级口，OPEN）

- **观察**：冻结 discovery 仅验证 `asset=BTC` 单数参数（E2 用复数 `assets`，
  E2b 用单数 `asset`，参数名差异印证）。`fetch_cost_leg_chain` 仅对
  `probed_assets[0]` 探一次 E2b；tier② 覆盖受限。tier①（E2）一次调用覆盖
  全候选，是现实主路径。
- **判定**：实现严格遵循 §1.3 快照级单 tier（非实现 bug）。
- **决策**：DEFERRED。是否调整 tier② 全候选覆盖（实测 E2b 是否接受逗号
  `asset`）属耦合面之外的 design 决策，按红线 R3 停手上报，不在本 stage 自行 fix。
- **后续**：留 review-1 / review-2 / 用户决策。

---

本地北京时间: 2026-07-06 11:21 CST
作者: bookkeeper (claude_glm，续任会话)，决策依据见 10-design.md +
Task A/B 实现报告 §2 + 方向基线 @7168266
