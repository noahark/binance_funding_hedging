# Task Handoff: hyperliquid-funding-compare-design-review-codex

## Source Report (author-only; immutable after task end)

- task_id: `hyperliquid-funding-compare-design-review-codex`
- role: `Reviewer / Design Review-1`
- target_model: `codex`（OpenAI）
- stage_id: `2026-08-23-hyperliquid-funding-compare-v1`
- created_at: `2026-08-23 10:59:13 CST`
- base_sha: `25cc8fe4e31194261dd48415f085bc6f9fda062d`
- delivery_sha: `6ee75b0c1eb405fa2bf79a0a7aad4814142800d5`
- 设计 verdict: **REJECT**
- 正式闭环 verdict: **REWORK**（计划评审返修；按 AGENTS.md §8 不增加 `rework_count`）

### 评审背景与只读范围

本 stage 尚无实现代码。本次只读评审固定提交范围
`25cc8fe4e31194261dd48415f085bc6f9fda062d..6ee75b0c1eb405fa2bf79a0a7aad4814142800d5`，
受审交付恰为：

1. `docs/planning/hyperliquid-funding-compare-v1.md`；
2. `reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hl-binance-pairing-20260823.json`；
3. `reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/pairing-probe.py`。

`status.json`、`ACTIVE.json`、dispatch、自指控制提交及 packet 勘误提交均不在受审交付内。
除本 create-only handoff 外没有写入任何文件。

### 总结

产品方向是最小且合理的：前四个费率相关格增加 HL 第二行、历史三列暂缓、第一版不做别名和乘数映射，
都符合“先交付真实可比较数据”的边界；`funding × 24 × 365` 的 HL 口径也成立。但方案尚未把关键失败语义、
符号类别防错、decimal wire contract、xyz 风险提示及 D1–D5 的可执行验收闭合。现状直接派实现会让实现者在
“HL 失败时显示旧值还是 `—`”“如何区分无匹配与源失败”“新撞名如何 fail-closed”等关键点自行发明规则，
且验收 5 在当前 Binance 驱动的行模型中根本无法执行。因此 REJECT，按下列最小修正补设计后重审。

### 必须逐条核实的 7 条事实断言

1. **通过。** 2026-08-23 CST 独立调用 HL `metaAndAssetCtxs`，`dex=""` / `dex="xyz"` 的
   `isDelisted != true` 数量仍为 main `177`、xyz `101`。
2. **通过。** 独立使用 Binance `/fapi/v1/exchangeInfo` 的 `TRADING + USDT + PERPETUAL/TRADIFI_PERPETUAL`
   集合重算，同名且类别一致为 main `166`、xyz `78`，合计 `244`；别名 9 + k-prefix 乘数 5 后为
   main `171`、xyz `87`，与固定 JSON 的 258 行一致。
3. **通过。** 当前所有同名但类别不一致的集合恰为 `xyz:BB`、`xyz:QNT`；HL 侧属于 xyz HIP-3，
   Binance 同名合约均为普通 `PERPETUAL` 加密资产，证明不是同一标的。当前没有第三个漏掉的撞名。
4. **有条件通过，设计稿分母表述错误。** 固定 JSON 与独立实时重算的 **258 个已配对集合**均为
   `122 × 4h + 136 × 8h`，足以证明不可统一按 8h。但设计稿 §4 写成“实测 870 个合约中”，与
   122+136 的分母不相容；实时 Binance 全部 active USDT perpetual/tradfi 为 696，原始
   `/fundingInfo` 又只列发生 cap/floor/interval 调整的 symbol，不能拿它的行数当全市场分母。
5. **定性通过，精确历史计数未能独立复现。** `predictedFundings` 当前返回 main 232、零个 colon/xyz
   名称；BinPerp 非空集合仍是 171，且仍恰好 `VINE` 假阳性 / `HYPE` 假阴性；同一次近邻采样中
   `HlPerp` 与 `metaAndAssetCtxs.funding` 为 `56/177` 不同，证明双源异步。设计稿的 `54/177`
   是瞬时值，现有固定 JSON 不含 predicted 原始响应，故只能标为当时采样值，不能写成稳定契约。
