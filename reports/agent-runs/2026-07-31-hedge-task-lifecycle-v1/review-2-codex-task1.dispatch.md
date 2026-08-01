# Dispatch —— review-2-codex-task1（最终评审，只读）

```text
Identity:
  task_id:         review-2-codex-task1
  target_role:     Reviewer
  target_model:    codex
  provider:        openai
  status_revision: 14
  required_skill:  agents/skills/reality-checker.md
```

## Goal

对 Task 1（`hedge-merged-positions-v1`，含修复轮 1）做 **review-2**：判断**用户批准的需求、实际交付效果、证据、运行风险与发布就绪度**。

- 实现与修复作者是 `claude_glm`（`zhipu_glm`），你是 `codex`（`openai`），provider 隔离成立；你**未参与本 stage 的方案设计**（方案由 `claude_glm` 出、`deepseek` 计划评审），符合"最终评审者未参与设计"的偏好。
- review-1 由 `grok`（`xai`）经两轮后返回 `ACCEPT`。
- 只读会话。未取得明确、格式良好的 `ACCEPT` 即为非接受（`AGENTS.md` §3 #7）。
- 当前 `rework_count = 1`（上限 3）。

**你不是第二个 review-1。** 代码正确性、契约、测试与接缝已由 grok 覆盖两轮。你的职责是回答：**这东西真的做到了 Human 要的事吗？证据可信吗？上线会出什么问题？现在能合并吗？**

## 评审对象（固定区间，不得移动 HEAD）

```text
base_sha     = c1cc10e8fb491f83fe4c09f565b34e06c2de0a50
delivery_sha = 6d6aa7bee34134b5f51a760d3ff0c1204c3f3dc4
```

其中 `969c455` 为首次交付、`6d6aa7b` 为修复轮 1；区间内其余提交为 Bookkeeper 控制提交，按 §8「评审范围口径」是上下文而非受审交付。

## Human 批准的需求（判断"是否做到"的基准）

- **D5/D6**：持仓展示改为**以交易所真实 UM 持仓为基准**，匹配现货/杠杆账户资产与任务卡成交记录，**合并成一张表**，现有「UM 持仓」子表并入。
- **D7**：真实持仓与任务记录**对不上时都显示、标清楚**；**只展示，不做任何自动动作**。
- **D14**：合并在**后端**做。**D15**：**保留被删除任务的成本基**（改 `aggregate_positions` 两条 `WHERE`）。
- 展示形状基准：fake UI 交付 `63f5007`（Human 已看过并认可）。
- **D2**：`done` 语义本轮不处理，不新增状态枚举。

出处：`02-scope-decisions.md`、`03-fake-ui-outcome-and-plan-scope.md`、`04-backend-merge-decision.md`。

## ⚠️ 已由 Human 明确接受、不得据以返工

以下两条是**真实缺陷**，Bookkeeper 核验时发现并向 Human 说明了各自代价，**Human 两次明确决定本轮不修**，待其结合真实使用场景另行设计。五要素记录见 `22-bookkeeper-rejection-task1.md` §5：

- **限制 A**：`single_leg_exposure` 判据为「现货成交量 > 0 且合约成交量 == 0」，**漏报聚合后的部分失衡**（现货 2.0 / 合约 1.0 判为无敞口）。
- **限制 B**：`spot_balance` 与 `drift` 读经典现货账户，而对冲现货腿买入统一账户，**`drift` 因而恒为 `False`**，手工减仓检测静默失效。

**不得据此返工。** 但你是 review-2，**发布就绪度正是你的职责** —— 请明确回答：**带着这两条限制合并，是否可接受？** 若你认为它们的实际后果比 `22-` §5 所记更严重（例如会误导操作决策、或与 Task 2 的自动删除叠加后风险升级），请直接说明。**那是新信息，Human 会重新权衡**，不是返工要求。

Human 推后的建议项（混合桶均价单测、HTTP 级 N2 断言、强平价 title、注释更正）与 review-1 的观察 C-1~C-4 见 `42-review-1-grok-task1-r2.md` §2，同样不构成返工。

## Acceptance Checks —— 逐条给出结论

