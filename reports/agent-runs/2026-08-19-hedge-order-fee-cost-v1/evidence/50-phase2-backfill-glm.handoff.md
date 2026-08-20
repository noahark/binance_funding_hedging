# Task Handoff: 50-phase2-backfill-glm

## Source Report (author-only; immutable after task end)

- task_id: `50-phase2-backfill-glm`
- role: `Implementer`
- target model: `claude_glm`（provider `zhipu_glm`）
- stage_id: `2026-08-19-hedge-order-fee-cost-v1`
- created_at: 2026-08-20 11:56 CST
- base_sha: `f510c562667312a0ebf8d531e4add3f95acbe7e1`（`git rev-parse HEAD`）
- delivery_sha: pending（dispatch 未授予 commit；交付提交后由 Bookkeeper 解析）

### 任务背景

阶段二（T3）历史数据回补（10-design §2.2/§3/§4.3/§7.1/§8）：公共成交拉取与
手续费折算组件（断点 3：回补与 T5 下单链共用一套，禁止各写一套）、公开 BNB
1m K 线拉取、独立回补脚本（游标断点、限速防爆、running 保护、纯离线单测）。
本任务**只交付脚本与单测**，未对实盘库执行任何带网络外发的 live 回补。

### 实际修改范围（全部在 dispatch Assigned Files 内）

1. `backend/hedge_open_tasks/fee_fetcher.py`（新建，共享组件）：
   - 纯逻辑：`group_trades`（§4.1 分组：BNB / 恰一种 ∈{USDT,base} / 多种或
     第三种资产不全）、`um_query_window`（B1a 分钟级窗：dispatched→
     last_query，缺列回退 ±10min，>7 天 clamped）、`route_for_endpoint`。
   - `fetch_leg_fees(transport, …)`：路由 → 拉取 → 截断检查（`len>=1000`
     判不全禁求和）→ UM 本地 orderId 过滤（滤空=未知）→ 分组 → BNB 冻价
     （`bnb_close_price(dispatched_ms)`，缺价数量仍写、标不全）。
     `RateLimited`（429/418）上抛整轮停；其余失败折叠为 `columns=None`。
   - `BackfillEngine`：running 拒绝启动 → 选腿（`list_legs_missing_fees`）→
     逐腿拉取折算 → `update_leg_fees` 写 / failed 集记因 → 每腿后落盘断点
     （`save_progress`：cursor + failed{id:reason}）；签名 GET 间强制 1s
     节流（注入 sleep）；dry-run 零网络零写入（含断点文件）。
   - 纯度：不 import 网络原语、不引用服务层（purity import 扫描绿）。
2. `backend/hedge_open_tasks/store.py`：`update_leg_fees`（四列全空才写的
   幂等守卫 UPDATE）+ `list_legs_missing_fees`（FILLED + order_id + 四列空
   + id>游标 + 排除失败集，带 attempt→task 身位列，只读）。
3. `backend/services/hedge_open_live_client.py`：ALLOWLIST 增 3 条成交明细
   GET（`/api/v3/myTrades`、`/papi/v1/margin/myTrades`、
   `/papi/v1/um/userTrades`）+ 路径常量 + `TRADES_LIMIT=1000` + 三个签名
   GET 方法（spot/margin 带 orderId；um 无 orderId、带分钟窗参数）。
4. `backend/adapters/binance_public.py`：`fetch_kline_close(symbol, *,
   start_time_ms)`——公开 `/api/v3/klines` 1m `limit=1`，close 只收原始
   字符串，空/数字类型 → None；offline → None。无签名，不进签名白名单。
5. `scripts/backfill-leg-fees.py`（新建，薄 CLI）：装配真传输（签名客户端 ×3
   + 公开 K 线）；`--db/--progress/--limit/--dry-run`；offline 或缺凭证拒绝
   启动（exit 1）；429/418 中断 exit 2（断点已保存）；绝不写 close_log。
6. `backend/tests/test_hedge_purity.py`：`_MONEY_ZERO_SCOPE` 增
   `scripts/backfill-leg-fees.py`；`_FROZEN_ALLOWLIST`/`_PAPI_KEYS`/
   `_SPOT_KEYS` 与数量钉（16→19、10→12、6→7）同步 3 条新 GET。