6. **通过。** 40 天 BTC `fundingHistory` 请求返回 500 行，首末相差 499 小时（约 20.8 天）；省略
   `coin` 返回 HTTP 422。官方 Info endpoint 也规定 time-range 响应最多 500 项并要求 `coin`。
7. **通过（点时事实），不可当稳定比例。** 对固定 JSON 独立重算为 xyz 映射 87 个中 83 个 Binance
   `bn_f == 0`；实时复测为 87 中 80 个为 0，现象仍在但比例会漂移。设计稿必须保留采样时间限定。

### R1–R7 结论

- **R1 范围：通过但需补展示约束。** 四列正好覆盖原值、结算频率、日归一化、年化归一化，没有更小的
  做法仍能满足 Human 的“四列同位置可比”。HL 固定写“每小时”比显示下一整点更直接地暴露 1h 对 4h/8h
  的错拍；但第二行必须有明确 `HL`/`HL·xyz` 标签，且不得参与现有筛选、排序、借币或开单逻辑。
- **R2 边界：结论通过，成本论证须勘正。** 历史三列暂不做正确。HL 30D 需要每 coin 至少两页
  （720 个小时结算点 > 500），而 Binance 当前每个 symbol 一次最多 1000 条；若沿用每 tick 10-symbol
  sweep，HL 最坏新增 20 次请求，历史请求总量从 10 变 30，不只是笼统“翻倍”。
- **R3 fail-closed：当前集合通过，长期边界不闭合。** 当前仅 BB/QNT 两个 deny 没有遗漏，14 个
  alias/multiplier 暂不映射也符合 DEC-2026-08-07-003。但仅靠静态两项无法支持 §7“漂移不会显示错值”
  的结论；两个现存撞名已经证明该缺陷家族可达。
- **R4 口径：公式通过，wire/刷新契约缺失。** HL 官方说明 funding 每小时支付，故
  `daily = funding × 24`、`annualized = daily × 365` 正确；现有项目证据也确认 Binance
  `lastFundingRate` 是当前周期实时预估。两者可同属 60s Group A，但必须独立失败，且全部计算复用
  Decimal 字符串规则，不能照证据脚本使用 float。
- **R5 风险：不通过。** §7 未定义 HL 冷启动失败、成功后下一轮失败、main/xyz 单边失败、坏 shape、
  stale last-good 的投影；也未说明如何让 Human 区分“确实无对手”和“源读取失败”。此外“xyz 休市读数
  UI 需能表达”没有字段、渲染方案或验收项。
- **R6 文件边界：不通过。** `frontend/self-check.js` 必须加入以验证新增 subline/默认开/关闭恢复；
  `docs/api/public-market-contract.md` 必须登记新的 row block、空值与失败语义（可由实现任务或 Bookkeeper
  收口承担，但计划必须列明）。若采用依赖注入而非 SnapshotService 内部构造，再显式加入
  `backend/app/server.py`；不可在实现时临时决定而不更新边界。
- **R7 验收：不通过。** 验收 5 用 MNT/PURR/APEX/CASHCAT/kNEIRO，但 `build_rows` 只遍历 Binance
  futures；实时 Binance exchangeInfo 中这五个均无行，所以不可能出现“第二行显示 —”。D1 的“每小时”、
  D3 的 alias/multiplier 不映射、D4 的零 predicted 调用、D5 的默认开也没有各自的可执行断言。

### REWORK findings（均为 `in-range`）

#### F1 — HL 失败语义未定义，直接复用现有缓存会违反验收 7

