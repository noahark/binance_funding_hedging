Identity:
- task_id: `review-1-position-balance-display-v1-deepseek`
- target_role: `Reviewer`（Review-1）
- target_model: `deepseek`
- provider: `deepseek`
- status_revision: `11`
- required_skill: `agents/skills/code-reviewer.md`

Goal

以独立、只读方式审查 v4.1 双账户余额展示的完整固定范围 `89103303bd29a64ac5915b56639f8a4a885a56b7..7f965f8282c989625a80dfde0be96b0e008cafab`。这一范围含派发与核验的 Bookkeeper 控制提交；它们仅作上下文，受审产品交付是后端 `65bdd8176d7e9757f97886a902932e999919a441` 与前端 `7f965f8282c989625a80dfde0be96b0e008cafab`。实现作者分别为 `claude_glm`（Zhipu）与 Grok（xAI）；DeepSeek provider 与二者均不同，满足 Review-1 隔离。DeepSeek 曾完成本范围的只读计划评审但未参与设计决策或实现，现须以代码、固定 diff 和证据重新独立判断。

核查 v4.1 §9 的实际效果：后端四字段纯投影及契约、前端双行余额与隐私/缺失语义、抵押额度标签位置、两个时间位置，以及缓存刷新/GET pure-read/无自动轮询等既有边界保持。只以明确、可复现的 in-range 缺陷阻塞；不得针对未经证实的极端场景增加机制。

Allowed Files

- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/review-1-position-balance-display-v1-deepseek.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`，结果为通过；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件）

Inputs

- `AGENTS.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/review-1-position-balance-display-v1-deepseek.dispatch.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`
- `agents/roles.md` 的 Reviewer 与 Task Handoff Evidence Contract 章节
- `agents/skills/code-reviewer.md`
- `docs/planning/hedge-status-account-refresh-v4.md`（§9）
- `docs/api/public-market-contract.md`（v0.11）
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/plan-review-position-balance-display-v1-deepseek.handoff.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-position-balance-display-v1.handoff.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-position-balance-display-v1.pytest.txt`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-position-balance-display-v1.handoff.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-position-balance-display-v1.self-check.txt`
- 固定 diff `89103303bd29a64ac5915b56639f8a4a885a56b7..7f965f8282c989625a80dfde0be96b0e008cafab` 及其触及的源码、测试与契约

Acceptance Checks

1. 核验固定 SHA、两位实现作者到 DeepSeek 的 provider 隔离、两个 delivery 的产品范围与 create-only handoff；控制提交不作为产品交付发现。
2. 核验 `merge_positions` 在唯一 row 构造路径中从同一已发布 `private_account` 精确投影现货/统一账户 amount + `value_usdt`；未就绪、单侧缺失、真零、1000x 不对齐与输入不变性正确，`cross_margin_borrowed` 仍为独立借款列，positions GET 保持零上游 I/O，v0.11 契约与 exact keyset 一致。
3. 核验市场表抵押额度「已满」/「未知」只迁移一次到同一行「借贷状态 / 资产」单元格；判定三态、title、排序/过滤/按钮语义不变。
4. 核验真实对冲开单持仓的两行余额只消费 positions row 四字段：两侧独立缺失、amount 有/value 缺失、真零和隐私遮蔽均诚实；不从 snapshot 拼接，不重算估值，借款列不变。
5. 核验聚合账户时间唯一地替换标题区固定副标题，右侧只余倒计时/两个刷新按钮；PM 时间只在私有账户标题下呈现 capability 缺失隐藏、null 未就绪、成功北京时间三态，概览无重复；source freshness、缓存 POST、手动 GET、GET pure-read 与零自动轮询边界不变。
6. 独立离线复跑 `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q backend/tests/test_positions_merge.py backend/tests/test_hedge_api.py` 与 `node frontend/self-check.js`；核对各自输出与提交证据一致。不得访问网络、读取凭证、操作实盘或部署。
7. 所有 in-range 阻塞发现须列出文件/行、事实、影响、最小修复及 AGENTS.md §8 的范围分类；范围外发现必须附早于 base 的引入证据。

Stop

保持只读：不得编辑交付代码、测试、契约、status、PROJECT_STATE 或既有证据，不得 commit/merge/push；唯一写入是上述交接件。交接件先完成 Source Report 与 Human Brief，再以其内容生成合规 `[TASK_RESULT v2]` 及明确 `评审结论: ACCEPT` 或 `REWORK`；REWORK 必须有问题记录和可执行修复要求，并在问题记录标明每项范围三分类。不要自行启动 Implementer、Bookkeeper、Review-2、部署或任何实盘/网络操作。
