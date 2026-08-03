Identity:
- task_id: `review-2-position-balance-display-v1-opus5`
- target_role: `Reviewer`（Review-2，reality check）
- target_model: `opus5`
- provider: `anthropic`
- status_revision: `12`
- required_skill: `agents/skills/reality-checker.md`

Goal

以独立、只读方式对 v4.1 双账户余额展示做最终 reality check，范围是同一个固定区间 `89103303bd29a64ac5915b56639f8a4a885a56b7..7f965f8282c989625a80dfde0be96b0e008cafab`。该区间含派发与核验的 Bookkeeper 控制提交，它们只作上下文；受审产品交付是后端 `65bdd8176d7e9757f97886a902932e999919a441`（`claude_glm`/Zhipu）与前端 `7f965f8282c989625a80dfde0be96b0e008cafab`（Grok/xAI）。评审 provider `anthropic` 与区间内每一位实现作者都不同，满足 Review-2 隔离；Opus 5 未参与本阶段的设计、计划评审或实现。

Review-1（DeepSeek）已返回 ACCEPT 并经 Bookkeeper 核验封存。本任务不重做 Review-1 的逐行代码检查，而是判断 Human 批准的需求（`docs/planning/hedge-status-account-refresh-v4.md` §9）与实际交付效果是否吻合、证据是否足以支撑结论、上线后有哪些运行风险、以及是否具备进入 Human 合并决策的就绪度。默认怀疑：没有证据支撑的结论一律不予认可；证据缺失时 fail-closed。

披露：本阶段 Bookkeeper 已由 `codex` 移交为 `opus5`（Human 决策，codex 额度不可用）。你与 Bookkeeper 同模型但是彼此独立的会话；Bookkeeper 只做状态核验与派发，未参与任何实现或设计，受审代码全部来自 Zhipu 与 xAI 作者。如你认为该同模型关系削弱了本次评审的独立性，在交接件中明确披露并上交 Human，不要自行更换路由。

Allowed Files

- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/review-2-position-balance-display-v1-opus5.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e <path>`，结果为不存在，通过；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件，路径已存在即任务失败）

Inputs

- `AGENTS.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/review-2-position-balance-display-v1-opus5.dispatch.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`
- `agents/roles.md` 的 Reviewer 与 Task Handoff Evidence Contract 章节
- `agents/skills/reality-checker.md`
- `docs/planning/hedge-status-account-refresh-v4.md`（§9，尤其 §9.5 的五条验收标准）
- `docs/api/public-market-contract.md`（v0.11 的 positions projection 字段与 null/真零语义）
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/review-1-position-balance-display-v1-deepseek.handoff.md`（含 Bookkeeper Verification 追加块）
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-position-balance-display-v1.handoff.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-position-balance-display-v1.pytest.txt`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-position-balance-display-v1.handoff.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-position-balance-display-v1.self-check.txt`
- 固定 diff `89103303bd29a64ac5915b56639f8a4a885a56b7..7f965f8282c989625a80dfde0be96b0e008cafab` 及其触及的源码、测试与契约

Acceptance Checks

1. 需求闭合：逐条对照 v4.1 §9.5 的五条验收标准与实际交付，判定每条成立或不成立；并确认本次改动没有触碰 §1–§8 已锁定的 refresh cycle、source 时间语义、`/hedge-open-positions` 的 zero-upstream GET 性质、无自动前端刷新，以及全部资金、订单、借贷、划转、Start gate 与风险限制边界。
2. 实际效果与展示诚实性：判断这些展示语义在真实使用中会不会误导资金决策——账户未就绪时四字段全 null、单侧账户缺该 asset 时只该侧为 `—`、真 `0` 仍显示 0 而不退化为未知、估值缺失时显示 `≈ — U`、隐私模式同时遮蔽数量与估值、1000x 资产不自动对齐因而全 null，以及「杠杆」行是统一账户全仓余额而非 `cross_margin_borrowed`（借款仍在独立列）。任何可能让用户把未知读成 0、把借款读成余额或把两个账户读混的地方都要具名指出。
3. 证据充分性：独立离线复跑 `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q backend/tests/test_positions_merge.py backend/tests/test_hedge_api.py` 与 `node frontend/self-check.js`，与提交证据比对；然后判断这些证据是否真的支撑「页面会那样显示」，并明确指出 self-check 覆盖不到而只有真实浏览器或真实账户数据才能暴露的风险。不得访问网络、读取凭证、启动服务、操作实盘或部署。
4. 运行风险与发布就绪：这是纯展示投影交付，评估它在真实运行下的风险面——`private_account.verified=false`、PM capability 缺失、某侧 `value_usdt` 为 null、资产在一侧账户不存在等状态下的页面表现；并确认代码中没有任何路径把这四个展示字段用于下单、借贷、风控或缓存写入。给出「是否具备进入 Human 合并决策的就绪度」的明确判断。
5. Review-1 闭包复核：核验 Review-1 的 ACCEPT 与其 2 项非阻塞观察是否成立，独立判断观察 1（`backend/tests/test_positions_merge.py` 与 `docs/api/public-market-contract.md` 各一个 EOF 多余空行）是否需要在合并前处理；并对 Bookkeeper 把 Review-1 回执缺少 `评审结论:` / `问题记录:` / `修复要求:` 三行字段裁定为「格式偏差、非拒收」表示同意或反对，理由写入交接件。
6. 发现分类：所有 `REWORK` 发现必须给出文件/行、事实、影响、最小修复，并按 `AGENTS.md` §8 标注 `in-range`、`pre-existing-independent` 或 `pre-existing-release-critical`；`pre-existing-*` 必须附早于 `base_sha` 的引入提交引用（`git blame` 或 `git log -L`），无此证据者只记为观察。不得为未经证实的极端场景要求新增机制。
7. 回执合规：`[TASK_RESULT v2]` 块内必须含显式独立字段行 `评审结论: ACCEPT` 或 `评审结论: REWORK`，以及 `问题记录: <path | none>` 与 `修复要求: <path | none>`；`结果摘要` 不超过 300 字符，`检查结果` 不超过八项，三条中文交接行齐全，`[/TASK_RESULT]` 为最后一行非空白输出。

Stop

保持只读：不得编辑交付代码、测试、契约、`status.json`、`PROJECT_STATE.md` 或任何既有证据，不得 commit、merge、push；唯一写入是上述 create-only 交接件。先完成交接件的 Source Report 与 Human Brief，再以其内容生成一致的控制台回执，不得另写与交接件不一致的叙事。不要自行启动 Implementer、Bookkeeper、下一轮评审、部署或任何实盘/网络操作。ACCEPT 不等于合并、部署或实盘授权，这些仍由 Human 在本次评审返回后单独决定。
