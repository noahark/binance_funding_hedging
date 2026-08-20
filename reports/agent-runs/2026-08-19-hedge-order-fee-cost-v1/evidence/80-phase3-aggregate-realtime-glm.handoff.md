# Task Handoff: 80-phase3-aggregate-realtime-glm

## Source Report (author-only; immutable after task end)

- task_id: `80-phase3-aggregate-realtime-glm`
- role: `Implementer`
- target model: `claude_glm`（provider `zhipu_glm`）
- stage_id: `2026-08-19-hedge-order-fee-cost-v1`
- created_at: 2026-08-20 13:29 CST
- base_sha: `06c00c07e0181c596292c2f163890456abed3d8d`（`git rev-parse HEAD`）
- delivery_sha: pending（dispatch 未授予 commit；交付提交后由 Bookkeeper 解析）

### 任务背景

阶段三终章（10-design §3/§4.1/§5/§7.1 T2后半+T5/§8）：读链路真实聚合
（持仓表折 U + 关仓全腿聚合）与开平仓实时手续费写入（两站点 commit-first）。
前端在真数据下零改动运行（kimi 阶段一展示层已按冻结键契约实现）。

### 实际修改范围（全部在 dispatch Assigned Files 内）

1. `backend/hedge_open_tasks/fee_fetcher.py`：
   - 新增 `usdt_fee_total(rows)`（§5.1/§5.2 折 U：Σ(bnb×价)+Σ(USDT)+
     Σ(本币×该腿 quote/base 均价)；任一参与腿缺构成量 → None/None/False；
     本币均价 `_leg_vwap` 严禁 `avg_price` 列，quote/base 任一缺失或为 0
     （G5 哨兵）→ 不可定价）。
   - 新增 `resolve_leg_identity(row)`（§4.1 符号对应，dict/Row 兼容，回补
     引擎与实时钩子共用）；`_backfill_one` 改用它（行为不变）。
   - 新增 `build_realtime_transport(client, bnb_close_price)`（T5 传输装配，
     duck-typed 签名客户端，模块仍不 import 服务层）。
   - **`um_query_window` 行为修正**：零宽/倒置窗（`end <= start`）由「返回
     None 判失败」改为「向前扩 10 分钟回退窗」。理由：inline
     `resolve_attempt` 用**同一个 now_us** 落 `dispatched_at_us` 与
     `last_query_at_us`（store.py COALESCE 两列同值），每条 inline 终态的
     合约腿窗口恒为零宽——不修则 T5 对合约腿全灭（本地测试实证：修复前
     um 腿一次 GET 都发不出）。多余成交由本地 orderId 过滤兜底。这是对
     阶段二已 ACCEPT 行为的一处**收紧为可用**的修正，Review 请重点看。
2. `backend/hedge_open_tasks/store.py`：
   - `aggregate_positions`：腿 SELECT 增四列费用字段；桶增 `fee_rows`，
     仅 `task_type=open` 且有成交的腿入列（§5.1）；输出由占位
     None/None/True 改为 `FF.usdt_fee_total` 真实聚合（键名不变，
     `_POSITION_KEYS` 契约不动）。legacy fill 桶无费用数据 → 自然不全。
   - `insert_close_log`：三个手续费键**未显式传入**时按该周期 open+close
     有成交腿现算聚合（完整 → 真实值 + 0；任一不全 → NULL/NULL/1；空周期
     → 不全）；显式传入原样落库（阶段二「回补不改写旧行」契约不变）。
     新增私有 `_cycle_trading_fee_total(cycle_id)`（只读 joined SELECT）。
3. `backend/hedge_open_tasks/service.py`：
   - `_fetch_leg_fees_after_terminal(task_id, attempt_id, now_us, *,
     only_leg_id)`：终态提交后的回写钩子——FILLED + order_id + 四列空才
     发 GET（每腿至多 1 次，复用 `FF.fetch_leg_fees`，断点 3）；任何失败
     （含 429/418）不重试、不进 drain、不改腿终态，只记任务卡日志
     （kind=``leg_fee_fetch``，含 written/incomplete/reason/error）。
   - `_realtime_fee_transport()`：懒装配——注入 live 执行器的 `_client`
     （duck-typed；disabled/测试无此属性 → None → no-op，绝不为凑传输层
     发请求）+ `_bnb_price_reader()`（D4 链直接复用预检 provider 的现价
     读取器：price_map ≤300s → 公开现价 → None；不在本包重写）。
     `configure_fee_transport(transport)` 为测试注入点。
   - 接线三处（§4.1「两个写入站点」覆盖全部终态入口）：
     a. inline 主终态 `resolve_attempt`（try/else，commit 后）；
     b. inline 暂停类终态结算（同 try/else）；
     c. drain `resolve_leg_from_query` 成功且 terminal+FILLED（only_leg_id
        单腿）。