7. `backend/tests/test_backfill_leg_fees.py`（新建，37 用例全离线）：§8 全部
   夹具——纯 BNB / 纯 USDT / BNB+USDT / 本币 / 第三种资产（含与 BNB 并存）/
   多种其他资产 / 全零佣金 / 坏形状 fail-closed / 合约分钟窗 5 形态（含 >7d
   clamp、双缺、时序倒置）/ 截断不求和（um）/ UM 本地滤 orderId 与滤空未知 /
   冻价成功与缺价降级 / K 线抛错降级 / RateLimited 上抛 / 路由参数正确性 /
   store 写入幂等与选择器过滤 / 断点往返与坏文件回退 / 游标推进（成功与
   失败都推进）/ 已写跳过 / 已失败重跑不打 / running 拒绝 / 限速停+断点 /
   节流 1 次 / dry-run 零网络零写入 / close_log 哨兵行原样 / 签名客户端三
   方法参数与 URL / 公开 K 线 live+offline / 脚本可编译。

### 设计裁决与解释（供 Review 核）

1. **UM 窗 >7 天（B1a「截到 7 天并视该腿为不全」）**：实现为**不发那次 GET**、
   直接 `um_window_clamped_7d` 判失败（四列保持空）。理由：截断后的窗口
   已不可信，无论查到与否都必须标不全，查询只会白耗签名配额。若 Review
   认为应查询后丢弃结果，改 `fetch_leg_fees` 一个分支即可。
2. **全零佣金**（所有成交 commission 合计为 0）：判 `no_fee_found` 失败、
   四列保持空。D1 的「空=没有」没有「完整零」的表达位，宁欠报不臆造资产名。
3. **零合计资产不参与分类**：`BNB 0.001 + USDT 0` 不会因 USDT 侧零佣金行
   误判成两种资产（§8 的 BNB+USDT 夹具语义按「真扣的资产」算）。
4. **UM 是否支持 orderId 未做只读确认**（须 Human 授权的 live 调用），按
   B1a 预设的「无 orderId」分支实现（分钟窗 + 本地过滤）。T5/后续可用一次
   授权确认翻转。
5. `dispatched_at_us=0` 按缺失处理（falsy，与仓内时间列惯例一致）。
6. 限速（429/418）的腿**不推进游标**（该腿未完成，冷却后重跑会再试）；
   其余一切失败（HTTP 错、空、滤空、不可折算、截断、clamped）都推进游标并
   进 failed 集，重跑不再打。
7. `update_leg_fees` 的 WHERE 带四列全空守卫：已写入是该腿历史真值，二次
   写（哪怕同值）被拒；引擎把「守卫拒绝」计为已写入（并发场景不改写）。
8. dry-run 也会构造 Store（跑幂等迁移）；对不存在的 --db 路径会建空库后
   报 0 候选——dry-run 的「零写入」指不写费用列与断点，不含库文件创建。
9. dispatch `skill: agents/skills/backend-implementer.md` **不存在**（skills
   目录只有 senior-developer / minimal-change-engineer）；本任务为实现类，
   沿用本会话已加载的 `agents/skills/senior-developer.md`，偏差在此具名。

### 命令与结果

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_backfill_leg_fees.py
  backend/tests/test_hedge_purity.py -q` → **68 passed**（验收 7）。
- 邻域回归：`pytest backend/tests/test_hedge_store.py
  backend/tests/test_hedge_open_live_client.py backend/tests/test_hedge_leverage.py
  backend/tests/test_hedge_api.py -q` → 147 passed；
  `pytest`（BinancePublicClient 相关 3 文件）→ 93 passed。
- 脚本冒烟（/tmp 临时库）：`--dry-run` → 候选 1 条（无 order_id 的腿被
  正确排除）、断点文件未创建、exit 0；live 模式无凭证 → 「拒绝启动」exit 1。
- 本机未对 `data/hedge-open-tasks.sqlite3`（实盘库）执行任何读写；全部
  验证在 tmp_path 与 /tmp 临时库。

### 不能假设的事实 / 交接边界

- live 回补（对实盘库 + 真实签名 GET）**未执行**，须 Review 验收后由 Human
  单独授权；建议首跑 `--limit 5` 小批试跑并盯 `readyz` 与服务日志。
- 有 running 对冲任务时脚本拒绝启动（exit 1）；不是自动降速——§4.3 允许
  二选一，取了更保守的拒绝。
- 腿的冻结价语义：回补 = 成交分钟公开 1m K 线收盘价；T5 实时路径须换注入
  D4 现价提供方（`FeeTransport.bnb_close_price` 是唯一注入位），且 T5 必须
  复用 `fetch_leg_fees`（断点 3），不得另写一套分组。
- 聚合读取侧（持仓/历史 close_log 的折 U 合计）不属本任务：腿四列的 NULL
  语义（价格缺=数量在、折 U 不全）由 T2 后半/T4 消费。

### 未完成事项（按设计属后续任务）

- T5：两写入站点（`resolve_attempt` / `resolve_leg_from_query` 终态 commit
  后）各接至多 1 次 `fetch_leg_fees` + `update_leg_fees`。
- UM orderId 支持性的授权只读确认（见设计裁决 4）。
- live 回补执行（Human 授权后）。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/50-phase2-backfill-glm.handoff.md`
  2. `backend/hedge_open_tasks/fee_fetcher.py`
  3. `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/status.json`
