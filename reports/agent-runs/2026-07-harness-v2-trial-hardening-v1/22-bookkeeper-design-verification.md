# Bookkeeper 核验记录 — Opus 5 设计任务

- 阶段: `2026-07-harness-v2-trial-hardening-v1`
- 核验者: Bookkeeper `opus5`（provider `anthropic`）
- 核验任务: `harness-v2-trial-hardening-bookkeeper-design-verification`
- 被核验任务: `harness-v2-trial-hardening-design-opus5`
- 日期: `2026-07-30`
- 工作树: `/Users/ark/Desktop/ai code/funding_hedging-harness-v2`，分支
  `codex/harness-v2-trial-hardening`，HEAD `14c98a7`

## 0. 独立性披露

本次核验者与设计产物 `20-opus5-design.md` 的作者是同一模型会话族（Opus 5）。按
`AGENTS.md` §3.4，实现或修复作者不得**正式评审**自己的交付；Bookkeeper 核验与正式
评审是不同事项，且本次核验由 Human 交付的 dispatch 明确指派。

因此本记录的效力被明确限定：核验的是**存在性、完整性、边界合规与外部 Git 事实**，
不构成对设计内容正确性的独立判断。设计内容的独立判断仍需一次跨 provider 的独立计划
评审，该闸门保持关闭（见 §6）。

## 1. 原始结果保存

Human 在本终端转交的 Opus 设计任务原始 `[TASK_RESULT v2]` 已逐字保存于
`21-opus5-design-result.md`，未摘要、未改写、未截断。围栏代码块仅用于隔离其闭合标记，
围栏内内容与原始输出一致。

## 2. 产物与工作树核验

| 项 | 命令 | 结果 |
|---|---|---|
| 产物存在 | `ls -l .../20-opus5-design.md` | 存在，40,968 字节 |
| 产物内容标识 | `git hash-object .../20-opus5-design.md` | `3f26dd547ffd74113f7b91d4fc1f5ad29bdaffb5` |
| 空白/冲突标记 | `git diff --check` | 退出码 0，通过 |
| 工作树状态 | `git status --short` | 三项未提交，见下 |

**对验收检查 2 的如实偏差报告。** 该检查要求"设计产物是唯一的先前未提交改动"。实测
未提交项为三个：

1. `?? 20-opus5-design.md` — 设计任务的产物；
2. `M  status.json` — 上一轮 Bookkeeper（`codex`）的 revision 2 写入；
3. `?? 30-opus5-bookkeeper-design-verification.dispatch.md` — 同一轮准备的本任务 packet。

准确表述是：**在可归因于设计任务的改动中，`20-opus5-design.md` 是唯一一项**；另外两项
是上一轮 Bookkeeper 自己的未提交 packet 准备输出，属预期且被 dispatch 授权，不是设计
任务的越界。设计任务的 Allowed Files 只允许创建 `20-opus5-design.md`，实测符合：
`AGENTS.md`、`agents/**`、`scripts/**`、`docs/**`、`PROJECT_STATE.md`、`ACTIVE.json`、
产品代码与产品阶段工作树均未被该任务改动。

附带观察（非缺陷）：这三项混在同一工作树状态里，正是设计 §2 中 `G3` 所描述的"阶段
控制改动与交付改动混在同一区间"的现场实例。

## 3. Git 证据：`main` 已包含完成的产品阶段

不采信叙述，全部为命令输出：

| 断言 | 证据 |
|---|---|
| `main` 指向合并提交 | `git rev-parse main` = `a5160474a1b78468d1513fc14539232fdf36d7aa`；提交标题 `Merge stage/2026-07-unknown-not-zero-v1: unknown is not zero, and a discarded failure is a defect` |
| 阶段分支已并入 | `git merge-base --is-ancestor stage/2026-07-unknown-not-zero-v1 main` → 真；阶段尖端 `b0257c9` |
| §9.6 活动指针已清空 | `git show main:reports/agent-runs/ACTIVE.json` = `{"active": null}` |
| §9.5 阶段目录已移除 | `git ls-tree -d --name-only main:reports/agent-runs/` 中无 `2026-07-unknown-not-zero-v1` |
| §9.4 证据已归档 | 标签 `archive/2026-07-unknown-not-zero-v1` = `1e0f20b`，其树内含完整阶段目录 |
| §9.3 已记录完成 | `git show main:PROJECT_STATE.md` 的 Last Completed 段记为 `2026-07-unknown-not-zero-v1` / `archive/2026-07-unknown-not-zero-v1` / `2026-07-30` |

