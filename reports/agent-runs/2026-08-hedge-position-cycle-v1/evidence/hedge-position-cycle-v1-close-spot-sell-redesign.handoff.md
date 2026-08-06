# Task Handoff: hedge-position-cycle-v1-close-spot-sell-redesign

## Source Report (author-only; immutable after task end)

- task_id: `hedge-position-cycle-v1-close-spot-sell-redesign`
- role: `Implementer`（target_model: `deepseek`，provider: `deepseek`）
- stage_id: `2026-08-hedge-position-cycle-v1`（拟用值，以 Bookkeeper `status.json` 为准）
- created_at: `2026-08-05 21:16 CST`
- base_sha: `08127aabbb15548f46484257614f34f384c6cac8`（`git rev-parse HEAD`，未移动 HEAD）
- delivery_sha: `pending`（未提交任何 commit，交付为工作树改动）

### 任务背景

平仓现货卖出路由重设计：修复 COOKIEUSDT 平仓单腿事故（forward close 现货 SELL 被 collateral-cap
预检误导到普通现货账户 → -2010 insufficient_funds，合约已平、现货单腿 paused，Human 手工处理现货）。
Human 已拍板：① forward 平仓现货 SELL 统一走普通现货账户（余额够直接卖；不够先万向划转补足再卖；
卖出后 USDT 划回统一账户）；② reverse 平仓现货 BUY 维持统一账户（还币后续任务）；③ 划转一次性、
失败不重试、平单任务卡直接停（paused）+ 日志；④ 划转后复检余额（防响应丢失误判）；⑤ USDT 回流失败
不算任务失败（平仓完成是主事实）；⑥ 当前单腿暂停的任务不动、COOKIE 现货 Human 手工处理。

### 实际修改范围

**模块 A（万向划转能力，`backend/services/hedge_open_live_client.py`）**
- 白名单受控扩展 13 → 14：`("POST", "/sapi/v1/asset/transfer") → api.binance.com`（用户万向划转，
  权重 TRADE；API key 权限 Human 已确认开启，沿用开单 key）；
- `UNIVERSAL_TRANSFER_PATH` + type 冻结枚举 `TRANSFER_TYPE_PM_MAIN`（统一→现货）/
  `TRANSFER_TYPE_MAIN_PM`（现货→统一）+ `_ALLOWED_TRANSFER_TYPES`；
- `universal_transfer(type_, asset, amount)`：type 白名单校验（非枚举 ValueError）、签名 POST、
  **写语义与订单一致（超时/5xx 不重试）**，返回原始响应（tranId 由调用方解析）；
- 普通现货账户余额：复用既有 `get_spot_account`（GET /api/v3/account，白名单已有）。

**模块 B（平仓现货路由，`domain.py` + `hedge_preflight_provider.py` + `service.py`）**
- `domain.decide_spot_route(..., task_type='open')`：close+forward → 固定
  `(regular_spot, ROUTE_REASON_CLOSE_SELL_REGULAR)`（**不再走 collateral-cap 预检**）；
  close+reverse → 固定 `(papi_margin, papi_default)`；open → 现有逻辑逐字不变；
  新增 `ROUTE_REASON_CLOSE_SELL_REGULAR` 常量；
- `hedge_preflight_provider.get_snapshot(coin, direction, task_type='open')`【越界，见下】：
  route 决策按持仓方向（close 的 preflight direction 是反转后的余额方向，provider 内反转回持仓方向
  再调 decide_spot_route）；open+forward 才读 collateral-cap 列表（close 不依赖 cap，读失败不阻塞
  close 路径）；
- `service.create_task` close 分支 + `_resolve_fresh_preflight`：preflight 统一用反转方向做余额检查
  + 传 task_type——**消除 create 与发单 fresh preflight 的路由漂移**（COOKIE 事故根因之一：
  创建时 papi 路由、发单时 fresh preflight 按 forward 走 cap → regular_spot）。

**模块 C（划转时序，`service.py` + `live_hedge_executor.py` + `store.py`）**
- `service._ensure_close_spot_balance(task, now_us)`：仅 forward close——实时查普通账户该币 free
  （executor duck-typed）→ 够则返回 None；不足 → `universal_transfer('PORTFOLIO_MARGIN_MAIN',
  base, 差额)` 一次 → **复检**余额 → 仍不足/查询失败/划转异常 → 中文错误（fail-closed，不重试、
  不发单）；reverse close / dry-run（无原语）→ None（跳过/模拟余额足够）；
