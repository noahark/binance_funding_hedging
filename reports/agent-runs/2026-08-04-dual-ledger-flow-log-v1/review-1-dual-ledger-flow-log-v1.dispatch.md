Identity:
- task_id: `review-1-dual-ledger-flow-log-v1`
- target_role: `Reviewer`（Review-1，只读）
- target_model: `deepseek`
- provider: `deepseek`
- status_revision: `19`
- required_skill: `agents/skills/code-reviewer.md`

Goal

对双栏流水日志的**统一实现交付**（任务 A + B + C + 前端最终布局）做 review-1（`HIGH_RISK`：资金/账务语义 + 本地账本 + 定时上游拉取）。作者：A、B = `claude_glm`（`zhipu_glm`），C 与两轮前端布局 = `grok`（`xai`）。本评审须与两者全部跨 provider（`deepseek` 满足；kimi 额度 2026-08-07 后可用，本轮不候）。fresh 只读会话。

**受审区间（fixed）**：`base_sha=dc4cc6d9dc629c06cff4a98f98ff7a81a533a3c8` .. `delivery_sha=5613c4e4d1d3668c04ae5f05e264edb8c0575213`。
**受审范围（区间内本 stage 的实现交付）**：
- 任务 A（`aba7420`）：`backend/services/private_client.py`（白名单 13→15 + 两单页 fetcher）、`backend/ledger_flow/__init__.py`、`domain.py`、`store.py`、`backend/tests/test_ledger_flow_{domain,store}.py`、`test_private_client.py`
- 任务 B（`550f8b7`）：`backend/ledger_flow/service.py`、`scheduler.py`、`backend/app/server.py`、`backend/services/snapshot_service.py`（仅只读访问器）、`docs/api/public-market-contract.md`（v0.12）、`backend/tests/test_ledger_flow_{service,api}.py`
- 任务 C + 前端最终（`f23368b` + `5613c4e`）：`frontend/index.html`、`frontend/self-check.js`
- 证据：A/B/C 与 `plan-v13`、`plan-v14` 的 handoff（含 Bookkeeper Verification）、`plan-review` / `plan-review-r2` / `plan-revise`（计划评审与修订轨迹）、各 `.pytest.txt` / `.selfcheck.txt`

**范围说明**：区间内本 stage 的 fake 前端原型与控制提交（`84e37b0`…`a8dee78` 等）为上下文而非受审交付；针对它们的发现按 `AGENTS.md` §8 范围三分类标注。设计权威 = `docs/planning/2026-08-04-dual-ledger-flow-log-design.md` **定稿 v1.4**（契约章节与 v1.2 冻结内容一致，布局章节为最终形态）；接口权威 = 契约 v0.12。

