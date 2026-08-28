# P11 — Repaid interest price Review-2 dispatch（kimi）

Identity:
- task_id: `P11-repaid-interest-price-review-2-kimi`
- target_role: `Reviewer / Review-2`
- target_model: `kimi`
- provider: `moonshot`
- status_revision: `17`
- required_skill: `agents/skills/reality-checker.md`

Goal:
- 现实性复评——交付是否真的做到它声称的事，尤其资金口径与假绿。**HIGH_RISK 独立只读评审**（资金 / PnL 口径）。

固定范围与 SHA:
- base_sha: `f4f6c6f60113b15a6b7b84abf1c665d67eb00449`（P10 派单控制提交）
- **delivery_sha: `d315fbd9e5ac93461ecdbd8a4edd1890e35f7f4e`**（`status.json.delivery_sha` 同值）
- **固定实现 diff**：`git diff f4f6c6f60113b15a6b7b84abf1c665d67eb00449..d315fbd9e5ac93461ecdbd8a4edd1890e35f7f4e`
  （恰 9 文件：8 个实现文件 + 实现者 handoff；该区间不含任何 stage 控制提交）
- 分支 `main`。`HEAD` 会因本派单等控制提交前移，**这是预期的**——一律以固定 delivery_sha 为准。

需求权威（已定案，不在本轮重新发散）:
- `reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md`
  固定于 `e37d45a29017c739118018cab9f250e74a1155e5`，经 P6 / P8 两轮独立跨 provider
  计划复评；Human 明示豁免剩余计划复评轮直接进入开发。**对计划口径本身的异议记为范围外**并上交 Human。

隔离披露:
- 实现作者：`claude_glm` / zhipu_glm。计划作者：`opus5` / anthropic。
- 本 Reviewer：`kimi` / moonshot，与实现作者跨 provider，隔离成立，须新鲜只读会话。
- **Bookkeeper 特别披露**：本 stage Bookkeeper 已由 `gpt-5.6-sol`/codex 临时移交
  `opus5`/claude（codex 会话额度耗尽）。**Bookkeeper 同时是计划作者**，这是移交造成的
  非常规状态；因此本轮评审对计划落实程度的判断尤其不应受 Bookkeeper 核验结论影响，
  请独立复核。
- **Review-1（grok）与 Review-2（kimi）并行执行**，互不知悉对方结论。

必查项:
- **M1 资金缝隙**（计划 §3.2 / §4.2 B3、B8）：`_dispatch_margin_repay` 返回至
  `store.resolve` 之间是否**只有**一次 best-effort 内存取价；有无网络、重试、sleep、
  跨库读、第二次观测；`_capture_repay_spot_bid` 是否真的绝不抛出；`resolve` 是否在
  异常边界之外无条件恰好执行一次。**该缝隙改动前动作数为 0**，任何多余动作都是新增风险。
- **M2 终态谓词**：是否唯一且为精确 `amount == "0" AND status == "succeeded"`；
  非零部分还款与 `pending`/`unknown`/`failed` 是否一律不锁价；终态后 re-borrow 是否重新开放；
  代码注释与 API 文档是否如实写成 **Human 约定**而非交易所债务归零证明。
- **M3 单一折算权威**：PnL 曲线与持仓视图是否走同一份 domain 实现；
  `(settlement_ms, client_request_id)` 排序与同毫秒 tie-break 是否确定；
  `update_time` → `updated_at_us // 1000` 回退是否正确；开放行用当前价、匹配行用存储价。
- **M4 fail-closed**：终态行缺价、开放行缺当前价是否都让该资产**整体**不计入并遮蔽净收益；
  有无任何路径用当前价 / 计提价 / 零值静默顶替缺失的终态价。
- **M5 schema 与迁移**：是否只加 `repay_price_usdt` / `repay_price_source` 两个 nullable TEXT；
  **是否确实没有 CHECK 或封闭枚举**（计划为 §7 人工 `manual_correction` 保留写入路径）；
  旧库幂等迁移、旧行新列 NULL、`list_records()` 返回是否确定且含 `updated_at_us`。
- **M6 零回归**：`close_log`、既有 `net_pnl` 公式、币本位 `sum_interest_by_asset`、
  前端 wire 形状是否未变；前端确为零改动。
- **M7 被删设计未复活**：债务归零查询、K 线回补、历史推断、`--assume-debt-zero`、
  `coverage_for_window` 闸门、新脚本、新依赖、新抽象层——是否有任何一项以改名或等价形式回到实现里。
- **M8 测试真实性**：T1-T10 是否**真的**被覆盖，还是存在假绿（恒真断言、oracle 不唯一、
  mock 掉被测逻辑、fixture 恰好绕开边界）。**本仓库有前科**：曾出现「断言 warnings 非空」
  而该数组恒非空的假绿，以及候选集为空使断言被空集满足的假绿。请用同等怀疑审视。

已知基线问题（不必重复报告）:
- `backend/tests/test_private_client.py::test_urlopen_only_in_designated_http_clients` 失败，
  因 `backend/services/public_ip_service.py` 未登记直连守卫白名单，属 `PROJECT_STATE.md`
  Open Follow-ups `[OPEN][2026-08-23]` 既有项，Bookkeeper 已独立复现其早于本交付。

复现命令（Bookkeeper 已全部自跑，结果见 handoff Bookkeeper Verification 段）:
```bash
.venv/bin/python -m pytest backend/tests/test_ledger_flow_domain.py backend/tests/test_ledger_flow_service.py backend/tests/test_margin_repay.py -q   # 期望 177 passed
.venv/bin/python -m pytest backend/tests -q      # 期望 2062 passed, 1 failed(基线)
node frontend/self-check.js                       # 期望全部通过
git diff --check f4f6c6f60113b15a6b7b84abf1c665d67eb00449..d315fbd9e5ac93461ecdbd8a4edd1890e35f7f4e
```

Allowed Files:
- Reviewer 完全只读，除下面唯一 create-only handoff 外零写入：
  `reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P11-repaid-interest-price-review-2-kimi.handoff.md`
- Bookkeeper 预检（2026-08-28）：该路径 **ABSENT**，create-only 权威成立。
- 不得修改源码、测试、schema、计划、`status.json`、`ACTIVE.json`、`PROJECT_STATE.md`、他人 handoff。
- **不得**运行会启停服务、下单、写库、访问私有 API 或使用凭据的命令；上述复现命令均为只读。

Verdict:
- `ACCEPT` / `REWORK`，逐条对应 M1–M8。按 AGENTS.md §8 范围三分类标注每条发现，
  `pre-existing-*` 须附早于 base_sha 的引入提交引用。
- 若 `REWORK`，给出最小修正建议，不扩大范围。
- 本 verdict 不授权合并、部署、实盘或 §7 的 STORJ 人工数据库修正。

Stop:
- 写完 handoff 即停。不实现、不修复、不推进 stage 状态、不合并、不部署。

reply_to: claude
After emitting the normal console receipt, send that same receipt once to the
reply_to window per `HERDR.md`, then stop.
