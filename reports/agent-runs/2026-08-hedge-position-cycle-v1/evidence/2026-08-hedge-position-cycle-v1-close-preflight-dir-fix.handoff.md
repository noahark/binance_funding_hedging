# Task Handoff: 2026-08-hedge-position-cycle-v1-close-preflight-dir-fix

## Source Report (author-only; immutable after task end)

- task_id: `2026-08-hedge-position-cycle-v1-close-preflight-dir-fix`
- role: `Implementer`（target_model: `deepseek`，provider: `deepseek`）——sonnet5 评审 REWORK 修复轮
- stage_id: `2026-08-hedge-position-cycle-v1`（拟用值，以 Bookkeeper `status.json` 为准）
- created_at: `2026-08-06 11:05 CST`
- base_sha: `08127aabbb15548f46484257614f34f384c6cac8`（`git rev-parse HEAD`，未移动 HEAD）
- delivery_sha: `pending`（未提交任何 commit，交付为工作树改动）

### 任务背景

sonnet5 综合评审 REWORK 唯一发现（P0/F1）：`_resolve_fresh_preflight` 的 `D.compute_preflight(...)`
第 3 参（方向）传入未反转的 `task["direction"]`，而上同一函数 `get_snapshot` 已用反转变量
`preflight_dir`（forward close → reverse；reverse close → forward）。后果（live 模式）：forward
close 发单前 fresh preflight 按 forward 走「需要 USDT」分支 → 查普通现货账户闲置 USDT（几乎恒 0）
→ 误判余额不足 FATAL 停任务；且此时真实划转已执行（币已划、单未发、任务停，需人工介入）。
reverse close 对称错在另一侧。测试盲区：既有平仓测试全为 dry-run，不触发 live fresh preflight 路径。

### 实际修改范围（2 个文件，均在 dispatch Allowed Files 内）

1. `backend/hedge_open_tasks/service.py` `_resolve_fresh_preflight`（`:2180`）：一行修复——
   `D.compute_preflight` 第 3 参 `task["direction"]` → **`preflight_dir`**（与上方 `get_snapshot`
   使用同一反转变量），注释同步：「余额校验必须与路由决策同方向（close 用反转方向校验实际资金
   约束）」。`grep compute_preflight(` 全仓库仅两处（create_task 用 `preflight_direction`、
   `_resolve_fresh_preflight` 用 `preflight_dir`）——方向处理现已一致。
2. `backend/tests/test_hedge_cycle_close.py` +2 live 模式回归用例（评审盲区补防）：
   - `test_live_fresh_preflight_forward_close_checks_base_asset`：真实 `_live_dispatch_capable()`
     路径（`mode="live"` + 假 executor 带 `.dispatch` + spy preflight provider）；统一账户 base
     资产充足（100000）、普通账户 USDT 0（balances 无 USDT、spot_account_usdt 不设）→ 断言
     provider 收到反转方向（reverse）、preflight `ok=True` 且无 FATAL/拒绝——修复前按 forward
     查 USDT 会误拒；
   - `test_live_fresh_preflight_reverse_close_checks_usdt`：对称——统一账户 USDT 充足
     （100000）、base 0 → provider 收到反转方向（forward）、preflight `ok=True`。
   - 断言同时落在 spy（compute_preflight 收到的方向经 provider 调用记录）与行为（ok/rejection）。

### 测试结果

- 全量：`timeout 400 python3 -m pytest backend/tests -q -p no:cacheprovider` → **1421 passed**
  （91s；含新增 2 个 live 用例；既有 dry-run 平仓测试未回退、语义未动）。
- 前端：`node frontend/self-check.js` → **139 PASS，0 FAIL**（本修复轮无前端改动，回归确认）。
- 实盘零写：未对实盘发单/划转、未写 `data/*.sqlite3`；未提交 git、未移动 HEAD。

### 验收逐项