结论：产品阶段 `2026-07-unknown-not-zero-v1` 已按 `AGENTS.md` §9 完成并合入 `main`，
证据充分。本工作树的 `ACTIVE.json` 指向本 Harness 阶段，与之不冲突。

**尚未对账的部分**：本 Harness 分支尚未整合 `main`。
`git merge-base --is-ancestor main HEAD` 为假；`base_sha` `6471873` 仍是 `main` 的
祖先，落后 28 个提交。本次未做 rebase 或 merge（dispatch 禁止），`base_sha` 保持不变，
须在实现前的对账门重算。

## 4. 已作出的两项 Human 决策

按 dispatch 记录，Human 已否决设计中的两项提案：

1. **否决新增任务结果检查器及其测试文件**（对应设计 §4 与 §10 决策项 1，即
   `scripts/check-task-result.py` 与 `scripts/tests/test_check_task_result.py`）。
2. **否决每阶段 `decisions.md` 文件**（对应设计 §2 的 `G5` 处置与 §10 决策项，即在
   `AGENTS.md` §4 表格中点名 `<stage>/decisions.md`）。

Bookkeeper 据此记录的直接后果（事实陈述，不重开已决事项）：

- 批次 A 因此**不再包含任何新增文件**，其 Allowed Files 中的 `scripts/**` 整体失效。
  `G1` 与 `G14` 失去设计所选的机制方案，须改由纯措辞路线重新作答（例如在 `AGENTS.md`
  §7 声明未识别标签与错误闭合标记为非 accepting），或重新审视 `AGENTS.md:118` 那条
  "含糊即非 accepting"。这属于设计层面的再决策，不在本次核验权限内。
- `G5` 失去设计所选的落点。设计已在文内否决"向 `status.json` 增加 `decisions` 指针
  字段"（理由为重开封闭字段集，违反 W3）。因此 `G5` 需要新答案，或被定为"不修复"。

两项后果均须在实现前由 Human 或后续设计动作解决，本记录只登记，不代为裁决。

## 5. `status.json` 变更与转换核验

**核验上一轮转换（revision 1 → 2，未提交）**：`bookkeeper` 由 `codex` 改为 `opus5`，
`checkpoint`、`current_task`、`next` 同时更新。`agents/roles.md:248-249` 规定中途交接
"只改这一个值"；本次交接与一次新 dispatch 合并在同一修订内完成。判定为**已解释、非
未授权转换**——依据是 Human 交付的 `30-*.dispatch.md` 其 Identity 即为
`target_model: opus5`，且其验收检查第 5 条明确要求 `bookkeeper` 为 `opus5`。作为观察
登记：交接与派工合并在一次修订，与 roles.md 的字面表述有轻微出入。

**本轮写入（revision 2 → 3）**：

| 字段 | 前 | 后 | 理由 |
|---|---|---|---|
| `revision` | 2 | 3 | 本次状态更新 |
| `checkpoint` | `opus5-design-returned-awaiting-bookkeeper-verification` | `opus5-design-verified-implementation-gate-closed` | 反映已核验且闸门关闭 |
| `ledger_sha` | `6471873…` | `14c98a772f544cf864523c66952018539b2465fe` | 最后一个已提交基线，取自 `git rev-parse HEAD`，符合 W2 与"不自指"定义 |
| `current_task` | 核验任务 / `dispatched` | 设计任务 `harness-v2-trial-hardening-design-opus5` / `verified` / `10-opus5-design.dispatch.md` | 按 dispatch 验收检查 5，把已完成的设计任务标为 `verified` |
| `next.action` | `start-prepared-opus5-bookkeeper-design-verification` | `human-decide-open-design-decisions-then-authorize-independent-plan-review` | 下一个行动者是 Human，且不指向任何实现 dispatch |
| `blockers` | `[]` | 三项，见下 | 明示实现闸门关闭的具体原因 |

保持不变：`schema_version`、`stage_id`、`bookkeeper`（已为 `opus5`）、`phase`
（`design`）、`base_sha`、`delivery_sha`（`null`）、`rework_count`（`0`）。

写入的 `blockers`：

1. 设计决策未决——`checker` 与 `decisions.md` 两项已否决，其余决策项待裁；
2. 独立计划评审未进行——设计尚未经跨 provider 的独立评审；
3. `main` 未整合——`base_sha` 须在整合后重算，findings 快照须重新对账。

**字段数说明**：dispatch 验收检查 5 写"preserve the 12 top-level fields"，而
`agents/roles.md:178-203` 的权威模板为 **13 个顶层字段**（`schema_version`、`revision`、
`stage_id`、`bookkeeper`、`phase`、`checkpoint`、`base_sha`、`delivery_sha`、
`ledger_sha`、`current_task`、`next`、`rework_count`、`blockers`）。按 `AGENTS.md` §2
的单一权威原则，以 `roles.md` 为准，实际保留 13 个字段逐字不变。dispatch 中的"12"记为
计数笔误，登记于此不作改动。

