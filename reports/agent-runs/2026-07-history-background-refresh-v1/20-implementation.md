# Implementation Report — `2026-07-history-background-refresh-v1`

> 状态：**DONE — T1–T9 全部实现并通过测试**。本报告覆盖实际源码改动、关键并发/
> 失败语义、测试结果与证据状态。前一次（BLOCKED）报告所述 macOS App Management
> 写入阻塞已由操作者解除，本会话在解除后完成了全部实现。

## 1. 实现者身份

- provider identity：`zhipu_glm`（`claude_glm`）
- model：`glm-5.2`（`glm-5.2[1m]`）
- skill：`senior_developer`（`agents/skills/senior-developer.md`），遵守
  `agents/developer-discipline.md`
- session ID：`9cc72c7a-1f7f-463c-832a-380bef105578`（harness 当前会话）
- 角色边界：唯一实现作者；未承担 bookkeeper / reviewer / fix author 职责；
  **未调用任何其它模型或 subagent**。

## 2. T1–T9 完成映射

| 任务 | 状态 | 落点 |
|---|---|---|
| T1 `config.py` kill switch / tick / batch / timeout + env | **完成** | `background_refresh_enabled`、`background_tick_seconds`、`history_sweep_batch_size`、`refresh_deadline_seconds`、`funding_history_cache_ttl_seconds` 及对应 `_env_bool`/`_env_int` |
| T2 `private_client.py` force-TTL exact-key bypass | **完成** | `_evict(method,path,params)` 仅移除 3 个单资产键；`force=True` 经由 `fetch_cost_leg_chain` / `fetch_max_borrowable` 入口 |
| T3 `binance_public.py` per-symbol premiumIndex 适配器 | **完成** | `fetch_premium_index_for(symbol)` 只读 GET |
| T4 `domain/snapshot.py` default-view 选择器 + 单行投影 | **完成** | `default_view_history_symbols(rows)`；单行投影经 `PublishedState.rows_by_symbol` 在 service 层完成 |
| T5 `snapshot_service.py` PublishedState + worker + 命令队列 + 生命周期 | **完成** | `PublishedState`（冻结）、`RefreshSymbolCommand`、守护线程、`start_worker`/`stop_worker`（幂等/及时）、bootstrap、deadline timeout |
| T6 `snapshot_service.py` build_snapshot 拆分 + all-valid-cache 组装 + get_snapshot 读语义 + get_funding_history 纯投影 | **完成** | live `get_snapshot()` 只读 `_published_state`；`get_funding_history()` 零上游、零缓存写；`_all_valid_history()` 仅合并未过期成功项 |
| T7 `snapshot_service.py` symbol-snapshot + refresh 命令处理 + 失败矩阵 + deadline 闸门 | **完成** | `get_symbol_snapshot(symbol)`、`submit_refresh`（同 symbol 合并）、`_handle_refresh_command`（deadline 闸门 + 失败矩阵） |
| T8 schema + server 路由 + 503 + 生命周期钩子 | **完成** | `schemas/api/public-market/symbol-snapshot.schema.json`（跨文件 `$ref`，`additionalProperties:false`）；`server.py` 路由 + 503 + worker 生命周期钩子 |
| T9 frontend + self-check + 测试 + 证据 | **完成** | `index.html`（`patchRow` 单行替换 + `fetchSymbolSnapshot` + 1s 防连点 + in-flight 守卫 + stale 校验）；`self-check.js`（symbol-snapshot 契约 + 新增 #57–#59）；公开样本 + 脱敏审计模板 |

## 3. 实际修改文件

修改（已跟踪）：

```text
backend/config.py
backend/domain/snapshot.py
backend/services/private_client.py
backend/services/snapshot_service.py
backend/adapters/binance_public.py
backend/app/server.py
backend/tests/test_config.py
backend/tests/test_funding_history.py
backend/tests/test_funding_history_endpoint.py
backend/tests/test_private_client.py
frontend/index.html
frontend/self-check.js
```

新增（本阶段产物）：

```text
backend/tests/test_background_worker.py          # 生命周期/节奏/选择器/缓存（17 tests）
backend/tests/test_symbol_snapshot_endpoint.py   # 端点契约/失败矩阵/force-TTL 端到端（20 tests）
schemas/api/public-market/symbol-snapshot.schema.json
```

清理：删除了前次 BLOCKED 尝试遗留的空残留文件 `backend/config.py.new`（0 字节）。

> 注：`00-intake.md` / `10-design.md` / `11-adr.md` 的工作区改动是本会话之前
> （design/bookkeeper 阶段）就存在的，**非本实现会话所改**，本会话未触及
> intake/task/design/ADR/breakdown/status.json/70-handoff 等单写文件。

