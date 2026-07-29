排查完成。说明一下：我读文件的过程中（02:18–02:19）AGENTS.md/roles.md/三个 review skill 正被 Phase E task2 的 GLM 终端改动，所以下面的结论基于去重改动落盘后的当前工作区。task2 要处理的那条（结果字段在 roles/skills 里被复述）已经收口了，我没有再算进待办。

以下是仍然存在的"同一定义被多处描述"的问题，按危害排序。

---
一、真冲突：多处描述且内容不一致

1. 模型路由被定义了四次，且互相矛盾

- AGENTS.md:73：GLM 后端 / Kimi 前端 / Codex 或 Claude 规划与决策评审
- agents/roles.md:59-68（Implementer 表）+ :126-140（Review-1/2 模型）
- docs/development/DEVELOPMENT_GUIDE.md:204-218「Model Routing」整节
- docs/planning/DECISIONS.md:21（DEC-2026-07-08-001）

冲突点：
- Grok：roles.md:129 允许 Grok 4.5 作为 Kimi 不可用时的 review-1 备选（Phase E 实际就是这么用的，见 30-phase-e-task1-grok45-review.dispatch.md）；DEVELOPMENT_GUIDE.md:216-218 写的是"Grok 被排除在核心后端/契约/修复任务外，仅可用于非关键 UI 草图"。
- Claude 评审模型：DECISIONS.md:21 记的是"Fable5 优先，Fable5 额度耗尽后用 Opus4.8"；roles.md:136-138 写的是"Opus 5 是 review-2 默认，Fable5 仅在人工明确选择其独立付费额度时使用"。
- 自指矛盾：AGENTS.md:73 一边写"完整路由与 provider 身份只存在于 agents/roles.md"，一边在同一句话里给出了默认路由。这句话本身就是它禁止的那种复述。

2. "一个任务读几个 skill"有三个不同基数

| 位置 | 说法 |
|---|---|
| AGENTS.md:38 | at most one（可以为 0） |
| agents/roles.md:73 | exactly one task skill（必须 1） |
| agents/roles.md:219 | required_skill (zero or one) |

Implementer 按 roles.md 读会认为"没点 skill 就是包有问题"，按 AGENTS.md 读则认为合法。

3. "高风险"清单有三份，集合都不一样

- AGENTS.md:19（需人工授权）：money, orders, live gates, credentials, destructive data actions, risk-limit changes, deployment, external side effects
- AGENTS.md:164（需双评审）：orders, positions, borrowing, repayment, transfer, money/PnL, accounting, live gates, risk limits, credentials, controlling contracts
- agents/skills/complexity-evaluator.md:24-27：上一条 + destructive actions + unclear test oracle

三份互有增减：:164 没有 destructive actions 和 unclear test oracle，:19 没有 positions/borrowing/accounting/controlling contracts。没有任何一处声明谁是权威。

附带问题：唯一给出可判定分类规则的 complexity-evaluator.md，在 AGENTS.md:63-71 的角色路由表里根本没被指名，属于"权威定义放在默认读不到的文件里"。

4. Stage 生命周期 / SHA 口径存在两套并行体系

docs/planning/stage-branch-mode.md 状态标着 APPROVED-PENDING，DECISIONS.md:20 也把它记为生效决策。它定义的是：head_sha、diff_fingerprint、H_intake、stage_accepted_waiting_user、validator 门禁、70-handoff.md、stage-delivery.yaml、docs/parallel-development-mode.md。

而 v2 的口径是 delivery_sha（roles.md:239-240）、没有 fingerprint、没有 validator，AGENTS.md:174-185 的 Stage Completion 只讲归档、完全不提"何时建 stage 分支"。它引用的 stage-delivery.yaml、parallel-development-mode.md、validator 脚本都已在本分支删除。

也就是说"阶段怎么开分支、sha 锚在哪、什么时候合 main"这一个定义，同时存在 v1 和 v2 两个版本，两边互不引用，v1 那份还挂着 APPROVED。

5. dispatch packet 字段集有三种枚举

- AGENTS.md:51（表格）：scope, files, checks, role, model, skill
- agents/roles.md:9-11（Shared Rules）：target_role, target_model, allowed files, acceptance checks, ≤1 skill
- agents/roles.md:214-224（Bookkeeper）：Identity 六项（含 task_id/provider/status_revision）+ Goal / Allowed Files / Inputs / Acceptance Checks / Stop

