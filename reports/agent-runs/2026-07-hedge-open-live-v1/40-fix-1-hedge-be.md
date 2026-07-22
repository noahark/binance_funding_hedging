# Fix 报告 — hedge-be fix-1（stage 2026-07-hedge-open-live-v1）

Fix 执行者：Claude-GLM（`zhipu_glm`，经 Claude Code）。review-1（Kimi）verdict=
REWORK，两项必修 F-001(P1) / F-002(P2)；F-003~F-006 记为 live 轮 follow-up，本轮
不动。固定审查范围 `6639b002..b773a470`（本 fix 在该 head 之上的工作树内完成，未
commit）。原始评审：`30-review-1-hedge-be.md`。

R10 收尾声明：未 commit、未改 `status.json`、未启动/转派任何其他模型会话；写完本
报告即停，交 bookkeeper 收证据、重算指纹、重进 review-1（Kimi）。本会话未发任何
真实网络请求；`backend/hedge_open_tasks/` 零网络原语不变。

---

## 0. 文件边界核验（hard）

仅触及允许范围，无越界：

| 文件 | 类别 | 是否允许 |
| --- | --- | --- |
| `backend/hedge_open_tasks/domain.py` | 模块 | ✅ `backend/hedge_open_tasks/**` |
| `backend/hedge_open_tasks/store.py` | 模块 | ✅ |
| `backend/hedge_open_tasks/service.py` | 模块 | ✅ |
| `backend/tests/test_hedge_domain.py` | 测试 | ✅ `backend/tests/test_hedge_*.py` |
| `backend/tests/test_hedge_api.py` | 测试 | ✅ |
| `reports/agent-runs/.../60-test-output.txt` | R10 工件 | ✅ 允许的 R10 工件 |

未触碰：`backend/app/server.py`、frontend、`borrow_tasks`/borrow 路由、`docs/**`、
`AGENTS.md`、`.env*`、根配置、`status.json`、`schemas/**`。未引入新依赖。

`git diff --stat HEAD`：6 files changed, 85 insertions(+), 9 deletions(-)（其中
`60-test-output.txt` 为纯追加，非代码改动）。

---

## 1. F-001（P1）— `GET ?status=all` 不含 deleted

### 根因
冻结契约 §3.1 规定「default excludes `deleted` unless `status=deleted|all`」，即
`?status=all` 必须含 deleted。但 `filter_status_for_list('all')` 与 `None` 同样
返回 `None`（`domain.py` 原实现把 `None/""/"all"` 三者合并为同一分支）；而
`store.list_tasks(None)` 执行 `WHERE status != 'deleted'`（排除 deleted 的默认行
为）。于是 `all` 与默认视图**塌缩为同一行为**——都排除 deleted。结果：删除一个任务
后 `?status=all` 返回空，而 FE `frontend/index.html:3323-3327` 固定拉
`?status=all` 并依赖 deleted 在其中（已删除筛选永远为空）。BE 自测
`test_filter_status_for_list_mapping` 把 `filter_status_for_list("all") is None`
这一**错误行为钉成了断言**，掩盖了 seam drift（与 R4-001 同类 mock-masked seam）。

### 改动位置
- `backend/hedge_open_tasks/domain.py:57`：新增哨兵常量 `LIST_ALL = "__all__"`
  （与 `None` 区分；`None` 语义保持为「默认视图，排除 deleted」——该语义正确且被
  `test_list_tasks_excludes_deleted_by_default` / 多处 `svc.list_tasks(None)` 依
  赖，不可改）。
- `backend/hedge_open_tasks/domain.py:706`（`filter_status_for_list`）：`all` 分
  改为 `return LIST_ALL`；`None/""` 仍 `return None`（默认视图）；`deleted`/具体
  status 行为不变；未知值仍 `invalid_field`。
- `backend/hedge_open_tasks/store.py:241`（`list_tasks`）：新增
  `elif status_filter == D.LIST_ALL` 分支——无 `WHERE` 子句，返回全部（含
  deleted）；`None` 分支（排除 deleted）与具体 status 分支（`WHERE status=?`）不
  变。

### 测试结果
- 改写 `backend/tests/test_hedge_domain.py:341`
  `test_filter_status_for_list_mapping`：断言 `filter_status_for_list("all") ==
  D.LIST_ALL`（不再 `is None`），并补 `""` 也映射 `None`。
- 新增 `backend/tests/test_hedge_api.py:329`
  `test_status_all_includes_deleted_default_excludes`（HTTP 级，逐字对齐 review-1
  required fix）：创建→删除任务后，`?status=all` 含该任务、默认 list 不含、
  `?status=deleted` 仅含该任务。