- `_worker_round`：close 任务 `scheduled_attempt_count == 0`（首个 attempt 发单前）调
  `_ensure_close_spot_balance`，错误 → `PAUSE_REASON_CLOSE_SPOT_BALANCE` 暂停 + 任务卡日志
  （kind=`close_transfer`），不发单；后续 attempt 不再进入（幂等）；
- `live_hedge_executor.query_spot_free(asset)`（解析 GET /api/v3/account balances free；失败 →
  None）与 `universal_transfer(type_, asset, amount)`（转调 client，返回 tranId；失败抛错）【越界，
  见下】；
- `store.append_log(task_id, ts_us, kind, payload)` 通用日志辅助 + `close_task_spot_quote_total`
  （close 任务现货腿成交额合计，任一不可解析 → None）；
- `domain`：`PAUSE_REASON_CLOSE_SPOT_BALANCE` 常量 + 中文文案。

**模块 D（USDT 回流，`service.py`）**
- `_transfer_back_usdt(task, now_us)`：forward close 完成后统计 close 任务现货腿
  `cumulative_quote_amt` 合计 → `universal_transfer('MAIN_PORTFOLIO_MARGIN', 'USDT', 合计)` 划回
  统一账户；失败 → 任务卡日志（`usdt_back_failed`，中文「USDT 回流失败，金额 X，请人工处理」），
  **任务状态不变（done）**；金额 0/空跳过；reverse close / dry-run 跳过；
- `_finalize_close_task` 末尾调用（平仓完成是主事实，回流不阻塞）。

**模块 E（测试 + 文档）**
- `test_hedge_cycle_close.py` +16 用例：路由（close+forward 固定 regular_spot 且 cap_exceeded=True
  不受影响——复现 COOKIE 场景；close+reverse 固定 papi；open 路由回归不变；endpoint 映射）、
  universal_transfer（type 冻结/签名参数/500 抛错不重试）、query_spot_free 解析、划转时序
  （余额够不划转 / 不足划转+复检成功 / 划转失败 pause+日志 / 复检不足 fail-closed / 查询失败 /
  reverse 跳过 / dry-run noop）、USDT 回流（成功划回 / 失败不阻塞 / reverse 跳过 / dry-run noop）；
- `test_hedge_purity.py`：白名单冻结测试 13 → 14（transfer 归 spot host 组，_SPOT_KEYS 5 → 6）；
- `test_hedge_review2_regressions.py`/`test_hedge_task_local.py`：preflight provider stub
  `get_snapshot` 补 `task_type` 参数（get_snapshot 签名扩展的必要适配）；
- `docs/planning/hedge-open-position-cycle-v1.md`：append-only 新增 §12「平仓现货卖出路由重设计」
  （路由规则表 / 划转时序 / USDT 回流 / 万向划转端点 / 安全要点）。

### 越界标注（2 处，需 Bookkeeper/评审知悉）

1. **`backend/services/hedge_preflight_provider.py`**：不在 dispatch Allowed Files 字面列表，但
   路由权威必须在 preflight 层——`decide_spot_route(task_type)` 的调用点只有 provider；若只改
   domain 不改 provider，create 与发单 fresh preflight 的路由漂移无法根治（COOKIE 事故根因）。
   必要性驱动：`get_snapshot` 加 `task_type` 参数（默认 'open'，开仓行为不变）。
2. **`backend/services/live_hedge_executor.py`**：`query_spot_free`/`universal_transfer` 原语
   （service 经 executor duck-typed 访问 client 能力，沿用 `query_symbol_um_qty` 先例）——
   services 层文件，Allowed Files 只列了 `hedge_open_live_client.py`，live_hedge_executor.py 为
   必要性扩展（与功能三同款越界）。

### 测试结果

- 全量：`timeout 400 python3 -m pytest backend/tests -q -p no:cacheprovider` → **1415 passed**（91s，
  含新增 16 用例；功能一/二/三逻辑未回退）。