`rework_count` 保持 `0`：本次为 Bookkeeper 核验通过，未产生任何返工轮次。
`delivery_sha` 保持 `null`：本阶段无受审交付。

## 6. 实现闸门状态：关闭

以下条件全部满足之前，不得准备任何实现 dispatch：

1. Human 就设计 §10 中尚未裁决的决策项作出裁决（其中两项已否决，见 §4）；
2. `G1`/`G14` 与 `G5` 在失去所选方案后的替代答案确定；
3. 本 Harness 分支整合当时的 `main`，`base_sha` 按 W2 重算并校验；
4. findings 快照 `be789d6:docs/planning/harness-v2-trial-findings-2026-07-30.md` 与当时
   最新版本对账，新增或变更条目逐条分流；
5. 设计通过一次独立的、非 `anthropic` provider 的计划评审。

本次未准备实现 packet，未准备计划评审 packet（dispatch 明确禁止），未编辑
`AGENTS.md`、`agents/roles.md`、`PROJECT_STATE.md`、产品代码或任何产品阶段文件，未
提交、合并、变基、推送、部署、访问凭据或启动其他模型。

## 7. 给 Human 的中文小结

设计产物在、内容完整、没有越界改动，已核验通过并把原始输出原样存档。用 Git 命令确认了
产品阶段确实已经做完并合进主线：主线上的合并提交在、阶段目录已按规矩移除、归档标签在、
活动指针已清空——不是靠谁的口头说明。

您已经否决的两件事我记下了：不做那个结果格式检查器，也不为每个阶段单独建决策文件。
后果如实说明：第一批改造因此不再新增任何文件，但"模型交回来的结果格式没人检查"这个
问题也就还没有解法，需要改用纯文字规则重新回答；每阶段决策记录同理，需要另找落点或
定为不修。这两件都要您或下一轮设计再定。

实现闸门仍然关着，我没有准备任何实现或评审的启动包。开工前还差三件事：其余设计决策
拍板、本分支整合最新主线并重算基准点、以及让这份设计过一次由**别家模型**做的独立评审
——因为设计是我写的，我自己的核验只能证明"东西在且没越界"，不能替代对内容对错的独立
判断。

---

## 8. Human 已拍板设计决策（追加于 2026-07-30）

本章为**追加**内容。按本次 Human 决策第 8 条，已封存的交付原文不得改写，勘误与补充
只可追加——本章严格遵守：上文第 0 至 7 节一字未改、未删。

记录任务: `harness-v2-trial-hardening-record-human-decisions`（status revision 3 → 4）。
记录者: Bookkeeper `opus5`。下列决定由 Human 作出，Bookkeeper 只如实登记，不改写为新
机制、不补充未经授权的实施细则。

### 8.1 决策原文登记

1. **不新增任务结果格式检查脚本，也不新增配套测试。** 回执只需清楚、可读、能定位
   产物、结论和下一步，由 Bookkeeper 核验是否足以推进。
2. **不新增每阶段 `decisions.md`。** 本 stage 的临时决定追加到既有 Bookkeeper 核验
   记录（即本文件），长期决定才进入既有规划决策文档。
3. **`status.json` 保持现有三态，不增加 `rejected`。**
4. **已交付后的正式修复都计入 `rework_count`；不得通过改任务名或拆分任务清零。**
5. **范围外发现必须先有可核验证据**：触发条件、实际影响、证据位置，以及早于本次交付
   存在的 Git 证据。无证据者只是观察，不能阻塞。
   - 普通范围外旧问题不阻塞当前交付，登记为后续项。
   - 涉及资金、实盘、安全的范围外旧问题不自动否定当前交付，但必须作为"合并前由
     Human 决定"的可见事项。
   - Human 可以明确授权"已知风险暂不修，仍允许合并"。该记录必须包含问题事实、可能
     影响、接受理由、临时限制或观察方式、后续复看条件。
   - 该授权只针对本次合并；部署、实盘操作、风险参数调整仍须单独获得 Human 明确授权。
     已发生的实盘风险仍须写入 `PROJECT_STATE.md`。
6. **不设置 32KB 等硬阈值**；任务包按需要指定大文件的读取范围、函数或符号。
7. **不恢复模型启动命令文档。**
8. **`G3` 的评审范围口径与 `G19` 的勘误规则可和后续 Harness 规则收口同批处理**；
   已封存的交付原文不得改写，勘误只可追加。
