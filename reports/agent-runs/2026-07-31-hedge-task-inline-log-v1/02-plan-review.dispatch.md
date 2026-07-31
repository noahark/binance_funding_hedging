# 02-plan-review：2026-07-31-hedge-task-inline-log-v1（计划评审 round 4，窄确认）

> AGENTS §8「计划评审」：HIGH_RISK 任务在实现开始前须经一次独立的、跨 provider 的
> 只读计划评审。verdict 回 Bookkeeper，不触碰 `rework_count`。本终端**只读**。

## Identity

- task_id: 2026-07-31-hedge-task-inline-log-v1-plan-review-r4
- target_role: Reviewer（计划评审 **round 4，窄确认**，只读）
- target_model: `deepseek`（DeepSeek Pro；Human 2026-07-31 决定改派）
- provider: `deepseek`
- status_revision: 8
- required_skill: `agents/skills/software-architect.md`

### provider 隔离状态（本轮为四方完全不重叠）

| 角色 | model | provider |
|---|---|---|
| 计划评审（本终端） | `deepseek` | `deepseek` |
| implementer | `claude_glm` | `zhipu_glm` |
| review-1 | `grok` | `xai` |
| review-2 | `codex` | `openai` |
| packet 定稿者 / bookkeeper | `opus5` | `anthropic` |

- **你是全新的独立评审方**，未参与本 stage 任何设计与前三轮计划评审。前三轮由 grok
  执行，而 grok 同时是本 stage 的 review-1——改派 DeepSeek 后，那条「计划评审与
  review-1 同 provider」的设计参与污染**消失了**。你不需要做任何隔离披露。
- 记账事项（Bookkeeper 已记，无需你处理）：`agents/roles.md` 的 provider identity 表
  尚无 DeepSeek 一行。本轮按 `deepseek` 为独立厂商记录；补进 `roles.md` 的动作留到本
  stage 收尾时统一处理，不在评审中途改 Harness 契约。

## 本轮背景（必读）

本 stage 只做一件事：**开单任务卡的内嵌日志**（展开后显示该任务每次尝试的成交明细表）。
「任务卡卡住」相关工作已由 Human 决定移出本 stage（见 `06-scope-reduction.md`）。

计划评审已跑三轮，全部由 grok 执行，三轮都是 `REWORK`：

- round 1 / round 2 针对的是收窄前的旧范围，结论见 `04-` / `05-` verdict（背景，不必读细节）。
- **round 3 针对当前范围**，提出三条阻塞 + 三条建议，合计「修订清单 1-6」。
  原文与 Bookkeeper 的逐条代码复核见 `07-plan-review-r3-verdict.md`。
- Bookkeeper 已按该清单把 `00-task.md` 修订为 `status_revision: 7`。

**本轮是窄确认**：核对那六条修订是否被正确、完整地落实，不是重新做一次全面计划评审。

## Goal

1. **核对修订清单 1-6 的落实情况**（清单原文在 `07-plan-review-r3-verdict.md` 的
   「Packet 修订清单」段，Bookkeeper 的落实说明在同文件「修订清单 1-6 落实情况」表）：

   | # | grok 的要求 | 你要核的 |
   |---|---|---|
   | 1 | 进展列改 `attempt_seq / target_n` | packet 是否已改且明确禁用 `scheduled_attempt_count` |
   | 2 | 错误原因主字段 + 只读回退链 + 收窄 AC4 + Stop 禁写路径 | 回退链是否可执行、AC4 三个用例是否够、是否真的堵住了「前端编造中文」 |
   | 3 | 未受理腿 `order_id` 门控 + AC3 收窄 + 金额用 `hedgeText` | 门控判据是否严密（后端已发 `"0"`）、AC3 断言范围是否恰当 |
   | 4 | `task_id` 全量 attempts+legs、不混游标、AC5 夹具 >50 | 读语义四条是否自洽、会不会重蹈 R4 共享游标缺陷 |
   | 5 | 状态映射冻结表 | 表是否完整、`warn` class 决定是否正确 |
   | 6 | 日志金额禁用 `formatHedgeDecimal` / `hedgeNum` | 是否落到硬约束与验收两处 |

2. **核对 Bookkeeper 独立追加的三项判断是否成立**：
   - `#task-id` 已在 `index.html:4207` 实现，故 Goal 2 降级为回归验收；
   - 时间格式复用既有 `hedgeLogEntryTimeText`（`index.html:4516`，北京时间）；
   - `accepted_pair` 中文取**「已受理」**而非 fake 原型的「已成交」（Human 已确认此选择）
     ——理由是两条腿拿到 `orderId` 不等于完全成交。请核这个理由是否站得住，以及
     UI 别处有没有仍写「已成交」而造成同一状态两种叫法的地方。