- 前端：`node frontend/self-check.js` → **138 PASS，0 FAIL**（本任务无前端改动，回归确认）。
- 实盘零写：未对实盘发单/划转、未写 `data/*.sqlite3`；未提交 git、未移动 HEAD。

### 验收逐项

1. **路由修复**：`decide_spot_route` 单测——cap_exceeded=True 时 forward close 仍
   `(regular_spot, close_sell_regular_spot)`（复现 COOKIE 场景，cap 不再影响 close）；reverse close
   固定 papi_margin；open 路由逐字不变（forward cap/tradifi/papi + reverse papi 回归断言）；
   endpoint 映射（regular_spot → /api/v3/order）pass。
2. **划转能力**：`POST /sapi/v1/asset/transfer` 进白名单（ALLOWLIST 14 端点，冻结测试同步）；
   `universal_transfer` type 冻结（非枚举 ValueError）、签名 POST 参数断言、500 抛错不重试、
   tranId 返回 pass。
3. **划转时序（一次性 + fail-closed）**：余额够 → 不划转直卖；不足 → 划转（PM_MAIN）+ 复检；
   划转失败 → 中文错误 + `close_transfer` failed 日志（不发单）；复检不足 → fail-closed；查询失败 →
   错误；reverse close / dry-run → 跳过；`scheduled_attempt_count == 0` 仅首次（worker 接入 + 单测）
   pass。
4. **USDT 回流**：forward close 完成后 `MAIN_PORTFOLIO_MARGIN` USDT 合计划回（usdt_back_ok 日志）；
   失败 → usdt_back_failed 日志、任务仍 done（不阻塞）；金额 0/空跳过；reverse close 无回流 pass。
5. **回归**：pytest 1415 + self-check 138 全绿；功能一/二/三既有逻辑未回退（全量测试绿）。
6. **范围核对**：`git status --short` 无 `backend/ledger_flow/store.py`、`backend/ledger_flow/domain.py`、
   `data/*.sqlite3` 改动；未提交 git、未移动 HEAD、未对实盘发单/划转；越界 2 处见上。

### 行为变化说明（对实盘/后续影响）

- **实盘启用前置**：API key 万向划转权限 Human 已确认开启；实盘划转/平仓发单仍须 Human 单独授权
  （本任务只做代码 + 测试库验证）。
- forward close 现货 SELL 现在固定走普通现货账户 + 发单前余额检查/一次性划转补足 + 平仓后 USDT 划回
  统一账户——COOKIE 类事故（卖错账户 -2010）从路由层根治；reverse close 维持统一账户（还币
  AUTO_REPAY 留后续任务）。