`all` 不再塌缩为默认视图；deleted 在 `?status=all` 中可见，FE 已删除筛选 seam
恢复。

---

## 2. F-002（P2）— `mode="smooth"` 被 BE 接受并被 immediate 引擎调度

### 根因
冻结契约 §3.1 冻结 `mode="immediate"` 本轮。但 `create_task` 仅调
`validate_mode`（`domain.py:609`），而 `validate_mode` 接受 `ALL_MODES =
(immediate, smooth)`——即 `smooth` 作为合法词表通过校验，随后被创建为
`status=running` 任务并进入 `list_eligible_tasks()`，被 1s immediate 调度器当成
immediate 执行（实证：`mode:'smooth'` 创建返回 201 且 1s 后被调度）。FE 已本地拒
绝 smooth，BE 却 fail-open。

### 改动位置
- `backend/hedge_open_tasks/service.py:200-202`（`create_task`）：在
  `validate_mode` 之后追加 round-1 冻结策略——`if mode != D.MODE_IMMEDIATE:
  raise D.invalid_field("mode", f"round-1 supports only {D.MODE_IMMEDIATE!r}")`
  （400）。`validate_mode` / `ALL_MODES` / `MODE_SMOOTH` 保持不变：`smooth` 仍是
  合法词表常量（保留备用，符合 prompt「smooth 常量保留备用」），round-1 冻结是
  service 层策略而非 domain 词表校验——与架构分层一致（domain=纯原语，
  service=编排/策略）。

### 测试结果
- 新增 `backend/tests/test_hedge_api.py:225`
  `test_smooth_mode_rejected_as_invalid_field`（service/API 级，逐字对齐 review-1
  required fix）：`mode:"smooth"` 创建→`400`，payload key-set 恰为
  `{error, detail}`，`error == "invalid_field"`。

非 immediate 的 mode 现在在 create 即 400 拒绝，immediate 引擎不可能再调度
smooth-labeled 任务。bogus mode（如 `"fast"`）仍由 `validate_mode` 先行拒绝（同为
400 invalid_field），路径一致。

---

## 3. 非目标遵守（未顺手改）

F-003~F-006（`_qty_bounds` 回落、限频 enforcement、AttemptContext docstring、
fill-all guard/start-gate 注记）本轮**未改**，bookkeeper 已记为 live 轮 follow-up。
未改 borrow 任何文件；未改 frontend；未引入新依赖；未发任何真实网络请求。

---

## 4. 自测结果

逐字命令（本 shell 无 `python`，使用同 review-1 的 `.venv/bin/python` 3.11.15，
等价于 venv 激活后的 `python -m pytest`）：

```text
.venv/bin/python -m pytest backend/tests -q
```

结果：**787 passed in 43.94s**，exit 0（review-1 基线 785 passed + 2 新增 HTTP 测
试 = 787，符合预期）。完整输出已追加到
`reports/agent-runs/2026-07-hedge-open-live-v1/60-test-output.txt` 新段
`===== hedge-be fix-1 (Claude-GLM) 自测：python -m pytest backend/tests -q =====`
（line 248 起），既有三段（hedge-be 自测 / hedge-fe 自测 / hedge-fe R4-fix-1）保留。

三项测试改动/新增：
1. 改写 `test_filter_status_for_list_mapping`（domain）— F-001
2. 新增 `test_status_all_includes_deleted_default_excludes`（api）— F-001
3. 新增 `test_smooth_mode_rejected_as_invalid_field`（api）— F-002

---

## 5. 改动汇总表

| 发现 | 根因 | 改动位置 | 测试 |
| --- | --- | --- | --- |
| F-001(P1) | `filter_status_for_list('all')` 塌缩为 `None`，与默认视图同（排除 deleted） | `domain.py:57`(LIST_ALL 常量)、`:706`(函数分支)、`store.py:241`(LIST_ALL 无 WHERE 分支) | 改写 domain 映射测试 + 新增 HTTP deleted 可见性测试 |
| F-002(P2) | `create_task` 仅 `validate_mode`，接受 smooth 词表即放行调度 | `service.py:200-202`(round-1 mode 冻结 → 400) | 新增 service/API smooth→400 测试 |

---

当前 Session ID: unavailable (本 Claude Code (GLM) 会话内无可观测 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-v1/40-fix-1-hedge-be.md
本地北京时间: 2026-07-23 07:36:01 CST
下一步模型: bookkeeper（随后 review-1 Kimi 复审）
下一步任务: bookkeeper 收 fix-1 证据（本报告 + 60-test-output.txt 新段）→ 重算指纹 → 重进 review-1（Kimi）