3. **新问题**：本轮虽是窄确认，但你是全新视角。**若发现前三轮和 Bookkeeper 都漏掉的
   阻塞级问题，照样提出来**——尤其是「钱的展示会让用户误判」这一类。不要因为「不在窄
   范围内」而咽回去；现在说的成本远低于 review 阶段说。

4. **结论**：若六条修订已正确落实、三项追加判断成立、无新的阻塞问题，返回 `ACCEPT`
   （本 stage 即可进入实现）。否则给出仍未闭合的具体判据与最小修订。

**不要**重新评审 grok round 3 已判 `pass` 的部分（收窄是否干净、`HIGH_RISK` 分级、
文件边界、「后端只动读路径」边界），除非本轮修订破坏了它们。

## Allowed Files

只读。不修改任何文件。评审结论以 `[TASK_RESULT v2]` 文本返回给 Human，由 Human 转交
Bookkeeper 落盘；本终端不写 `status.json`、不写 evidence 文件、不写 packet。

## Inputs

- 受审对象：`reports/agent-runs/2026-07-31-hedge-task-inline-log-v1/00-task.md`
  （`status_revision: 7`）。
- 上一轮结论与 Bookkeeper 核验：同目录 `07-plan-review-r3-verdict.md`（**必读**，
  含 grok 原文、六处代码引用的复核结果、修订落实表）。
- 范围说明：同目录 `06-scope-reduction.md`。
- 授权文件：`AGENTS.md`（尤其 §3 安全内核、§7 结果协议、§8 评审规则）、
  `agents/roles.md` Reviewer 段。
- 代码（只读，本轮重点）：
  - `frontend/index.html`：`hedgeText`（`:3602`）、`formatHedgeDecimal`（`:3631`）、
    `HEDGE_PAIR_OUTCOME_LABELS` / `_BADGE`（`:3563-3568`）、`.badge.warn` CSS（`:229`）、
    真卡卡头 `#task-id`（`:4207`）、fake 原型（`:4229` 起）、
    `bindHedgeTaskLogToggles` 绑定点（`:4159`）、`hedgeLogEntryTimeText`（`:4516`）、
    `renderHedgeLogEntryLeg`（`:4524`）。
  - `backend/hedge_open_tasks/service.py`：`_leg_to_doc`（`:214`）、
    `attempt_to_doc`（`:239`）、`get_logs`（`:673`）。
  - `backend/hedge_open_tasks/store.py`：`error_reason_zh` 写入（`:1085-1095`）、
    `list_legs_for_attempt`（`:1394`）、`list_attempts_for_task`（`:1403`）。
  - `backend/hedge_open_tasks/domain.py`：`LIMIT_DEFAULT` / `LIMIT_MAX`（`:518-520`）。
  - `backend/app/server.py`：`_hedge_open_logs`（`:588`）。
- 基线：`base_sha = 42de1aff364e7c979d2fbb5dc56f1dec65287cc7`。

## Acceptance Checks

- 逐条回答 Goal 1 的六项、Goal 2 的三项、Goal 3（有无新问题）、Goal 4（结论）。
- 每项给出明确判断与依据（引用 `文件:行号`）。
- 对每条问题标注严重度（阻塞实现 / 建议修改 / 观察），阻塞项须给出可执行的修改要求。
- 返回 `[TASK_RESULT v2]`（格式见 `AGENTS.md` §7），含 `评审结论: ACCEPT | REWORK`、
  `问题记录`、`修复要求`。
- **`问题记录` / `修复要求` 不要写 `none`**：写 `inline-full-text` 并把发现清单与修订
  要求放在同一次输出的正文里。前三轮有两轮因为正文没随回执交出，Bookkeeper 无法封存，
  白跑一趟。
- 计划评审的 `REWORK` 表示 packet 需修订后才可实现，**不计入** `rework_count`。

## Stop

- 只读：不改代码、不改 packet、不改 `status.json`、不建分支、不提交。
- 不做实现、不写修复代码、不启动其他终端。
- 不重评已移出本 stage 的工作（F10 / 暂停→删除 / 持仓聚合 / 51169，见 `06-`）。
- 不重评 round 3 已判 pass 的部分，除非本轮修订破坏了它们。
- 不替 Human 做合并、部署、实盘决策。
