# Task Handoff: hyperliquid-funding-compare-impl-claude-glm

## Source Report (author-only; immutable after task end)

- task_id: `hyperliquid-funding-compare-impl-claude-glm`
- role: `Implementer` / target model: `claude_glm` (provider: zhipu)
- stage_id: `2026-08-23-hyperliquid-funding-compare-v1`
- created_at: 2026-08-23 12:08:59 CST
- base_sha: `dd1283398efcccfc3ddd6c1c5e281076b97c3427`（dispatch 指定的实现基线；
  `status.json.base_sha` 为阶段评审锚 `25cc8fe4e31194261dd48415f085bc6f9fda062d`，
  Bookkeeper 封存时以 status.json 为准）
- delivery_sha: `pending`（本 handoff 随唯一交付 commit 入库）

### 任务背景与实现范围

设计权威 `docs/planning/hyperliquid-funding-compare-v1.md` rev3（固定于
`fe91abb`）。在既有费率行情表前四个费率列内每行下方加一行 Hyperliquid
同口径数值；市场表下方追加「HL 数据时间」，不可用/陈旧时红色高亮。
只读展示，未触碰任何下单、保证金、借币、平仓、账户路径；
`SPOT_SYMBOL_MAP` 现有条目与币安侧费率/年化算法零改动。

实际修改（全部在 dispatch 文件边界内）：

- `backend/adapters/hyperliquid_public.py`（新增）：`POST /info`
  `metaAndAssetCtxs` main+xyz 原子组适配器；任一 POST 失败即整组失败且
  第二个 POST 不再发出；funding 必须是可转有限 Decimal 的**字符串**
  （JSON number 拒绝，同 bookTicker 的 Decimal wire 纪律），否则整源
  ValueError。
- `backend/domain/normalize.py`：`HL_SYMBOL_DENY`（`xyz:BB`/`xyz:QNT`），
  形制照抄 `SPOT_SYMBOL_DENY`。
- `backend/domain/snapshot.py`：纯函数 `build_hyperliquid_matches`
  （DENY → isDelisted → raw-name exact → 类别校验 main↔PERPETUAL /
  xyz↔TRADIFI_PERPETUAL）；`build_rows` 新增 `hyperliquid_by_sym` 入参并
  恒显式输出行内 `hyperliquid` 键（null 或 block）；`assemble_snapshot`
  恒输出顶层 `hyperliquid_data_time`。
- `backend/services/snapshot_service.py`：独立 source_id `hyperliquid`
  （60s 组，与 premium_index 同频独立）；成功才缓存并打 `updated_at`
  时间戳；失败**弃缓存**（无 warm last-good 投影，D6/A8），下一 tick 即
  重试；不在 `force_account_panels` 强制刷新集合（「更新缓存」按钮不刷 HL）。
  `_hl_client` 在 `start_worker()` 惰性构造——offline、kill switch、未启动
  worker 的组合（含既有直驱 `_scheduled_tick` 的测试 stub）在结构上零 HL
  网络请求（A9c），`server.py` 零改动。
- `backend/config.py`：`hyperliquid_base_url` / `hyperliquid_request_timeout`
  （与既有 base_url 同策略，不做环境覆盖）。
- `schemas/api/public-market/snapshot.schema.json`：顶层
  `hyperliquid_data_time` 与行内 `hyperliquid` block 均注册且**均非
  required**（IC-1：既有 offline fixture 不带新键继续通过校验，有专测）。
- `frontend/index.html`：四列（资金费率/结算时间/日费率/年化 24h）第二行
  `hl-subline`（main `HL` / xyz `HL·xyz` 标签；无对手显示 `—`；结算时间
  第二行恒「每小时」不显示时刻）；`filter-show-hl` 开关默认开，关闭后零
  标记残留（A14）；`market-snapshot-meta` 改写 innerHTML，HL 数据时间为
  独立 `<span id="hl-data-time">`，unavailable（缺失/null/非法 ISO）显式
  并入标红条件（IC-2：`isStaleTime(NaN)` 恒 false），红色只作用于 HL 片段。
- `frontend/self-check.js`：注册 `filter-show-hl`；meta 断言改读 innerHTML
  （mock 不镜像 innerHTML→textContent）；新增 33c-hl 块。
- `docs/api/public-market-contract.md`：追加 v0.22 修订（新公共源、row
  block、顶层字段、空值/失败语义、offline 零网络）。
- `backend/tests/test_hyperliquid_compare.py`（新增，22 用例）；
  `backend/tests/test_private_client.py`：urlopen 守卫允许集登记
  `hyperliquid_public.py`（它就是新的指定 HTTP 客户端）。

### 设计稿 §9 全部 18 条验收 → 证据映射

