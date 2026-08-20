# Task Handoff: 32-phase1-frontend-ui-kimi

## Source Report (author-only; immutable after task end)

- task_id: `32-phase1-frontend-ui-kimi`
- role: `Implementer`
- target model: `kimi`（provider `moonshot`）
- stage_id: `2026-08-19-hedge-order-fee-cost-v1`
- created_at: 2026-08-20 11:00 CST
- base_sha: `6d83f051563af103a3d60d527c86cba066d52cf3`（`git rev-parse HEAD`，与 status.json 一致）
- delivery_sha: pending（dispatch 禁止本任务 commit；交付提交由后续流程落盘后由 Bookkeeper 解析）

### 任务背景

阶段一前端排版展示（10-design r4 §5.1/§5.2、§7.1 第 1 步 T1）：在持仓表与历史仓位表
各加一列「手续费成本」，接入 31 任务已冻结的键名（`trading_fee_usdt` / `fee_bnb_qty` /
`trading_fee_incomplete`），未全或 null 显示「—」，完整时显示折 U 金额与第二行 BNB 数量；
同步空表 colspan（持仓 17→18、历史 16→17）、self-check 断言与新增手续费渲染用例，并顺带
修复 `test_frontend_field_binding.py` 中 base 即红的 `loadHedgeTasks` 签名锚点（31 交接件
已具名，Bookkeeper 已在 revision 11 dispatch 中授权顺带修）。

### 实际修改范围（全部在 dispatch Allowed Files 内）

1. `frontend/index.html`
   - `renderHedgeMergedPositions`（持仓表）：表头在「开单价差率」与「累计资金费」之间新增
     `<th title="…">手续费成本</th>`；行模板在价差率格后插入手续费格。渲染规则：
     `p.trading_fee_incomplete === true || === 1`、或 `p.trading_fee_usdt` 为
     null/undefined/''、或 no_task 行缺键 → 单行 `<span class="muted">—</span>`，无第二行；
     完整时主行 `formatUsdt2` 两位小数（成本按 `negative` 着色），`p.fee_bnb_qty` 非空时
     第二行 `<br/><span class="side-line muted small">… BNB</span>`（经 `escapeHtml` +
     `formatHedgeDecimal` 原生小数去尾零）。空态 colspan `17 → 18`。
   - `renderHedgeHistory`（历史仓位表）：表头在「总资金费率收益」后新增「手续费成本」；
     行模板在资金费率格后插入同规则手续费格（`r.trading_fee_incomplete === 1 || === true`
     判不全）。空态 colspan `16 → 17`。
   - 注：dispatch 所述 `#positionsTable` / `#closeLogsTable` 为概念名；实际两张表均由
     `renderHedgeMergedPositions` / `renderHedgeHistory` 动态渲染进 `private-panel-body` /
     `history-list`，无静态表元素 id，改动落在上述两渲染函数。
2. `frontend/self-check.js`
   - 既有持仓结构断言同步新列：空态 `colspan="17"→"18"`（含错误文案与 PASS 文案「18 列结构」）；
     表头/行 td 计数 `17→18`（原 8541/8550 附近）；列索引位移：资金费格 `13→14`、净盈亏格
     `14→15`、标记格 `16→17`（82c 块三处）。
   - 新增测试块「83z. 手续费成本列」：持仓表头顺序（开单价差率→手续费成本→累计资金费）、
     完整行（`'1.234'`→`1.23` 负向着色 + `0.00075 BNB` 第二行）、incomplete=true 单行 —
     且无 `<br`/BNB、incomplete=false 但金额 null → —、无 BNB 只出主行（`0.50`）、
     no_task 缺键行 → —；历史表头位置、完整行（`'2.345'`→`2.35` + `0.001 BNB`）、
     incomplete=1 → —、incomplete=0 但金额 null → —、历史空态 `colspan="17"` 且不再含 16。
3. `backend/tests/test_frontend_field_binding.py`（仅限 dispatch 授权的锚点修复）
   - `test_expanded_log_poll_includes_all_running_tasks_and_retains_non_running_expanded`：
     `text.index("async function loadHedgeTasks()")` → `"async function loadHedgeTasks("`
     （index.html:5607 实为 `loadHedgeTasks(opts)`）；同测试内调用处锚点
     `"await loadHedgeTasks()"` → `"await loadHedgeTasks({ liveOnly: true })"`
     （index.html refreshExpandedRunningHedgeLogs 实际调用形状，2026-08-18 两秒刷新收窄
     交付引入，早于本 stage base）。业务断言本体未动。

### 命令与结果