- 分类：`in-range`
- 证据锚点：设计稿 §2/§6/验收 7；base
  `backend/services/snapshot_service.py:1277-1331,1467-1486`。现有 Group A/B 是 success-only cache：
  失败不覆盖缓存，compose 继续投影 last-good；若把 HL 塞进 premium fetch，同一次失败又可能让 Binance
  冷启动无法发布。两种朴素实现分别违反“失败即 `—`”或“Binance 照常显示”。
- 当前影响：实现者没有唯一正确路径；源失败时可能展示无 freshness 的旧 HL 值，或阻断整个快照。
- 最小修正：定义独立 60s HL source_id 和“最近一次尝试失败”状态；最简单采用 main+xyz 原子组，任一
  POST/shape 失败则本次 HL 全部 `null`、追加可见 warning、Binance 正常发布、不得投影 warm last-good。
  增加 cold failure 与 success→failure 两个断言。若要 per-dex 部分成功，须明确为另一个设计选择。

#### F2 — 验收 5 不可执行，D1–D5 未形成闭环

- 分类：`in-range`
- 证据锚点：设计稿 §8.5；base `backend/services/snapshot_service.py:522-550` 与
  `backend/domain/snapshot.py:181-274` 证明行基底是 Binance futures；公开 exchangeInfo 当前不存在
  MNT/PURR/APEX/CASHCAT/kNEIRO 行。
- 当前影响：即使实现完全正确，验收 5 也无法通过，形成不清晰 acceptance oracle；默认开和
  不调用 predicted 还可能无测试假绿。
- 最小修正：用 synthetic Binance-only fixture（或固定存在的 Binance-only fixture symbol）验证
  `hyperliquid=null`/UI `—`；分别补 D1“每小时”、D3 alias+multiplier 为 `—`、D4 adapter 仅两次
  `metaAndAssetCtxs` POST、D5 默认开及关闭后恢复单行高度/首行内容的断言。

#### F3 — 静态 deny 只覆盖今天，不能支撑“漂移不会错值”

- 分类：`in-range`
- 证据锚点：当前公共 API 中同名跨类别集合恰为 BB/QNT；设计稿 §7 同时记录 xyz 半年新增 101、下架 15，
  却断言 exact 漂移“不会显示错值”。两个已发生撞名是该缺陷家族的当前证据，不是假设。
- 当前影响：未来新增一个与加密币同名的 xyz 标的会被 exact 静默误配，向 Human 展示错误费率。
- 最小修正：运行时 exact join 同时校验类别：main 只匹配 Binance `PERPETUAL`，xyz 只匹配
  `TRADIFI_PERPETUAL`；BB/QNT deny 可作为显式回归防线保留。加一个 synthetic 新撞名测试，证明不依赖
  当前两项枚举。

#### F4 — 新 block 的 wire、精度、在架过滤和 xyz 告知契约不完整

- 分类：`in-range`
- 证据锚点：设计稿仅命名 `funding_1h/daily_rate/annualized_24h`，未定义字段类型、dex 身份、invalid
  行为或 `isDelisted` 过滤；base `schemas/api/public-market/snapshot.schema.json` 使用 decimal string，
  `backend/domain/snapshot.py:155-167,205-220` 以 Decimal/8 位字符串计算；项目活约束要求“读不到”不得
  假装“知道没有”。
- 当前影响：可能引入 JSON number/float 舍入、把 delisted 行当在架、无法给 xyz 静态休市提示，也无法
  区分无匹配与源失败。
- 最小修正：冻结 `hyperliquid: null | {dex: "main"|"xyz", funding_1h, daily_rate,
  annualized_24h}`，三个数值均为 decimal string；复用现有 Decimal helpers，非法 funding 对该 match
  fail-closed；显式过滤 `isDelisted`，按完整 HL key 先 deny 再取 raw name。对 xyz 第二行显示 `HL·xyz`
  并给静态提示“非美股交易时段读数可能退化”，加入验收。

#### F5 — 文件清单和事实标签需最小勘正

- 分类：`in-range`
- 证据锚点：`frontend/self-check.js` 已按 15 列/cell index 对市场表作回归；
  `docs/api/public-market-contract.md` 是 rows wire 的活契约；固定 JSON 的 122+136 分母是 258；
  predicted 精确差异实时为 56 而非 54。