- 执行：Bookkeeper 核验阶段二回补交付（复跑上方两条 pytest 命令与脚本
  dry-run 冒烟），随后按 §8 路由准备 Review-1（跨 provider，Kimi 优先）。
- 关卡：Human 启动评审窗口；live 回补另需单独授权。
- 不能假设的事实：T5 必须复用 `fetch_leg_fees`；UM 无 orderId 分支未经
  live 确认；>7d 窗与全零佣金两处 fail-closed 读法见「设计裁决」1/2，
  Review 若不同意按该节翻转。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: 50-phase2-backfill-glm
执行结果: completed（完成）
结果摘要: 新建共享组件 fee_fetcher.py（分组折算、UM 分钟窗、截断禁求和、BNB 冻价、BackfillEngine 断点/节流/running 保护）与回补脚本 scripts/backfill-leg-fees.py（--dry-run 零网络零写入、缺凭证/离线拒绝、429/418 立停落盘）；签名客户端加 3 条成交明细 GET，binance_public 加公开 1m K 线收盘价；money-zero 扫描范围纳入脚本。指定两文件 68 passed，邻域 240 passed。未做任何 live 回补（红线）。
产物: [backend/hedge_open_tasks/fee_fetcher.py, scripts/backfill-leg-fees.py, backend/tests/test_backfill_leg_fees.py, backend/hedge_open_tasks/store.py, backend/services/hedge_open_live_client.py, backend/adapters/binance_public.py, backend/tests/test_hedge_purity.py, reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/50-phase2-backfill-glm.handoff.md]
检查结果: [验收1 ALLOWLIST 三 GET + 冻结集/数量钉 16→19/10→12/6→7 pass；验收2 K 线公开无签名挂 binance_public 且断言不进签名白名单 pass；验收3 UM 分钟窗（B1a 回退与 7d clamp）+ limit=1000 截断判不全禁求和 pass；验收4 断点推进（成功与失败都推进）、已写跳过、已失败重跑不打、close_log 哨兵行原样 pass；验收5 429/418 立即停+断点落盘、running 任务拒绝启动 pass；验收6 money-zero 范围含回补脚本且全绿 pass；验收7 指定两文件 68 passed + 邻域 147/93 passed + dry-run 冒烟（无 order_id 腿正确排除、断点不建、无凭证拒绝 exit1）pass；验收8 安全红线：未对实盘库外发任何请求，live 回补留待 Human 授权 pass]
阻塞项: [none]
本地北京时间: 2026-08-20 11:56:29 CST
下一步模型: gemini-3.7-flash（Bookkeeper，agy 窗口）
下一步任务: 读取：reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/50-phase2-backfill-glm.handoff.md；执行：核验阶段二回补交付并按 §8 准备 Review-1（跨 provider）；关卡：Human 启动评审窗口，live 回补另需单独授权
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- **verification_time**: 2026-08-20 11:57:45 CST
- **source_sha256**: `64acae97288c11fe8284660e6056652297c0ebf7ad768d2939d6cfd41abe9ca4`
- **status_revision**: 14 -> 15
- **base_sha**: `f510c562667312a0ebf8d531e4add3f95acbe7e1`
- **delivery_sha**: `831e255492628fded3720f9bcc68489256410788`
- **verdict_checks**:
  1. `ALLOWLIST 三条新 GET 与数量钉同步`: pass
  2. `binance_public.py 增加公开 1m K 线方法`: pass
  3. `fee_fetcher.py 共享组件与分钟窗/截断安全`: pass
  4. `scripts/backfill-leg-fees.py 游标断点与纯离线单测`: pass
  5. `money-zero 纯度守卫扫描`: pass（`pytest backend/tests/test_backfill_leg_fees.py backend/tests/test_hedge_purity.py` 68 passed）
  6. `邻域回归测试`: pass（`pytest backend/tests/test_hedge_store.py ...` 147 passed）
  7. `dry-run 冒烟测试`: pass（--dry-run 零网络零写入正常 exit 0）
  8. `安全红线`: pass（未对外执行 live 实盘回补）
- **verification_status**: `verified`

## Errata (append-only)