## 4. 关键并发 / 失败语义

**单写入器不可变发布（single-writer immutable publication）**

- 后台守护线程**独占**所有域缓存写入（`_base_raw`、`_funding_history_cache`、
  `_last_private_inputs`）与唯一的发布操作；HTTP 请求线程只提交命令 / 读
  `PublishedState`。无第二缓存生产者。
- `PublishedState` 为冻结 dataclass，携带单调递增的 `published_version` 与由同一
  `snapshot["rows"]` 派生的 `rows_by_symbol` 索引；发布是一次引用替换
  （`self._published_state = new`），读者始终拿到一个完整自洽的快照。

**RefreshSymbolCommand（点击路径）**

- 同 symbol 并发点击在 `submit_refresh` 中**合并为同一条命令**（合并键是 symbol，
  共享同一个 `deadline_monotonic` 发布闸门）；不同 symbol 各自一条命令。
- `_handle_refresh_command` 暂存 I/O（premium/history + force-TTL 该资产），在
  提交缓存 + 发布之前做 `time.monotonic() >= deadline_monotonic` 闸门检查：
  - I/O 在窗口内完成 → 提交缓存 + 发布一次（`refresh_status="ok"`，`published_version` 恰好 +1）；
  - I/O 在窗口外完成（第 31 秒模拟）→ **不提交任何缓存变更、不发布**，保留上次
    `PublishedState`（`refresh_status="timeout"`，`_published_state` 引用不变）；
  - assembly/validation 失败 → `refresh_status="timeout"`，`error="assemble_failed:…"`，不发布。

**失败矩阵（refresh_status / warnings / HTTP 状态）**

- history upstream failure → `partial` + warning `funding_history_unavailable`（失败不缓存、不毒化、不删除已发布态）；
- premium upstream failure → `partial` + warning `premium_refresh_failed`；
- assemble 失败 → `timeout` + `assemble_failed:…`；
- 端点：`400 invalid_symbol` / `404 symbol_not_found` / `503 snapshot_not_ready`（首次发布前）/ `200`（单 `row`，无 `rows` 数组）。

**force-TTL exact-key bypass（签名隔离）**

- 点击路径 `force=True` 时 `_evict` **仅移除 3 个单资产键**：单资产 next-hourly-rate
  （E2）、单资产 dailyInterestRate（E2b）、`maxBorrowable`；共享多资产 batch 键、
  `account/info`、`allAssets`、`allPairs`、`crossMarginData` **存活**。
- 该行为由 `test_click_force_ttl_evicts_only_single_asset_keys` 用**真实
  `PrivateClient` + monkeypatched `urlopen`**（脱敏 fake key `"k"*64/"s"*64`，
  不触网、无真实签名）端到端验证。`hmac`/`hashlib`/签名拼装仍只在 `private_client.py`
  内，单一 HMAC 出口、GET 白名单。

**默认视图选择器（替代 top-N 预热）**

- `route_class != "PERP_ONLY_EXCLUDED"` 且 `abs(Decimal(daily_funding_rate)) >
  Decimal("0.00030000")`（严格大于；null/无效/非数值排除）。
- 串行滚动预热：每个 tick ≤ `history_sweep_batch_size` 条缺失/过期历史，稳定光标
  （`cursor mod n` 在候选集缩小时回绕，不跳号）。

**前端（§11）**

- `openDrawer` 每次点击都触发 `fetchSymbolSnapshot`（即便 hasPreloaded）；
  hasPreloaded 行立即显示（`drawerLoading=false`）但后台刷新。
- `patchRow(symbol)` 只替换选中行的 `<tr>` outerHTML + 抽屉，**移除点击路径的全表
  `renderTable()`**；`bindRowSelection` 经 `data-bound` 标记幂等。
- 1 秒防连点（`clickGuardUntil`）+ in-flight 忽略（`inflightSymbol`，§11.3）；
  stale 响应身份校验：`schema_version === 'public-market-symbol-snapshot/v1'` 且
  `data.symbol === symbol` 且 `data.row` 为对象且**无** `rows` 数组，否则丢弃并标
  `history_response_invalid`；迟到响应沿用既有 `drawerRequestId/isActive()` 守卫。

## 5. 测试命令与结果