1. **一行修复**：`service.py:2180` 用 `preflight_dir`（与 get_snapshot 同变量）；`grep
   compute_preflight(` 全仓库两处（create_task + _resolve_fresh_preflight）方向处理一致 pass。
2. **live 回归测试**：forward close（base 充足 + 普通 USDT 0 → 不误拒）+ reverse close（对称）；
   断言余额校验走反转方向（spy provider 记录 direction）+ 行为（ok/rejection）；测试触发真实
   `_live_dispatch_capable()`（`mode="live"` + 假 executor 带 dispatch，非 dry-run 模拟）pass。
3. **回归全绿**：pytest 1421 + self-check 139 PASS 0 FAIL pass。
4. **范围核对**：本修复轮仅改 `backend/hedge_open_tasks/service.py`（compute_preflight 方向一行 +
   注释）与 `backend/tests/test_hedge_cycle_close.py`（+2 用例）；无前端/ledger/白名单/实盘写；
   未提交 git、未移动 HEAD pass。

### 行为变化说明

- 修复仅影响 live 模式 close 任务发单前的 fresh preflight 余额校验方向（此前是 P0 缺陷路径）；
  dry-run 与开仓任务路径不变（open 任务 `preflight_dir == task["direction"]`，无行为差异）。
- **修复合入/实盘启用前「立即平仓」保持不可用提示**（dispatch 明示）：close_gate 默认开，实盘
  触发旧代码仍会误停任务 + 划转副作用——Human 已知悉，重启加载修复代码前不要实盘点平仓。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/2026-08-hedge-position-cycle-v1-close-preflight-dir-fix.handoff.md`（本交接件）
  2. `reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/2026-08-hedge-position-cycle-v1-review-sonnet5.handoff.md`（评审原文 P0 节）
  3. `backend/hedge_open_tasks/service.py`（_resolve_fresh_preflight / create_task 对照）
  4. `backend/tests/test_hedge_cycle_close.py`（新增 live 回归用例）
- 执行：**回 sonnet5 复评确认 F1 闭环**（Human 已认可；复评 ACCEPT 后本 stage 统一评审收尾）
- 关卡：复评 ACCEPT → 统一 review 收尾；修复合入/实盘启用（close_gate 生效发单）需 Human 单独授权
- 不能假设的事实：修复在工作树未提交（delivery_sha pending）；全部六个任务均未提交；实盘库周期数据
  仍 0（未回填）；实盘未启用平仓（Human 明示重启加载修复代码前不要实盘点平仓）。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: 2026-08-hedge-position-cycle-v1-close-preflight-dir-fix
执行结果: completed（完成）
结果摘要: sonnet5 评审 P0/F1 一行修复完成：_resolve_fresh_preflight 的 compute_preflight 方向参数改为反转变量 preflight_dir（与 get_snapshot 一致，grep 全仓库两处调用方向统一）；补 2 个 live 模式回归用例（forward/reverse close 对称，真实 _live_dispatch_capable 路径，防评审盲区复发）；全量 1421 passed + self-check 139 PASS；未提交、未写实盘。
产物: [backend/hedge_open_tasks/service.py, backend/tests/test_hedge_cycle_close.py, reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/2026-08-hedge-position-cycle-v1-close-preflight-dir-fix.handoff.md]
检查结果: [一行修复（compute_preflight 用 preflight_dir，两处调用一致）pass；live 回归测试（forward 查 base 不误拒 + reverse 对称 + 真实 live 路径）pass；回归 1421+139 全绿 pass；范围核对（仅 service.py + 测试文件）pass]
阻塞项: [none]
本地北京时间: 2026-08-06 11:05:39 CST
下一步模型: sonnet5（复评确认 F1 闭环；Human 已认可本轮复评）
下一步任务: 读取：reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/2026-08-hedge-position-cycle-v1-close-preflight-dir-fix.handoff.md（及评审原文 P0 节）；执行：sonnet5 复评 F1 闭环；关卡：复评 ACCEPT 后本 stage 统一评审收尾，实盘启用（close_gate 生效发单）需 Human 单独授权
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->
