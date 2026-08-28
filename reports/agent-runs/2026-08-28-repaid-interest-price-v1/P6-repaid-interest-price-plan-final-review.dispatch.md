# P6 — Repaid interest price final plan review（只读计划复评）

Identity:
- task_id: `P6-repaid-interest-price-plan-final-review`
- target_role: `Reviewer / Plan Review (pre-implementation)`
- target_model: `gpt-5.6-sol`
- provider: `openai`
- status_revision: `12`
- required_skill: `agents/skills/software-architect.md`（**仅此一个**；不得同时加载
  `code-reviewer.md` / `reality-checker.md` —— 本轮无实现代码可审）

Isolation disclosure:
- 计划作者：`opus5` / anthropic（P5 定档）；P1/P3 作者：`claude_glm` / zhipu_glm。
- 本 Reviewer：`gpt-5.6-sol` / openai。**跨 provider 成立**，且必须是**新鲜只读会话**
  （`agents/roles.md` Reviewer / Isolation:279-283）。
- 本 stage 的 Bookkeeper 亦为 `gpt-5.6-sol`（窗口 `codex`）。**若本会话与该 Bookkeeper
  会话是同一会话，须停止并要求 Human 另开新鲜会话**——Isolation 要求的是 fresh
  read-only session，不只是 provider 不同。

Goal:
- 对 **P5 定档计划**做实现前的最后一次独立只读复评。**本 stage 至今零实现代码**，
  评审对象是计划文档本身，不是代码 diff。
- 判定该计划是否为落实 Human 最终产品口径的**最小充分**方案，以及 P4 命名的两个根因
  家族是否**真的被穷举扫描**，而不是又一次点补丁。
- 无实现可在 P6 `ACCEPT` 之前开始。

Fixed scope:
- base_sha: `e93af61630e87a759d8820d33fef61789dac1dcd`
- delivery_sha: `4e3fba75a64326a2b57bfe4727b010e7988fef83`
- **评审对象恰好一个文件**：
  `reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md`（P5 定档版）
- 对照前序（作为上下文，不是受审交付）：
  - `P1-repaid-interest-price-plan.dispatch.md`
  - `P3-repaid-interest-price-plan-revision.dispatch.md`
  - `P5-repaid-interest-price-plan-simplification.dispatch.md`
  - `evidence/P2-repaid-interest-price-plan-review.handoff.md`
  - `evidence/P4-repaid-interest-price-plan-rereview.handoff.md`
- 只审固定提交区间
  `e93af61630e87a759d8820d33fef61789dac1dcd..4e3fba75a64326a2b57bfe4727b010e7988fef83`；
  必须先用 Git 核验该区间恰好只改上述计划文件，不得以移动 `HEAD` 或未提交工作区替代。

Human-fixed product rule（不可在评审中重新发散；对口径本身的异议记为范围外并上交 Human）:
- 未出现本地终态事件前，累计利息按当前缓存价格动态折 U。
- 唯一终态：本地资产卡还款且**存储意图** `amount == "0"` **且** `status == "succeeded"`；
  届时用还款成功后捕获的内存现货买一价锁定此前累计利息。
- `0 + succeeded` 是 **Human 产品约定**，不是交易所债务归零的证明；**不得**为加强它而
  增加实时余额查询或债务归零推断。
- 非零部分还款及 `pending` / `unknown` / `failed` 不锁价。
- STORJ 等存量异常由以后单独授权、备份、审计的人工数据库修正处理；正常程序不做通用
  推定、K 线回补或兜底引擎。

必查项:
- **R1 删除完整性**：计划是否已把下列全部移出产品实现范围——三个 `repay_after_*` 列、
  签名余额 GET、债务归零观测、a/b/c 推断、`coverage_for_window` 回补闸门、跨库历史推断、
  `--assume-debt-zero`、通用历史/未来 K 线回补脚本。有无残留引用或被改名后留存。
- **R2 终态谓词**：是否唯一且为精确 `amount == "0" AND status == "succeeded"`；是否在
  计划、代码注释要求、API 文档三处都**如实**表述为 Human 约定而非交易所证明；非零部分
  与全部非成功态是否保持动态；重复 repay-all / re-borrow 区间与同毫秒并列是否确定性。
- **R3 资金缝隙**（根因 B）：`_dispatch_margin_repay` 返回至 `store.resolve` 之间的动作
  清单是否**只有** best-effort 内存缓存读价与本地解析；有无网络请求、重试、sleep、跨库读、
  第二次业务观测；异常是否全部产出 NULL 价格；`resolve` 是否在异常边界**之外**恰好执行一次。
