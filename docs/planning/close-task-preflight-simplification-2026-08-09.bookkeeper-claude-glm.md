# 平仓两段式交付：Claude-GLM Bookkeeper 执行文稿

## Identity

- task_id: `close-task-preflight-simplification-bookkeeper-seal`
- target_role: `Bookkeeper`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `bootstrap`（当前 `reports/agent-runs/ACTIVE.json` 为 `{"active": null}`）
- required_skill: `none`

## Goal

Human 已指定本次由 Claude-GLM 担任 Bookkeeper。把 Codex/OpenAI 已完成但尚未提交的“平仓任务两段式建卡 + 启动后预检瘦身”交付核验并封存成固定 `base_sha..delivery_sha`，建立 `HIGH_RISK` stage，准备 Opus 5/Anthropic 的正式 Review-1 dispatch。

你不是实现者或评审者：不得修改产品实现来“顺手修好”，不得给出代码评审 `ACCEPT/REWORK`。核验不通过就停在 Bookkeeper 拒收；核验通过才提交、建 stage 和准备下一份 dispatch。

本稿允许为封存创建并切换本地分支 `codex/close-task-preflight-simplification`。不授权 merge、push、部署、重启、服务控制、live DB、交易所请求、凭据或 gate 操作。

## Allowed Files

### 可核验并纳入 delivery commit 的既有交付

- `PROJECT_STATE.md`
- `backend/hedge_open_tasks/domain.py`
- `backend/hedge_open_tasks/service.py`
- `backend/hedge_open_tasks/store.py`
- `backend/services/hedge_preflight_provider.py`
- `backend/tests/test_hedge_cycle_close.py`
- `backend/tests/test_hedge_leverage.py`
- `backend/tests/test_hedge_preflight_provider.py`
- `backend/tests/test_hedge_service.py`
- `backend/tests/test_hedge_task_local.py`
- `docs/architecture/ARCHITECTURE.md`
- `docs/planning/DECISIONS.md`
- `docs/planning/hedge-open-position-cycle-v1.md`
- `docs/product/PRD.md`
- `frontend/index.html`
- `frontend/self-check.js`
- `docs/planning/close-task-preflight-simplification-2026-08-09.review-request-opus5.md`
- `docs/planning/close-task-preflight-simplification-2026-08-09.review-opus5-result.md`
- `docs/planning/close-task-preflight-simplification-2026-08-09.v2.review-request-opus5.md`
- `docs/planning/close-task-preflight-simplification-2026-08-09.v2.review-opus5-result.md`

### 核验通过后可创建或纳入 control commit 的 Bookkeeper 控制文件

- `reports/agent-runs/ACTIVE.json`
- `reports/agent-runs/2026-08-09-close-task-preflight-simplification-v1/**`
- 本文稿
- `docs/planning/close-task-preflight-simplification-2026-08-09.review-1-code-opus5.md`

控制文件不得进入 delivery commit；它们在 delivery SHA 已产生后进入单独的 ledger/control commit。`PROJECT_STATE.md` 当前已经把本交付标成“本地待评审、未部署”，若事实一致，不要为改措辞再动它。

除上述路径外不得写文件。发现额外或重叠改动就停下，不覆盖其他终端工作。

## Inputs

严格按顺序读取：

1. `AGENTS.md`
2. `docs/planning/close-task-preflight-simplification-2026-08-09.bookkeeper-claude-glm.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `agents/roles.md` 的 `Shared Rules`、`Task Handoff Evidence Contract`、`Bookkeeper` 小节
6. `docs/planning/close-task-preflight-simplification-2026-08-09.v2.review-request-opus5.md`
7. `docs/planning/close-task-preflight-simplification-2026-08-09.v2.review-opus5-result.md`
8. `docs/planning/close-task-preflight-simplification-2026-08-09.review-1-code-opus5.md`
9. `git diff`、列入 Allowed Files 的实现/测试/活文档，以及实际测试原始输出

固定已知事实：

- 当前预期分支：`main`
- 预期 `HEAD` / `base_sha`：`dc356cd7f6acdc8502cd6caa44a48f6e3c760cac`
- 实现作者：Codex / OpenAI
- 计划复评：Opus 5 / Anthropic，结论 `ACCEPT`
- 当前运行中服务仍是旧行为；本地改动未提交、未部署、未重启、未做实盘验证
- 本次属于订单/持仓/划转前置门的 `HIGH_RISK` 交付，Review-1 后仍必须 Review-2；任何评审接受都不等于合并或部署授权

若现场任一固定事实不成立，先用只读证据解释差异；无法证明安全时返回 `blocked`，不要猜。

## Acceptance Checks

### A. Intake 与边界核验

1. 确认 `ACTIVE.json` 仍为 `{"active": null}`，Git `HEAD` 精确等于上述 base，且没有已存在的同名 stage。
2. `git status --short` 只能出现 Allowed Files 中列出的既有交付和两份控制文稿；不得出现 `.env`、数据库、凭据、日志、缓存或未知文件。
3. 用 `git diff --check`、逐文件 diff 和调用链核对实现确实对应 v2 计划及 C1—C3；Bookkeeper 只核验完整性，不代替独立代码评审。
4. 确认四份计划/计划评审文稿内容未被当前实现终端改写；它们可随交付提交以闭合 DEC 引用。

### B. 独立复测

运行并保留原始输出到 stage evidence（不要只写摘要）：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider backend/tests
node frontend/self-check.js
git diff --check
```

