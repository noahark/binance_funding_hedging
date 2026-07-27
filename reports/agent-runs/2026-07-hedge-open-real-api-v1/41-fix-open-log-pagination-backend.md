# 41 — 开单日志分页兼容修复（后端）：Hedge Open Real API v1

> 模型：`glm-5.2[1m]`（Claude Code 会话，本任务唯一后端兼容修复实现者）。
> 数据包：`56-open-log-pagination-backend.dispatch.md`。
> 最高权威契约：`17-opening-log-pagination-compatibility.md`（冻结加法式分页 seam）。
> 问题证据：`18-replacement-r4-diff-reconciliation.md`（R4 §阻断发现）。
> 范围：为 `GET /api/hedge-open-logs` 的加法式 `entries` 增加独立分页 seam（`entries_limit` / `entries_cursor` / `entries_next_cursor`），修复 R4 发现的「加载更多重复 task_event」缺陷。**不改任何下单数量/节奏、预检、错误矩阵、live 网关或签名行为。**
> 合同：不 commit、不改 `status.json` / `70-handoff.md` / PRD / 设计 / ADR / `frontend/**` / `docs/**` / `backend/services/**` / `backend/borrow_tasks/**` / 15-18 文档 / 54-55 包。绝不读凭据、绝不连 Binance、绝不发真实 POST。

---

## 1. 问题与修复语义

### 1.1 R4 缺陷（`18` §阻断发现）

`service.get_logs()` 把旧 `next_cursor` 从 legacy `logs` 计算，却把 `entries` 另行由 attempts 与 task events 合并：

- 旧 `next_cursor` 只来自 `list_logs_page()`（`hedge_open_log(ts_us, id)` 序列）；
- `entries` 的 attempts 复用旧 cursor，但 task events 调 `list_task_event_logs(limit, …)` **没有 cursor 参数**（原 `store.py:1288-1307`：每一页都取最新 `limit` 条）；
- 两类记录来自**不同的持久化序列**（`hedge_open_attempt(created_at_us, id)` 与 `hedge_open_log(ts_us, id)`），不能共用同一个两段式旧游标；
- 前端把 `doc.next_cursor` 当 entries 游标回传 → 新的 task_event 在每一页重现 → 用户看到重复日志。

实际影响仅限审计页显示正确性，不新增/重发/改变任何订单；但日志页是失败审计入口，不能带重复记录进入提交与复审。

### 1.2 修复（`17` 冻结的加法式 seam）

- 旧 `cursor` / `limit` / `logs` / `attempts` / `next_cursor` **语义完全不变**；`entries_cursor` 绝不塞进旧 `next_cursor`。
- 新增可选请求参数 `entries_limit`（`1..100`，同旧 `limit` 的安全解析/默认纪律，但独立上限 100）与 `entries_cursor`（opaque）；响应顶层新增 `entries_next_cursor`。entry 每一项的冻结字段名（`16` §5）**逐字不变**。
- `entries` 从 attempt + task_event 的**统一稳定排序流**翻页：键 `(ts_us, rank, source_id)` DESC。`rank` 是固定的来源标记（attempt=0, event=1）——两表 `id` 自增序列独立、会冲突，`rank` 既消解冲突又提供同 ts 的确定性 tie-break。
- 每个源用**同一**三元组 cursor `(cur_ts, cur_rank, cur_id)` 各取 `entries_limit+1` 条，合并后取前 `entries_limit+1` → **has-more 来自统一流的 limit+1 结果**。`entries_next_cursor` 从本页最后一条的统一键派生，**不从旧 logs 派生**。
- `entries_cursor` 只影响 `entries`；旧 `logs`/`attempts` 的返回保持既有 cursor 行为。
- 缺少 `entries_next_cursor` 时前端安全地视为没有更多；不得退回旧 `next_cursor`（那会重新引入重复）。

### 1.3 分页前后语义对照

