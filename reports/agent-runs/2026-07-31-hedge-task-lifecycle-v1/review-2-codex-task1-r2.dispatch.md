# Dispatch —— review-2-codex-task1-r2（最终评审复审，只读）

```text
Identity:
  task_id:         review-2-codex-task1-r2
  target_role:     Reviewer
  target_model:    codex
  provider:        openai
  status_revision: 19
  required_skill:  agents/skills/reality-checker.md
```

## Goal

你在上一轮对 `6d6aa7b` 返回 `REWORK`（**F3**：合并表未标记两类错配，且无任务记录的行把成本显示为 `0`），并判定**当前不可合并**。实现者已完成修复，review-1（`grok`）经四轮后对新交付返回 `ACCEPT`。请复审。

- 实现与修复作者 `claude_glm`（`zhipu_glm`），你 `codex`（`openai`），provider 隔离成立；你未参与本 stage 的方案设计。
- 只读会话。未取得明确、格式良好的 `ACCEPT` 即为非接受（§3 #7）。
- `rework_count = 2 / 3`（第 3 轮修复未发生，已回落）。**仅剩 1 次**，请把发现的分量判准。

**你仍不是第二个 review-1。** 代码正确性由 grok 覆盖了四轮。你的职责是：**这东西真做到 Human 要的事了吗？证据可信吗？上线会出什么问题？现在能合并吗？**

## 评审对象（固定区间，不得移动 HEAD）

```text
base_sha     = c1cc10e8fb491f83fe4c09f565b34e06c2de0a50
delivery_sha = ef53a025114933e8c472d9ae89f8ebfb35d19513
```

**本轮复审重点是修复差异 `git diff 6d6aa7b..ef53a02`**（`domain.py`、`store.py`、`index.html`、`self-check.js`、三个测试文件与两份报告）。`6d6aa7b` 是你上轮判 `REWORK` 的版本。区间内其余提交为 Bookkeeper 控制提交。

## 你上轮的 F3 被怎么修的

| 你的要求 | 实现 |
|---|---|
| 每行给出明确的来源/匹配状态 | 新增**后端契约键 `match_status`**（`normal` / `no_task` / `no_um`），前端渲染短标签「无任务记录」「交易所无仓」，推测原因放 `title` |
| `no_task` 的成本字段不得显示 `0` | `_merge_empty_bucket_row` 的成本字段由 `"0"` 改为 `None`，前端渲染 `—`；派生的价差率一并处理 |
| 增加两类错配的前端 self-check | 已增；Bookkeeper 独立破坏探测确认可失败 |
| 新 commit 后回 review-2；扩展契约先补 review-1 | 已扩展契约（`match_status`），已重过 review-1（r3 `REWORK` → r4 `ACCEPT`） |

**同时修了三项真机观察发现的问题**（`44-runtime-observation-task1.md`）：

- **合约均价被「金额记成字面 0」污染** —— 真机上 `RSRUSDT` 曾显示合约均价 `0.000623`、价差率 `-100%`，真实值约 `0.001246` / `+0.3%`。现在金额未知的腿不计入均价分母、置不完整标记；Bookkeeper 用**真实数据库**验证均价已回到 `0.001246`。
- 均价改为 8 位有效数字（原先同列 4 到 27 位不等）。
- 全仓借款在同币多行不再重复呈现。

## ⚠️ 范围外，不得据以返工

以下均已由 Human 明确接受或裁定，五要素记录见括注路径：

- **限制 A / B**（`22-` §5）：单腿敞口漏报部分失衡；`spot_balance` / `drift` 读经典现货账户致 `drift` 恒 `False`。
- **限制 F4**（`46-` §3，**本轮新增**）：账户读不到时（`SnapshotNotReady` 或 `verified: false`）`match_status` 仍输出 `no_um`，前端渲染「交易所无仓」+「可能已强平」`title`。Human 在知悉「`verified=false` 任何时刻都可能发生、并非只在启动期」这一更正后仍决定接受，**修复已具名折入 Task 2 的范围**（`46-` §3.3），并已写入 `status.json.blockers`。
- **Human 已裁定的两项**（`45-` §4）：均价用 8 位有效数字而非固定小数位；借款去重保留。
- **Human 推后的建议项与历轮观察**（`41-` §2、`42-` §2、`46-` §4 观察 1-5）。
- **同币双向**（D13）：Human 已移出范围，将来由开单闸门根治。

