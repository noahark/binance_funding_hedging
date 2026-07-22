# 实现报告 — hedge-be（对冲开单后端模块 + API + 测试）

阶段 `stage/2026-07-hedge-open-live-v1`，第一轮（立即开仓 + 默认 dry-run record transport）。
执行者：Claude-GLM（后端域唯一实现者）。真实下单路径本轮**不接线**：默认执行器为 dry-run record transport，**绝不发 HTTP POST、绝不碰真实 Binance 网络**。

---

## 1. 改动摘要

新增独立 modular-monolith 包 `backend/hedge_open_tasks/`（镜像 `borrow_tasks/` 的 domain/store/service/executor + durable SQLite + 单调度线程 + disabled/gated executor 结构），在 `backend/app/server.py` 新增并列的 hedge-open 路由（不动 borrow 逻辑），并新增 5 个测试文件覆盖 domain/store/executor/service/API。包对外完全隔离：`backend.services` / `backend.domain` 无任何模块 import 本包，本包也不 import 它们；全包零网络/签名原语。

| 类别 | 文件 | 行数 |
| --- | --- | --- |
| 新增模块 | `backend/hedge_open_tasks/__init__.py` | 47 |
| 新增模块 | `backend/hedge_open_tasks/domain.py` | 714 |
| 新增模块 | `backend/hedge_open_tasks/store.py` | 575 |
| 新增模块 | `backend/hedge_open_tasks/service.py` | 443 |
| 新增模块 | `backend/hedge_open_tasks/executor.py` | 292 |
| 新增模块 | `backend/hedge_open_tasks/scheduler.py` | 57 |
| 改动（仅新增路由） | `backend/app/server.py` | — |
| 新增测试 | `backend/tests/test_hedge_domain.py` | 365 |
| 新增测试 | `backend/tests/test_hedge_store.py` | 224 |
| 新增测试 | `backend/tests/test_hedge_executor.py` | 273 |
| 新增测试 | `backend/tests/test_hedge_service.py` | 245 |
| 新增测试 | `backend/tests/test_hedge_api.py` | 416 |

边界遵守：只改 `backend/hedge_open_tasks/**`、`backend/app/server.py`（仅新增 hedge-open 路由）、`backend/tests/**`（仅新增 hedge-open 测试）；未触碰 frontend、borrow、docs、reports（除两个 R10 工件）、AGENTS.md、根配置、.env*、未引入任何新依赖。`schemas/api/hedge-open/**` 本轮未新增 schema 文件——冻结契约的"字段名精确性"改由 `test_hedge_api.py` 的显式 `set(doc.keys()) == {...}` 断言等价锁定（与 `additionalProperties:false` 同等严格，且更直读）。

---

## 2. 交付项 → 代码位置

| 交付项（契约条目） | 代码位置 |
| --- | --- |
| Task/Fill 字段、`status`（含 `deleted`）常量与 stage-1 对齐 | `domain.py:33-41,73-84`（SCHEMA_VERSION/STATUS_*/LEG_*/ATTEMPT_*） |
| 方向映射 + `NO_SIDE_EFFECT`（ADR-3/DI-4） | `domain.py:56-57,179`（`direction_to_leg_actions`）；现货腿 `sideEffectType=NO_SIDE_EFFECT` 见 `executor.py:105`（`build_spot_order_params`） |
| 共同网格取整（ADR-2/§4，绝不分别取整） | `domain.py:228`（`decimal_lcm`）、`251`（`floor_to_grid`）、`437-441`（两腿取同一 `q_common = floor(single_amount, lcm(step_spot, step_perp))`） |
| preflight（§5；snapshot=None→dry-run 未知，不拒绝） | `domain.py:396`（`compute_preflight`）；反向余额用 base `crossMarginFree >= q*N`：`domain.py:462-480` |
| 立即引擎 + dry-run record transport（§6） | `scheduler.py`（1s durable 线程）；`service.py:359`（`tick`）、`388`（`_dispatch_one_for_task`）；`executor.py:65`（`OutcomeSpec`）、`105/126`（`build_spot/perp_order_params`，记录将发签名参数、**无密钥/签名**） |
| 单腿敞口状态机（ADR-4/§7，不自动补/平，>3 终止） | `domain.py:510`（`classify_attempt`）、`531`（`build_leg_exposure`）、`567`（`resolve_status_after_attempt`，`FAIL_TERMINATE_THRESHOLD=3` 见 `:100`）；store 落库 `store.py:303`（`apply_attempt_outcome`） |
| 安全闸门（ADR-5/§9） | 默认执行器 `RecordTransportExecutor`（`service.py:136`，无 POST）；`DisabledHedgeExecutor`（`executor.py`）；live 执行器**本轮不接线**：`server.py:657`（`_build_hedge_service` 读 `APP_HEDGE_EXECUTOR`，即便 `live` 也只构造 record transport） |
| API 端点/字段/错误码/软删除（§3） | 路由表 `server.py:75`（`_HEDGE_OPEN_ROUTES`）、`89`（`_HEDGE_OPEN_ACTIONS`）、`452`（`_try_hedge_open`）、`533-562`（各 handler）；service 编排 `service.py:190`（`create_task`）、`275/281`（fill-once/fill-all）、`347`（`set_start_gate` Python seam）；错误码 `insufficient_balance`/`invalid_field`/`invalid_state`/`unknown_task` 经 `domain.py:138`（`HedgeError.as_payload`）序列化 |
| 持久化（4 张表） | `store.py:31/49/67/75`（task/fill/log/settings）；持仓聚合 `store.py:445`（`aggregate_positions`） |

