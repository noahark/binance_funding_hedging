# Task Handoff: fix-capital-flow-error-zh-v1

## Source Report (author-only; immutable after task end)

- task_id: `fix-capital-flow-error-zh-v1`
- role: Implementer（窄修复，原交付作者）
- target model: `claude_glm`（provider: `zhipu_glm`）
- required_skill: `agents/skills/senior-developer.md`
- stage_id: `2026-08-10-cross-margin-flow-log-v1`
- created_at: 2026-08-10 20:19:11 CST
- base_sha: `a11a8734a3da988501fa5cac5baa52dcea3ea2ef`（未变；`git rev-parse` 一致）
- delivery_sha: `cf247fbf7060e18afeda0c6366c5724b27ef0ce0`（本次修复提交实际 `git rev-parse`，非 pending）
- status_revision 核对: `status.json` revision=6、phase=`fix`、current_task.id=`fix-capital-flow-error-zh-v1`、base_sha 与 `git rev-parse` 一致；rework_count=1；Bookkeeper=`grok4.5`。
- 原实现交付: `9a4e0198ee7f7d2102ab1b9550c39e79a76e24fa`（review-2 REWORK F-1 即针对该交付）。

### 修复对象（review-2 F-1，权威：`evidence/review-2-cross-margin-capital-flow-v1.handoff.md`）

本次交付（`9a4e019`）新增两个 capital 失败短码——`_ERR_CAPITAL="capital_flow_failed"`（`service.py:45`）与字面量 `"capital_internal_error"`（`service.py` `_run_capital_flow` 兜底分支）——但前端 `FLOW_LOG_ERROR_ZH`（`frontend/index.html:6931-6936`）未补对应中文。消费方 `flowLogErrorZh`（`FLOW_LOG_ERROR_ZH[code] || String(code)`）未命中时**原样透传 snake_case 短码**，故 capital `last_run.status=error` 时中栏状态行/空态会显示「上次失败：capital_flow_failed」之类英文短码，与同文件既有四码 100% 配中文的先例（及项目「UI 以中文为主」惯例）不一致。`rate_limited` 因复用既有映射已配中文，无需处理。review-2 另指出 self-check 的 mock payload 恒为「成功」形状，是放过 F-1 的断言盲区。

### 实际修改范围（全部在 `cf247fb`，仅前端两文件）

| 文件 | 改动 |
|---|---|
| `frontend/index.html` | `FLOW_LOG_ERROR_ZH` 字面量新增两 key：`capital_flow_failed: '全仓流水拉取失败'`、`capital_internal_error: '全仓流水内部错误'`（措辞与既有「利息历史拉取失败」「合约流水拉取失败」同风格）。既有四条映射逐字不变。消费方 `flowLogErrorZh` / `renderFlowLogCapitalCol`（已在 `9a4e019` 调用 `flowLogErrorZh(last.error)`）无需再改，补映射即生效。 |
| `frontend/self-check.js` | 新增一条 F-1 回归断言块（98b-F1）：构造 `capital_flow.last_run={status:'error',error:'capital_flow_failed'}` + 空 rows 的 payload，`renderFlowLogPanel` 后断言中栏状态行含「全仓流水拉取失败」、不含 `capital_flow_failed` snake_case、空态亦不露短码。关上「mock 恒成功」盲区。无其它逻辑改动。 |

未触碰：`backend/**`、`docs/**`、`data/**`、capital 拉取/隔离逻辑、schema/契约。diff = index.html +2 行 / self-check.js +29 行，无无关改动。

### 为何直接回 review-2（§8）

按 `AGENTS.md` §8「A narrow review-2 finding returns directly to review-2 after repair, retest, and a new commit」与「A review-2 repair that expands files, changes a contract, or adds risk must pass review-1 again」：本修复仅改前端展示文案映射 + 一条测试断言，**未扩文件范围**（两个文件都是原交付 `9a4e019` 已触碰的文件）、**未改契约/schema**、**未新增风险**（纯失败态 i18n 文案），故直接回 review-2，不重新 review-1。

### 对 dispatch 五条 Acceptance Checks 的逐条判断

1. `FLOW_LOG_ERROR_ZH` 含 `capital_flow_failed`→`全仓流水拉取失败`、`capital_internal_error`→`全仓流水内部错误` → **pass**。
2. 中栏 `last_run.status=error` 经 `flowLogErrorZh` 显示上述中文、不露 snake_case → **pass**（新断言 `98b-F1` 直接验证）。
3. 既有四条错误中文映射不变、无其它无关 diff → **pass**（`git diff` 仅 +2/+29 行，集中在两处）。
4. `node frontend/self-check.js` 全绿、含新增失败态断言 → **pass**（末行「全部自检通过」，含 `[PASS] review-2 F-1：…`）。
5. 创建唯一 handoff、顺序 实现→自测→提交→写 handoff、`delivery_sha=cf247fb` 实际 `git rev-parse`（非 pending） → **pass**。