9. **`_proposals` 仅是草稿，不得作为正式证据。**
10. **历史 stage 目录清理暂缓**，未来必须单独取得 Human 授权。

### 8.2 对 `20-opus5-design.md` 相关条目的状态登记

下表只登记"设计中的哪一项被哪条决定定案"，不推导新规则。

| 设计条目 | 决定 | 登记状态 |
|---|---|---|
| `G1`/`G14` 结果与闭包机制（设计 §4 新增可执行文件） | 决定 1 | 否决新增脚本与测试；改由 Bookkeeper 按可读性与可定位性人工核验 |
| `G5` 每阶段决策落点（设计 §2 `G5`） | 决定 2 | 否决新增文件；临时决定追加于本核验记录，长期决定进既有规划决策文档 |
| `current_task.state` 第四态（设计 §3 问题 2 的方案 A） | 决定 3 | 否决；采用保持三态，即设计中列为方案 B 的形态 |
| `rework_count` 口径（设计 §3 问题 2） | 决定 4 | 确认：交付后的正式修复一律计数，改名或拆分不清零 |
| 范围外发现三分类（设计 §3 问题 5、`G18`） | 决定 5 | 确认三分类，并加强为"须先有可核验证据（含早于本次交付的 Git 证据）"；无证据者仅为观察 |
| 分段阅读阈值（设计 §2 `G7`、§10 决策项 5） | 决定 6 | 否决 32KB 等硬阈值；保留"任务包按需指定范围、函数或符号" |
| 模型启动命令文档（设计 §2 `G9(a)`、§10 决策项 6） | 决定 7 | 确认不恢复 |
| `G3` 评审范围口径、`G19` 勘误规则（设计 §5 的批次归属） | 决定 8 | 确认可与后续 Harness 规则收口同批处理；封存原文不得改写，勘误只可追加 |
| `_proposals` 定性（设计 §2 `G13`） | 决定 9 | 确认为草稿，不得作为正式证据 |
| 历史 stage 目录清理（设计 §2 `G11`、§7） | 决定 10 | 确认暂缓，未来须单独授权 |

### 8.3 对本文件 §4 与 §6 的接续说明

- 本文件 §4 记录的两项否决（结果检查器、每阶段 `decisions.md`）由上述决定 1 与 2
  最终确认，并已给出替代处置，因此 §6 第 1、2 项（"设计决策未决"与"`G1`/`G14`、
  `G5` 替代答案待定"）视为已了结。§4 原文保留不改。
- 本文件 §6 第 3、4、5 项（整合 `main`、重算 `base_sha`、对账 findings 快照、独立
  计划评审）**仍然未决**，实现闸门保持关闭。
- 本次记录未修改任何 Harness 契约文件，未整合 `main`，未准备任何评审或实现任务包。

### 8.4 `status.json` 本轮变更

| 字段 | 前 | 后 |
|---|---|---|
| `revision` | 3 | 4 |
| `checkpoint` | `opus5-design-verified-implementation-gate-closed` | `human-design-decisions-recorded-awaiting-main-integration` |
| `blockers` | 三项 | 两项：移除"设计决策未决"，保留"`main` 未整合"与"独立计划评审未进行" |
| `next.action` | `human-decide-open-design-decisions-then-authorize-independent-plan-review` | `human-authorize-main-integration-then-independent-plan-review` |

保持不变：`schema_version`、`stage_id`、`bookkeeper`（`opus5`）、`phase`（`design`）、
`base_sha`、`delivery_sha`（`null`）、`ledger_sha`（`14c98a7`，本轮无新提交）、
`current_task`（设计任务 `harness-v2-trial-hardening-design-opus5`，`verified`）、
`rework_count`（`0`）。顶层字段仍为 13 个。

### 8.5 给 Human 的中文小结

十条决定已经原样记在案，没有被我改写成别的做法。其中两条把上一轮悬着的事收了口：
结果格式不做脚本检查，改由我按"看得懂、能对上产物和结论"来判断够不够推进；阶段里的
临时决定就写在这份核验记录里，长期的才进规划文档。

还剩两件需要您点头才能往下走：一是授权把这条分支整合到最新主线、重算基准点、再把这段
时间新冒出的问题重新对一遍账；二是授权由**别家模型**做一次独立的设计评审。这两件没做
之前，我不会准备任何实现或评审的启动包。

---

## 9. main 整合与 findings 对账（追加于 2026-07-30，Human 口头授权）

本章为**追加**内容，上文 §0–§8 一字未改。记录 Human 于 2026-07-30 给出"授权"后
Bookkeeper `opus5` 执行的整合与对账，及其查出的一处授权冲突。