**不得据以返工。但发布就绪度是你的职责** —— 请明确回答：**带着限制 A、B、F4 合并，是否可接受？** 特别是 F4：它与你上轮 F3 同源（展示断言了它不知道的事），而 Human 选择了"接受 + 折入 Task 2"而非当场修。若你认为该处置不足以支撑合并，**直接说明** —— 那是发布判断，不是返工要求。

## Acceptance Checks —— 逐条给出结论

- **E1｜F3 是否真的修好**：两类错配现在标得清楚吗？`no_task` 行还有没有把不存在的成本画成数字？D7「都显示、标清楚」现在算达成了吗？
- **E2｜与 Human 认可的形状一致性**：对照 fake `63f5007` 与 `10-design.md` §5 的差异清单。本轮新增/恢复的状态标识、不完整标记、8 位有效数字、借款去重是否都已列入 §5？还有没有未列出的偏离？（上轮 F3 的性质正是"未披露的形状偏离"。）
- **E3｜证据可信度**：`61-` 是否为原始输出？新增测试是否覆盖真实失败模式？特别是**均价分母改动**的测试 —— 它改的是资金数字，测试是否足以防止回归？
- **E4｜运行风险**：本轮改动在真实服务上会怎样？重点：`match_status` 新键对既有消费者的影响；均价分母改变后，用户看到的均价与他实际的成本是否一致（**未知金额的腿被排除在分母外，这会不会让均价偏离真实持仓成本？**）；8 位有效数字在极端价格下的表现。
- **E5｜发布就绪度**：**现在能合并到 `main` 了吗？** 合并前必须做什么？注意本交付已做过**一次部分的只读真机观察**（`44-`，Human 启动、executor 强制 disabled、零 running 任务），覆盖了真实服务可启动/页面可渲染/真实持仓可读；**未覆盖**账户未就绪路径、统一账户现货余额匹配、快照陈旧性。这对发布就绪度意味着什么？
- **E6｜串行链影响**：Task 2（任务状态机 + 五种自动删除 + 限频退避）将基于本交付 rebase，并须一并修 F4。本交付有没有给 Task 2 埋下麻烦？F4 的修复要求（`46-` §3.3）是否充分？
- **E7｜你认为最该让 Human 知道的三件事**：用 Human 能懂的话说。

## Inputs

| 文件 | 读什么 |
|---|---|
| 本 dispatch | 全部 |
| `git diff 6d6aa7b..ef53a02` | **本轮受审差异** |
| `43-review-2-codex-task1.md` | 你上轮的原文与 F3 |
| `44-runtime-observation-task1.md` | 真机观察、G5 的数据库证据、Human 的四项决定 |
| `45-` §4 / `46-` §3 / `47-` | Human 裁定、F4 接受记录、review-1 四轮收口 |
| `10-design.md` §5 / `21-` §11.2 | 形状差异清单与「每列 × 六场景」穷举表 |
| `22-` §5 / `41-` §2 / `42-` §2 | 范围外清单 |
| `PROJECT_STATE.md` | Live Risks 与 Open Follow-ups |
| `agents/skills/reality-checker.md` | 全部 |

字节数请自行 `wc -c`。禁止整文件读三个后端主文件，按差异定位。

## 输出要求

按 `AGENTS.md` §7 返回 `[TASK_RESULT v2]`，含三行闭合字段：

```text
评审结论: ACCEPT（接受） | REWORK（返工）
问题记录: <path | none>
修复要求: <path | none>
```

- **`问题记录` 与 `修复要求` 填 `inline-full-text`，完整正文放在同一次输出的正文里。** 你上轮做到了，本轮请保持。
- 每条 `REWORK` 发现按 §8 标注范围三分类；`pre-existing-*` 须附早于 `base_sha` 的引入提交引用。
- **`本地北京时间` 须由 `date '+%Y-%m-%d %H:%M:%S CST'` 实际产生。**
- **发布就绪的结论请明确**：可合并 / 可合并但须先做某事 / 不可合并及原因。`ACCEPT` 不等于授权合并（合并由 Human 决定），但你的判断是 Human 决策的主要依据。
- 若无 in-range 缺陷请返回 `ACCEPT`；返工额度只剩 1 次，不要为凑发现而制造边缘问题。

## Stop

- 只读：不得修改任何文件（含 `status.json`）、不得写代码、不得提交、不得合并、不得推送。
- 不得移动 `HEAD`，只评审写死的 `base_sha..delivery_sha`。
- 不得启动、调用、转交或冒充任何其他模型会话（§3 #2）。
- `ACCEPT` 不构成实现、验收、合并、部署或实盘授权；结论交回 Human，由 Bookkeeper 同步。
