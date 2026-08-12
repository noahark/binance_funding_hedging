# Task Handoff: 05-o2-text-sync-and-jst-backfill

## Source Report (author-only; immutable after task end)
- task_id: `05-o2-text-sync-and-jst-backfill`
- role: `Implementer`
- target model: `codex`（provider `openai`）
- stage_id: `2026-08-12-hedge-slippage-spread-v1`
- status_revision: `9`
- created_at: `2026-08-12 10:23:53 CST`
- base_sha: `05d2ac9fa41c5ccecf7e0c50cf1c8615bf5b1f64`
- delivery_sha: `pending`

### 任务背景与实际修改

按 Human 明确授权，先同步 O-2 旧口径文字，再备份并单行补录 JSTUSDT 本地历史数据。

- `frontend/index.html` 仅修改历史仓位表的 1 处滑点注释与 2 个 tooltip，统一说明开/平单现货与
  合约两腿真实成交数量加权均价价差，公式为
  `(卖出腿均价 - 买入腿均价) / min(两腿均价) * 100`，卖价高于买价为正。值渲染未改。
- `backend/hedge_open_tasks/service.py` 仅同步 `_finalize_close_task` 上方同族注释。计算、API 与
  schema 未改。
- 完整保留 Human 在 `frontend/index.html` 的“尝试时间线最近 10 条”未提交 hunk；
  `frontend/self-check.js` 未编辑。两者均不属于 delivery commit。

### O-2 检查