预期基线是后端 `1610 passed`、前端 self-check 全通过、`git diff --check` 通过。数量变化、失败、跳过或环境限制都必须解释；不得把旧终端的口头结果当成你自己的验证。

同时用静态/单测证据确认整个 Bookkeeper 过程没有交易所请求、服务控制、live DB 写入、凭据读取、gate 操作或订单/划转。

### C. 交付提交

仅在 A/B 全部通过后：

1. 创建并切换 `codex/close-task-preflight-simplification`；不得 merge 或 push。
2. 只显式 stage“可核验并纳入 delivery commit”的 20 个文件，不使用会误收控制文件或未知文件的宽泛 add。
3. 提交信息建议：`feat: defer close preflight until manual start`。
4. 用 `git rev-parse HEAD` 取得 `delivery_sha`，确认 `base_sha..delivery_sha` 恰好包含本次产品实现、测试、活文档和四份计划证据。
5. 两份控制文稿不得进入该 delivery commit；Review-1 的固定范围始终是 `dc356cd7f6acdc8502cd6caa44a48f6e3c760cac..delivery_sha`。

### D. 建立 stage 并准备正式 Review-1 dispatch

交付提交后创建：

- stage_id：`2026-08-09-close-task-preflight-simplification-v1`
- bookkeeper：`claude_glm`
- phase：`review-1`
- checkpoint：`delivery-sealed`
- base_sha：上述固定 base 的直接 `git rev-parse` 值
- delivery_sha：C 节新提交的直接 `git rev-parse` 值
- ledger_sha：准备本次 status 更新前的已验证 delivery SHA
- rework_count：`0`
- blockers：`[]`
- current task：`close-task-preflight-simplification-review-1-opus5`，状态 `dispatched`
- next：Human 启动准备好的任务

建立 stage intake evidence，至少记录：Human 直接授权、实现作者/provider、计划评审 `ACCEPT`、准确改动文件、A/B 原始证据路径、base/delivery SHA、未部署事实。不要伪造一个事后 Implementer handoff；本 stage 是对已完成 Human-direct 工作树的 review intake。

随后按 `agents/roles.md` 的最小 dispatch shape 创建 Review-1 dispatch：

- target_role：`Reviewer`
- target_model：`opus5`
- provider：`anthropic`
- required_skill：`agents/skills/code-reviewer.md`
- 固定范围：上面的 `base_sha..delivery_sha`
- Allowed Files：只允许新建一个预先 `test ! -e` 通过的确定性 handoff：`reports/agent-runs/2026-08-09-close-task-preflight-simplification-v1/evidence/close-task-preflight-simplification-review-1-opus5.handoff.md`
- Inputs 必须包含 Task Handoff Evidence Contract、`status.json`、stage intake evidence、v2 计划、v2 计划评审、Opus code-review companion 以及固定 diff
- 明确披露 Opus 5 参与过计划复评但未写实现；provider 与 OpenAI 实现作者隔离成立
- Acceptance Checks 引用 code-review companion 的逐项检查，但正式 dispatch 自己必须给出确定 SHA、status revision、handoff create-only 路径和 stop 条件
- Stop：Reviewer 只读，除确定性 handoff 外零写入；不得提交、修码、merge、push、部署或触碰实盘

先准备 dispatch，最后一次更新 `status.json` 使其指向该 dispatch，再更新 `ACTIVE.json`。把 stage 文件、两份控制文稿作为 ledger/control commit 提交；该提交不是 delivery SHA，也不得扩大 Review-1 范围。

### E. 收口核验

1. 用 `git rev-parse` 复核 status 内每个 SHA，验证 formal review diff 未随 ledger commit 移动。
2. 验证 Review-1 handoff 路径尚不存在且 dispatch 已记录 create-only preflight。
3. 工作树应无未知或遗漏文件；若因合理证据文件仍有改动，明确列出并处理后再交接。
4. 最终只报告“已封存并准备 Review-1”或具体 blocker；不得替 Opus 宣布评审结论。

## Stop

完成固定交付区间、stage、证据和 Opus 5 正式 Review-1 dispatch 后停止，等待 Human 启动 Opus 5。不得自行调用、转发给、模拟或启动下一模型。

按 `AGENTS.md` §7 输出合规 `[TASK_RESULT v2]`，`下一步模型` 写 `Opus 5 / Anthropic（由 Human 启动）`，`下一步任务` 必须用“读取／执行／关卡”格式指向你创建的正式 Review-1 dispatch；闭合标记后不得再输出任何文字。
