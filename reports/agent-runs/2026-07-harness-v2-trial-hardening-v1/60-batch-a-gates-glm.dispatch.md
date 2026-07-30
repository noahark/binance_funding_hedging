# Harness v2 Trial Hardening — 批次 A：闸门与机制

## Identity

- task_id: `harness-v2-trial-hardening-batch-a-gates`
- target_role: `Implementer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `12`
- required_skill: `agents/skills/senior-developer.md`

## Goal

实施已通过两道计划评审的批次 A：把 Harness v2 缺失的几处闸门语义补进**既有权威文件**。

这是**契约文本改动，不是代码改动**。全批次**不新增任何文件**。你的产出是对
`AGENTS.md` 与 `agents/roles.md` 的最小编辑，加一份结果报告。

设计与其勘误已由 Grok 4.5（`xai`）与 Fable5（`anthropic`）分别 `ACCEPT`。你的任务是
**照此实施**，不是重新设计。若你发现设计中某条无法实施或自相矛盾，报阻塞，不要自行改写
规则。

### 必须遵守的四项口径（评审遗留，原样执行）

**`O1` —— `E1` 与 `E5` 的用词澄清。** 设计勘误 `E1` 表格写"作废方案 A，采用方案 B"，
但 `E5` 规定拒收时 `current_task.state` **保持 `reported`**，与设计原文 §3 问题 2 的
方案 B（"`verified` + `blockers` 非空"）不同。**以 `E5` 的四步为唯一有效表述**；`E1` 的
"采用方案 B"只表示"不采用新增第四状态的方案 A"。

**`O2` —— `W6` 引用扫描不得被误用。** 该扫描只证明"活跃契约文件不引用已删除路径"，
**不证明**单一权威、不证明规则正确、不证明字节预算。本批次不新增文件，故该检查基本为
空跑；仍须执行并返回空，但在报告中必须按上述范围陈述它证明了什么，不得当作总体合规
证据。

**`O3` —— 1.5 KB 口径的确切定义。** 指 `AGENTS.md` 与 `agents/roles.md` **两文件字节数
之和**的增量，`1.5 KB = 1536 字节`。基线取自 `base_sha`：

```bash
git show c6f23f6:AGENTS.md | wc -c && git show c6f23f6:agents/roles.md | wc -c
# 基线：12744 + 10534 = 23278 字节
wc -c AGENTS.md agents/roles.md   # 交付后；两者之和 - 23278 必须 ≤ 1536
```

**`O4` —— 勘误与修复的分界（权威原文，逐字写入，不得改写、压缩或转述）：**

> 产物勘误仅限不改变交付效果的编辑性更正：只修正文字、格式、引用路径或证据标注，且
> 更正后交付物的代码行为、契约语义、验收标准、各项检查的通过状态与评审结论均须与更正
> 前一致。凡为响应评审发现或 Bookkeeper 拒收而改动上述任何一项的再交付，无论载体是
> 代码还是文档，一律按修复任务递增 `rework_count`。

**注意单一权威（`AGENTS.md` §2）**：上述两句中"递增 `rework_count`"属计数规则，其详细
权威是 `AGENTS.md` §8；"勘误怎么写"属证据纪律，其权威是 `agents/roles.md` Shared Rules。
落笔时把计数后果放 §8、把勘误写法放 Shared Rules，两处不得互相复制完整规则，可互相指向。

## Allowed Files

只允许修改：

- `AGENTS.md` —— **仅限 §7（第 95–169 行区域）与 §8（第 170–183 行区域）**
- `agents/roles.md` —— **仅限** `Shared Rules`（第 7–25 行区域）、
  `Reviewer` 的 `Verdict` 子节（第 152–160 行区域）、`Bookkeeper` 的
  `Task State Vocabulary` 子节（第 205–216 行区域）

只允许创建：

- `reports/agent-runs/2026-07-harness-v2-trial-hardening-v1/61-batch-a-result.md`（结果报告）

**禁止**修改：`AGENTS.md` §1–§6 与 §9–§10；`agents/roles.md` 的其他任何段落；
`PROJECT_STATE.md`；`reports/agent-runs/ACTIVE.json`；本阶段 `status.json`；
`docs/**`；`scripts/**`；`schemas/**`；`workflows/**`；产品代码与测试；
本阶段的 `20-`/`22-`/`4x-`/`5x-` 等已封存证据文件。

**全批次不得新增除上述结果报告以外的任何文件。**

## Inputs

按 `AGENTS.md` §4 顺序读取：

1. `AGENTS.md`；
2. 本 dispatch；
3. `reports/agent-runs/ACTIVE.json`；
4. `PROJECT_STATE.md`；
5. 本阶段 `reports/agent-runs/2026-07-harness-v2-trial-hardening-v1/status.json`；
6. `agents/roles.md` 的 `Implementer` 段（并通读将被你修改的三个子节）；
7. `agents/developer-discipline.md`；
8. `agents/skills/senior-developer.md`；
9. **实施依据**：
   `reports/agent-runs/2026-07-harness-v2-trial-hardening-v1/20-opus5-design.md`
   ——重点 §3（七个设计问题的正面回答）、§5（批次 A）、以及末尾"勘误 1"的
   `E1`/`E2`/`E3`/`E5`/`E6`。**冲突处以勘误为准。**
10. `22-bookkeeper-design-verification.md` 的 §8（十条 Human 决定）、§12.3（`O1`）、
    §14.2（`O4` 权威两句）、§15（决定 11）。

不要读取已完成阶段、产品源码、运行时数据、凭据或 `reports/agent-runs/_proposals/`
（后者按 Human 决定 9 是草稿，不得作为证据）。

## Acceptance Checks

### 一、必须写入的规则（逐条落地）

**A1. `AGENTS.md` §8 —— 返工轮次的计数口径（`G15`）**
在 `AGENTS.md:182` 现有句子**之后追加**，保留原句逐字不变（该原句即设计 W4，是本阶段
两轮评审得以不消耗预算的依据）。追加内容须表达：

- 计数绑定**交付物**（最初被 dispatch 的可交付成果），不绑定 `current_task.id`；
- 首次交付存在之后，为修复缺陷而进行的任何新实现任务递增一次，**无论发现来自 review-1、
  review-2 还是 Bookkeeper 验证**；
- **改名或拆分修复任务不重置计数**；只有 Human 同意的新交付范围才重置为零；
- `O4` 两句中"递增 `rework_count`"的计数后果写在此处。

**A2. `AGENTS.md` §8 —— 同根因刹车（`G12`）**
连续两轮 `REWORK` 被归因于同一根因时，禁止第三次点补丁；下一个修复任务必须是一次穷举
根因扫描，产出该缺陷家族在受审范围内的路径枚举清单，并对清单外站点给出不适用理由。
穷举扫描本身仍算一轮，占用既有三轮预算；若它仍返回 `REWORK`，由 §8 既有的三轮上限接管。
**不得新增计数器、不得新增数值限额、不得新增 `status.json` 字段**——"连续两轮"是条件
不是限额。根因由评审者在 `问题记录` 中命名，Bookkeeper 在修复 dispatch 的 `Goal` 中原样
引用。

**A3. `AGENTS.md` §8 —— 发现的范围三分类（`G18` + Human 决定 5）**
评审者须为每条 `REWORK` 发现标注三者之一：

- `in-range`（由本次交付引入或触碰）→ 阻塞交付，走修复轮；
- `pre-existing-independent` → 不阻塞，记为后续项；
- `pre-existing-release-critical`（涉及资金、实盘、账务含义、安全）→ 不机械阻塞交付，
  但阻塞合并/发布，作为"合并前由 Human 决定"的具名事项上交。

配套三条同时写入：

1. `pre-existing-*` 必须附**早于 `base_sha` 的引入提交引用**（`git blame` 或
   `git log -L` 输出），Bookkeeper 封存前核验该引用；无此证据者只是观察，不能阻塞；
2. **不新增第三个 verdict 值**：发现全为范围外时评审者返回 `ACCEPT`，`问题记录` 照常
   填路径，`修复要求` 指向后续项或 `none`；
3. Human 可明确授权"已知风险暂不修，仍允许合并"，该记录须含：问题事实、可能影响、
   接受理由、临时限制或观察方式、后续复看条件；该授权**仅针对本次合并**，部署、实盘
   操作、风险参数调整仍须单独授权；已发生的实盘风险仍须写入 `PROJECT_STATE.md`。

**A4. `AGENTS.md` §8 —— 评审范围口径（`G3`）**
一句：评审区间可能包含本阶段自身的控制提交（dispatch、`status.json`、阶段报告）；它们是
评审者的上下文而非受审交付，针对它们的发现按 A3 的分类记为范围外。
**不得改动 `base_sha` 的定义**（其权威在 `agents/roles.md` 的 SHA Discipline，本批次不
允许修改该节）。

**A5. `AGENTS.md` §8 —— 计划评审（`G2`）**
一句：`HIGH_RISK` 任务在实现开始前须经一次独立的、跨 provider 的只读计划评审；其 verdict
返回 Planner，不触碰 `rework_count`（已由 §8 既有的 pre-dispatch 豁免覆盖，**不要重复
写豁免规则**，指向即可）。**不新增角色、不新增技能、不改 §5 与 §6。**

**A6. `AGENTS.md` §7 —— 可质疑的验收检查（`G16`）**
不新增字段。给既有 `检查结果` 定义三态语义 `pass` / `fail` / `contested`：

- `contested` 项必须携带：被质疑检查的原文名称、质疑理由、替代证据（可执行命令或已提交
  路径）；
- **`contested` 不等于 `pass`**：只要存在 `contested` 项，`执行结果: completed` 即
  **不可封存**，Bookkeeper 必须显式裁定后状态才能推进；
- 裁定二选一：驳回 → 该检查成立，走一轮修复并按 A1 递增；采信 → Bookkeeper 按勘误规则
  更正该验收检查，**不消耗返工预算**（缺陷在 packet 不在交付）。

**A7. `AGENTS.md` §7 —— 结果块合规措辞（`G1`/`G14`）**
一句：未识别的标签行、不在枚举内的取值、错误的收尾标记，使结果块不合规，Bookkeeper 不得
据以封存；并写明按 Human 决定 1，回执"只需清楚、可读、能定位产物、结论和下一步，由
Bookkeeper 核验是否足以推进"。
**不得新增任何脚本、schema、YAML 或自动检查**（Human 决定 1、11）。

**A8. `agents/roles.md` Shared Rules —— 勘误规则（`G19` + `O4`）**
在既有 "Preserve raw evidence" 条目旁增加：自己的已交付文档可就地更正，但须附日期说明
改了什么、为什么；他人的已交付产物只可追加显著标记的勘误，**不得编辑其散文**；原始模型
输出、测试输出与 verdict 永不编辑，只以追加勘误更正。并写入 `O4` 两句中"什么算勘误"的
判据部分（计数后果指向 §8，见 A1）。

**A9. `agents/roles.md` Verdict 子节 —— 分类义务**
一句：`REWORK` 的每条发现须按 `AGENTS.md` §8 的三分类标注并附证据。**详细分类规则不得
在此复制**，只指向 §8。

**A10. `agents/roles.md` Task State Vocabulary —— 拒收落盘四步（`E5`）**
在保持**恰好三个状态**（`dispatched` / `reported` / `verified`）的前提下写入：

1. Bookkeeper 核验未通过时，`current_task.state` **保持 `reported`**，不得写 `verified`；
2. 拒收事实、依据与可复现命令写入该阶段的 Bookkeeper 核验记录；
3. 同时在 `status.json.blockers` 写一条具名条目；
4. 随后的修复任务按 §8 递增 `rework_count`，改名或拆分不清零。

**不得新增第四个状态**（Human 决定 3）。

### 二、必须通过的核验（在结果报告中附命令与原始输出）

1. `git diff --stat` 显示改动只落在 `AGENTS.md`、`agents/roles.md`，加新建的
   `61-batch-a-result.md`；**零新增其他文件**。
2. `git diff` 确认 `AGENTS.md` §1–§6、§9–§10 与 `agents/roles.md` 其余段落逐字未改。
3. **字节预算（`O3` 口径）**：`wc -c AGENTS.md agents/roles.md` 之和减去基线 `23278`
   必须 ≤ `1536`。附实测数字。
4. **`status.json` 字段集未变**：
   `python3 -c "import json;print(len(json.load(open('reports/agent-runs/2026-07-harness-v2-trial-hardening-v1/status.json'))))"`
   输出 `13`。（你不修改该文件，此检查用于证明未被误动。）
5. **W6 引用扫描（按 `O2` 口径陈述）**：运行设计 §8 / findings 文档 Part 2 中的引用扫描
   循环，必须返回空；报告中须写明"该结果只证明活跃契约文件不引用已删除路径，不证明
   单一权威或规则正确"。
6. **单一权威自查**：`AGENTS.md` §7/§8 与 `agents/roles.md` 三个子节之间，没有复制的
   字段清单、枚举集合、数值限额或完整工作流；跨文件只用指向。附你的逐条自查说明。
7. **`G1`/`G14` 仍为 OPEN**：结果报告中必须明确声明本批次**未解决** `G1`/`G14`，只增加了
   措辞约束；任何"已解决/已闭合"表述均为不合格。（设计勘误 `E2`、Human 决定 1 与 11。）
8. **`dispatch` 六节形状与 `status.json` 三态未被本批次改动**（保护 W5、W3）。

### 三、提交与报告

- 授予提交责任：完成后在当前分支 `codex/harness-v2-trial-hardening` 提交，**不得**
  合并、变基、推送、切换分支或触碰 `main`。
- 结果报告写入 `61-batch-a-result.md`，须含：逐条 A1–A10 的落点（文件 + 行号）、
  第二节 1–8 项的命令与原始输出、以及未解决事项。
- 你可以把自己的任务从 `dispatched` 改为 `reported` —— **但本 dispatch 不允许你修改
  `status.json`**，因此改为在结果报告中声明"已回报"，由 Bookkeeper 落状态。

## Stop

按 `AGENTS.md` §7 返回完整中文 `[TASK_RESULT v2]`，含三行中文交接标签，以
`[/TASK_RESULT]` 作为最后一个非空白输出，其后不得有任何文字。

**不要**发明结果字段、不要复制本 dispatch 的 `Identity`、不要使用
`[/TASK_RESULT v2]` 之类的收尾标记（`G14` 的原始违规正是如此）。若有验收检查你认为
错误，按 A6 的 `contested` 方式返回，并给出替代证据——**不要为了让检查变绿而放宽定义**。

下一步行动者是 Human：由 Human 把你的原始结果转交本阶段 Bookkeeper `opus5` 核验并封存。
你不得启动或指派任何模型，不得准备评审包，不得进入批次 B。