| 命令 | 结果 |
|---|---|
| `python3 -m pytest backend/tests -q -p no:cacheprovider` | **282 passed**（基线 244 → +38） |
| `python3 -m pytest backend/tests/test_background_worker.py backend/tests/test_symbol_snapshot_endpoint.py -v` | **37 passed**（17 + 20） |
| `node frontend/self-check.js` | **全部通过**（含新增 #57 缺 row / #58 含 rows 数组 / #59 in-flight 守卫） |
| `git diff --check` | exit 0（无空白/冲突标记） |
| symbol-snapshot schema load + meta 验证（`referencing.Registry`） | 通过：`$ref → snapshot.schema.json#/$defs/row` 可解析，`additionalProperties:false` |

完整命令与原始输出已**追加**至：

```text
reports/agent-runs/2026-07-history-background-refresh-v1/60-test-output.txt
```

（前次 BLOCKED 报告中该文件因 provenance 无法追加；本次环境阻塞解除后已成功追加。）

> 已知真实 bug 修复：`_load_symbol_snapshot_schema` 原先用裸 `jsonschema.validate`
> 无法解析 symbol-snapshot schema 对 `snapshot.schema.json#/$defs/row` 的跨文件
> `$ref`。改为构造 `referencing.Registry` + `Draft202012Validator` 并以
> `.validate(payload)` 调用——这是影响线上 `get_symbol_snapshot` 的真实缺陷，
> 已修复并由测试覆盖。

## 6. 证据状态

**公开样本（AGENTS.md 硬门：契约修订须带原始公开样本）——已满足：**

```text
reports/api-samples/2026-07-history-background-refresh-v1/20260713T000000Z/
  raw/fapi-v1-premiumIndex-BTCUSDT.json          # 真实 GET /fapi/v1/premiumIndex?symbol=BTCUSDT
  raw/fapi-v1-fundingRate-BTCUSDT-limit1000.json # 真实 30 天 8h 结算历史（90 条）
  capture.md                                     # 证据说明
  signed-audit-template.json                     # 脱敏审计字段模板（明确标注非事实证据）
```

**脱敏签名证据：**

- force-TTL 缓存键驱逐语义由 `test_click_force_ttl_evicts_only_single_asset_keys`
  以**脱敏 fake-key `PrivateClient` + monkeypatched `urlopen`**（不触网、不记录真实
  凭证/签名/请求头）端到端验证——这是行为级脱敏证据，证明 force 路径只驱逐 3 个
  单资产键、共享键存活。
- 真实 **live signed capture 为 follow-up**：force-TTL 触及签名端点，未经操作者
  授权的安全 live 环境下**未发起签名实网调用**；`signed-audit-template.json` 为
  字段模板（仅字段名，非事实证据）。未用合成 fixture 冒充事实证据。

## 7. 未完成项 / 风险 / BLOCKED

- **无 BLOCKED。** T1–T9 全部完成；pre-review repair（见 §8）补齐六个 timeout
  契约缺口后，287 后端测试 + 前端 self-check 全通过。
- **风险/未完成**：真实 live signed capture（force-TTL 在生产 key 下的实网脱敏
  录制）为操作者授权后的 follow-up，非本 bounded task 的实现门。
- **未宣称阶段通过审查**：实现 + 测试 + 证据已就绪，但是否进入 review-1 由
  bookkeeper/操作者验收决定。

## 8. Pre-review repair（审查前修复，2026-07-13）

bookkeeper 在正式 review-1 前发现六个 symbol-snapshot 的 timeout（超时）契约缺口。
本次以 `minimal_change_engineer`（最小改动工程师）skill 做最小修复，**不改变**
`rework_count`（返工计数，这不是正式 review 返回的 REWORK）。逐项映射如下：

