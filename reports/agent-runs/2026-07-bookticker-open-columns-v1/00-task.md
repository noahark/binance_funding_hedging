# Stage Task

## Stage ID

`2026-07-bookticker-open-columns-v1`

## Goal

在现有只读 Binance 资金费率工作台中增加 60 秒参考开单报价，同时压缩默认表格的重复信息。交付结果必须：

- 将“净收益”明确命名为“日净收益”。
- 删除默认表的“提示标记”展示列。
- 把借贷状态与资产标签合并为一格，借贷状态在上、资产标签在下。
- 后端每个 Group A 周期全量抓取一次现货与 USDⓈ-M 合约 bookTicker，只有两端都成功时才原子更新配对缓存。
- 后端使用 `Decimal` 计算正向与反向可执行一档价差，前端展示两腿价格及两位小数百分比。
- 保持系统只读，不新增任何交易或借贷副作用。
- 将 provider-native Session ID、来源和 raw output 路径加入 Harness 的
  统一执行 footer 与 `status.json.session_receipts`，供后续任务和审查导航。

## Frozen Product Semantics

### 正向开单

- 含义：买入现货、卖出合约。
- 上方：合约买一 `futures bidPrice`。
- 下方：现货卖一 `spot askPrice`。
- 展示百分比：`(合约买一 - 现货卖一) / 现货卖一 * 100`。

### 反向开单

- 含义：卖出现货、买入合约。
- 上方：现货买一 `spot bidPrice`。
- 下方：合约卖一 `futures askPrice`。
- 展示百分比：`(现货买一 - 合约卖一) / 合约卖一 * 100`。

两个方向均以正数表示该方向存在正价差。百分比固定保留两位小数；正数显示 `+`，负数显示 `-`，零显示 `0.00%`。

## Non-Goals

- 不实现下单、借币、还币、划转、平仓、WebSocket 或自动交易。
- 不把 60 秒 REST 报价描述为实时可成交价格或成交保证。
- 不请求逐 symbol bookTicker，也不在行循环中发 HTTP。
- 不新增 order-book depth、bid/ask 数量、滑点、手续费、资金占用或成交量计算。
- 不修改 funding history TTL、1500 秒 refresh-ahead、history cursor 或每 tick 最多 10 个 symbol 的约束。
- 不修改 `-0.00030000` 借贷门槛、coverage ledger、max-borrowable、borrow-rate cadence 或 private transport TTL。
- 不修改私有 API 白名单、凭据处理、账户面板或任何签名 GET 行为。
- 不新增配置项或环境变量；bookTicker 复用 `Config.cache_ttl_seconds`，默认 60 秒。
- 不清理历史 API 路由 `/api/public-market/snapshot`，不升级 `public-market-snapshot/v1`。
- 不删除或重解释后端 `ui_flags`、`asset_tag`、`negative_funding_status` 字段；只改变默认表的展示。
- 不在本 stage 修改 PRD、ROADMAP 或 DECISIONS 的产品阶段方向。
- 不把 Session ID 当作 credential、provider identity、raw review evidence
  或跨 provider transcript locator；不记录 token、cookie、expanded env 或
  Kimi global diagnostic log。

## File Boundaries

Backend/API task allowed files:

- `backend/adapters/binance_public.py`
- `backend/domain/snapshot.py`
- `backend/services/snapshot_service.py`
- `schemas/api/public-market/snapshot.schema.json`
- `backend/tests/test_book_ticker.py`（可新增）
- `backend/tests/test_background_worker.py`
- `backend/tests/test_snapshot.py`
- `backend/tests/test_negative_schema.py`
- `backend/tests/test_symbol_snapshot_endpoint.py`
- `docs/architecture/ARCHITECTURE.md`（仅同步已实现的数据流）
- `docs/development/DEVELOPMENT_GUIDE.md`（仅同步公开 endpoint、缓存与验证命令）
- `docs/api/public-market-contract.md`（同步 additive `opening_quotes` wire contract）

Frontend task allowed files:

- `frontend/index.html`
- `frontend/self-check.js`
- `frontend/fixture/public-market-snapshot.json`

Evidence and stage bookkeeping allowed files:

- `reports/api-samples/api-samples-index.md`
- `reports/api-samples/2026-07-bookticker-discovery-v1/**`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/**`
- `reports/agent-runs/ACTIVE.json`

User-approved Harness session-receipt amendment allowed files:

- `AGENTS.md`（仅 Output Footer / Checkpoint 的 Session 回执规则）
- `docs/model-adapters.md`（各 provider Session ID 获取与验证方法）
- `workflows/templates/stage-delivery.yaml`（执行回执契约）
- `reports/agent-runs/_template/*.md`（统一 footer）
- `reports/agent-runs/_template/status.json`（`session_receipts` 模板）

Forbidden or out-of-scope files unless a reviewer identifies a blocking contract defect and the user approves expansion:

- `backend/config.py`
- `backend/services/private_client.py`
- `backend/app/server.py`
- `schemas/api/public-market/symbol-snapshot.schema.json`
- `schemas/api/public-market/funding-history.schema.json`
- `docs/product/PRD.md`
- `docs/planning/ROADMAP.md`
- `docs/planning/DECISIONS.md`
- `agents/**`
- `scripts/validate-stage.py`
- 未在上方列出的其他 Harness/template 文件

## Acceptance Criteria

### Adapter and cache

- `GET /api/v3/ticker/bookTicker` 与 `GET /fapi/v1/ticker/bookTicker` 均以无参数全量模式请求，每个 due 周期各一次。
- request log 继续按两个真实 endpoint 分开计数，价格保持 JSON decimal string，不经过 `float`。
- 只有 JSON string 类型的 `bidPrice`/`askPrice` 可进入归一化 map；不得把
  number 通过 `str(number)` 静默转换成可计算价格。
- 非 list、空全量 payload 或双端任一请求失败均不得推进 pair cache 成功时间戳，也不得部分提交。
- pair cache 使用独立 source id，复用 `cache_ttl_seconds`；成功时间戳在两个请求和解析完成后写入。
- 首次无缓存时不阻塞其他公开快照发布，行报价状态为 `unavailable`。
- last-good pair 在刷新失败后可短暂继续使用；age `>= 2 * cache_ttl_seconds` 时为 `stale`，价格与价差不再作为可用值发布。
- 每次 assembly 都必须按 monotonic age 重算可用性；跨过 120 秒不依赖
  再发生一次失败 fetch 才进入 `stale`。
- bookTicker 始终是公共数据，不受 `private_channel_enabled` 或 classic reference 是否成功影响。

### Join and calculations

- 合约 map 按 `row.futures.symbol` 连接；现货 map 按已经解析的 `row.spot.symbol` 连接。
- bStock alias 必须正确连接，例如 futures `TSLAUSDT` 使用 spot `TSLABUSDT`。
- 四个价格中任一缺失、非数字、空字符串或 `<= 0` 时，对应行状态为 `incomplete`；正向与反向分别只检查各自公式所需的两条价格，一个方向缺失不得连带清空另一个仍可计算的方向。
- 后端只用 `Decimal` 执行两个冻结公式，百分比按 `ROUND_HALF_UP` 量化为两位，负零规范化为 `0.00`。
- 当前服务产生的每一行都包含 `opening_quotes`；旧冻结快照可缺少该可选字段并继续通过 schema。
- `opening_quotes.status` 只允许 `fresh`、`incomplete`、`stale`、`unavailable`。
- `opening_quotes` 内字段与 `10-design.md` 完全一致；对象和 schema 均禁止未知属性。
- selected-symbol click 不新增 bookTicker HTTP；它投影/复用最近发布的 canonical row 报价。

### Frontend

- “净收益”表头与 sort-basis 文案改为“日净收益”“日净收益优先”。
- 默认市场表不再渲染“提示标记”表头或单元格，但 `REQUIRED_ROW_FIELDS` 仍保留 `ui_flags`。
- 合并列标题为“借贷状态 / 资产”：借贷状态在上，资产标签在下。
- max-borrowable 数量及约合 USDT 从日净收益格移到合并列，日净收益格保留日借币成本和成本来源，不重复可借额度。
- 正向列上合约买一、下现货卖一；反向列上现货买一、下合约卖一；百分比位于两行价格右侧。
- `opening_quotes` 缺失、`stale`、`unavailable` 或价差为 null 时显示 `—`，页面不白屏。
- `incomplete` 显示存在的单腿价格；每个方向缺少自身任一 operand 时该方向价差显示 `—`，另一方向可独立显示有效价差。
- 列头或单元格 title 明示“约 60 秒刷新；失败时 last-good 最多约两个周期（默认 120 秒）后停用；非成交保证”。
- 开单百分比必须使用独立 formatter；禁止调用面向 fractional funding
  rate 的 `formatFundingRate`。锁定 `-0.04 -> -0.04%`、`0.00 -> 0.00%`，
  不得显示成 `-4%` 或 `0%`。
- 表格最终仍为 12 列，empty-state `colspan` 保持正确，现有行点击/键盘抽屉行为不受影响。

### Evidence and regression

- Grok 的原始 public response、headers 与 normalized summary 原样进入 stage evidence，不以模型总结替代 raw evidence。
- focused backend tests、完整 `backend/tests`、frontend self-check、`py_compile` 与 `git diff --check` 全部通过并写入 `60-test-output.txt`。
- review 必须检查 schema 兼容、双请求原子性、失败不推进时间戳、120 秒失效、bStock alias、公式方向、两位小数与旧后端降级。
- 所有后续模型执行 footer 显示 Session ID、来源和 raw output 路径；若
  runtime 不暴露 ID，显示 `unavailable (reason)`。bookkeeper 将完成的
  execution receipt 写入 `status.json.session_receipts`。

## Human Gates

- 当前产品语义和轻量路线已由用户批准。
- Claude provider 必须在实现前完成 `12-development-breakdown.md`；Fable5 配额耗尽后才允许 Opus4.8。
- 用户明确允许 Grok 对本次初始设计做补充评审，但 Grok 不是正式 review-1 或 review-2 gate，也不获准写交付代码。
- 任何对冻结公式、两周期失效、公开/私有边界、文件范围或交易副作用的修改必须重新请求用户批准。
- review-2 ACCEPT 只进入 `stage_accepted_waiting_user`；合并、推送仍需用户显式授权。

## Designer

- Model: `codex / gpt-5`
- Skill: `software_architect`
- Date: `2026-07-15`

当前 Session ID: 019f639a-7890-7573-a04b-7a62debff633
Session ID 来源: runtime_env (`CODEX_THREAD_ID`)
原始输出路径: reports/agent-runs/2026-07-bookticker-open-columns-v1/00-task.md
本地北京时间: 2026-07-15 17:34:26 CST
下一步模型: claude_glm（由人工执行）
下一步任务: 实现 Task A 配对 bookTicker cache、opening_quotes contract 与后端测试
