# Fix 报告 — hedge-be fix-2（stage 2026-07-hedge-open-live-v1）

Fix 执行者：Claude-GLM（`zhipu_glm`，经 Claude Code）。review-2（Codex/GPT 终审）
verdict=REWORK，一项必修 F-007(P1) — `leg_exposure` 跨 FE/BE 契约漂移（安全关键）。
固定审查范围 base `6639b0025682f406f9a726104ef8d3b9e6f8fadd` head
`bd01eb52e9ec5464bb9f026f5ce666bc883db441`（本 fix 在该 head 之上的工作树内完成，
未 commit）。原始评审：`50-review-2.md`。

R10 收尾声明：未 commit、未改 `status.json`、未启动/转派任何其他模型会话；写完本
报告即停，交 bookkeeper 收证据、重算 diff fingerprint、重进 review-2（Codex/GPT）。
本会话未发任何真实网络请求；`backend/hedge_open_tasks/` 零网络原语不变。

---

## 0. 文件边界核验（hard）

仅触及允许范围，无越界：

| 文件 | 类别 | 是否允许 |
| --- | --- | --- |
| `backend/hedge_open_tasks/domain.py` | 模块 | ✅ `backend/hedge_open_tasks/**` |
| `backend/tests/test_hedge_domain.py` | 测试 | ✅ `backend/tests/test_hedge_*.py` |
| `backend/tests/test_hedge_executor.py` | 测试 | ✅ |
| `backend/tests/test_hedge_service.py` | 测试 | ✅ |
| `backend/tests/test_hedge_store.py` | 测试 | ✅ |
| `backend/tests/test_hedge_api.py` | 测试 | ✅ |
| `reports/agent-runs/.../60-test-output.txt` | R10 工件 | ✅ 允许的 R10 工件 |

未触碰：`backend/app/server.py`、frontend（`index.html`/`self-check.js`，Kimi 域）、
`borrow_tasks`/borrow 路由、`docs/**`、`AGENTS.md`、`.env*`、根配置、`status.json`、
`schemas/**`。未引入新依赖。

`git diff --stat`：7 files changed, 104 insertions(+), 30 deletions(-)（其中
`60-test-output.txt` 为纯追加 13 行，非代码改动）。

---

## 1. F-007（P1）— `leg_exposure` 跨 FE/BE 契约漂移

### 根因
冻结契约 `12-development-breakdown.md` §3.2 规定 Task 的
`leg_exposure: null | {leg, qty, price, ts}`。但后端
`domain.build_leg_exposure` emit 的是 `{filled_leg, spot, perp, ts}`（`filled_leg`
取 `spot`/`perp`/`both_mismatched`，外加 `spot`/`perp` 两腿子文档），与 §3.2 不一致。
而 `test_hedge_api.py` 用 `doc['leg_exposure']['filled_leg']` 把这个**错误 shape 钉
成了断言**，掩盖了漂移。前端则已符合 §3.2：`frontend/index.html:3599-3600` 读
`task.leg_exposure.leg/qty/price`，`self-check.js:3664-3665` mock 也用 §3.2。

**影响（安全关键）**：单腿敞口（尤其现货单成、合约失败）时，前端 `leg` 读不到
（后端给的是 `filled_leg`）→ `leg === 'spot'` 判定为假 → 走合约分支，渲染
`undefined` 数量/价格，向操作员**错误展示已成交腿与数量**。任务暂停（exposure_alert）
是对的，但人工决策所需的告警信息严重错误。这是本 stage 第三次跨 seam 漂移
（R4-001、F-001 之后），根因同类：BE 与 FE 各自的 mock 互相掩盖，契约 shape 从未对齐。

### 改动位置

**`backend/hedge_open_tasks/domain.py:535-564`（`build_leg_exposure`）— 重写为 §3.2**
- emit `{leg, qty, price, ts}`：现货单成 → `leg="spot"`，`qty`/`price` 取现货腿实际
  成交量/价；合约单成 → `leg="perp"`，`qty`/`price` 取合约腿。
- `qty`/`price` 为十进制字符串，与 Fill JSON §3.3（`filled_qty`/`avg_price` 均为
  字符串）一致，避免浮点精度损失。
- `None` 当无任一腿成交（普通失败，非敞口）。
- 移除仅此函数使用的 `_leg_doc` 闭包（本改动产生的孤儿，已清理；`LEG_UNKNOWN` 仍为
  模块级常量且被 `DisabledHedgeExecutor` 等使用，未动）。
- **完整的双腿原始细节仍按 ADR-4 保留在 fills 表**（`hedge_open_fill` 记录双腿
  `*_filled_qty`/`*_avg_price`/`*_order_id`/`*_client_order_id`，经
  `GET /api/hedge-open-logs` 可见）——`Task.leg_exposure` 这个面向操作员的字段收敛
  到 §3.2，不丢证据。

**测试（5 个文件，锁 §3.2 + 新增回归）**
- `test_hedge_domain.py:243-274`：旧 `test_build_leg_exposure_records_filled_leg`
  拆为 spot-only / perp-only 两个方向，断言 `set(keys)=={leg,qty,price,ts}` 且
  `leg`/`qty`/`price` 正确；保留 `none_when_neither_filled`；**新增**
  `test_build_leg_exposure_none_when_both_filled_mismatched`（钉 both_mismatched→None）。