4. 测试：`test_hedge_store.py` +9（聚合完整/未查询/缺 BNB 价/本币 vwap/
   排除 close 腿/第三种资产/关仓聚合完整/不全写 NULL/显式键优先）；
   `test_hedge_service.py` +5（钩子写冻结列/无传输层 no-op/失败不改终态
   且留痕/每腿恰 1 次 GET+已写跳过/按腿解析符号）；
   `test_backfill_leg_fees.py` 1 处改（零宽/倒置窗新行为）+ 既有全绿。
5. 前端零改动：`node frontend/self-check.js` 全部自检通过（真数据结构与
   阶段一冻结键契约一致，无需排版微调）。

### 设计裁决与解释（供 Review 核）

1. **UM 零宽窗修正**（见上「实际修改范围」1）——最重要的一处，inline 合约
   腿费用写入的必要条件；旧行为在阶段二数据上不触发（回补腿的 dispatched/
   last_query 来自不同时刻），仅 T5 实时腿必然命中。
2. `usdt_fee_total` 的「半截残留」判据：有 BNB 价无量、有资产名无量 → 不全
   （正常路径一次写四列，残留只可能来自异常半写）。
3. 完整但无 BNB 的腿组：`fee_bnb_qty` 输出真零 `"0"`（非 NULL）——全部腿
   已查询且无 BNB 是已知事实；前端按「有 BNB 才显示第二行」自行判断。
4. 实时装配用私有属性 duck-typing（`_client` / `_read_est_price`）而非组合根
   接线：server.py、live 执行器、预检 provider 均不在本任务 Allowed Files；
   getattr 缺失即 no-op（disabled/测试天然安全）。若 Review 希望改公开接口，
   需要一个扩 Allowed Files 的后续小任务。
5. `_dispatch_simulated`（disabled 路径）不接钩子：该路径永不产生真实成交。
6. 阶段二 Review-2 的 O1（dry-run 被拒绝时静默打印「候选 0 条）**未修**：
   修法在 `scripts/backfill-leg-fees.py`，不在本任务 Assigned Files，留给
   收口轮（Bookkeeper 已记录为顺手修复项）。
7. close_log「空周期」（无有成交腿）→ incomplete=1：fail-closed，不为无腿
   周期编「完整零」。

### 命令与结果

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_hedge_store.py
  backend/tests/test_hedge_api.py backend/tests/test_hedge_service.py
  backend/tests/test_backfill_leg_fees.py backend/tests/test_hedge_purity.py -q`
  → **232 passed**（验收 6 前半）。
- `node frontend/self-check.js` → **全部自检通过**（验收 6 后半）。
- 邻域回归：`pytest backend/tests/test_hedge_cycle_close.py
  backend/tests/test_hedge_cycle_core.py backend/tests/test_positions_merge.py
  backend/tests/test_hedge_api.py -q` → 204 passed（关仓结算链无破坏）。
- 本任务未对实盘库/币安做任何读写；全部验证在 tmp_path。

### 不能假设的事实 / 交接边界

- 实时写入在生产生效需服务重启加载新代码（当前运行进程仍是旧代码）；
  重启须 Human 授权，本任务未触碰服务。
- live 回补仍未执行（阶段二边界不变）；T5 上线后新成交腿由实时路径写入，
  断点 2 的空窗腿用同一回补脚本补。
- D4 冻价在实时路径取「写入时现价」（price_map ≤300s 或公开现价），与回补
  的「成交分钟 K 线收盘价」是两条不同冻价路径（设计 D3/D4/§4.3 既定）。
- UM orderId 支持性仍未做 live 确认（阶段二裁决 4 不变）。

### 未完成事项（按设计属后续）

- 阶段三 Review-1 / Review-2（§8：HIGH_RISK 双评审）。
- Review-2 O1 的脚本 dry-run 拒绝提示（收口轮顺手修）。
- live 回补执行与 UM orderId 确认（Human 授权后）。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/80-phase3-aggregate-realtime-glm.handoff.md`
  2. `backend/hedge_open_tasks/fee_fetcher.py`
  3. `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/status.json`