前两处都缺 status_revision 和 Inputs。而 AGENTS.md:41 又要求"revision 不符就停"——按 Shared Rules 校验包的模型根本不知道该字段必须存在。同一个 roles.md 内部前后两处枚举不一致，这一条最容易实际踩到。

6. current_task.state 的合法值没有单一定义

AGENTS.md:158 提到 dispatched/running/reported；roles.md:245 提到 verified；roles.md:188 的模板只给了一个 dispatched 示例。完整状态机不存在于任何一处。

---
二、重复但当前一致（冗余，是未来漂移的种子）

7. "禁止模型调度另一个模型"——7 处
AGENTS.md:20、:88-89、:149-150；roles.md:14、:47、:94、:146-147、:253-254。
已经开始漂移：AGENTS.md:20 是 "start, call, relay to, assign, or impersonate"，roles.md:14 少了 assign。

8. "评审只读 + 人工转交 Bookkeeper"——7 处
AGENTS.md:158；roles.md:114、:152-153、:167-168（同一文件内两处说同一件事）；三个 review skill 的 overrides 各一条。

9. base_sha..delivery_sha 评审基准——5 处
AGENTS.md:24、:167；roles.md:131-132；reality-checker.md overrides 与 Mandatory Process 第 1 条（同文件两处）。

10. "只改 dispatch 批准的文件"——5 处
AGENTS.md:21；roles.md:15-16、:81；minimal-change-engineer.md「Touch only files required by the finding」；developer-discipline.md §3 Surgical Changes。

11. 凭据禁令——7 处，两种措辞
roles.md:19-20 写 "expanded secret environments"，六个 skill overrides 统一写 "expanded auth environments"。

12. "实时事故立即记录 / 仓库历史不是运行时检查"——6 处
AGENTS.md:160；roles.md:88、:249-250；PROJECT_STATE.md:4、:42。

13. skill 优先级链：9 个 skill 各写一份，四种版本
- vendored 四件（code-reviewer / security-reviewer / senior-developer / software-architect / task-planner）：AGENTS.md + dispatch + status.json
- complexity-evaluator.md / product-strategist.md：多了 "user decisions"
- test-strategist.md：多了 "product acceptance criteria"
- minimal-change-engineer.md：多了 "raw review findings"

同一条优先级规则，九份措辞，四个不同的权威集合。

14. agents/developer-discipline.md §1–§4 与 /Users/ark/Desktop/CLAUDE.md §1–§4 逐字相同（只有箭头字符和折行差异）。Claude 会话里这两份会同时进上下文；AGENTS.md:7「最小充分改动、不做投机抽象」是同一立场的第三处表述，minimal-change-engineer.md 是第四处。

15. "草稿→批准文档"的晋升规则两处：docs/README.md:13-14 与 DEVELOPMENT_GUIDE.md:6-8。

16. "低风险可走单次终评"三处：AGENTS.md:81、:165、complexity-evaluator.md:30-31，三种措辞（"justified" / "dispatch records why" / "dispatch records the reason"）。

---
三、同一概念、不同叫法

- 人：Human / human operator / human_operator（status.json 的 next.actor）
- 终评：review-2（AGENTS.md §8）/ final review（roles.md:32）/ decision review（AGENTS.md:73）
- 模型标识：GLM、Kimi（AGENTS.md 散文）/ claude_glm、kimi（roles.md 规范 id）/ Claude-GLM（DEVELOPMENT_GUIDE、developer-discipline）
- 包：packet / dispatch packet / task packet（AGENTS.md:29 用 task packet，:32 用 <task>.dispatch.md）

---
我的判断

第 1、5 两条是现在就会导致模型行为分歧的（Grok 能不能评审、包缺 status_revision 该不该拦）；第 4 条是最大的一块——v1 的 stage 分支制文档还挂着 APPROVED 且指向已删文件，任何模型读到它都会按已废弃的口径行事。第 3 条的隐患在于高风险判定的唯一可执行规则藏在一个路由表不指名的 skill 里。

第 7–13 属于 AGENTS.md:13「progressive disclosure，优先改已有权威文件」自己想避免的那类冗余，目前还一致，但第 7、11 条已经出现措辞漂移，说明机制在生效中。