- **R4 存储 schema**：是否最小化为 `repay_price_usdt TEXT` 与 `repay_price_source TEXT`
  两列；来源命名是否准确为 `snapshot_spot_bid_at_capture`；终态缺价是否 fail-closed 且
  **不被**当前价 / 计提价 / K 线价静默顶替。
- **R5 单一折算权威**：是否一份共享 domain 实现同时服务 PnL 曲线与持仓视图；是否按
  `(settlement_ms, client_request_id)` 把每条利息行映射到其后第一个 `0 + succeeded` 终态；
  未匹配用当前价、已匹配用存储价、终态后 re-borrow 行重新开放。
- **R6 存量异常边界**：STORJ 处理是否明确在正常代码与脚本之外；计划是否只给后续操作
  清单（单独授权、备份、独立选定历史价、直接更新并用可区分的人工来源、回读校验、审计
  留证），并声明部署/评审不授权该写入。
- **R7 测试最小充分性**：是否收敛到最小的资金/PnL 守卫（部分保持动态、`0+succeeded`
  切换一次并保持固定、re-borrow 重开、取价异常仍落 `succeeded` 且 NULL 并 fail-closed、
  终态排序与 tie-break、两消费者一致、additive 迁移幂等）；是否**不存在**仅为已删除推断
  机制服务的测试脚手架。
- **R8 同根因穷举**（本轮重点）：§4 的两张扫描表是否**真正穷举**——根因 A 是否覆盖计划内
  全部以缺席/推断为事实的判定点（含已改与已删站点），根因 B 是否覆盖还款派发返回到
  `store.resolve` 之间的全部动作（含已删站点），清单外站点是否**逐一**给出不适用理由。
  **若发现任何一个应入表而未入表的站点，即为 in-range 发现。**
- **R9 A9 的自洽性**：§4.1 A9 把 `0 + succeeded` 保留在根因 A 家族内并声明其为「产品约定
  而非证明」。请独立判断：该保留是否构成对根因 A 的实质豁免？其四处表述要求是否足以
  防止后续实现或文档把它重新写成事实主张？

评审纪律:
- **不接受计划自述**。计划中引用的每一处代码事实（行号、字段、现状行为）须自行打开源文件
  核实。已知引用点：`server.py:1028-1029`（缝隙）、`store.py:35-47`（现有列）、
  `store.py:51-63`（`_row_to_doc` 无 `updated_at_us`）、`domain.py:571`（利息折算分支）、
  `snapshot.py:806-812`（`fresh` 语义）、`hedge_open_live_client.py:538`（还款响应字段）。
- 按 AGENTS.md §8 **范围三分类**标注每条发现（`in-range` /
  `pre-existing-independent` / `pre-existing-release-critical`），`pre-existing-*` 须附早于
  `base_sha` 的引入提交引用。
- 按 §8 **新假设场景证据门**：以自行提出的新假设场景阻塞交付时，须满足 §1 Scenario
  Admission 并给出证据锚点、对本交付的具体影响、以及为何必须本轮修而不能带重开条件观察。
- 计划评审 verdict 返回 Planner，**不触碰** `rework_count`。
- 若判定 `REWORK`，请一并回答：剩余问题是否**必须在计划阶段**解决，还是可以带明确的重开
  条件进入实现、由实现后的代码评审兜住。P1→P5 已历经三轮计划评审，需要一个关于边际收益
  的明确判断。

Allowed Files:
- Reviewer 完全只读，除下面唯一 create-only handoff 外零写入：
  `reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P6-repaid-interest-price-plan-final-review.handoff.md`
- Planner 预检（2026-08-28）：该路径 **ABSENT**，create-only 权威成立；若开始时已存在即任务失败。
- 不得修改计划、`status.json`、`ACTIVE.json`、`PROJECT_STATE.md`、任何源码/测试/schema，
  不得提交、部署、操作生产库或凭据，不得发送其他终端窗口。

Verdict:
- `ACCEPT` 或 `REWORK`，逐条对应 R1–R9。
- `ACCEPT` 时须明确声明：计划可进入实现 dispatch 准备（实现者 `claude_glm`，按 §5 固定
  文件边界）。**本 ACCEPT 不授权合并、部署、实盘或 §7 的人工数据库修正。**

Stop:
- 写完 handoff 即停。不实现、不改计划、不推进 stage 状态。
- 返回 Bookkeeper：`gpt-5.6-sol`（窗口标签 `codex`）。

reply_to: codex
After emitting the normal console receipt, send that same receipt once to the
reply_to window per `HERDR.md`, then stop.
