# Task Handoff: 2026-08-06-hedge-order-close-validation-set-leverage-before-open

## Source Report (author-only; immutable after task end)

- task_id: `2026-08-06-hedge-order-close-validation-set-leverage-before-open`
- role: Implementer（target_role 按 dispatch）
- target_model: deepseek（Human 指定，provider 按 `agents/roles.md` 映射）
- stage_id: `2026-08-06-hedge-order-close-validation`
- created_at: `2026-08-06 14:00:54 CST`
- base_sha: `f153cdc38469a3fde80d7d2f79682d4d7aa23df8`
- delivery_sha: `pending`（本任务未授权提交——dispatch 禁止未授权提交；改动在工作树，
  Bookkeeper 核验后定交付 SHA）

### 任务背景

THE 合约开仓 `-2027 Exceeded the maximum allowable position at current leverage`——
交易所以前默认 20 倍杠杆、现最大 10 倍，开仓量在 10 倍下超限。Human 拍板方案 B：
**开单（合约下单）前自动设置该币 3 倍杠杆，每任务只设置一次，放在开单校验通过之后**。

### 实际修改范围

1. `backend/hedge_open_tasks/domain.py`（Allowed）：
   - `OPEN_LEVERAGE = 3`（Human 拍板；注释注明先硬编码、后续可配置化）。
   - `PAUSE_REASON_LEVERAGE_SET_FAILED = "leverage_set_failed"` + `_PAUSE_REASON_ZH`
     中文「设置合约杠杆失败，任务已暂停（fail-closed，未发单）。详情见任务卡日志，
     请人工核对后手动恢复」。
   - `SIGNAL_LEVERAGE_SET_FAILED = "signal_leverage_set_failed"`——刻意不在
     `SIGNAL_TASK_LOCAL_PAUSE` 内（暂停已由 `_dispatch_one_for_task` 落库，避免
     worker 侧 `_pause_from_signal` 二次暂停）。
2. `backend/services/hedge_open_live_client.py`（Allowed）：
   - 白名单新增 `("POST", "/fapi/v1/leverage"): "https://fapi.binance.com"`
     （fapi 域名硬绑定，配置不可覆盖）。
   - `LEVERAGE_PATH = "/fapi/v1/leverage"` 常量。
   - `set_leverage(symbol, leverage, *, timestamp_ms, recv_window_ms=None)`：
     签名 POST（`_post_signed`，参数冻结 symbol + leverage），返回原始响应，
     one-shot 不重试（写语义与订单一致）。
3. `backend/services/live_hedge_executor.py`（Allowed）：
   - `set_leverage(symbol, leverage)`：调 client；非 200 / body 不可解析 / 缺
     `leverage` 字段 → `RuntimeError` 带交易所详情（body 截断 200，沿用
     `universal_transfer` 模式）；成功无返回值。
4. `backend/hedge_open_tasks/service.py`（Allowed）：
   - `_dispatch_one_for_task` live 分支：fresh preflight ok 后、`prepare_attempt`
     前插入——`live and task_type==OPEN and scheduled_attempt_count==0` →
     `_set_leverage_before_open(task, now_us)`；失败 → `_pause_task_local`
     （`PAUSE_REASON_LEVERAGE_SET_FAILED` + 中文原因含错误详情 + kind=
     `leverage_set_failed` 事件）→ 返回 `(updated_task, SIGNAL_LEVERAGE_SET_FAILED)`，
     **不创建 attempt、不发单**。
   - 新增 `_set_leverage_before_open(task, now_us)`：`getattr(executor, "set_leverage")`
     为 None（dry-run/disabled）→ 跳过返回 None；异常 → 中文错误（详情截断 200）。
   - worker 信号分支：`SIGNAL_LEVERAGE_SET_FAILED` → `return False`（暂停已落库，
     直接退出本轮，不二次暂停）。
   - 插入点位于 `prepare_attempt` 之前，保证「设置成功才创建 attempt 发单」。
5. 测试（Allowed 相关测试文件）：
   - 新增 `backend/tests/test_hedge_leverage.py`（12 条）：白名单注册
     fapi 域名；client `set_leverage` 签名 POST 到 fapi + 参数冻结 + one-shot；
     executor 成功/HTTP 失败带详情/缺字段抛错；service 首 attempt 设一次 +
     target_n>1 每任务一次（spy 计数 1）+ 失败 fail-closed（paused + 中文原因含
     -2027 详情 + 无 attempt + 事件落库）+ dry-run 跳过 + close 不设杠杆（双向）。
   - `backend/tests/test_hedge_purity.py`：白名单冻结测试同步（15 条，`_FAPI_HOST`
     组 + `_FAPI_KEYS` + per-group host 断言更新）。
   - `backend/tests/test_hedge_task_local.py`：`_LiveWireClient` 补 `set_leverage`
     （模拟真实 client 新方法，返回 200 成功）。

### 结论

- 修复完成：live 开单任务首 attempt 发单前自动设 3 倍杠杆，每任务一次；设置失败
  fail-closed 暂停（中文原因 + 错误详情，无 attempt、不发单）；dry-run 跳过；
  close 任务绝不设杠杆；SPOT_ONLY 路由修复（任务 01）未回退（工作树保留）。
- 全部验收面通过：白名单冻结同步（15 条）；时机（preflight ok 后、prepare_attempt
  前）；每任务一次（spy 计数 1）；fail-closed（paused + 中文 + 无 attempt + 日志）；
  close/dry-run 不越界；回归全绿。
- 内置只读 review：minor nits、OK to ship（每任务一次/fail-closed/dry-run/close
  门控/信号不二次暂停/白名单冻结全部静态核实正确）。

### 命令与结果

