Identity:
- task_id: `review-1-backend-ledger-store-fetch-v1`
- target_role: `Reviewer`（Review-1，只读）
- target_model: `kimi`
- provider: `moonshot`
- status_revision: `10`
- required_skill: `agents/skills/code-reviewer.md`

Goal

对任务 A `backend-ledger-store-fetch-v1` 的交付做 review-1（HIGH_RISK：资金/账务语义）。作者 `claude_glm`（`zhipu_glm`）；本评审须跨 provider（`moonshot` 首选；如不可用由 Human 改派 `deepseek`）。fresh 只读会话。

**受审对象（fixed range）**：`base_sha=dc4cc6d9dc629c06cff4a98f98ff7a81a533a3c8` .. `delivery_sha=aba7420c07024b0e5cc31d4ae5b166ada5314841`。
**受审范围 = 任务 A 的 Allowed Files**（区间内唯一本任务改动）：
- `backend/services/private_client.py`（白名单 13→15、`fetch_interest_history_page`、`fetch_um_income_page`）
- `backend/ledger_flow/__init__.py`、`backend/ledger_flow/domain.py`、`backend/ledger_flow/store.py`（新建）
- `backend/tests/test_ledger_flow_domain.py`、`backend/tests/test_ledger_flow_store.py`（新建）、`backend/tests/test_private_client.py`
- 证据：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-store-fetch-v1.handoff.md`（含 Bookkeeper Verification）与 `backend-ledger-store-fetch-v1.pytest.txt`

**范围说明**：`dc4cc6d..aba7420` 区间内含本 stage 的 fake 前端原型与 bookkeeper 控制提交（`84e37b0`/`8da9649`/`d46523d`/`a8dee78` 等），与 A 的 Allowed Files 零重叠——它们是**上下文而非受审交付**；针对它们的发现按 `AGENTS.md` §8 范围三分类标注。评审以 A 的 Allowed Files 为实际受审范围。

**重点核查**（不限于）：
1. 白名单两条路径与 base URL 正确、deny-by-default / GET-only / 门禁先于签名 / 审计日志不含密钥与签名 / 单一 HMAC 出口未变。
2. 两个单页 fetcher：不写 `PrivateClient.last_error`（快照 `borrow_validation` 降级依据）、不走 `_cached_get`（TTL 旧数据）、失败以 `PrivateEndpointError` 上抛、参数形状与设计 §13.5 一致。
3. `domain.py` 纯函数四硬规则：19 位 ID 一律 `str`（`>2^53`）、金额/利率原样字符串透传且缺失/空串→`None`、`Decimal` 求和于显式 `localcontext(prec=40)` 并 `format(total,"f")`、分组内任一不可解析金额→`*_total=None` 且 `unparsed_row_count>0`（绝不用部分和冒充合计）；去重键（`tx_id` / `(income_type, tran_id)`）与倒序排序键符合 §13.2 规则 6；`summarize_funding_by_symbol` 与冻结形状一致。
4. `store.py` F1 事务模型：`insert_run` 独立事务绝不被明细失败回滚；`commit_interest`/`commit_income` 各自一个事务（明细 + 该源 coverage + gaps 同提交）；任一源失败回滚该源、不影响另一源与 run 记录；`ON CONFLICT DO NOTHING` 绝不覆盖 `first_seen_*`；同批行共享 `first_seen_at_ms`/`run_id`。
5. 金额精度红线：金额列 `TEXT`；store 无 `SUM`/`AVG`/`TOTAL`/算术 SQL、无 `float()` 参与金额路径；高精度金额往返逐字符不变。
6. 查询面：窗口明细（可限行）、全量汇总行、`first_seen_at_ms > baseline_ms` 增量、分源 coverage + gaps 读写、`recent_runs` 只按 `finished_at_ms` 倒序且**不判成功语义**（F3）；空库所有查询安全返回 `[]`/`None`。
7. 测试质量：84 个离线测试是否覆盖上述硬规则（尤其注入失败点、不可解析金额、空库、幂等不覆盖、高精度往返）；有无关键路径无测试；`test_private_client.py` 白名单断言 13→15 与 base-url 集合同步。
8. 边界：未新增 HTTP 路由、未启动线程、未改 `server.py`/`snapshot_service.py`/快照 schema/60 秒调度/cache-refresh/持仓合并/前端；`backend/ledger_flow/__init__.py` 仅 docstring。

Allowed Files

- 只读。唯一可写：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/review-1-backend-ledger-store-fetch-v1.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`（2026-08-04 17:00 CST）：PASS(absent)；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件，只含你自己的结论与证据路径）
- **不得**修改：受审代码/测试/其他 packet、`status.json`、`PROJECT_STATE.md`、git 提交

Inputs

- `AGENTS.md`（§3 安全内核、§7 任务结果协议、§8 评审规则与范围三分类）
- `agents/roles.md` 的 Reviewer 章节与 Task Handoff Evidence Contract 章节
- `agents/skills/code-reviewer.md`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-store-fetch-v1.handoff.md`（交付事实、domain/store/fetcher 公开签名、Bookkeeper Verification）
- `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（定稿 v1.2：§13.2/§13.5/§13.6/§14/§15.4 为权威契约）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-review-r2-dual-ledger-flow-log-v1.handoff.md`（N1–N10 观察项，与本任务相关的 N2/N3 已由实现处理，请核对）
- `backend/services/private_client.py`、`backend/ledger_flow/*`、`backend/tests/test_ledger_flow_*.py`、`backend/tests/test_private_client.py`
- 两份 recon（`reports/api-samples/2026-08-*-recon-v1/.../recon.md`，接口事实）

Acceptance Checks

1. 按 Goal 逐项核查并给出判断与依据（引用 文件:行号 或 § 号）。
2. 每条发现按 `AGENTS.md` §8 标注范围三分类（`in-range` / `pre-existing-independent` / `pre-existing-release-critical`，后者须附引入提交引用）；针对 fake 前端/控制提交的发现为范围外，按三分类处理。
3. 每条发现标严重度（阻塞 / 建议修改 / 观察）；阻塞项须给出可执行的修复要求。
4. 结论：`评审结论: ACCEPT（接受） | REWORK（返工）`，附 `问题记录: <path | none>` 与 `修复要求: <path | none>`（按 `AGENTS.md` §7）。
5. 创建唯一交接件 `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/review-1-backend-ledger-store-fetch-v1.handoff.md`（Source Report + Human Brief，含 `TASK_RESULT v2` 与三行中文交接；`delivery_sha` 写 `none`）；控制台回执与 Human Brief 一致。
6. 全程只读：不修改受审对象、不启动其他终端、不访问网络、不读凭据、不做实盘操作。

Stop

评审是只读的；唯一写是创建上述 create-only 交接件。不改代码、不改 packet、不改 `status.json`、不建分支、不提交。不替 Human 做合并/部署/实盘决策。评审完成后停止，等待 Human 把 verdict 转交 Bookkeeper。