### 9.1 已执行的动作

| 动作 | 结果 |
|---|---|
| 提交本阶段记账产物 | `128e564` bookkeeper: opus5 design verified, Human decisions recorded (revision 4) |
| 整合 `main` 到本分支 | `0bea9c0` bookkeeper: integrate main@a516047 into the harness stage branch |
| 冲突处理 | 唯一冲突为 `reports/agent-runs/ACTIVE.json`；`main` 侧为 `null`（产品阶段已关闭），本分支侧为本 Harness 阶段。取本分支值，因为当前活动阶段确为本阶段 |
| `main` 是否被改动 | 否。`git rev-parse main` 前后均为 `a5160474a1b78468d1513fc14539232fdf36d7aa`，未合并回 `main`、未推送 |
| 整合校验 | `git merge-base --is-ancestor main HEAD` → 真 |
| 新基准 | `git rev-parse HEAD` = `0bea9c084b8209b19113b169eaf152ab33455884` |
| 工作树 | 干净；`git diff --check` 退出码 0 |

### 9.2 findings 快照对账

对比对象：快照 `be789d6:docs/planning/harness-v2-trial-findings-2026-07-30.md`
（blob `f8c825c`）与 `main` 上当时最新版本（blob `07a6691`）。

差异：**12 行新增，无删除、无改写**，全部由提交 `406d83a`
（`bookkeeper: hold the harness batch pending Human vetting (D-9)`）引入。

分流结果：

1. **无新增 G 条目。** 十九条 G 与六条 W 的编号、内容、证据均未变动，`20-opus5-design.md`
   对它们的裁决不受影响，无需改写设计。
2. **`G17` 新增一次同阶段复现**（文中"Second occurrence, same stage"）：D-9 决策在
   review-2 终端运行于 `status_revision: 12` 时抵达，同样只能停放在证据文件里。这是对
   既有 `G17` 的证据加强，不是新问题，设计中 `G17` 的处置不变。
3. **新增一条治理性 Hold 决策 D-9**，见 §9.3。这是本次对账唯一需要 Human 处理的事项。

### 9.3 查出的授权冲突：D-9 / `[HUMAN-OWNED]` 条目

整合后进入本分支的两处文本，直接约束本阶段正在做的事：

`docs/planning/harness-v2-trial-findings-2026-07-30.md`（`main` 版，D-9）：

> Hold — Human decision D-9, 2026-07-30. Human is vetting these findings against
> Codex personally. Until Human says that is finished, no model may open a Harness
> stage, write a Harness plan, or dispatch Harness work from this document. ...
> Record the vetting outcome per finding in this file.

`PROJECT_STATE.md`（`main` 版，第 29–32 行）：

> `[HUMAN-OWNED]` The 19 Harness v2 findings are being fixed by Human with Codex on
> a separate branch. **No model may open a Harness stage or plan from
> `docs/planning/harness-v2-trial-findings-2026-07-30.md`**, incl. the withdrawn
> `task2-same-family-rework-rule`.

**时序证据**（`git show -s --format='%h %ad'`，ISO 本地时间）：

- `406d83a` D-9 记录：`2026-07-30 19:52:45 +0800`
- `14c98a7` 本 Harness 阶段开启：`2026-07-30 20:20:24 +0800`

即本阶段是在 D-9 之后、由 Codex 作为 Bookkeeper、在独立分支
`codex/harness-v2-trial-hardening` 上开启的。`PROJECT_STATE.md` 中"Human 与 Codex 在
独立分支上处理这十九条"所描述的，正是本阶段本身。因此本阶段**不是**违反 D-9 的并行
开工，而是 D-9 所指的那个受认可载体；`00-intake.md` 的 Design-Only Gate 是其配套限制。

**但仍有一处必须由 Human 处理的实际障碍**：上述禁令文本仍以现在时留在
`PROJECT_STATE.md` 中，而 `PROJECT_STATE.md` 属 `AGENTS.md` §4 的启动必读文件。下一个
被启动的独立计划评审终端（非 anthropic provider）在启动阶段就会读到"任何模型不得从该
findings 文档开启 Harness 阶段或撰写 Harness 计划"，按契约它应当停止。**在该条目被更新
之前派工，等于明知会让评审终端在启动即停机。**

同时，D-9 要求"把每条 finding 的 vetting 结果记录在该文件中"，该记录尚未写入。Human
本轮给出的十条决定实质上已覆盖其中多条，但它们目前只存在于本核验记录 §8。

### 9.4 因此未做的事