| 维度 | 修复前（R4 缺陷） | 修复后（`17` seam） |
| --- | --- | --- |
| `entries` 翻页驱动 | 复用旧 `cursor`/`limit` | 独立 `entries_cursor`/`entries_limit` |
| task_event 翻页 | **无 cursor**，每页取最新 limit 条 → 重复 | 三元组 cursor，严格向前，**不重复** |
| has-more 判定 | 旧 `next_cursor`（来自 logs） | 统一流 `limit+1`（来自 entries） |
| `next_cursor` 来源 | logs 序列 | logs 序列（**不变**） |
| `entries_next_cursor` | 不存在 | 本页最后一条统一键 |
| 同 ts 跨表排序 | 未定义（id 冲突） | `(ts, rank, id)` 确定性 tie-break |
| 下单/预检/错误矩阵/签名 | — | **完全不变** |

---

## 2. 实现说明（逐文件，仅本任务增量）

### 2.1 `backend/hedge_open_tasks/domain.py`
- 常量：`ENTRIES_LIMIT_DEFAULT = 50`、`ENTRIES_LIMIT_MAX = 100`（`LIMIT_MIN=1` 复用）。
- `validate_entries_limit(value)`：与 `validate_limit` 同解析/默认纪律，但上限 100；`None → ENTRIES_LIMIT_DEFAULT`；错误码沿用 `invalid_limit`（纪律一致）。
- `encode_entries_cursor(ts_us, rank, row_id)` / `decode_entries_cursor(value)`：`"{ts}:{rank}:{id}"` 三段 base64url，`rank ∈ {0,1}` 校验；与两段式 `encode_cursor` 字符串形态不同，**绝不混淆**。旧 `encode_cursor`/`decode_cursor`/`validate_limit` 未动。

### 2.2 `backend/hedge_open_tasks/store.py`
- `list_attempts_entries_page(limit, cur_ts, cur_rank, cur_id)`：attempt 源（rank=0）统一流分页，按 `(created_at_us DESC, id DESC)`，三元组 cursor 的字典序 `<` 展开为三段 OR。caller 传 `limit = entries_limit+1` 读 has-more。返回最多 `limit` 条 `(attempt, spot_leg, perp_leg)`。
- `list_task_event_logs_page(limit, kinds, cur_ts, cur_rank, cur_id)`：event 源（rank=1）统一流分页，按 `(ts_us DESC, id DESC)`，`kinds` 过滤 + 三元组 cursor 组合 WHERE。
- 旧 `list_attempts_page` / `list_task_event_logs` **保留不变**（service 的旧 `attempts` 字段仍用前者）。

**统一流正确性**：统一流 `F = A ∪ E`，按 `K=(ts,rank,id)` DESC。给定 cursor `K_c`，下一页是 `F` 中 `K < K_c` 的前 `limit` 条。分别从 A/E 各取 `K < K_c` 的前 `limit+1` 条，合并排序取前 `limit+1`——第 `j (≤limit+1)` 名必在某一源的 `limit+1` 子集内（其在所属源排名 `≤ j ≤ limit+1`），故合并后即统一流前 `limit+1`。`K` 由 `(rank, source_id)` 保证全局唯一 → 严格 `<` 不漏不重。

### 2.3 `backend/hedge_open_tasks/service.py`
- 常量 `_ENTRY_ATTEMPT_RANK = 0` / `_ENTRY_EVENT_RANK = 1`（跨表 id 冲突的确定性消解）。
- `_entries_projection` → 重构为 `_entries_page(entries_limit, entries_cursor_str)`，返回 `(entries, next_cursor)`：解码三元组 cursor → 两源各取 `entries_limit+1`（同一 cursor）→ 投影 + 合并 + 按 `(ts DESC, rank DESC, id DESC)` 排序 → 取前 `entries_limit+1`，`has_more = len > entries_limit`，截断 `entries_limit`，`next_cursor` 由最后一条统一键编码（仅当 has_more）→ 清理 `_sort_*`。
- `_attempt_to_entry` / `_event_to_entry` 各加 `_sort_rank`（`_ENTRY_ATTEMPT_RANK` / `_ENTRY_EVENT_RANK`）。
- `get_logs(cursor_str, limit_raw, entries_cursor_str=None, entries_limit_raw=None)`：旧 `logs`/`attempts`/`next_cursor` 路径**逐字不变**；新增 `entries_limit = _parse_entries_limit(...)` 与 `entries, entries_next_cursor = _entries_page(...)`，响应顶层加 `entries_next_cursor`。
- `_parse_entries_limit` / `_parse_entries_cursor`：镜像旧 `_parse_limit` / `_parse_cursor` 纪律；无效 `entries_cursor` 抛 `invalid_cursor` 400（fail-closed，不静默回首页）。