- 当前影响：实现可在 self-check 零新增断言的情况下“全绿”，API 活文档继续漂移，瞬时数字可能被误当
  稳定事实。
- 最小修正：把上述两文件列入收口边界；把 §4 改为“本次 258 个已配对样本中 122 个 4h、136 个 8h”；
  把 54/177、83/87 明示为带采样时刻的 snapshot，并为 predicted 精确数补原始响应，或删精确数只保留
  “集合/值不一致”的稳定结论。

### 执行过的核验与结果

- `git diff --name-status 25cc8fe4...6ee75b0c`：交付含三份受审文件及两个控制文件；按 dispatch 仅审前三者。
- `git diff --check 25cc8fe4...6ee75b0c`：通过。
- `jq` 对固定 JSON 重算：258；main 171；xyz 87；4h 122；8h 136；xyz `bn_f==0` 为 83：通过。
- Python AST 解析固定 `pairing-probe.py`：通过；仓库 `.venv` 有 ccxt 4.5.64，系统 Python 无 ccxt。
- 独立原生 HTTP 复测：HL live 177+101；exact 166+78；撞名仅 BB/QNT；扩展映射 171+87；配对周期
  122/136；predicted BinPerp 集合仍为 171 且 VINE/HYPE 双向相消；HlPerp 差异 56/177；BTC history
  500 行/499 小时；xyz 87 中 80 个 Binance rate 为 0。
- 官方契约核对：Hyperliquid Funding 文档确认每小时支付；Info endpoint 文档确认 time-range 最多 500；
  Binance Funding Info 文档确认该端点只返回发生 cap/floor/interval 调整的 symbols。
- 全程未调用凭证、未下单、未访问私有 API、未改状态或源码。

### Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-design-review-codex.handoff.md`；`docs/planning/hyperliquid-funding-compare-v1.md`
- 执行：Planner 按 F1–F5 做最小设计修正，固定新的 delivery SHA 后重新派发跨 provider 计划评审
- 关卡：修订设计的独立计划评审 `ACCEPT` 后，才可准备实现 dispatch
- 不能假设的事实：`54/177` 与 `83/87` 是点时采样，不是稳定常量；无 Binance 行的 HL-only symbol 不会出现在当前表格；HL 失败不能用无标识 last-good 冒充当前值

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: hyperliquid-funding-compare-design-review-codex
执行结果: completed（完成）
结果摘要: 设计方向合理，但失败降级、撞名防线、数值契约及验收闭环尚未定义；验收 5 在 Binance 驱动的表格中不可执行。结论 REWORK，补齐最小契约后重审，rework_count 不变。
产物: [reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-design-review-codex.handoff.md]
检查结果: [pass：固定 SHA、范围与隔离成立；pass：事实 1/2/3/6 独立复核；pass：事实 4 在 258 个配对样本口径成立；pass：事实 5/7 定性成立但精确数为点时值；pass：R1 与 R4 核心方向成立；fail：R2 成本数字、R3 漂移防错、R5 失败语义、R6 文件边界不闭合；fail：R7 含不可执行验收且未覆盖 D1–D5]
阻塞项: [按 handoff F1–F5 最小修订设计并重新计划评审；本次为实现前计划修订，不增加 rework_count]
评审结论: REWORK（返工）
问题记录: reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-design-review-codex.handoff.md
修复要求: reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-design-review-codex.handoff.md
本地北京时间: 2026-08-23 10:59:13 CST
下一步模型: Opus 5 / Claude（当前 Bookkeeper）
下一步任务: 读取：reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-design-review-codex.handoff.md、docs/planning/hyperliquid-funding-compare-v1.md；执行：核验 REWORK 并派 Planner 最小修订 F1–F5；关卡：修订设计重新通过独立计划评审后才可派实现
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

## Errata (append-only)