| # | 证据（测试名 / 命令） |
|---|---|
| A1 | `test_a1_deny_blocks_even_when_category_would_match`（类别一致、仅 DENY 能拦） |
| A2 | `test_a2_synthetic_cross_category_collision_is_blocked`（main 上的 TSLA、xyz 上的 DOGE，不依赖 BB/QNT 枚举） |
| A3 | `test_service_a6_a9b_partial_match_has_timestamp_not_null`（HYPE → dex main）+ `test_a3_hype_row_and_decimal_string_wire` |
| A4 | `test_a4_binance_four_columns_unchanged_and_order_stable`（四列逐格相等 + 行序稳定）；服务层另断于 A6/A7 测试 |
| A5 | `test_a5_interval_4h_and_8h_each_correct`（4h ×6 / 8h ×3，未统一 8h） |
| A6 | `test_service_a6_a9b…`（ZKUSDT `hyperliquid == null` 且时间戳非 null） |
| A7 | `test_service_a7_cold_start_failure_publishes_with_null_timestamp`（发布不阻断、四列照常、时间戳 null）；前端标红见 self-check 33c-hl |
| A8 | `test_service_a8_success_then_failure_clears_values_and_timestamp`（不留旧值旧时间戳，恢复成功即整组恢复） |
| A9 | `test_adapter_a9_invalid_funding_fails_whole_source` + `test_adapter_a9_shape_violations_fail_whole_source` + `test_service_a9_valueerror_same_oracle_as_source_failure`（与 A7 同一 oracle） |
| A9b | `test_service_a6_a9b_partial_match_has_timestamp_not_null`（时间戳有值不标红；前端 oracle 在 self-check 33c-hl） |
| A9c | `test_service_a9c_offline_zero_hl_requests_all_null_schema_ok`（零调用 + 全 null + schema 通过） |
| A10 | `test_a3_hype_row_and_decimal_string_wire` + `test_a10_vectors_negative_scientific_zero`（全 str、定点串） |
| A11 | frontend/self-check.js 33c-hl（`HL 每小时`，第二行片段断言无数字） |
| A12 | `test_a12_alias_and_multiplier_symbols_show_no_hl_row`（GOLD/kPEPE 代表；14 为采样值不作常量断言）+ self-check 缺键行 `—` |
| A13 | `test_adapter_a13_success_exactly_two_posts`（恰两次、dex 各一次）、`test_adapter_a13_first_post_failure_short_circuits`（首个失败第二个不发）、`test_service_a13_one_refresh_exactly_two_posts_and_due_gate`（60s 内不重取）、`test_d4_predicted_fundings_never_called` |
| A14 | frontend/self-check.js 33c-hl（默认开、关闭零残留、重开恢复） |
| A15 | frontend/self-check.js 33c-hl（HL/HL·xyz 标签、近 24h 列无第二行、搜索无 HL 数据行仍可见）+ A4 行序稳定 |
| A16 | `node frontend/self-check.js` 全部通过（167 PASS，含 33c-hl） |

### 命令与结果（可复现）

- `python3 -m pytest backend/tests/test_hyperliquid_compare.py -q` → **22 passed**
- `python3 -m pytest backend/tests/ -q` → **2023 passed, 1 failed**。唯一失败
  `test_private_client.py::test_urlopen_only_in_designated_http_clients` 为
  **先于本 stage 的既有缺陷**：守卫允许集从未登记 2026-08-12（v0.19）引入的
  `backend/services/public_ip_service.py`。已用 `git stash` 在基线
  `dd12833` 上复现同一失败（同一 offender、同一条断言）；本交付加入
  `hyperliquid_public.py` 后失败面与基线完全一致（仍是且仅是
  public_ip_service.py）。按 developer-discipline §2 不并入本次修复，
  报请 Bookkeeper 记为后续项。
- `node frontend/self-check.js` → **全部自检通过**（exit 0）
- offline 冒烟：`SnapshotService(Config(offline=True)).build_snapshot()` →
  647 行、`hyperliquid_data_time: None`、schema 校验通过。

### 实现中的关键决策（评审关注点）

1. **`_hl_client` 惰性构造于 `start_worker()`**（而非 `__init__`）：既有
   live-mode 测试 stub（`test_background_worker` 等直驱 `_scheduled_tick`）
   不知 HL 存在，若 `__init__` 构造真实客户端会令既有套件发真实网络请求，
   违反「测试套件零网络」。惰性构造使「未启动 worker ⇒ 零 HL 请求」成为
   结构保证，同时 `server.py` 零改动（dispatch 的停止条件未触发）。
2. **失败弃缓存**而非置失败标志：等价于 funding-history 既有「失败不缓存、
   下一 tick 重试」先例，且天然满足 D6「不投影 warm last-good」与 A8
   「不留旧时间戳」——无第二个状态位。