---

## 3. 契约符合性自查（逐条）

1. **API（§3）**：✅ 5 个端点（tasks / settings / logs / positions / `{id}/{action}`）齐全；task/settings/error/position/logs 字段名由 `test_hedge_api.py` 的显式 key-set 断言锁定；错误码 `insufficient_balance`/`invalid_field`/`invalid_state`/`unknown_task`/`invalid_json`/`body_too_large`/`method_not_allowed` 均可达且确定；软删除语义（默认 list 排除 `deleted`，`?status=deleted` 可见，重复删除→`invalid_state`）有 HTTP 测试。
2. **方向映射 + NO_SIDE_EFFECT（ADR-3/DI-4）**：✅ 两方向现货腿均 `NO_SIDE_EFFECT`（`executor.py:105`）；反向 preflight 用 `crossMarginFree(base) >= q_common×N`，`maxBorrowable` 不当可卖（`domain.py:462-480`）；`positionSide` 取自 snapshot 的 `position_mode`（BOTH=单向 / hedge=LONG|SHORT），不改模式。
3. **共同网格取整（ADR-2/§4）**：✅ 定点 `lcm(step_spot, step_perp)`，两腿同一 `q_common`；任一腿 min/max/notional 违反→拒绝（`_check_common_quantity`，含 `q_common<=0→below_min_qty`）；从不分别取整。
4. **preflight（§5）**：✅ 结构齐备（filters/balances/position_mode/est_price/rate_limit）。**第一轮限制**：默认 `DisabledPreflightProvider` 不做网络读（返回 None→dry-run 未知结果，task 仍可创建以演练 record transport）；真实 live 读由后续轮注入 provider 接入。任一 market step 读不出→拒绝。
5. **立即引擎 + dry-run record transport（§6）**：✅ 1s durable 调度（`scheduler.py`）；record transport 记录将发签名参数（endpoint/symbol/side/type/quantity/sideEffectType/positionSide/newClientOrderId，**无 apiKey/signature/timestamp/recvWindow**）、filter 版本、preflight 快照、client id，`posted=false`，**不发 POST**；模拟结果可 seed 注入（`spot_only_filled`/`perp_only_filled`/`both_failed`/`qty_mismatch`），默认双腿成交。
6. **单腿敞口状态机（ADR-4/§7）**：✅ 按成交状态分类（一腿 FILLED 另一腿否→`single_leg_exposure`），落 `leg_exposure` + 置 `exposure_alert` + 暂停 + 记录，**不自动补/平**；累计失败 `>3`→终止 + `paused`。**第一轮限制**：按 client id 主动查 order/trades/positionRisk 的对账钩子为接口预留（`HedgeExecutor` 协议 + AttemptContext 携带 client id），实际网络对账随 live 执行器在后续轮接入；本轮用可注入 seed 演练全部敞口路径。
7. **安全闸门（ADR-5/§9）**：✅ 默认 `RecordTransportExecutor`（无 POST）；真实 POST 仅在 `APP_HEDGE_EXECUTOR=live` AND 全局 Start AND preflight 通过时可达——**但 live 执行器本轮未接线**，故真实 POST **本轮不可达**（`test_live_mode_still_uses_record_transport_no_real_post` 证明即便 mode=live 仍是 record transport）。Start gate 默认关，仅 `set_start_gate` Python seam 可开（本轮无 HTTP toggle，settings 只读）。
8. **Task/Fill 字段 + status（§2/§3）**：✅ 沿用 stage-1 字段与状态机（含 `deleted` 软删除）。

---

## 4. 自测结果

自测命令（逐字，任务指定）：

```
python -m pytest backend/tests -q
```

结果：**785 passed in 45.00s**，exit=0，全绿。完整输出已贴入 `60-test-output.txt`（hedge-be 段，带 `=====` 标题；同文件并存 hedge-fe Kimi 的前端自检段）。