- `node frontend/self-check.js` → `全部自检通过`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider backend/tests/test_hedge_store.py backend/tests/test_hedge_cycle_close.py -q`
  → `131 passed in 3.37s`。
- `git diff --check` → pass（无输出）。

### JSTUSDT 写前只读复算

目标数据库：`data/hedge-open-tasks.sqlite3`。只读连接重新确认 close-log 唯一目标行为：

`(id=6, cycle_id=30918cf0-6f9d-4c93-b876-395eb37c804f, symbol=JSTUSDT,
direction=reverse, open_slippage=-0.37, close_slippage=NULL)`。

同周期查询命中 6 个 attempt、12 条正数成交腿；每个阶段/腿各 3 条。以每条腿真实
`cumulative_quote_amt / cumulative_base_qty` 用 `Decimal` 分别跨 attempt 加权：

- open spot：`(9.80900000 + 9.80900000 + 9.80800000) / 300 = 0.09808666666666666666666666667`
- open perp：`(9.7870000 + 9.7870000 + 9.7840000) / 300 = 0.0978600`
- close spot：`(10.05800000 × 3) / 300 = 0.10058`
- close perp：`(10.0360000 × 3) / 300 = 0.1003600`
- reverse open（spot sell / perp buy）→ `0.2316`
- reverse close（perp sell / spot buy）→ `-0.2192`

### 备份与单行补录

- 使用 Python 标准库 `sqlite3.Connection.backup` 创建 create-only SQLite 在线备份：
  `data/hedge-open-tasks.sqlite3.bak-jst-slippage-row6-20260812-095000`。
- 备份 SHA-256：`11dd8cb0346de001d67c2139fe4dcc40994a726a69840570f58b1022d8703e59`。
- 备份 `PRAGMA integrity_check` → `ok`；备份目标行与原库写前六字段逐项相同，仍为
  `-0.37 / NULL`。
- 原库写入在单个 `BEGIN IMMEDIATE` 事务内执行，UPDATE 同时固定 `id`、`cycle_id`、`symbol`、
  `direction`、旧 `open_slippage` 与 `close_slippage IS NULL`。事务断言
  `rowcount=1`、`total_changes=1`，写后行精确为 `0.2316 / -0.2192` 后才 commit。
- commit 后只读复核：原库 `PRAGMA integrity_check` → `ok`，`id=6` 唯一目标行精确为
  `0.2316 / -0.2192`。无第二行变化。
- 原库和备份均由 `.gitignore:32:data/` 排除，未加入 Git。

### 边界与未完成事项

未控制、重启或部署服务，未执行订单、资金、闸门、凭证、网络或合并动作，未修改其他数据库或
close-log 行。delivery commit 只含 dispatch 授权的四个 Git 路径。O-2 扩展产品文件并改变用户
可见账务说明，仍须重新通过独立 review-1 与 review-2；本任务不自行评审或启动下一终端。

### Required Reading for the Next Task
- 读取路径及顺序：`reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/05-o2-text-sync-and-jst-backfill.handoff.md`、`reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/status.json`
- 执行：Bookkeeper 核验 handoff 源区 SHA-256、O-2 cached diff、测试结果、备份 SHA-256/完整性、写前写后目标行、事务单行变更与 delivery commit 四路径范围，解析 `pending` 为实际 delivery SHA 并准备独立 review-1 dispatch
- 关卡：Bookkeeper 核验通过后，由 Human 启动独立 review-1 终端；随后仍须 review-2
- 不能假设的事实：本交付未包含 Human 的最近 10 条前端 hunk或 `frontend/self-check.js`；本地数据补录不等于代码已评审、合并、部署或服务已加载新口径

## Human Brief / Console Receipt Source

```text
[TASK_RESULT v2]
任务 ID: 05-o2-text-sync-and-jst-backfill
执行结果: completed（完成）
结果摘要: O-2 三处前端说明与后端同族注释已同步为两腿真实成交价差公式，值渲染/计算/API/schema 未变；前端自检与定向后端 131 项通过。已在线备份本地库并以完整 guard 单行补录 JSTUSDT id=6 为 0.2316/-0.2192，原库和备份完整性均通过。
产物: [frontend/index.html, backend/hedge_open_tasks/service.py, reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/status.json, reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/05-o2-text-sync-and-jst-backfill.handoff.md, data/hedge-open-tasks.sqlite3, data/hedge-open-tasks.sqlite3.bak-jst-slippage-row6-20260812-095000]
检查结果: [
1. pass 仅同步三处前端旧口径文字与 service.py 同族注释，公式/正号说明完整，值渲染、计算、API、schema 零变化；
2. pass Human 最近 10 条前端 hunk 完整保留且未提交，cached 产品差异不含该逻辑，frontend/self-check.js 未暂存；
3. pass 前端自检全部通过、定向后端 131 passed、git diff --check 通过；
4. pass 写前唯一目标行与 6 个 attempt/12 条成交腿复核通过，Decimal 独立复算命中 0.2316/-0.2192；
5. pass SQLite 在线备份 create-only，integrity_check=ok，写前目标行一致，SHA-256=11dd8cb0346de001d67c2139fe4dcc40994a726a69840570f58b1022d8703e59；
6. pass BEGIN IMMEDIATE 完整 guard 更新，rowcount=1、total_changes=1，提交后原库 integrity_check=ok 且目标行精确，无第二行变化；
7. pass handoff 已记录数据库、备份、复算输入、写前写后、事务与检查结果，数据库及备份均未加入 Git；
8. pass delivery commit 仅含授权四个 Git 路径，零服务/订单/资金/网络/部署/合并或其他数据库副作用
]
阻塞项: [none]
本地北京时间: 2026-08-12 10:23:53 CST
下一步模型: codex（本阶段 Bookkeeper）
下一步任务: 读取：reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/05-o2-text-sync-and-jst-backfill.handoff.md, reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/status.json；执行：Bookkeeper 核验源 SHA-256、O-2 cached diff、测试、备份/单行补录证据与 delivery commit 四路径范围，解析 pending delivery SHA 并准备独立 review-1 dispatch；关卡：Bookkeeper 核验通过后由 Human 启动独立 review-1 终端，随后仍须 review-2
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

## Errata (append-only)
任何更正均追加，说明日期、作者、改动原因与不改变的事实；不得改写 Source Report 或 Human Brief。