- `.venv/bin/python3 -m pytest backend/tests/test_hedge_leverage.py -q` → `12 passed`
- `.venv/bin/python3 -m pytest backend/tests/test_hedge_purity.py backend/tests/test_hedge_task_local.py backend/tests/test_hedge_leverage.py -q` → `87 passed`
- `.venv/bin/python3 -m pytest backend/tests -q` → `1438 passed`（全量后端回归全绿）
- `node frontend/self-check.js` → 全部自检通过
- `git status --short`：本次交付 `backend/hedge_open_tasks/{domain,service}.py`、
  `backend/services/{hedge_open_live_client,live_hedge_executor}.py`、
  `backend/tests/{test_hedge_leverage.py 新增,test_hedge_purity.py,test_hedge_task_local.py}`；
  任务 01 改动（`hedge_preflight_provider.py`、`test_hedge_preflight_provider.py`）
  仍在工作树未回退；`reports/agent-runs/ACTIVE.json` 为 stage 控制文件改动。
  无前端/ledger/实盘写。

### 未完成事项 / 不能假设

- 未提交（dispatch 禁止未授权提交）；未实盘执行。
- **实盘启用需 Human 单独明确授权**：本任务只做代码 + 测试库验证；设置杠杆属于
  实盘资金/风险操作（dispatch Stop 段）。Human 重启服务实盘复测：开一个合约标的
  下单，确认先设 3 倍杠杆再发单成功。
- 若某币设置 3 倍被币安档位拒绝（该币最低档 >3 或档位上限 <3），按 fail-closed 暂停
  并如实记录——交易所事实，本地不可绕过（不在本次范围）。
- 后续可配置化（杠杆 3 硬编码，Human：不做配置 UI）。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`
  2. `backend/hedge_open_tasks/service.py`（`_dispatch_one_for_task` 约 2313 行、
     `_set_leverage_before_open` 约 2255 行、worker 信号分支约 1451 行）
  3. `backend/services/hedge_open_live_client.py`（`ALLOWLIST`、`set_leverage` 约 445 行）
  4. `backend/services/live_hedge_executor.py`（`set_leverage` 约 700 行）
  5. `backend/tests/test_hedge_leverage.py`（12 条验收测试）
- 执行：Bookkeeper 核验工作树改动 + 回归记录，定 `delivery_sha`；Human 重启服务
  实盘复测（开单先设 3 倍杠杆再发单）。
- 关卡：Human 实盘复测 + 本 stage 下一验证任务。
- 不能假设的事实：测试库 start gate 默认关闭（live 发单路径测试需显式开启）；
  THE 合约 -2027 在 3 倍杠杆下是否解除须实盘确认（设置杠杆若被档位拒绝按
  fail-closed 暂停）；任务 01（SPOT_ONLY 路由修复）与任务 02 改动同在工作树未提交。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: 2026-08-06-hedge-order-close-validation-set-leverage-before-open
执行结果: completed
结果摘要: 开单前自动设置合约杠杆 3 倍完成（THE -2027 方案 B）：live 开单任务首 attempt 发单前设一次，失败 fail-closed 暂停（中文原因+错误详情，无 attempt 不发单），dry-run 跳过、close 不设杠杆；白名单冻结测试同步；新增 12 条测试，全量 1438 passed、self-check 全绿。
产物: [reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-set-leverage-before-open.handoff.md]
检查结果: [白名单 POST /fapi/v1/leverage 进白名单 + 冻结测试同步 pass；时机 preflight ok 后 prepare_attempt 前 pass；每任务一次（spy 计数 1）pass；fail-closed 暂停（中文+详情+无 attempt）pass；close/dry-run 不设杠杆 pass；全量回归 1438 passed + self-check 全绿 pass；范围核对仅内列文件 pass]
阻塞项: [none]
本地北京时间: 2026-08-06 14:00:54 CST
下一步模型: deepseek（Bookkeeper，按 status.json bookkeeper 字段；Human 启动其终端核验并封存本任务）
下一步任务: 读取：reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json + evidence/2026-08-06-hedge-order-close-validation-set-leverage-before-open.handoff.md；执行：核验工作树改动与回归记录、定 delivery_sha；关卡：Human 重启服务实盘复测（开单先设 3 倍杠杆再发单成功，需 Human 单独授权实盘启用）
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- verified_at: `2026-08-06 18:40:28 CST`
- source_sha256: `2525bd14f4a8c39e33569b087df8e272ea1e43864bae4a05fd07817ae9cb6d85`
- status_revision: 2（本任务 reported 时状态；封存时随 03 一次性提交，status.json 现指向 03）
- base_sha / delivery_sha: `f153cdc38469a3fde80d7d2f79682d4d7aa23df8` .. `ee7ec4f3a41db8d896652101fcd1821972b381bc`（Human 授权一次性提交 stage 全部工作树改动）
- verdict: **verified（通过）**
- 依据（可复现）：
  - `python3 -m pytest backend/tests -q` → **1446 passed**（本 Bookkeeper 实测；含 test_hedge_leverage.py 12 条）
  - 白名单含 `("POST", "/papi/v1/um/leverage")`（`hedge_open_live_client.py:138,506`）；`service.py:2256 _set_leverage_before_open`、`:2326` 插入点（preflight ok 后）、`:1455` 信号分支、`:2330` fail-closed 暂停
  - 注：handoff 正文写 `/fapi/v1/leverage`，实际交付代码为 `/papi/v1/um/leverage`（UM 杠杆端点，与下单同域同权限）——以代码为准，属交接描述不精确，不改变功能语义
- 后续状态：02 `reported` → `verified`；杠杆实盘启用仍须 Human 单独授权（重启服务复测）
