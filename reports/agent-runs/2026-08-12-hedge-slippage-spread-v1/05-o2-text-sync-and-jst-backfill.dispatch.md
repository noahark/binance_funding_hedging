# Dispatch: 05-o2-text-sync-and-jst-backfill

## Identity

- task_id: `05-o2-text-sync-and-jst-backfill`
- target_role: `Implementer`
- target_model: `codex`
- provider: `openai`
- status_revision: `9`
- required_skill: `agents/skills/minimal-change-engineer.md`

## Goal

执行 Human 于 2026-08-12 明确授权的两项顺序动作：

1. 同步 O-2 旧口径文字，仅修改前端滑点注释/tooltip 与后端同族注释，统一说明为：开/平单
   现货与合约两腿真实成交数量加权均价的价差百分比，公式
   `(卖出腿均价 - 买入腿均价) / min(两腿均价) * 100`，卖价高于买价为正。不得改值渲染、
   计算、API 或 schema。
2. O-2 修改与检查通过后，备份本地数据库并仅补录 JSTUSDT 历史 close-log `id=6`：
   `open_slippage` 从旧值 `-0.37` 更正为 `0.2316`，`close_slippage` 从 NULL 补为 `-0.2192`。

Human 的本地数据库授权只覆盖该数据库、该行、该两列和上述两个值；不授权其他数据、订单、
资金、服务重启、部署或合并。目标值由同周期六组成交腿真实 quote/base 数量加权独立复算：
reverse open 为 spot sell / perp buy → `0.2316`；reverse close 为 perp sell / spot buy →
`-0.2192`。

这是 Human 明确同意的新交付范围，`rework_count` 为 0。O-2 在 review-2 后扩展了产品文件并改变
用户可见账务说明，交付后按 `AGENTS.md` §8 重新走 review-1 与 review-2；Implementer 不得自行
评审或启动下一终端。

## Allowed Files

- 启动只读：`AGENTS.md`、本 dispatch、`reports/agent-runs/ACTIVE.json`、`PROJECT_STATE.md`、
  本阶段 `status.json`、`agents/roles.md` 的 Implementer 与 Task Handoff Evidence Contract 段落、
  `agents/developer-discipline.md`、`agents/skills/minimal-change-engineer.md`、
  `evidence/04-review-2.handoff.md`。
- 产品修改仅限：`frontend/index.html`、`backend/hedge_open_tasks/service.py`。
- `frontend/index.html` 已有 Human 的未提交“尝试时间线只展示最近 10 条”修改；必须原样保留，
  不得修改或提交该 hunk。O-2 行位于约 5339/5361-5362，既有 hunk 位于约 6599，提交时只暂存
  O-2 hunk，并以 cached diff 反证未包含 `slice(0, 10)`。`frontend/self-check.js` 完全只读且不得
  暂存、提交或恢复。
- 阶段写入仅限：本阶段 `status.json` 的当前任务 `dispatched → reported`、create-only
  `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/05-o2-text-sync-and-jst-backfill.handoff.md`。
- 本地数据动作仅限：更新 `data/hedge-open-tasks.sqlite3` 的目标行，并 create-only 生成
  `data/hedge-open-tasks.sqlite3.bak-jst-slippage-row6-20260812-095000`。两路径均被 `.gitignore`
  排除，不得加入 Git。Bookkeeper 已核实目标库存在、备份路径不存在。
- 唯一允许的数据库 UPDATE 必须同时满足：
  `id=6`、`cycle_id='30918cf0-6f9d-4c93-b876-395eb37c804f'`、`symbol='JSTUSDT'`、
  `direction='reverse'`、`open_slippage='-0.37'`、`close_slippage IS NULL`；否则零写入并阻塞。
- 禁止修改测试、其他源码、docs、PROJECT_STATE、其他 close-log 行或其他数据库；禁止删除、覆盖
  或恢复任何既有文件；禁止订单、资金、网络、服务控制、重启、部署与合并。
- delivery commit 权限：只提交 `frontend/index.html` 的 O-2 hunk、
  `backend/hedge_open_tasks/service.py`、本 handoff 与 `status.json` 的一字段状态迁移。不得提交
  `frontend/index.html` 的最近 10 条 hunk、`frontend/self-check.js`、数据库或备份。

## Inputs

按以下顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/05-o2-text-sync-and-jst-backfill.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/status.json`
6. `agents/roles.md` 的 Implementer 与 Task Handoff Evidence Contract 相关段落
7. `agents/developer-discipline.md`
8. `agents/skills/minimal-change-engineer.md`
9. `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/04-review-2.handoff.md`
10. Allowed Files 中的两个产品文件与本地数据库目标行/成交腿只读查询

## Acceptance Checks

1. `pass|fail`：仅三处前端旧口径文字与 `service.py` 同族注释改为两腿真实成交价差说明；
   tooltip 明确公式/卖价高于买价为正，值渲染、API、schema、计算行为零变化。
2. `pass|fail`：完整保留并不提交既有最近 10 条前端 hunk；cached diff 不含 `slice(0, 10)`，
   `frontend/self-check.js` 未触碰/未暂存。
3. `pass|fail`：运行 `node frontend/self-check.js`、定向后端测试
   `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider backend/tests/test_hedge_store.py backend/tests/test_hedge_cycle_close.py -q`
   及 `git diff --check`，均通过。
4. `pass|fail`：写库前以只读查询重新确认 close-log 唯一目标行及六组成交腿；用 Decimal 复算
   open `0.2316`、close `-0.2192`，任何身份/原值/腿数据不一致立即阻塞且不写。
5. `pass|fail`：使用 SQLite online backup 创建指定备份，确认备份 `PRAGMA integrity_check=ok`、
   目标行与原库写前一致；备份不得覆盖既有文件。
6. `pass|fail`：在单个 `BEGIN IMMEDIATE` 事务内以全部固定条件 UPDATE 两列，程序断言
   `rowcount == 1` 与写后精确值后才 commit；否则 rollback。更新后原库
   `PRAGMA integrity_check=ok`，目标行精确为 `0.2316/-0.2192`，无第二行变化。
7. `pass|fail`：handoff 记录目标数据库、备份精确路径及 SHA-256、写前/写后目标行、复算输入、
   事务变更行数、完整检查命令与结果；不得把数据库或备份提交 Git。
8. `pass|fail`：delivery commit 仅含授权四个 Git 路径/状态迁移，handoff 使用 `delivery_sha:
   pending`；无服务、订单、资金、部署、合并或其他数据库副作用。

## Stop

完成 O-2、检查、备份、单行补录、handoff 与 delivery commit 后，仅把本任务状态从
`dispatched` 改为 `reported`，输出合规 `[TASK_RESULT v2]` 并停止。若 O-2 检查、备份、复算、
目标行 guard 或事务断言任一失败，不得继续后续动作；报告具体 blocker。不得启动 Reviewer。