- 执行：Bookkeeper 核验阶段三交付（复跑上方两条验收命令），随后按 §8 路由
  准备 Review-1（跨 provider，Kimi 优先；实现者为 zhipu_glm）。
- 关卡：Human 启动评审窗口；合并/重启/live 回补均另需 Human 授权。
- 不能假设的事实：`um_query_window` 零宽/倒置行为相对阶段二有一处必要修正
  （见设计裁决 1，Review 必查）；实时装配走私有属性 duck-typing（裁决 4）；
  O1 未修的原因是文件不在 Allowed Files（裁决 6）。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: 80-phase3-aggregate-realtime-glm
执行结果: completed（完成）
结果摘要: 读链路真实聚合落地：aggregate_positions 只汇总 open 有成交腿折 U（本币均价用 quote/base，严禁 avg_price），不全时 None/None/True；insert_close_log 未显式传键时按周期开+平全腿现算（完整 0 / 不全 NULL+1）。实时写入三处终态站点 commit-first 各至多 1 次 GET，复用 fee_fetcher（断点 3），失败只记日志不改终态；D4 现价复用预检价格链。修正 UM 零宽窗（inline 腿必要）。232+204 passed，self-check 全绿，前端零改动。
产物: [backend/hedge_open_tasks/fee_fetcher.py, backend/hedge_open_tasks/store.py, backend/hedge_open_tasks/service.py, backend/tests/test_hedge_store.py, backend/tests/test_hedge_service.py, backend/tests/test_backfill_leg_fees.py, reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/80-phase3-aggregate-realtime-glm.handoff.md]
检查结果: [验收1 持仓真实聚合（完整/未查询/缺价/第三种资产/排除 close 腿）pass；验收2 本币折 U 严格 quote/base 均价、_leg_vwap 禁 avg_price 且 quote/base 零值视为不可定价（G5）pass；验收3 关仓聚合开+平全腿、完整 0/不全 1/显式键优先、空周期 fail-closed pass；验收4 三终态站点 commit-first（try/else 结构）、失败不改终态留痕、每腿恰 1 次 GET、已写跳过 pass；验收5 D4 现价冻结复用预检价格链（≤300s→公开现价→None），无客户端 no-op pass；验收6a 五测试文件 232 passed pass；验收6b node frontend/self-check.js 全部自检通过、前端零改动 pass；回归 cycle_close/cycle_core/positions_merge/api 204 passed + UM 零宽窗修正（inline 合约腿必要，详见 handoff 裁决1）pass]
阻塞项: [none]
本地北京时间: 2026-08-20 13:29:43 CST
下一步模型: gemini-3.7-flash（Bookkeeper，agy 窗口）
下一步任务: 读取：reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/80-phase3-aggregate-realtime-glm.handoff.md；执行：核验阶段三交付并按 §8 路由 Review-1（跨 provider，Kimi 优先）；关卡：Human 启动评审窗口，合并/重启/live 回补另需授权
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- **verification_time**: 2026-08-20 13:31:00 CST
- **source_sha256**: `cd34087d5a587c693b0fa5757bebcb6362a9aba34fcfa2a8fdb466457690d7a9`
- **status_revision**: 19 -> 20
- **base_sha**: `06c00c07e0181c596292c2f163890456abed3d8d`
- **delivery_sha**: `3bc6acaec6e3bd2b837239d7a925007a29729db6`
- **verdict_checks**:
  1. `持仓真实聚合 aggregate_positions`: pass（支持完整折 U、均价使用 quote/base、不全返回 None/None/True）
  2. `关仓日志聚合 insert_close_log`: pass（聚合 open+close 腿、完整 0、不全 1）
  3. `实时开平仓写入 T5`: pass（三处终态 commit-first 后发至多 1 次 GET，复用 fee_fetcher，D4 现价冻结）
  4. `UM 零宽窗修正`: pass（解决 inline 终态 dispatched==last_query 问题）
  5. `自动化单测验证`: pass（`pytest` 232 passed）
  6. `前端自检`: pass（`node frontend/self-check.js` 全部通过）
  7. `邻域回归`: pass（`test_hedge_cycle_close.py` 等 204 passed）
- **verification_status**: `verified`

## Errata (append-only)