- **未准备独立计划评审的 dispatch packet。** 原因是 §9.3 的启动即停机风险，以及评审
  模型尚未由 Human 选定（计划评审是设计新提的机制，`agents/roles.md` 对它没有默认路由）。
- 未编辑 `PROJECT_STATE.md`、`docs/planning/harness-v2-trial-findings-2026-07-30.md`、
  `docs/planning/DECISIONS.md`——这三处都承载 Human 自己的决策记录，改动前需要 Human 的
  明确说法。
- 未合并回 `main`、未推送、未部署、未访问凭据、未启动或指派任何模型。

### 9.5 `status.json` 本轮变更（revision 4 → 5）

| 字段 | 前 | 后 |
|---|---|---|
| `revision` | 4 | 5 |
| `checkpoint` | `human-design-decisions-recorded-awaiting-main-integration` | `main-integrated-findings-reconciled-d9-hold-surfaced` |
| `base_sha` | `6471873…` | `0bea9c084b8209b19113b169eaf152ab33455884` |
| `ledger_sha` | `14c98a7…` | `0bea9c084b8209b19113b169eaf152ab33455884` |
| `blockers` | 两项 | 两项：移除 `main-not-integrated`，新增 `d9-hold-and-project-state-prohibition`，保留 `plan-review-pending` |
| `next.action` | `human-authorize-main-integration-then-independent-plan-review` | `human-resolve-d9-hold-and-select-plan-review-model` |

保持不变：`schema_version`、`stage_id`、`bookkeeper`、`phase`、`delivery_sha`（`null`）、
`current_task`（设计任务 `verified`）、`rework_count`（`0`）。顶层字段仍为 13 个。
`base_sha` 与 `ledger_sha` 均取自 `git rev-parse` 并已校验存在（W2）。

### 9.6 给 Human 的中文小结

整合做完了：本分支已经带上最新主线，主线本身一个字没动，也没有推送。冲突只有一个小
文件，取了本阶段的值。对账结果是好消息——十九条问题一条没变、没新增，设计不用改；只多
了一条对已有问题 `G17` 的补充例证。

但对账把一件事翻了出来：您 19:52 写下的 D-9 暂停决定，以及 `PROJECT_STATE.md` 里那条
"任何模型不得从这份 findings 文档开启 Harness 阶段或撰写计划"。本阶段是 20:20 才开的，
由 Codex 记账、在独立分支上——也就是说这条禁令描述的就是本阶段自己，本阶段不是违规的
并行开工。

问题出在下一步：那条禁令的文字还是"现在进行时"，而 `PROJECT_STATE.md` 是每个终端启动
必读的。我如果现在把独立评审派出去，那个评审模型一开机读到这句话，按规矩就该停下来。
所以我停在这里，没有准备评审启动包。需要您给两句话：一是那条禁令怎么改（本阶段已获授权
继续、设计已完成），二是这次独立评审用哪家模型。

---

## 10. D-9 收口与 review-1 派工（追加于 2026-07-30）

本章为**追加**内容，上文 §0–§9 一字未改。**本文件（§8 决定原文、§8.2 逐条处置、
本章授权记录）是这十条 Human 设计决定的唯一详细记录**；按 Human 决定第 4 条，不复制
到 `docs/planning/DECISIONS.md`，也不新建 `decisions.md`。

### 10.1 Human 最终决定（原文登记）

1. D-9 不再禁止已获 Human 认可的本 stage 进行独立计划评审。
2. 该放行只适用于 `2026-07-harness-v2-trial-hardening-v1`；未获 Human 认可的、临时从
   findings 自行扩展的 Harness 计划仍禁止。
3. 独立计划评审通过且 Human 再次授权前，不得进入实现。
4. 十条 Human 设计决定的唯一详细记录是本 stage 既有 `22-bookkeeper-design-verification.md`；
   不得复制到 `DECISIONS.md`。
5. findings 文档只能追加简短 Human 更新，并指向 `22`；不得改写原始 D-9 内容。
6. `PROJECT_STATE.md` 是当前状态，应将旧的全面暂停令更新为本 stage 可进入独立计划
   评审、实施仍关闭的当前事实。
7. review-1 指定 Grok 4.5（provider: `xai`）。
8. review-2 将由 Fable5 执行，但只能在 review-1 `ACCEPT` 后另行派包。Fable5 与本设计
   作者 Opus5 同属 `anthropic` provider；届时必须在 review-2 包中披露这是 Human 明确
   选择，且其不替代 Grok 的跨 provider 独立初审。

### 10.2 已执行的文档收口