- `node frontend/self-check.js` → **全部自检通过**（含新块 PASS：
  「手续费成本列：持仓/历史表头位置、incomplete/缺键单行 —、完整折 U+BNB 双行、历史空态 colspan=17」）。
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_frontend_field_binding.py
  backend/tests/test_hedge_api.py -q` → **55 passed**。
- 中间态证据：仅修第一个锚点后该测试仍红于第二个锚点（`await loadHedgeTasks()` vs 实际
  `{ liveOnly: true }`），两处都修后转绿；self-check 首轮红于「持仓表 th 数量期望 17」，
  同步 17→18 后转绿。

### 不能假设的事实 / 交接边界

- 持仓三键在**阶段一恒为占位 `None/None/True`**（31 交付），页面当前应全部显示「—」；
  真实折 U 聚合属 T2 后半，前端已按冻结键名接好，T4 无需再改渲染逻辑。
- no_task 行（UM 有仓、无本地任务）后端不含这三个键，前端按「—」处理（已有自检覆盖）。
- `fee_bnb_qty` 第二行只在完整（`trading_fee_usdt` 出数）时出现；D11 禁止半截 BNB。
- 手续费为成本，主行按 `negative`（红）着色但**数值本身不印负号**（金额是成本大小）。
- 31 交接件所载基线失败（本任务修复对象）经 Bookkeeper 裁定为 pre-existing，本次修复
  即该处置；修复后该测试全绿。
- 本任务未 commit（dispatch 禁止）；`status.json` 的既有未提交改动非本会话产生，未触碰。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/32-phase1-frontend-ui-kimi.handoff.md`
  2. `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/status.json`
- 执行：Bookkeeper 核验阶段一前端排版交付（复跑上方两条命令），随后派发阶段一 Review-1 评审任务（Opus 5）。
- 关卡：Opus 5 Review-1 ACCEPT 且经 Human 确认页面排版后进入阶段二。
- 不能假设的事实：前端不得把手续费 null 渲染成 0；持仓三键当前恒为占位（None/None/True），
  页面出「—」是阶段一的正确表现，不是联调失败。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: 32-phase1-frontend-ui-kimi
执行结果: completed（完成）
结果摘要: 持仓表与历史仓位表各加「手续费成本」列（持仓表在开单价差率与累计资金费之间、历史表在总资金费率收益旁），空态 colspan 18/17；未全/null/缺键单行「—」，完整时两位小数折 U（负向着色）+BNB 数量第二行；self-check 同步 18 列断言、列索引位移并新增手续费渲染用例；顺带修复 test_frontend_field_binding.py 两处 loadHedgeTasks 签名锚点。两条指定测试命令全绿。
产物: [frontend/index.html, frontend/self-check.js, backend/tests/test_frontend_field_binding.py, reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/32-phase1-frontend-ui-kimi.handoff.md]
检查结果: [持仓表头位置+完整/incomplete/缺键渲染（self-check 83z）pass；历史表头位置+三态渲染 pass；空态 colspan 持仓 18/历史 17（self-check 断言）pass；node frontend/self-check.js 全部自检通过 pass；pytest test_frontend_field_binding.py + test_hedge_api.py 55 passed pass；loadHedgeTasks 签名锚点两处修复后转绿 pass；交接件 create-only（预检 ABSENT 复核成立）pass]
阻塞项: [none]
本地北京时间: 2026-08-20 11:00:25 CST
下一步模型: gemini-3.7-flash（Bookkeeper，agy 窗口）
下一步任务: 读取：reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/32-phase1-frontend-ui-kimi.handoff.md；执行：核验阶段一前端交付并派发阶段一 Review-1 评审任务（Opus 5）；关卡：Opus 5 Review-1 ACCEPT 且经 Human 确认页面排版后进入阶段二
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- Bookkeeper: `gemini-3.7-flash`（provider `google`，窗口 `agy`）
- 核验时间（本地北京时间）：2026-08-20 11:05:00 CST
- 核对的 status revision：`11`（`phase=implementation`、`current_task.state=dispatched`）
- source_sha256（`BOOKKEEPER_APPEND_ONLY` 标记前字节，UTF-8）：`fff76f0330beea8e8cd6ae47ce69662db36507f3d0bc79c69c064cb207f0d2e1`
- 源边界复核：源区块收口于 Human Brief 闭合代码块（`...[/TASK_RESULT]\n\n`），标记独占一行。
- 核验结论：**通过核验，阶段一前端展示与断言交付采信**。
  1. **修改范围合规**：修改文件严格受限于 dispatch 声明的 `frontend/index.html`、`frontend/self-check.js` 与 `backend/tests/test_frontend_field_binding.py`；
  2. **create-only 成立**：本交接件在预检时为 ABSENT，本次任务新建；
  3. **功能与排版落地**：
     - 持仓表（`#positionsTable`）与历史表（`#closeLogsTable`）表头均增加「手续费成本」列；
     - 空态 `colspan` 分别更新为 18 与 17；
     - 未全/null 显示「—」，完整时支持折 U 金额与双行 BNB 数量；
     - 修复了既有 `test_frontend_field_binding.py` 的 `loadHedgeTasks` 签名锚点；
  4. **自动化测试 100% 全绿**：
     - `node frontend/self-check.js` 全部自检通过；
     - `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_frontend_field_binding.py backend/tests/test_hedge_api.py backend/tests/test_hedge_store.py backend/tests/test_hedge_purity.py` 147 passed。
- 可复现命令（核验脚本）：
  `python3 -c "import hashlib;raw=open('reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/32-phase1-frontend-ui-kimi.handoff.md','rb').read();m=b'<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->';print(hashlib.sha256(raw.split(m)[0]).hexdigest())"`
- 后续状态：提交本交付 commit，更新 `status.json` 至 `revision=12`，派发阶段一独立的 Review-1 评审任务给 Opus 5（`40-phase1-review1-opus5`）。

## Errata (append-only)

（暂无。）