- `test_hedge_executor.py:133-167`：spot-only / perp-only 两个 seed 断言 §3.2 shape
  与值（`_ctx` 带 `est_price=50000`，故 `qty="0.5"`/`price="50000"`）；
  `test_seed_qty_mismatch_is_single_leg_exposure` 增 `assert out.exposure is None`。
- `test_hedge_service.py:185-189`：spot-only 服务级断言改为 §3.2（dry-run 无
  preflight，`price="1"` 占位）。
- `test_hedge_store.py:99`：持久化往返测试的 exposure fixture 由旧 shape 收敛到
  §3.2 `{leg,qty,price,ts}`（该测例验证 JSON 往返不丢字段，shape 随契约更新）。
- `test_hedge_api.py:290-329`：HTTP spot-only 改为 §3.2 断言；**新增 HTTP 级回归**
  `test_injected_perp_only_exposure_http_shape` —— fill-once 注入 perp-only 单腿
  敞口，断言 Task 响应 `leg_exposure` 为 `{leg,qty,price,ts}` 且 `leg="perp"`/
  `qty`/`price` 正确。两方向均覆盖。

---

## 2. ESCALATED — both_mismatched 子情形（§3.2 契约缺口）

**情形**：双腿都 FILLED 但成交数量不匹配（如现货 0.5 vs 合约 0.4）。
`classify_attempt` 将其归为 `ATTEMPT_SINGLE_LEG_EXPOSURE`（数量错配也是一种敞口），
任务仍正确进入 `exposure_alert` 暂停。

**问题**：§3.2 的单值 `{leg, qty, price}` **无法无歧义表达双腿错配** —— 没有单一
「敞口腿」，`qty`/`price` 也无法同时承载两腿。若强行挑一腿会误导操作员；若新增字段
（如 `leg2`/`qty2` 或 `mismatch`）则**擅自扩展冻结 schema**，正是 review-2 recommendation
与 task 非目标明确禁止的（「If quantity-mismatch needs a richer representation than
§3.2 permits, stop for bookkeeper/user contract handling before extending the frozen
schema」）。

**本 fix 的处理（不扩展 schema、不丢信号、不误展示）**：
- `build_leg_exposure` 对该子情形返回 `None`（§3.2 合法值 `null|{...}`）。
- 任务状态仍由 `classify_attempt`→`SINGLE_LEG_EXPOSURE`→`exposure_alert` 驱动暂停，
  与 `leg_exposure` 内容解耦（`store.apply_attempt_outcome` 仅在 `outcome.exposure`
  为真时写 `leg_exposure`，status 由 category 决定）。
- 双腿完整细节（两腿各自 qty/price/order_id/client_order_id/status）保留在 fills 表
  （§3.3），操作员经 `GET /api/hedge-open-logs` 可见，人工决策信息不丢。
- **未抛错**：service `_dispatch_one_for_task` 对 executor 异常有容错包裹（吞成
  generic failed outcome），若在此抛 `HedgeError` 会被静默降级为普通失败，反而丢失
  exposure_alert 信号 —— 返回 `None` 是唯一不扩展、不丢信号、不误展示的确定性选择。

**遗留**：both_mismatched 进入 `exposure_alert` + `leg_exposure=null` 是可接受的确定性
中间态，但 §3.2 对该情形的表达力不足是真实契约缺口。**交 bookkeeper/用户做契约处理**
（是否扩展 §3.2 以表达错配，或维持「告警 + 查 fills」语义），不在本 fix 范围内擅自决定。

---

## 3. FE follow-up（不改前端，记录交 bookkeeper）

`frontend/self-check.js` mock 已用 §3.2 shape（`{leg, qty, price}`），但其 exposure
覆盖仅 `leg:'spot'` 一种方向（self-check #81）。本 fix **不改前端**（Kimi 域）；若需
补 `leg:'perp'` 渲染覆盖，记录为 **hedge-fe follow-up** 交 bookkeeper，不跨域改动。

---

## 4. 测试结果

- 聚焦：`.venv/bin/python -m pytest backend/tests/test_hedge_*.py -q` → **114 passed**
  （基线 111，本 fix +3 净增：domain 层 spot/perp 拆分 +1、both_mismatched 新测 +1、
  HTTP perp-only 回归 +1）。
- 全量：`.venv/bin/python -m pytest backend/tests -q` → **790 passed**（基线 787，
  +3，全绿，无 fail/skip/error）。
- 环境注：`python` 不在 PATH，定向用 `.venv/bin/python`（Python 3.11.15），与
  review-2 观察一致。
- 完整全量输出已追加到 `60-test-output.txt` 新起
  `===== hedge-be fix-2 (Claude-GLM) 自测：python -m pytest backend/tests -q =====`
  段（261-273 行），既有段全部保留。

---

当前 Session ID: unavailable（GLM 经 Claude Code，本会话未见 provider-native session id）
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-v1/40-fix-2-hedge-be.md
本地北京时间: 2026-07-23 08:45:15 CST
下一步模型: bookkeeper（人工操作员）
下一步任务: 收 fix-2 证据、在工作树内重算 diff fingerprint（head 自 bd01eb52 推进到本 fix commit）、重进 review-2（Codex/GPT 终审）