| 文件 | 改动 | 依据 |
|---|---|---|
| `PROJECT_STATE.md` | `[HUMAN-OWNED]` 条目由"任何模型不得从 findings 文档开启 Harness 阶段或计划"改为当前事实：本 stage 已获认可、正在独立计划评审、实施须待 `ACCEPT` 与 Human 再授权；其他模型仍不得从该文档撰写计划 | 决定 1、2、3、6 |
| `docs/planning/harness-v2-trial-findings-2026-07-30.md` | 在 D-9 段之后**追加**一段 Human update，明示"上文原文保留未改"，并指向本文件 §8 / §8.2 / §10 | 决定 5 |
| 本文件 | 追加本 §10 | 决定 4 |

`PROJECT_STATE.md` 收口后实测 2,044 字节（预算 2,048，余量 4 字节）。这正是设计 `G6`
描述的窘境：预算合理但没有淘汰规则，下一条新增事实将无处安放。此处如实记录，不越权
淘汰他人条目。

### 10.3 固定计划评审范围

- `base_sha`: `0bea9c084b8209b19113b169eaf152ab33455884`（`main` 整合提交，维持不变）
- `delivery_sha`: 本次 D-9 收口提交（见 §10.5）

**须向评审者明示的一点**：受审设计 `20-opus5-design.md` 由更早的提交 `128e564` 引入，
它是 `0bea9c0` 的祖先，因此**不在** `base_sha..delivery_sha` 区间内。该固定区间承载的是
D-9 收口的三处文档改动。计划评审的对象是设计文档本身，故 review-1 包要求评审者按
`delivery_sha` 那一刻的树读取 `20-opus5-design.md`（内容 blob `3f26dd5`），使读取仍然
确定、可复现。此事实写入 review-1 包的 `Inputs`，不隐去。

### 10.4 review-1 派工

- 模型: Grok 4.5，provider `xai`，角色 `Reviewer`，技能 `agents/skills/code-reviewer.md`
- 包路径: `reports/agent-runs/2026-07-harness-v2-trial-hardening-v1/40-grok45-plan-review-1.dispatch.md`
- provider 隔离核验: 设计作者为 Opus 5（`anthropic`），评审者为 `xai`，跨 provider 成立；
  Grok 未参与本设计的撰写或本阶段的记账。
- **未准备 Fable5 review-2 包**，按决定 8，仅在 Grok 返回 `ACCEPT` 后由 Bookkeeper 另行准备。

### 10.5 `status.json` 本轮变更（revision 5 → 6）

| 字段 | 前 | 后 |
|---|---|---|
| `revision` | 5 | 6 |
| `phase` | `design` | `plan-review` |
| `checkpoint` | `main-integrated-findings-reconciled-d9-hold-surfaced` | `d9-released-for-this-stage-plan-review-1-dispatched` |
| `delivery_sha` | `null` | D-9 收口提交 SHA |
| `current_task` | 设计任务 / `verified` | `harness-v2-trial-hardening-plan-review-1-grok45` / `dispatched` / `40-grok45-plan-review-1.dispatch.md` |
| `next.action` | `human-resolve-d9-hold-and-select-plan-review-model` | `start-prepared-grok45-plan-review-1` |
| `blockers` | 两项 | 一项：实施闸门关闭，须 review-1 `ACCEPT` 且 Human 再授权 |

保持不变：`schema_version`、`stage_id`、`bookkeeper`（`opus5`）、`base_sha`、
`rework_count`（`0`）。顶层字段仍为 13 个。`ledger_sha` 更新为 D-9 收口提交，即本次
状态更新之前最后一个已提交基线，仍不自指。

### 10.6 给 Human 的中文小结

三处文档都按您的说法改好了：主状态文件里那条"全面停"换成了现在的事实——本阶段已获
认可、正在做独立评审、实施仍然关着；findings 文档只在 D-9 那段后面**加**了一段说明，
原文一个字没动；十条决定仍然只存在于这份核验记录里，没有抄进决策文档。

Grok 4.5 的评审启动包已经备好，等您启动终端。Fable5 的复审包我没有准备，按您的说法要
等 Grok 给出通过之后再单独备。

提醒一件小事：主状态文件现在是 2,044 字节，离 2,048 的上限只剩 4 字节。下次再有新事实
要记，就必须先淘汰一条旧的——这正是设计里 `G6` 说的那个问题，目前还没有淘汰规则。

---

## 11. review-1 第一轮 `REWORK` 落盘与返工（追加于 2026-07-30）

本章为**追加**内容，上文 §0–§10 一字未改。

### 11.1 原始结论落盘

Grok 4.5（`xai`）针对固定范围 `0bea9c0..f90609d` 返回 `评审结论: REWORK`。原始输出已
逐字保存于 `41-grok45-plan-review-1-raw.md`，未摘要、未改写、未代为断行。