### 2.4 `backend/app/server.py`
- `_hedge_open_logs`：解析 `entries_cursor` / `entries_limit` query 参数，位置传入 `get_logs`（4 参数）。最小接线，**其他路由/方法零改动**。`parse_qs` 丢弃空值，故 `?entries_cursor=` 视为缺席（首页），与旧 cursor 约定一致。

---

## 3. 真实命令结果（调度文件指定，全部通过）

```text
# (1) focused：回归 + api + service
.venv/bin/python -m pytest backend/tests/test_hedge_review2_regressions.py \
  backend/tests/test_hedge_api.py backend/tests/test_hedge_service.py -q
→ 63 passed in 13.62s

# (2) 全量 backend 套件
.venv/bin/python -m pytest backend/tests -q
→ 882 passed in 44.86s   （较修复前 880 +2 新回归）

# (3) frontend self-check（本后端改动下仍全绿，证明 §5 seam 两侧对齐）
node frontend/self-check.js
→ 全部自检通过
  （含「开单日志 no-orderId 确认失败行 + newest-first 两页 entries_cursor 分页
   （不回退旧 next_cursor）+ entry_id 不重复 + 加载更多 + 显式刷新」、
   「entries_next_cursor 缺失/非字符串安全降级为没有更多，不回退旧 next_cursor」——
   前端负责人 57 号包已实现 entries 分页并与本后端契约对齐）

# (4) 空白/冲突检查
git diff --check
→ CLEAN（DIFF_CHECK_CLEAN）
```

无真实网络、无凭据读取、无 Binance、无真实 POST、无 live/Start。

---

## 4. 回归测试（确定性离线，fake-transport）

新增（`backend/tests/test_hedge_review2_regressions.py`）：

- **`test_8c_entries_unified_stream_paginates_no_dup_no_gap`**：交错 6 个 accepted attempt + 3 个 task_event（事件与 attempt 1/3/5 同 ts），`entries_limit=3` 逐页翻到 `entries_next_cursor` 为空。断言：
  - 9 个 `entry_id` 恰好一次（无重复、无遗漏）；
  - 全局 newest-first（跨页拼接的 `created_ts` 降序）；
  - 相邻页 `entry_id` 无交集（**R4 缺陷会在每页重现 event**）；
  - 3 个 task_event 各存活一次，且分散在 3 页（非全挤首页）；
  - has-more 来自统一流 `limit+1`：9/3 恰好 3 个满页，末页 `entries_next_cursor=None`（无多余空页）；
  - 同 ts 确定性 tie-break：事件（rank 1）紧接同 ts 的 attempt（rank 0）；
  - **旧 cursor/limit 仍独立工作**：`get_logs(None, 2)` 产生 legacy `next_cursor`（9 logs > 2），用该 cursor 再请求成功，且 `entries` 首页仍返回全部 9 条（entries cursor 未被触碰）。

新增（`backend/tests/test_hedge_api.py`）：

- **`test_logs_entries_pagination_params_threaded_through_http`**：HTTP 路由传递 `entries_limit`/`entries_cursor`；响应含 `entries_next_cursor`；`entries_limit=2` 截断；用 `entries_next_cursor` 翻第二页与首页 `entry_id` 无交集；末页 `entries_next_cursor=None`；无效 `entries_cursor` 返回 400（fail-closed）。

现有断言更新（反映 `17` 冻结的新解耦语义）：

- `test_hedge_service.py` / `test_hedge_api.py` / 回归 `test_8` 的 `get_logs` 响应键集加 `entries_next_cursor`。
- 回归 `test_8` 的分页断言由「旧 `limit` cap entries」（旧耦合语义）改为「旧 `limit` **不再** cap entries；旧 `next_cursor` 仍由 logs 产生」（新解耦语义）。完整独立分页由新 `test_8c` 覆盖。

`test_8b`（task_event 行 null leg 字段）未受影响，仍通过。

---

## 5. Changed files

**本任务（56 号包）所改：**