**重点核查**（不限于）：
1. **契约一致性**：A/B 实现与设计 §13.2/§13.5/§14/§15 及契约 v0.12 逐字段一致（`scheduler_enabled`、`last_run`、`coverage.by_source/gaps/pending_tail_ms/complete`、`delta`、`today`、两栏 rows/summary、`row_limit_applied`、ID 字符串、缺失 null、空态形状）；前端消费与后端返回一致。
2. **资金精度红线**：ID 一律字符串（`>2^53`）；金额/利率原样透传、缺失/空串→null；`Decimal` 求和于 `localcontext(prec=40)`；分组含不可解析金额 → `*_total=null` + `unparsed_row_count>0`；金额列 TEXT、无 SQL `SUM/AVG`、无 `float()` 参与金额路径；前端不重算汇总（`Number()` 仅用于正负号着色）。
3. **store 事务与幂等（F1）**：`insert_run` 独立事务；`commit_interest`/`commit_income` 各自事务（明细+该源 coverage+gaps 同提交）；任一源失败不影响另一源与 run 记录；`ON CONFLICT DO NOTHING` 不覆盖 `first_seen_*`；同批行共享 `first_seen_at_ms`/`run_id`。**已知项**：run 表 `*_new_row_count` 恒 0（store 无 `update_run`；对外语义不受影响——`last_run` 不含该字段、`delta` 用 `first_seen_at_ms`、POST 计数取自 `commit_*` 返回值）——请确认此项确不构成缺陷或需后续修复。
4. **增量与统计（F2/F3）**：`baseline_ms`=倒数第二次成功 run（`scheduled/startup_catchup/backfill` 且两栏 `ok`）的 `finished_at_ms`；`manual` 不入基准且其行计入当前增量；不足两次 `delta.complete=false` 不下发数字；`consecutive_failure_count` 实时计数（disabled 不计、无记录 0）；`today` 北京日界按发生时间；分组不跨币种。
5. **coverage 护栏（F4）与空态**：`complete` 仅起点覆盖 + 无相交 gaps；尾部 `pending_tail_ms` 不参与判定；窗口落空洞内必 `false`；空库 200 且逐字段符合规则 13；前端三态判定表（含 `scheduler_enabled`）无歧义；「空结果绝不允许呈现为没有流水」落实。
6. **调度与并发（Q4/Q7）**：整点 20s 节拍判据（本小时成功 + 尝试<3 + 距上次≥5min）在重启/时钟跳变/休眠下不漏跑不重复；启动 catchup；单飞锁；私有通道未启用不启动且 `scheduler_enabled=false`；独立调度线程边界（借币调度器先例）。
7. **前端展示硬规则**：panel-actions 双看板 tab（`#btn-market-board` 默认选中、`#btn-flow-log`）、侧栏三项（`#nav-flow-log` 已移除）、`setMarketBoard` 同页切换不改 `activeView`、元数据卡片两列 + 窄屏堆叠、60 秒轮询随看板/页进出（恰好一个、切走 `clearInterval`、回调复核）、20 条与三数字文案、筛选零请求、隐私遮蔽、护栏三情形文案、self-check 断言覆盖。
8. **边界**：未新增白名单外请求、无 Binance 直连、无下单/借还/划转/gate/凭据/部署/实盘；`snapshot_service.py` 仅新增只读访问器；未改快照 schema/60 秒调度/cache-refresh/持仓合并。
9. **测试质量**：A 84 + B 31 + 回归 194 + 前端 self-check 全绿——关键路径（注入失败点、不可解析金额、空库、幂等不覆盖、高精度往返、调度判定、空态、轮询生命周期）是否都有断言；有无遗漏风险。

Allowed Files

- 只读。唯一可写：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/review-1-dual-ledger-flow-log-v1.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`（2026-08-04 22:00 CST）：PASS(absent)；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件，只含你自己的结论与证据路径）
- **不得**修改：受审代码/测试/packet/设计、`status.json`、`PROJECT_STATE.md`、git 提交

Inputs

- `AGENTS.md`（§3 安全内核、§7 任务结果协议、§8 评审规则与范围三分类）
- `agents/roles.md` 的 Reviewer 章节与 Task Handoff Evidence Contract 章节
- `agents/skills/code-reviewer.md`
- `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（定稿 v1.4，权威）
- `docs/api/public-market-contract.md`（v0.12 amendment）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-store-fetch-v1.handoff.md`、`backend-ledger-schedule-api-v1.handoff.md`、`frontend-dual-ledger-flow-log-v1.handoff.md`、`frontend-flow-log-tab-layout-v2.handoff.md`、`plan-v13-c-packet-v1.handoff.md`、`plan-v14-layout-final-v1.handoff.md`、`plan-review-r2-dual-ledger-flow-log-v1.handoff.md`（评审轨迹与 N1–N10 观察项）
- 代码与测试（受审文件）、两份 recon（`reports/api-samples/2026-08-*-recon-v1/.../recon.md`）

Acceptance Checks

1. 按 Goal 逐项核查并给出判断与依据（引用 文件:行号 或 § 号/契约节）。
2. 每条发现按 `AGENTS.md` §8 范围三分类标注；针对 fake 前端/控制提交的发现为范围外，按三分类处理。
3. 每条发现标严重度（阻塞 / 建议修改 / 观察）；阻塞项须给出可执行的修复要求。
4. 结论：`评审结论: ACCEPT（接受） | REWORK（返工）`，附 `问题记录: <path | none>` 与 `修复要求: <path | none>`。
5. 创建唯一交接件 `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/review-1-dual-ledger-flow-log-v1.handoff.md`（Source Report + Human Brief，含 `TASK_RESULT v2` 与三行中文交接；`delivery_sha` 写 `none`）；控制台回执与 Human Brief 一致。
6. 全程只读：不修改受审对象、不启动其他终端、不访问网络、不读凭据、不做实盘操作。

Stop

评审是只读的；唯一写是创建上述 create-only 交接件。不改代码、不改 packet、不改 `status.json`、不建分支、不提交。不替 Human 做合并/部署/实盘决策。评审完成后停止，等待 Human 把 verdict 转交 Bookkeeper。