- **E1｜需求达成度**：交付是否真的实现了 D5/D6/D7/D14/D15？逐条对照，不看自述看实物。特别是：真实持仓是否**真的成为骨架**（而非仍以本地记录为主、真实数据只作装饰）？「对不上的两类」是否**都**显示且标得清楚？
- **E2｜与 Human 认可的形状是否一致**：对照 `63f5007` 的预览与 `10-design.md` §5 的差异清单。差异是否都被列出并有理由？有没有未列出的偏离？
- **E3｜证据可信度**：`61-merged-positions-test-output.txt` 是否为原始输出？测试是否真的覆盖了它声称的场景，还是覆盖了容易通过的路径？两条渲染断言是否名副其实（Bookkeeper 已做过回退探测，见 `42-` §1；请判断**覆盖面**而非重复探测）？
- **E4｜运行风险**：这段代码在真实服务上跑起来会怎样？重点考虑 —— 账户快照的发布时序与持仓接口的耦合；`private_account` 陈旧但 `verified:true` 时用户是否会把旧数据当实时；1000x 前缀币种的显示是否会误导；大量持仓行时的性能；以及**任何会让用户对自己的钱做出错误判断的展示**。
- **E5｜发布就绪度**：现在能合并到 `main` 吗？合并前必须做什么？**注意：本交付从未在真实服务上运行过**（Human 于 D4 选择跳过运行时验证；`PROJECT_STATE.md` 亦记录既有 inline-log 功能 `[OPEN][RUNTIME-UNVERIFIED]`）。这对发布就绪度意味着什么？
- **E6｜串行链影响**：Task 1 是 ①→②→③ 的第一环，Task 2（任务状态机 + 五种自动删除 + 限频退避）将基于本交付 rebase。本交付有没有给 Task 2 埋下麻烦？特别是：**限制 A 在 Task 2 落地后权重会上升**（自动删除使任务卡进入「已删除」筛选，卡上的敞口观察点从默认视图消失，合并表成为唯一入口）——这是否改变你对限制 A 的判断？
- **E7｜你认为最该让 Human 知道的三件事**：不限于上列检查项，用 Human 能懂的话说。

## Inputs

| 文件 | 读什么 |
|---|---|
| 本 dispatch | 全部 |
| `git diff c1cc10e..6d6aa7b` | 受审交付 |
| `02-scope-decisions.md` / `03-fake-ui-outcome-and-plan-scope.md` / `04-backend-merge-decision.md` | Human 的需求与决策（D1-D16） |
| `10-design.md` / `11-adr.md` / `12-development-breakdown.md` | 方案与 Task 1 验收标准 |
| `21-merged-positions-implementation.md` | 实现者自述（两轮） |
| `61-merged-positions-test-output.txt` | 原始测试输出 |
| `22-bookkeeper-rejection-task1.md` | **§0 已核验项、§5 已接受限制** |
| `41-` / `42-review-1-grok-task1*.md` | review-1 两轮原文与处置 |
| `PROJECT_STATE.md` | Live Risks 与 Open Follow-ups |
| `agents/skills/reality-checker.md` | 全部 |

字节数请自行 `wc -c`。禁止整文件读三个后端主文件（合计约 27 万字节），按差异定位。

## 输出要求

按 `AGENTS.md` §7 返回 `[TASK_RESULT v2]`，并含三行闭合字段：

```text
评审结论: ACCEPT（接受） | REWORK（返工）
问题记录: <path | none>
修复要求: <path | none>
```

- **`问题记录` 与 `修复要求` 填 `inline-full-text`，完整正文放在同一次输出的正文里。** 本仓上一 stage 七轮评审中有四轮的正文没跟着回执转交，两轮不得不回头补要。
- 每条 `REWORK` 发现按 §8 标注范围三分类；`pre-existing-*` 须附早于 `base_sha` 的引入提交引用。
- **`本地北京时间` 须由 `date '+%Y-%m-%d %H:%M:%S CST'` 实际产生。**
- 发布就绪度的结论请**明确**：可合并 / 可合并但须先做某事 / 不可合并及原因。`ACCEPT` 不等于授权合并（合并仍由 Human 决定），但你的判断是 Human 决策的主要依据。
- 若无 in-range 缺陷，请返回 `ACCEPT` —— 不要为凑发现而制造边缘问题；范围外的观察照常列。

## Stop

- 只读：不得修改任何文件（含 `status.json`）、不得写代码、不得提交、不得合并、不得推送。
- 不得移动 `HEAD`，只评审写死的 `base_sha..delivery_sha`。
- 不得启动、调用、转交或冒充任何其他模型会话（§3 #2）。
- `ACCEPT` 不构成实现、验收、合并、部署或实盘授权；结论交回 Human，由 Bookkeeper 同步。
- 若发现本 dispatch 与受审代码矛盾、或评审对象与 `status.json` 不符：停止并报告。