hedge-open 新增测试覆盖（共 104 个用例）：
- `test_hedge_domain.py`（49）：方向映射、`decimal_lcm`（相等/不等/互质）、`floor_to_grid`、`effective_market_step`、`compute_preflight`（接受/insufficient_balance 正反向/below_min_qty/below_min_notional/snapshot=None/step 读不出）、`classify_attempt`、`resolve_status_after_attempt`（done/exposure/>3/边界/deleted 粘滞）、各 validator。
- `test_hedge_store.py`（11）：持久化往返、list 默认排除 deleted、apply 结果（成功/敞口/>3 终止）、fill+log 落库、`list_logs_page` 游标分页、`aggregate_positions`（正向空头/反向多头/排除 deleted）、settings、崩溃式重启恢复。
- `test_hedge_executor.py`（15）：`DisabledHedgeExecutor`、record transport 默认双腿成交+参数形状+**无密钥**+`posted=false`+未舍入数量、seed 注入（spot_only/perp_only/both_failed/qty_mismatch）、种子消费顺序、**AST 纯度证明**（全包无 urllib/http/socket/hmac/hashlib/ssl/requests）、**运行期零 urllib 调用证明**、service 默认=record transport、毒化环境密钥不泄露。
- `test_hedge_service.py`（14）：create+preflight、生命周期转换、fill_once/fill_all、注入单腿敞口、>3 终止、Start-gated tick、**live 模式仍是 record transport（真实 POST 不可达）**、disabled 执行器可注入。
- `test_hedge_api.py`（20）：进程内 `ThreadingHTTPServer`，端点存在性+状态码+冻结字段集、确定错误码、软删除语义、405/404/503、**全场景零 urllib 调用**、`/healthz` 不被遮蔽、**无 borrow 接线时 hedge-open 独立可用**。

零网络证明：AST 扫描（`test_hedge_executor.py`）+ urllib monkeypatch 运行期证明（executor 与 api 各一）双层保证 hedge-open 路径不发任何网络请求；任何测试均未发真实 Binance 请求。

---

## 5. 已知限制（第一轮，均为设计内范围）

- **真实下单路径本轮不接线**：`_build_hedge_service` 即便在 `APP_HEDGE_EXECUTOR=live` 也只构造 `RecordTransportExecutor`；真实 POST 本轮不可达（ADR-5 第一轮安全姿态）。
- **preflight 默认无网络读**：`DisabledPreflightProvider` 返回 None，task 以 `q_common=None` 创建以演练 record transport；真实 exchangeInfo/balance/positionSide/dual/rateLimit 读由后续轮注入 `PreflightProvider` 接入。
- **单腿敞口无自动补救**：按 ADR-4 设计，仅 `exposure_alert`+暂停+记录，不自动补/平；按 client id 主动对账（order/trades/positionRisk）的钩子随 live 执行器后续轮接入，本轮以可注入 seed 覆盖全部敞口分类路径。
- **settings 本轮只读**：Start gate 仅经 `set_start_gate` Python seam 切换（无 HTTP toggle）；interval 固定 1s。
- **smooth 模式未接线**：ADR-6 本轮仅 immediate；smooth（流式推送通道）预留给后续轮，本包未实现。
- **持仓聚合为 stage-1 数学**：`aggregate_positions` 输出冻结 Position JSON 全字段，但 `open_basis_rate`/`price_pnl`/`accrued_funding`/`borrow_interest`/`net_pnl` 本轮无数据源，稳定输出 `"0"`；`position_qty`/`spot_avg`/`perp_avg` 由 fills 实算并经 `fmt_decimal` 去尾零。

---

## 6. R10 收尾状态

- [x] 自测命令已真实运行，完整输出贴入 `60-test-output.txt`。
- [x] 本实现报告已写入 `20-implementation-hedge-be.md`。
- [x] 未 commit、未改 `status.json`、未启动/转派其他模型、未越边界。
- 完成后停下，交 bookkeeper 收证据、R4 diff 核对、串行 commit、算指纹、调度 review-1（Kimi）。

```text
当前 Session ID: unavailable (harness 执行者在任务 prompt 内无法观测自身 provider-native session id；由 runner/operator 记入 status.json.session_receipts)
Session ID 来源: unavailable (prompt 内无可见的 runtime_env/hook_payload/cli_output/transcript_path 证据)
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-v1/20-implementation-hedge-be.md（本报告）；自测完整输出 reports/agent-runs/2026-07-hedge-open-live-v1/60-test-output.txt
本地北京时间: 2026-07-23 00:56:30 CST
下一步模型: bookkeeper（随后 review-1 Kimi）
下一步任务: bookkeeper 收证据 → R4 diff 核对 → 串行 commit → 算指纹 → 调度 review-1（Kimi）
```