### 自测命令与结果（原始输出）

```text
$ node frontend/self-check.js
（含）[PASS] review-2 F-1：capital 失败态显示中文（全仓流水拉取失败），不露 snake_case 短码
（末行）全部自检通过
```

（本修复无后端/契约改动，dispatch 未要求 pytest；未跑后端用例以守「不扩大范围」。）

### 未完成事项

- 无。本轮不启动 review、不 merge、不 push、不部署、不重启服务（dispatch Stop）。
- 待办（非本轮）：Bookkeeper 封存后由 Human 启动 review-2 复审 `cf247fb`（直接回 review-2）。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/fix-capital-flow-error-zh-v1.handoff.md`（本文件）
  2. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/review-2-cross-margin-capital-flow-v1.handoff.md`（F-1 与修复要求权威）
  3. `frontend/index.html`（`FLOW_LOG_ERROR_ZH`，第 6931-6938 行）
  4. `frontend/self-check.js`（`98b-F1` 断言块）
- 执行：Bookkeeper 核验本 handoff、解析 `delivery_sha=cf247fb` 写入 `status.json` 并封存；随后由 Human 启动 review-2（§8 窄发现，直接回 review-2，不重新 review-1）。
- 关卡：review-2 复审 `cf247fb`（base_sha=`a11a873`）。
- 不能假设的事实：
  - 不能假设 `capital_flow_failed` / `capital_internal_error` 是既有短码——二者由本次 stage 的 `9a4e019` 首次引入。
  - 不能假设失败态只走状态行——`renderFlowLogCapitalCol` 的空态分支（rows 空 + `last.status=error`）也调用 `flowLogErrorZh`，两处都已被新断言覆盖。
  - 不能假设本修复触发 review-1——按 §8 窄发现直接回 review-2。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: fix-capital-flow-error-zh-v1
执行结果: completed（完成）
结果摘要: 修复 review-2 F-1：FLOW_LOG_ERROR_ZH 补 capital_flow_failed→全仓流水拉取失败、capital_internal_error→全仓流水内部错误，中栏失败态经 flowLogErrorZh 显示中文、不再露 snake_case。self-check 补一条失败态中文断言（关上 mock 恒成功的盲区）。仅前端两文件，无后端/契约/schema/隔离改动。self-check 全绿。
产物: [reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/fix-capital-flow-error-zh-v1.handoff.md, frontend/index.html, frontend/self-check.js]
检查结果: [FLOW_LOG_ERROR_ZH 含 capital_flow_failed/capital_internal_error 两条中文=pass；中栏 last_run.status=error 经 flowLogErrorZh 显示中文、不露 snake_case=pass；既有四条错误中文映射不变、无无关 diff=pass；self-check 全绿含新增失败态断言=pass；唯一 handoff 创建 delivery_sha=cf247fb 实际 git rev-parse=pass]
阻塞项: [none]
本地北京时间: 2026-08-10 20:19:11 CST
下一步模型: grok4.5（本阶段 Bookkeeper，status.json.bookkeeper=grok4.5，由 Human 启动其终端）
下一步任务: 读取：reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/fix-capital-flow-error-zh-v1.handoff.md；reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/review-2-cross-margin-capital-flow-v1.handoff.md；frontend/index.html；frontend/self-check.js；执行：Bookkeeper 核验本 handoff、解析 delivery_sha=cf247fbf7060e18afeda0c6366c5724b27ef0ce0 写入 status.json 并封存；关卡：§8 窄发现，由 Human 启动 review-2 直接复审 cf247fb（不重新 review-1），ACCEPT 后由 Human 决定合并/部署。
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- bookkeeper: `grok4.5`
- verified_at: 2026-08-10 20:20:52 CST
- status_revision_at_verify: 6（fix / `fix-capital-flow-error-zh-v1` / dispatched）
- source_payload_sha256: `9d618a8c556dcef1c105c8d6c53243463b164d2341c972f53d2208634264f8b8`（marker 前全部字节）
- delivery_sha 解析：`cf247fbf7060e18afeda0c6366c5724b27ef0ce0` = `git rev-parse` 一致；`git show --stat` 仅 `frontend/index.html` + `frontend/self-check.js`（+2/+29），符合 Allowed Files 与窄修复边界
- 独立复跑：`node frontend/self-check.js` → 全部自检通过（含 F-1 失败态中文断言）
- 源码抽查：`FLOW_LOG_ERROR_ZH` 含 `capital_flow_failed`/`capital_internal_error` 中文；既有四码仍在
- 裁定：**核验通过** → 更新 `delivery_sha=cf247fb`；§8 窄发现直接回 review-2（sonnet5），不重新 review-1；`rework_count` 保持 1
- 后续：Human 启动 review-2 复审固定区间 `a11a873..cf247fb`（含原交付 9a4e019 + F-1 修复）

## Errata (append-only)

（无。）