3. **funding_1h 保留原始精度**（`1e-5` 规范化为 `0.00001` 仅为 schema
   定点串兼容），不量化到 8 位——与币安 `last_funding_rate` 直传 raw 串的
   wire 风格一致；`daily_rate`/`annualized_24h` 复用既有 8 位量化链。
4. **「HL·xyz 标签置于四格 subline」**：设计只要求第二行带来源标签，未定
   per-cell；每格带标签可避免脱离首列语境时误读为 HL 值。

### 未完成事项 / 后续项

- `public_ip_service.py` 未入 urlopen 守卫允许集（既有缺陷，见上，建议
  Bookkeeper 记后续项，不在本交付修）。
- 设计 §8 既有风险 unchanged（xyz 休市费率退化不加提示语 D7；行高翻倍由
  开关缓解）。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-impl-claude-glm.handoff.md`
  2. `docs/planning/hyperliquid-funding-compare-v1.md`
  3. `docs/api/public-market-contract.md`（v0.22 节）
  4. `backend/adapters/hyperliquid_public.py`
  5. `backend/domain/snapshot.py`（`build_hyperliquid_matches` / `build_rows` / `assemble_snapshot`）
  6. `backend/services/snapshot_service.py`（`_refresh_due_sources` HL 块 / `start_worker` / `_eligible_rows` / `_assemble`）
- 执行：Bookkeeper 核验交付 commit（`git show <delivery_sha>`），复跑
  `python3 -m pytest backend/tests/test_hyperliquid_compare.py -q` 与
  `node frontend/self-check.js`，裁决既有守卫失败是否记后续项，然后封存
  delivery_sha 并派发 Review-1。
- 关卡：HIGH_RISK 路由的 Review-1（`base_sha..delivery_sha` 固定区间，
  `base_sha` 以 status.json `25cc8fe…` 为准）；合并/部署/实盘须 Human 另行授权。
- 不能假设的事实：HL 采样计数（244/78/14/2 等）是 2026-08-23 时点值，
  不是契约；`hyperliquid_data_time` 与行内 `hyperliquid` 在 schema 中非
  required 但 producer 恒显式输出；「更新缓存」按钮不刷 HL；前端零直连。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: hyperliquid-funding-compare-impl-claude-glm
执行结果: completed（完成）
结果摘要: HL 对比行已实现：适配器 main+xyz 原子组、DENY+类别校验 fail-closed 匹配、
build_rows 行内 block、独立 source_id 失败弃缓存、schema 注册非 required、前端四列
第二行+开关+HL 数据时间独立 span 标红（IC-1/IC-2 均落实）。设计 §9 全部 18 条验收
有测试证据；后端 2023 passed（1 失败为基线已存在的 public_ip 守卫遗漏，stash 复证
与本交付无关），self-check 全过。已提交本分支，未合并/推送/部署。
产物: [backend/adapters/hyperliquid_public.py, backend/domain/normalize.py,
backend/domain/snapshot.py, backend/services/snapshot_service.py,
backend/config.py, schemas/api/public-market/snapshot.schema.json,
frontend/index.html, frontend/self-check.js, docs/api/public-market-contract.md,
backend/tests/test_hyperliquid_compare.py, backend/tests/test_private_client.py,
reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-impl-claude-glm.handoff.md]
检查结果: [
A1-A12 后端 22 用例全过 pass（pytest test_hyperliquid_compare.py 22 passed）,
A13 原子组恰两次 POST/失败短路/60s 内不重取/零 predictedFundings pass,
A7-A9c 失败 oracle：时间戳 null+全行 null+发布不阻断+offline 零请求 pass,
A16 self-check 全过（node frontend/self-check.js，含 33c-hl 新块）pass,
既有后端套件 2023 passed 零回归 pass,
唯一失败 test_urlopen 守卫为基线既有（public_ip_service.py 未登记，stash 于
dd12833 复现同因）pass,
IC-1 schema 注册非 required：legacy 快照剔除新键后校验通过（专测）pass,
IC-2 unavailable 显式标红+独立 span 只染 HL 片段（self-check 断言）pass
]
阻塞项: [none]
评审结论: none（实现任务无此项）
问题记录: none
修复要求: none
本地北京时间: 2026-08-23 12:08:59 CST
下一步模型: claude（Bookkeeper opus5）
下一步任务: 读取：reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-impl-claude-glm.handoff.md、reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/status.json；执行：核验交付 commit 与两条复现命令（pytest backend/tests/test_hyperliquid_compare.py、node frontend/self-check.js），封存 delivery_sha，把 current_task.state 置 verified 路由 Review-1；关卡：HIGH_RISK Review-1（base_sha 25cc8fe..delivery_sha），既有 public_ip 守卫遗漏是否记后续项由 Bookkeeper 裁定
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

（由 Bookkeeper 核验后追加）

## Errata (append-only)

（暂无）