| # | 发现 | 修复（文件） | 测试 |
|---|---|---|---|
| 1 | `get_symbol_snapshot()` 在 `cmd.done.wait()` 到期、worker 未完成时回退 `"ok"`，把超时标成成功 | `snapshot_service.py`：`cmd` 已提交但 `refresh_status` 为空 → 返回 `"timeout"` + warning `refresh_deadline_exceeded`，投影上次已发布行 | (b) `test_endpoint_wait_timeout_returns_timeout_not_ok` |
| 2 | `_handle_refresh_command()` 只在全部 I/O 后检查 deadline；已排队过期的命令仍启动新上游 I/O | `snapshot_service.py`：入口即 `time.monotonic() >= deadline` 检查，过期则 `timeout` + warning `refresh_command_expired`，**零** `fetch_raw`/`fetch_premium_index_for`/`fetch_funding_rate`/私有 fetcher | (a) `test_expired_queued_command_does_no_upstream_io` |
| 3 | deadline 未在 `_assemble()` 后、写 domain cache 前再检查；组装跨 deadline 仍提交 | `snapshot_service.py`：`_assemble()` 后、`_publish()` 前再加 deadline 闸门（超时 `assemble_crossed_deadline`）；把 `_funding_history_cache` 写**延迟**到此闸门之后，改用内存 overlay（memory overlay）把新 history 注入 `_assemble`，满足“组装后、写 history cache / `_last_private_inputs` / `PublishedState` 之前” | (c) `test_assemble_crossing_deadline_commits_nothing` |
| 4 | live worker 未运行（kill switch 关闭）但已有发布态时，端点伪报 `ok` | `snapshot_service.py`：`_worker_running()` 为假 → 不提交命令，`cmd=None` → 返回该行 `200` + `refresh_status="timeout"` + warning `worker_not_running`，零上游；无发布态仍 `503` | (d) `test_kill_switch_off_with_state_returns_timeout_zero_upstream` |
| 5 | 前端 `fetchSymbolSnapshot` 把任何 HTTP 200 当成功，未消费 `refresh_status`/`warnings` | `index.html`：新增 `state.drawerNotice`；`fetchSymbolSnapshot` 按 `refresh_status` 分流——`timeout` 保留上次行 + 非阻塞「刷新超时，显示上次数据」notice；`partial` 替换行 + 「部分刷新成功」notice 透传 warnings；`ok` 替换行无 notice；`renderDrawer` 渲染 notice（历史列表照常显示）；仍只 `patchRow` 目标行/抽屉，**无** `renderTable()` | (f) self-check #60 timeout / #61 partial |
| 6 | `_handle_refresh_command()` 的 `base_raw is None` 冷路径调用整宇宙 `fetch_raw()` | `snapshot_service.py`：`base_raw is None` → 直接 `timeout` + `error="base_not_ready"` + warning `base_raw_unavailable`，零 `fetch_raw()`、零发布 | (e) `test_base_raw_none_click_does_no_fetch_raw` |
| 7 (BK-6) | `_handle_refresh_command()` 在 post-assemble deadline gate 通过后**先写 `_funding_history_cache[symbol]` 再调 `_publish()`**；`_publish()` 内部才执行 `jsonschema.validate()`。schema validation 失败时旧 `PublishedState` 保留，但新的 history cache 已提交，违反冻结契约（assembly/validation failure 不得提交 history cache / `_last_private_inputs` / `PublishedState`） | `snapshot_service.py`：把 validation 提取为独立 `_validate(snapshot)`，在 post-assemble deadline gate **之后**、history-cache commit **之前**调用；`_publish` 重构为 `_publish_validated`（不再内部 validate，避免双重昂贵校验）；`_scheduled_tick` 同样改为先 `_validate` 后 `_publish_validated`。validation 失败 → 走既有 except → `refresh_status="timeout"` + `error="assemble_failed:…"`，history cache / `_last_private_inputs` / `PublishedState` 全部保持旧值。deadline 检查仍先于所有 domain commit / publish，无截止时间竞态 | (g) `test_schema_validation_failure_commits_nothing` |
| 8 (BK-7) | BK-6 把 `_validate(snapshot)` 置于 post-assemble deadline gate 之后、history-cache commit 之前；但 `_validate` 本身耗时，若它在 deadline 前开始、deadline 后返回，代码仍会在超时后写 history cache 并发布，违反冻结 timeout 契约（任何 domain cache commit / publication 之前都必须重新确认 deadline） | `snapshot_service.py`：在 `_validate(snapshot)` **成功返回后**、写 `_funding_history_cache` 与调 `_publish_validated` **前**补最终 deadline gate（`time.monotonic() >= deadline` → `refresh_status="timeout"` + `error="validation_crossed_deadline"`，history cache / `_last_private_inputs` / `PublishedState` 全部保留旧值，不发布）。BK-6 的 validation-failure 原子性保留不变（`_validate` 抛错仍走 except → timeout，不 commit） | (h) `test_validation_crossing_deadline_commits_nothing` |

点击路径 deadline 闸门真实顺序（BK-7 后）：入口 deadline gate → I/O → post-IO deadline gate →
`_assemble` → post-assemble deadline gate → `_validate` → **final deadline gate** →
history-cache commit → `_publish_validated`。每个 domain commit / publication 之前都有
`time.monotonic() < deadline` 重新确认。

### 8.1 修改文件（pre-review repair）