- `backend/hedge_open_tasks/domain.py` — 仅 entries 分页增量（常量 / `validate_entries_limit` / `encode_entries_cursor` / `decode_entries_cursor`）。
- `backend/hedge_open_tasks/store.py` — 仅 `list_attempts_entries_page` + `list_task_event_logs_page`。
- `backend/hedge_open_tasks/service.py` — 仅 `_entries_page`（重构自 `_entries_projection`）+ `get_logs` 新参数/响应 + `_sort_rank` + `_parse_entries_limit` / `_parse_entries_cursor` + rank 常量。
- `backend/app/server.py` — 仅 `_hedge_open_logs` 解析并传递 `entries_limit`/`entries_cursor`。
- `backend/tests/test_hedge_api.py` — 键集 + 新 HTTP 传递测试。
- `backend/tests/test_hedge_service.py` — 键集。
- `backend/tests/test_hedge_review2_regressions.py` — 键集 + `test_8` 分页断言 + 新 `test_8c`。

**本任务明确未改（合同边界）：**

- `backend/services/**`（`hedge_preflight_provider.py`、`live_hedge_executor.py`）、`backend/hedge_open_tasks/executor.py`、`backend/tests/test_hedge_domain.py`、`backend/tests/test_hedge_executor.py` —— 这些文件的当前工作树改动是**上个任务（54 号包）的未提交遗留**（54 允许改 services；本任务合同禁止改 services），本任务**未触碰**。
- `frontend/**`、`docs/**`、`reports/api-samples/**`、`backend/borrow_tasks/**`、`status.json`、`70-handoff.md`、`60-test-output.txt`、15/16/17/18 文档、54/55 包 —— **均未触碰**。

**并行/其他 owner（非本任务）：**

- `frontend/index.html`、`frontend/self-check.js`、`41-fix-open-log-pagination-frontend.md` —— 前端兼容修复 owner（57 号包）。
- `60-test-output.txt`、`70-handoff.md`、`status.json` —— bookkeeper。
- `17-*.md`、`18-*.md` —— bookkeeper 冻结的契约/对账文档（本任务权威输入）。

---

## 6. 剩余风险与限制

1. **`planned_quote_amount` 恒为 null**：`16` §5 允许可空；attempt 行不单独存 per-attempt 价格，本任务范围不计算（UI 渲染 —）。沿用 54 号包结论，非本任务引入。
2. **统一流 cursor 的进程内语义**：`entries_next_cursor` 编码 `(ts, rank, id)` 三元组，是**内容寻址**的稳定游标（非行号）——新插入的更新记录不影响已有页的边界，翻页期间新增的记录会在首页刷新后出现，不会让既有游标失效或重复。这与 `17`「稳定排序流」要求一致。
3. **`entries_limit` 与旧 `limit` 上限不同**（100 vs 200）：前端/调用方若误用旧 `limit` 语义传 `entries_limit>100` 会得 400 `invalid_limit`（message 指明 `entries_limit`）。已在 HTTP 测试覆盖 fail-closed。
4. **`rate_limited` / `preflight_incomplete` 任务事件的 `overall_result`**：仍为 null（`16` §5 枚举不含），`next_action=waiting_query`；本任务未改该映射（非分页范畴）。
5. **前端并行 diff**：`frontend/**` 与 `41-fix-open-log-pagination-frontend.md` 非本任务所改；bookkeeper 合并时按 57 号包归属处理。`node frontend/self-check.js` 在本后端改动下全绿，证明两侧 `entries_next_cursor` seam 对齐。
6. **跨表 id 冲突的消解依赖 `rank`**：若未来新增第三类 entries 源，需为其分配新 `rank` 并扩展 `encode_entries_cursor` 的 `rank ∈ {0,1}` 校验——当前两源已穷尽。

---

实现完成，全部自测通过。按合同**停止**——不 commit、不改 status.json / 70-handoff.md、不派发、不评审，等待 bookkeeper reconcile 后端分页改动与 57 号包并复跑集成测试。

---

当前 Session ID: unavailable (Claude Code / glm-5.2 harness 不暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/41-fix-open-log-pagination-backend.md
本地北京时间: 2026-07-24 18:15:23 CST
下一步模型: bookkeeper
下一步任务: reconcile the backend pagination change with packet 57 and run integration tests