- 当前单腿暂停的 COOKIE 任务按 Human 决定保持不动（现货 Human 手工处理）。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/hedge-position-cycle-v1-close-spot-sell-redesign.handoff.md`（本交接件）
  2. `reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/hedge-position-cycle-v1-close.handoff.md`（功能三，含事故现场）
  3. `backend/hedge_open_tasks/domain.py`（decide_spot_route task_type / 常量）
  4. `backend/hedge_open_tasks/service.py`（_ensure_close_spot_balance / _transfer_back_usdt /
     _worker_round 接入 / create_task 与 fresh preflight task_type）
  5. `backend/services/hedge_open_live_client.py` + `hedge_preflight_provider.py` + `live_hedge_executor.py`
  6. `docs/planning/hedge-open-position-cycle-v1.md` §12（重设计权威）
- 执行：Bookkeeper 核验本交接件与测试/范围，裁定 2 处越界
- 关卡：核验通过后进入统一 review-1 + review-2（HIGH_RISK：新增实盘资金划转写操作 + 路由资金语义）；
  实盘启用（划转/平仓发单）需 Human 单独授权
- 不能假设的事实：功能一/二/三/本任务均未提交（工作树改动，delivery_sha 均 pending）；close_gate 默认
  开；实盘库周期数据仍 0（未回填）；白名单已扩至 14（含万向划转 POST）；API key 万向划转权限 Human
  已确认开启但实盘未启用。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: hedge-position-cycle-v1-close-spot-sell-redesign
执行结果: completed（完成）
结果摘要: 平仓现货卖出路由重设计完成：forward close 固定普通账户+发单前一次性划转补足+复检+fail-closed、reverse close 维持统一账户、USDT 回流不阻塞；万向划转白名单 14 端点（type 冻结、写不重试）；开仓路由逐字不变；全量 1415 passed + self-check 138 PASS；2 处越界（preflight_provider/live_hedge_executor）已标注；未提交、未写实盘、未发单划转。
产物: [backend/hedge_open_tasks/domain.py, backend/hedge_open_tasks/service.py, backend/hedge_open_tasks/store.py, backend/services/hedge_open_live_client.py, backend/services/hedge_preflight_provider.py, backend/services/live_hedge_executor.py, backend/tests/test_hedge_cycle_close.py, backend/tests/test_hedge_purity.py, backend/tests/test_hedge_review2_regressions.py, backend/tests/test_hedge_task_local.py, docs/planning/hedge-open-position-cycle-v1.md, reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/hedge-position-cycle-v1-close-spot-sell-redesign.handoff.md]
检查结果: [路由修复（close+forward 固定 regular_spot 不受 cap 影响、reverse 固定 papi、open 不变）pass；划转能力（白名单 14 + type 冻结 + 写不重试 + tranId）pass；划转时序（一次性 + 复检 + fail-closed + 日志）pass；USDT 回流（成功划回 + 失败不阻塞 + reverse 跳过）pass；回归 1415+138 全绿 pass；范围核对 pass（2 处越界已标注）]
阻塞项: [none（2 处越界待 Bookkeeper/评审裁定）]
本地北京时间: 2026-08-05 21:16:54 CST
下一步模型: Bookkeeper（核验交付与范围，裁定越界）
下一步任务: 读取：reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/hedge-position-cycle-v1-close-spot-sell-redesign.handoff.md（含引用文件）；执行：Bookkeeper 核验测试/范围并裁定 2 处越界；关卡：核验通过后进入统一 review-1 + review-2，实盘启用（划转/平仓发单）需 Human 单独授权
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification（2026-08-05 代记，正式 Bookkeeper 开 stage 后复核）

- source_sha256: `3907bdd51ddbda3abcadc647626ae5aef07a832ab83df38a4bce917652940cf7`
- 核验时间: 2026-08-05 CST（无活跃 stage，ACTIVE.json=null；Human 授权当前会话代记）
- 核验命令（可复现）:
  - `python3 -m pytest backend/tests/test_hedge_cycle_close.py backend/tests/test_hedge_purity.py -q` → **53 passed**（独立复跑）
  - `node frontend/self-check.js` → **全部通过**（本任务无前端改动，回归确认）
  - `git status --short`：无 `backend/ledger_flow/store.py`、`backend/ledger_flow/domain.py`、`data/*.sqlite3` 改动
- 结论：**通过**（`reported` → 待统一评审；`delivery_sha=pending`）
- 安全面核对（资金划转写操作）：`POST /sapi/v1/asset/transfer` 白名单 14 端点；type 冻结
  `_ALLOWED_TRANSFER_TYPES`（仅 PORTFOLIO_MARGIN_MAIN / MAIN_PORTFOLIO_MARGIN，非枚举 ValueError）；
  划转在 close 任务首个 attempt 发单前一次性调用（`_ensure_close_spot_balance`），失败暂停不发单
  （fail-closed）；复检防「响应丢失但划转成功」误判；USDT 回流失败不阻塞任务（done + 任务卡日志）。
- 2 处越界裁定（Human 授权当前会话代记）：
  1. **`hedge_preflight_provider.py`**：验收驱动正当扩展——`decide_spot_route(task_type)` 唯一调用点
     在 provider，不改则 create/fresh preflight 路由漂移（COOKIE 事故根因）无法根治；
     `get_snapshot` 加 `task_type` 参数（默认 'open'，开仓行为不变）。不递增 rework（缺陷在 packet）。
  2. **`live_hedge_executor.py`**：`query_spot_free`/`universal_transfer` 原语，沿用
     `query_symbol_um_qty` 先例（service 经 executor duck-typed 访问 client）。不递增 rework。
- 记录依据：`AGENTS.md` §8 + Human 2026-08 拍板「全部开发后统一 review」；本块不授权实盘；
  实盘启用（划转/平仓发单）需 Human 单独授权。
