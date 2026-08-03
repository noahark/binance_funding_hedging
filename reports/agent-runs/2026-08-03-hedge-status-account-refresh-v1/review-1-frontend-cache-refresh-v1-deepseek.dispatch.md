Identity:
- task_id: `review-1-frontend-cache-refresh-v1-deepseek`
- target_role: `Reviewer`（Review-1）
- target_model: `deepseek`
- provider: `deepseek`
- status_revision: `6`
- required_skill: `agents/skills/code-reviewer.md`

Goal

以独立、只读方式审查 Grok/xAI 的前端交付，固定范围 `dab29be5e9ce3dfca47101615225775d8a1c7954..e4b16b01a2d06339920de3893383cc1d62da1425`。这一范围含先前 Bookkeeper 的前端派发控制提交；它仅作上下文，受审产品交付限于 delivery commit `e4b16b0` 的六个文件。后端 `8b624f7` 已获 DeepSeek Review-1 ACCEPT，本次不重复评审该范围；但必须检查前端与其 JSON/HTTP 契约及 v4 设计的接口衔接。审查正确性、用户可见文案、source freshness 语义、自动刷新边界、测试质量与改动范围。仅以明确、可复现的 in-range 缺陷阻塞；不得因假设性极端场景要求增加机制。

Allowed Files

- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/review-1-frontend-cache-refresh-v1-deepseek.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`，结果为通过；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件）

Inputs

- `AGENTS.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/review-1-frontend-cache-refresh-v1-deepseek.dispatch.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`
- `agents/roles.md` 的 Reviewer、Task Handoff Evidence Contract 章节
- `agents/skills/code-reviewer.md`
- `docs/planning/hedge-status-account-refresh-v4.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-cache-refresh-v1.handoff.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/review-1-backend-cache-refresh-v1-deepseek.handoff.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-cache-refresh-v1.handoff.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-cache-refresh-v1.self-check.txt`
- `frontend/index.html`、`frontend/self-check.js`、`frontend/fixture/public-market-snapshot.json`

Acceptance Checks

1. 核验固定 SHA、Grok/xAI→DeepSeek provider 隔离、delivery diff 与 create-only handoff；控制提交不作为产品交付发现。
2. 核验「更新缓存」按钮确为 `POST /api/public-market/cache-refresh`，loading/恢复完整；既有「手动刷新」仍只 GET snapshot。
3. 核验 `{published, account_panels}` 的 complete / partial / not_attempted / published=false / HTTP 失败 / 202 表达不撒谎：仅完成响应后按顺序 `loadApi()`、`loadHedgePositions()`；202 与失败不自动刷新、轮询、SSE 或 WebSocket；partial 不称账户完整更新。
4. 核验右上角只显示旧聚合「账户资产更新时间」，私有账户未读取保留在面板内；两者不复用文案职责。
5. 核验固定五 key 的 UTC→`Asia/Shanghai` 转换：统一/现货单源；PM capability 隐藏、null 未就绪、有时间显示；对冲持仓只在 UM+统一+现货皆有时间时显示最早值，任一缺失诚实未就绪；`price_map` 不占账户标题。
6. 独立运行 `node frontend/self-check.js`；核对 133 个 PASS、输出与已提交证据一致；不得启动服务、访问网络、读取凭证或作实盘操作。
7. 核验无越界后端/契约/任务状态变更、订单/借贷/凭证/部署或新的自动任务定时器；列出所有 in-range 阻塞发现的文件/行、事实、影响、最小修复及 AGENTS §8 三分类。

Stop

保持只读：不得编辑交付代码、fixture、测试、状态、PROJECT_STATE、现有证据，不得 commit/merge/push；唯一写入是上述交接件。交接件先完成 Source Report 与 Human Brief，再以其内容生成合规 `[TASK_RESULT v2]` 及明确 `评审结论: ACCEPT` 或 `REWORK`；REWORK 必须有问题记录和可执行修复要求，并在问题记录标明每项范围三分类。不要自行启动 Implementer、Bookkeeper、Review-2、部署或任何实盘/网络操作。