```text
backend/services/snapshot_service.py            # 发现 1/2/3/4/6/7(BK-6)/8(BK-7)
backend/tests/test_symbol_snapshot_endpoint.py  # 新增 7 个确定性测试 (a)-(e)+(g,h)
frontend/index.html                             # 发现 5：drawerNotice + refresh_status 消费 + renderDrawer notice
frontend/self-check.js                          # 新增 #60/#61 (f)
reports/.../20-implementation.md                # 本章节
reports/.../60-test-output.txt                   # 只追加
```

### 8.2 测试结果（pre-review repair）

| 命令 | 结果 |
|---|---|
| `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider` | **289 passed**（BK-7 修复前 288 → +1） |
| `python3 -m pytest backend/tests/test_symbol_snapshot_endpoint.py -v` | **27 passed**（26 → +1：(h) BK-7） |
| `node frontend/self-check.js` | 全通过（新增 #60 timeout / #61 partial） |
| `git diff --check` | exit 0 |

完整原始输出已**追加**至 `60-test-output.txt`。所有测试确定性、不真实等待 30 秒、不访问网络。

### 8.3 剩余风险

- 无新增实现风险；六个 timeout 缺口 + BK-6 atomicity 缺口 + BK-7 deadline-race 缺口已闭环覆盖。
- **BK-6 零 residual**：validation 已前移至 history-cache commit 与 `PublishedState`
  替换之前（顺序为 post-assemble deadline gate → `_validate` → final deadline gate（BK-7）
  → history-cache commit → `_publish_validated`），`_scheduled_tick` 同样先 `_validate`
  后 `_publish_validated`。validation 失败时 `_published_state`（同一引用）、
  `_funding_history_cache[symbol]`（同一旧对象）、`_last_private_inputs`（同一引用）
  三者均由 `(g)` 确定性断言保留。无双重昂贵校验（`_publish_validated` 不再 validate），
  未重新引入截止时间竞态。测试不依赖“`_assemble` 理应产生有效 schema”——通过注入失败
  schema 让真实 `jsonschema.validate` 抛错。
- **BK-7 零 residual**：`_validate` 自身耗时不再构成 deadline race——validation 成功返回后、
  history-cache commit / `_publish_validated` 之前补了 final deadline gate
  （`time.monotonic() >= deadline` → `error="validation_crossed_deadline"`）。validation 在
  窗口内开始、窗口外返回的场景由 `(h)` 用可控 monotonic clock + 包装 `_validate` 确定性
  复现，断言 `refresh_status="timeout"`、`_published_state`（同一引用）、
  `_funding_history_cache[symbol]`（同一旧对象）、`_last_private_inputs`（同一引用）。
  BK-6 的 validation-failure 原子性未受影响（`_validate` 抛错仍走 except → timeout）。
- 真实 live signed capture 仍为操作者授权后的 follow-up（与 §6/§7 一致，未变）。

## 9. 声明

- **未提交、未推送、未合并、未 rebase、未启动其它模型、未调用 subagent。**
- 未修改 `status.json`、`70-handoff.md`、intake/task/design/ADR/breakdown/workflow/
  registry/Harness/canonical docs（bookkeeper/操作者单写）。
- 未发起任何签名实网调用；未记录任何凭证/签名/请求头/完整 signed query/余额/持仓/
  估值；签名证据已脱敏（fake key + 行为级单元验证）。
- 主 `snapshot.schema.json` **未修改**（same-version 一致性靠单发布者 + 单调版本 +
  测试保证）。
- 本次仅：编辑 12 个既有源/测试文件 + 新增 2 个测试文件 + 1 个 schema + 1 份公开
  样本目录 + 追加 `60-test-output.txt` + 重写本报告。

```text
本地北京时间: 2026-07-13 08:56:10 CST
下一步模型: Codex bookkeeper
下一步任务: 验收实现、测试与证据，创建本地 evidence commit 并准备 review-1
```

```text
本地北京时间: 2026-07-13 09:26:03 CST
本轮: minimal_change_engineer — BK-6 pre-review atomicity repair
下一步模型: Codex bookkeeper
下一步任务: 验收 BK-6 atomicity 修复（schema validation 前置于 history-cache commit 与 PublishedState 替换；validation 失败时 history cache / _last_private_inputs / PublishedState 全部保留旧值），创建本地 evidence commit 并准备 review-1
```

```text
本地北京时间: 2026-07-13 09:41:57 CST
本轮: minimal_change_engineer — BK-7 pre-review final-deadline-gate repair
下一步模型: Codex bookkeeper
下一步任务: 验收 BK-7 修复（_validate 成功返回后、缓存提交/发布前补 final deadline gate；_validate 自身耗时不再构成 deadline race），创建本地 evidence commit 并准备 review-1
```