### 11.2 Bookkeeper 对该结果的核验

| 项 | 结论 |
|---|---|
| provider 隔离 | 成立。设计作者 Opus 5（`anthropic`），评审者 `xai`，且 Grok 未参与设计撰写或本阶段记账 |
| 固定范围 | 与 `status.json` 的 `base_sha`/`delivery_sha` 一致，评审者未移动 `HEAD` |
| 只读边界 | 成立。`产物: [none]`，工作区无评审者产生的改动 |
| 回执可读性 | 传输中换行被压平，但各字段可无歧义读出。按 Human 决定第 1 条判定**足以推进** |
| 回执缺陷 | `阻塞项` 引用"F1"，但原始结果无单独 F1 正文；`问题记录` 与 `修复要求` 两个路径都指向落盘文件自身。可执行要求实际由 `检查结果` 第 1–4 项与 `阻塞项` 承载。理解口径已写入 `41-…-raw.md` 备注 3，供复审者核对是否曲解 |
| `rework_count` | 保持 `0`。本轮为交付前计划评审，`AGENTS.md:182` 的 pre-dispatch packet correction 豁免（即设计 W4）与 Human 决定第 4 条"已交付后"的限定同时适用 |

**核验结论**：`REWORK` 成立，其核心指控属实——Human 于 2026-07-30 作出十条决定后，
决定被记入本文件 §8，但设计原件 `20-opus5-design.md` 未同步更正，被否决的机制在文中
仍是首选路径，且批次 B 的文件清单与决定 2 直接冲突。这是 Bookkeeper 的疏漏，如实登记。

### 11.3 已执行的返工

在 `20-opus5-design.md` 末尾**追加**"勘误 1 — 2026-07-30"，上文 §0–§10 逐字保留、未删
未改（符合该设计 §3 问题 6 自定的规则与 Human 决定第 8 条）。勘误共八节：

- `E1` 作废因 Human 决定而失效的七类条目（检查器、`decisions.md`、第四状态、32KB 阈值、
  模型启动文档、清理作业、§10 待决项）；
- `E2` 把 `G1`/`G14` 明确标记为 **OPEN 残留**，写明批次 A 只剩措辞手段、把关点是
  Bookkeeper 的注意力而非机器，并要求批次 A 的验收检查包含"仍标记为 OPEN"一条，
  **禁止伪关闭**；
- `E3` 重定义批次 A：`scripts/**` 整体移除，本批次不新增任何文件，测试节改为可执行的
  文本核验，作废"检查器 ≤120 行"这条验收；
- `E4` 重定义批次 B：删除与决定 2 冲突的 `decisions.md` 行，`G5` 改落 `roles.md` 一句，
  `G7` 删除阈值改为按需指定范围/函数/符号，新增 `G1`/`G14` 残留登记，并保留
  `PROJECT_STATE.md` 4 字节余量带来的同批淘汰约束；
- `E5` 回应 Grok 第 4 项，给出不新增状态、不新增字段的四步拒收落盘（保持 `reported`、
  写核验记录、写具名 `blockers`、后续修复递增 `rework_count`）；
- `E6` 重述设计问题 1 与 2；`E7` 列出 Grok 已通过、本次不动的部分；`E8` 一句白话小结。

### 11.4 复审安排

- 新包: `42-grok45-plan-review-1-r2.dispatch.md`，同一模型 Grok 4.5 / `xai`
  （`AGENTS.md` §8"Review-1 `REWORK` 返回 review-1"）。
- 固定范围: `base_sha` 维持 `0bea9c0…`，`delivery_sha` 更新为本次勘误提交，使勘误全文
  落在受审区间内。
- 复审重点: 逐条核对 `E1`–`E8` 是否真正解决 `检查结果` 第 1–4 项，尤其 `G1`/`G14` 是否
  被伪关闭。
- **未准备 Fable5 review-2 包**，按 Human 决定第 8 条，仅在 review-1 `ACCEPT` 后另行准备。

### 11.5 给 Human 的中文小结

Grok 挑得对，问题也确实在我这边：您拍板之后，我把十条决定记进了这份工作记录，却没有
回头去更新设计原件本身，结果那份原件上还写着您已经否掉的做法。

现在已经补上了：设计后面追加了一份勘误，原文一个字没动，勘误里把被否掉的四样东西逐条
划掉、把两批改造的清单重排，并且特别写明"结果格式没人检查"这个洞**仍然开着**——不因为
不修就假装它没了。同一位 Grok 的复审包已经备好，等您启动。实施闸门继续关着。
