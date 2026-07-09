# Review: glm52 (round 2)

> Reviewer: GLM-5.2 (`zhipu_glm`, `claude_glm` 适配器)。本轮是针对
> `10-independent-task-branch-mode-draft.md` (DRAFT-1) 的再评审，焦点为
> handoff/§13 指定的四项：**§7 两个脚本契约、§6 两级指纹 + rebind 机械证明、
> §9 红线、§10 待改点完整性与 fail-closed 风险**。身份披露同 round-1：GLM 是本模式
> 要扩大自主权的实现者之一，涉"实现者对 git/证据写权"的结论请按轻度利益相关方审视。

## Verdict

REWORK（很接近了，但仍有若干**契约级**缺口，须再修一版 DRAFT-2 才能开始写脚本）

## Summary

DRAFT-1 把 round-1 四份 REWORK 的主要阻塞项都吸收了：放弃 Option A、recorder/integrator
改成确定性脚本、不新增 status 枚举、review-1 保持 GLM↔Kimi 交叉审、review-2 锚
integration committed 指纹。方向（用户 DEC-2026-07-08-001）我认同，**两级指纹 + rebind
机械证明**是本草案最有价值的设计，理论上足以替代单分支单指纹的可复现性。

但我作为实现者模型，按"能不能照着 §7 把脚本写出来并过 validator"的标准逐条核，
发现仍有四处会让脚本**照写就跑不通或绕过红线**的契约缺口，且大多不在 codex-gpt5 已命中的
F1–F9 里。最关键的三处：(1) `record-checkpoint` 的提交/`head_sha` 时序有自指缺陷，照写
要么脏树失败、要么指纹绑错 commit；(2) §10.2 把 R1/R3 的 validator 校验写成"**可选**"，
这是本草案最大的 fail-closed 风险——红线若不强制机检就会在压力下被绕过；(3) rebind 的
逐位相等**依赖 §7 step3 的 scope 校验**，但 §6 与 §7 没把这层因果关系钉死，pathspec 也未
要求设计期冻结。这些是精度问题，不是概念问题；修完即可进入脚本实现。

与已有评审的关系：我**确认并强化** codex-gpt5 的 F1（metadata 交集）、F2（必改文件名）、
F3（rebind hash 分离）、F4（immutable-script guard），下文凡重合处只补 codex 没说清的
机制层；本轮的主干是我新加的 G 系列。

## Findings

### G1 (P1, 新) — `record-checkpoint` 的 commit / `head_sha` 时序有自指缺陷

§7 `record-checkpoint` 步骤是：4. candidate commit（本 task 改动 + 证据）→ 5. 写
branch-scoped status.json（base/head/task_diff_fingerprint、status=review_1）→ 6. 跑
`validate-stage --phase pre-review`。这个顺序照写**必然跑不通**：

- status.json 在步骤 5 才写，但 candidate commit 在步骤 4 已落 → 步骤 6 时 status.json
  **未提交** → `require_clean_worktree`（`validate-stage.py:831`，pre-review 必跑）**失败**。
- 若想把 status.json 塞进步骤 4 的同一个 commit，又撞 canonical 指纹的自指：指纹
  `head_sha:sha256(git diff base..head -- . :(exclude)status.json)` 的 `head_sha` 必须是
  **包含最终 status.json 的那个 commit**，而该 commit 的 hash 在提交前不可知（鸡生蛋）。
- 唯一正确的两段式（canonical exclude 之所以存在就是为了让它成立）：
  1. 提交 C_e = 本 task 改动 + 证据 + status.json 占位（或不含 status.json）；
  2. 因 diff 排除 status.json，`sha256(diff(base..C_e))` **稳定**；算出
     `fp = C_e : sha256(...)`；
  3. 写 status.json：`head_sha = C_e`（**不是后续 status 提交的 tip**）、`diff_fingerprint = fp`、`status = review_1`；
  4. 提交 status.json → C_s（分支 tip）。
- 于是 tip=C_s，但 status.json 记 `head_sha = C_e`。validator 用**记录值** C_e 重算指纹
  （`validate_common` 只校验记录的 head_sha 是真实 commit 且指纹匹配，**不校验 HEAD==head_sha**），
  通过；`require_clean_worktree` 在 C_s 通过。review-1 必须审 `base..C_e`（记录范围），
  这正是 AGENTS.md「review prompts must use `<base_sha>..<head_sha>`, never a moving HEAD」
  要覆盖的情形。

**契约必须显式写出的**：(a) 步骤 5 与 6 之间有一次 status.json 提交（草案漏了）；
(b) `head_sha` 语义 = 证据 commit C_e，不是分支 tip C_s；(c) review-1 审 `base..<记录 head_sha>`。
这三条不写，实现者（包括我）会照字面把 head 填成 tip 或漏提交 status.json，两种都过不了门。

### G2 (P1, 新) — §10.2 把 R1/R3 的 validator 校验写成"可选"，是本草案最大 fail-closed 风险

§10.2：「新增（或扩展 pre-review）对 integration rebind 与 changed-file 不相交的**可选**校验」。
但 §9 把"不相交"（R1）和"rebound 逐位可证"（R3）定为**红线**。红线 + 可选校验 = 仅靠自觉执行 =
在 deadline 压力下一定会被跳过。这正是 round-1 各方反复强调的"红线必须机器强制"的反面。

- R1（不相交）若不机检：实现者改了共享 schema/contract，`prepare-review-2` 照 merge，rebind 断言
  可能因 pathspec 巧合仍过（见 G4），夹带改动进 review-2。
- R3（rebind）若不机检：集成分支 diff 是否真等于两个 ACCEPT diff 的合并，完全靠脚本自觉。

**必须**：这两个校验在本模式下**强制**，并由 status.json 一个开关（如
`independent_task_branch_mode: true` 且 `tasks[]` 含 ≥2 条）触发，`pre-review`/`pre-accept`
必跑、不过即 fail-closed。不要留"可选"二字。（codex F1/F3 指出了要校验什么；我补的是
"必须强制而非可选"这层 fail-closed 论证，这是 §10 焦点里最该改的一句。）

### G3 (P1, 新) — rebind 的逐位相等依赖 §7 step3 scope 校验，§6/§7 未钉死且 pathspec 未冻结

§6 的 rebind 断言 `sha256(integration_diff ∩ backend_paths) == backend task diff hash` 在
**changed-file 不相交**前提下成立，但"不相交"不是天上掉下来的——它来自 `record-checkpoint`
步骤 3 的 scope 校验（changed files ⊆ 该 task 的 allowed scope）。也就是说：

- **G3-a（因果链未连）**：rebind 用 `owner_pathspec`（= backend/**）过滤 integration diff，
  只有当 record-checkpoint 已保证"backend task 的改动 ⊆ backend/**"时，
  `git diff base..integration_head -- backend/**` 才会逐位等于 `git diff base..backend_head`。
  §6 写成"因 changed-file 不相交"是结论，§7 step3 才是前提；两节必须互指为**不变量对**，
  否则 rebind 的前提可被绕过（task 偷偷改了 backend_pathspec 之外的 backend 归属文件）。

- **G3-b（pathspec 必须设计期冻结）**：rebound 的 `owner_pathspec` 不能由实现者运行期拼，
  必须取自 H_intake 冻结的 stage 元数据（任务书的 allowed scope）。否则实现者可改 pathspec
  让 rebind"恰好"通过。（与 codex F4 immutable-script guard 同源，但 F4 守的是脚本文件本身，
  这里守的是 pathspec 输入来源——两者都要。）

- **G3-c（实现形式不是"文本∩"）**：§6 写的 `integration_diff ∩ backend_paths` 字面像在对
  diff**文本**做路径交集，这不可靠（hunk header、rename 记录会破坏逐位相等）。脚本必须用
  `git diff --binary <base>..<integration_head> -- <owner_pathspec>` 与
  `git diff --binary <base>..<task_head>` 做字节比较，而不是过滤 diff 文本。二进制/重命名/
  mode 位变更需列为残留风险并加 fixture 覆盖（见 Trial Plan）。

- **G3-d（rebound 比的是 raw task diff，不是 task 指纹）**：rebound 需要两个 ACCEPT 的**原始
  task diff**。脚本可从保留的 task 分支 `base..<task_head>` **现算**（无需落盘 raw diff），
  前提是 task 分支在 rebind 前不被删（见 G6）。注意：不能拿 `task_diff_fingerprint`（hash）
  去拼出 integration 指纹——hash 不可逆，rebound 必须对 raw diff。

（与 codex F3 一致：canonical 指纹作 gate 锚、rebound 用分离的 path-restricted hash。我补的是
G3-a/b/c/d 四条机制细节。）

### G4 (P1, 强化 codex F1) — status.json 在两条 task 分支都会改，R1"交集为空"按字面会误杀 happy path，且 `prepare-review-2` step4"无冲突"不成立

codex F1 已指出两条 task 分支都会写 `reports/agent-runs/<stage-id>/status.json`。我补机制层：

- §9 R1「changed-file 交集为空」若**无条件**成立，则任意一对成功的 backend/frontend 任务都
  会因共享 status.json 被判 BLOCKED——happy path 跑不通。R1 必须重定义为**product 路径交集为空**，
  显式把 canonical 排除的 status.json（以及任何 stage 元数据生成物）从交集校验里剔除。
- §7 `prepare-review-2` step4「scope 不相交 → 无冲突」**对 status.json 不成立**：两条分支都改了
  同一路径 status.json，`git merge` 必然在该文件冲突。脚本必须：`git merge --no-commit --no-ff
  <backend> <frontend>` → 遇 status.json 冲突时**丢弃双侧、重写为集成版** → `git add status.json`
  → 提交 merge commit。这个冲突解决策略与"integration status.json 取得所有权"（§6）必须写成
  可执行的 git 步骤，不能停留在叙述。
- 更稳的做法（赞同 codex F1 备选）：task 分支不写顶层 status.json，改写 task-local 快照
  （`tasks/backend/status.json` 之类），集成时由 `prepare-review-2` 产出唯一顶层 status.json。
  这样 product 交集与 metadata 交集天然分离，R1 不需要特判。

### G5 (P2, 新) — `prepare-review-2` 缺"anti-stale-tip"校验：review-1 ACCEPT 后 task 分支 tip 漂移会让 rebind 审错对象

§7 step1 只校验"两条 review-1 verdict 均 ACCEPT"。但 review-1 ACCEPT 之后、`prepare-review-2`
之前，若某条 task 分支被 amend（rebase 已被全局禁止，但 amend 仍可能）或追加了提交，则：
- task 分支当前 tip 的指纹 ≠ review-1 当初 ACCEPT 的指纹；
- rebind 现算 `base..<task_head>` 用的是**新 tip**，于是 rebind 证明的是"新代码 == 集成 diff"，
  而 review-1 批的其实是**旧 tip**——集成进了未经评审的改动。

**必须**：`prepare-review-2` step1/2 增加
`当前 task tip 的 task_diff_fingerprint == 该 task review-1 ACCEPT verdict 里记录的 diff_fingerprint`，
不等即 BLOCKED。codex F5 讲的是 ancestry（不允许乱 merge），我这条是**指纹级防 stale tip**，
两者互补。

### G6 (P2, 新) — task 分支保留期未定：rebind 依赖 `base..<task_head>` 现算，分支提前删则 rebind 不可复算

§6/§7 的 rebind 与 canonical task 指纹都从 `base..<task_head>` 现算（G3-d）。若 task 分支在
review-1 后被清理（worktree remove + 分支删），`prepare-review-2` 的 rebind 断言、以及 review-2
事后复算 task 指纹都会失效。codex F9 讲的是分支命名/重试清理，我这条是**保留期依赖**：

- **红线级要求**：两条 task 分支必须保留到 review-2 ACCEPT + 用户验收 merge 之后，才允许清理；
  清理前 `prepare-review-2` 的 rebind 才可复算。
- 失败模式表（§11）应补一行："task 分支提前删除 → rebind/复算不可复现 → BLOCKED → 回退"。

### G7 (P2, 新) — `parallel_mode.enabled` 开关归属未定，影响一组 validator 校验是否触发

本模式与 `docs/parallel-development-mode.md` 并列、且复用其 embedded 预审（§5 Phase2「预审四件套」）。
但草案没说本模式是否置 `status.json.parallel_mode.enabled = true`：

- 若**置 true**：`validate_parallel_mode`（`validate-stage.py:359`）会强制 R10 checklist、
  `embedded-review-<task>-round<N>.{diff.patch,dispatch.md,raw-output.md}` 等具名证据、
  `r10_dispatch_tail_required`、`r4_diff_reconciliation_required` 等。本模式的 embedded 预审产物
  命名必须与之对齐，否则 pre-review 失败。
- 若**置独立开关**（如 `independent_task_branch_mode: true`）：上述 embedded 校验**不会触发**，
  除非 validator 显式为本模式端口一遍——否则 embedded 预审的落档纪律变成自觉执行（又一个
  fail-closed 缝隙）。

**必须**：明确开关归属，并据此清单化"哪些 parallel-mode validator 校验在本模式下继承/移植"。
这直接影响 §10 改动清单是否完整。

### G8 (P2, 补 codex F2) — 必改文件名不止 `20/60`，pre-accept 还卡 `30-review-1.md`/`50-review-2.md`

codex F2 命中了 `20-implementation.md`/`60-test-output.txt`/`70-handoff.md` 的单数 vs
`-<task>` 后缀冲突（`validate_required_files`，`validate-stage.py:689-698`）。补两点：

- pre-accept 还要求 `30-review-1.md` 与 `50-review-2.md`（`:695-696`）。本模式 review-1 是
  per-task（`30-review-1-backend.md` / `-frontend.md`？），review-2 是单条 integration。单数
  `30-review-1.md` 在双 owner 下如何对应（取 backend？合并？别名？）必须定，否则 pre-accept
  fail-closed。
- `validate_stage_branch` 对 `stage_branch.name` **只做字符串相等比较，不校验模板**
  （`validate-stage.py:504`，无 regex）。所以"允许 task branch 形态"（§10.2）对 validator 代码
  几乎是 no-op——真正要改的只是 YAML `stage_branch_name_template` 的描述文字。这是**好消息**
  （风险比草案暗示的小），但 §10.2 措辞应更正，避免高估改动量。

### G9 (P3, 新) — §9 R4 措辞与 §7 step9 自审条款需收敛

- R4「recorder/integrator 是脚本……**不做判断**」：rebind pass/BLOCKED 本身就是一个确定性判断。
  应改为"不做**语义/模型**判断，只做 git/test/validator/diff 的确定性机械判定"，否则与 step5
  rebind 断言自相矛盾。
- §7 `prepare-review-2` step9「若 reviewer 曾任 recorder-脚本触发者不构成代码作者自审」：reviewer
  是模型（Codex/Claude），recorder 是**人**跑的脚本，模型从不"曾任 recorder"。该条款要么删，要么
  改成"人运行脚本不产生任何模型的代码作者身份，故不影响 review-2 的 provider 隔离"。

### G10 (P3, 补 codex F8) — 单 owner 路径缺 R2 的对应物

§4/§5/§11 提到单 owner 阶段"直接在 stage/<id> 单终端自锚，无集成步"，但 §9 R2「review-1 审 task
fingerprint、review-2 审 integration fingerprint」对单 owner 不成立（没有 integration 分支）。
单 owner 下 review-1 与 review-2 审的是**同一个**顶层 committed 指纹。应补一句单 owner 变体：
无 `prepare-review-2`、无 integration 指纹、review-1=review-2 候选 = 顶层 `diff_fingerprint`。
否则单 owner 阶段照 R2 字面执行会找不到 integration 指纹。

## Required Changes（进 DRAFT-2，先于写脚本）

1. **(G1)** 在 §7 `record-checkpoint` 写明两段式提交：C_e（证据 commit）→ 算稳定指纹 → 写
   status.json（`head_sha=C_e`）→ 提交 status.json 为 tip C_s → pre-review；并注明 review-1 审
   `base..<记录 head_sha=C_e>`，不用 HEAD。
2. **(G2)** §10.2 删除"可选"，把 R1（product 路径不相交）与 R3（rebind 逐位）改为**强制**机检，
   由 `independent_task_branch_mode` 开关触发，pre-review/pre-accept fail-closed。
3. **(G3)** §6 与 §7 step3 互指为不变量对；rebound pathspec 取自 H_intake 冻结 scope（不允许运行期拼）；
   rebind 用 `git diff --binary <range> -- <pathspec>` 字节比较、对 raw task diff 而非指纹；
   列二进制/重命名/mode 为残留风险。
4. **(G4)** R1 重定义为 product 路径交集为空（排除 status.json 等元数据）；§7 step4 写明 status.json
   冲突的可执行解决（或改 task-local status 快照方案）。
5. **(G5)** `prepare-review-2` step1/2 加 anti-stale-tip：当前 task tip 指纹 == review-1 ACCEPT 记录指纹。
6. **(G6)** 红线/§11 加 task 分支保留期（到 review-2 ACCEPT + 验收 merge 后方可清理）。
7. **(G7)** 明确 `parallel_mode.enabled` vs 独立开关归属，清单化继承/移植的 validator 校验。
8. **(G8)** §10 补 `30-review-1.md`/`50-review-2.md` 在双 owner 下的对应规则；更正"task branch 形态"
   对 validator 代码是 no-op 的措辞。
9. **(G9/G10)** R4 改"不做语义判断"；删/改 step9 自审条款；补单 owner 的 R2 变体。
10. （沿用 codex F4）`record-checkpoint`/`prepare-review-2` 加 immutable-script guard：Harness 控制
    文件（AGENTS.md/workflows/**/registry/model-adapters/parallel-mode/本两脚本/validate-stage/schemas/**）
    在 task 分支有改动即 fail，除非显式许可；allowed scope 取自冻结元数据而非 CLI 入参。

## Open Questions（需人拍板）

1. task 分支写**顶层 status.json** 还是 **task-local 快照**？后者让 R1 不必特判、merge 不冲突，
   我倾向后者（G4 备选）。
2. 本模式开关是 `parallel_mode.enabled=true`（继承全部 R10/embedded 校验）还是独立 flag？
   这决定 §10 清单边界（G7）。
3. rebind 的 owner pathspec 在首个试运行阶段的**冻结值**是什么？必须在分发前写死，不能实现后推断
   （codex OQ3；我升级为前置要求 G3-b）。
4. 首个试运行阶段是否允许动 schema/API contract？按 R1 不应允许（共享面破不相交），建议首个 trial
   明确禁止契约改动。

## Recommended Trial Plan（回答 §13 Q1–Q5）

Q1（作为独立 trial mode 可接受？）**可接受**，前提是 G1–G4 进 DRAFT-2。Q2（两级指纹 + rebind 是否
足以替代单分支单指纹？）**理论上足以**，但 rebind 必须由"测试"证明而非"断言"——见下。Q3（确定性
脚本是否满足独立重算？）**满足**，前提是 immutable-script guard（codex F4）+ pathspec 冻结（G3-b）。
Q5（直接上 worktree 分支制）**接受该决定**，不再争论"先串行"；但首个实现目标应是"用 fixture 证明
rebind"，而非直接上真 GLM/Kimi 阶段。

建议把首个实现阶段做成 **Harness-only enablement stage**（赞同 codex trial plan，并强化）：

1. 先实现 `record-checkpoint` / `prepare-review-2`（不调模型）+ §10 的 validator/schema 改动，
   全部走 stage 分支。
2. **用合成 dry-run fixture 证明 rebind**（这是对 §13 Q2/Q3 的实证回答，不可省）：
   - 两条不相交 toy 分支 → product 路径交集空、task 指纹可复算、rebind hash 逐位相等、integration
     指纹可复算、pre-review/pre-accept 全过；
   - 共享文件 fixture → R1 BLOCKED；
   - status.json 冲突 fixture → 集成版正确产出；
   - stale-tip fixture（ACCEPT 后 amend 一条 task 分支）→ anti-stale-tip BLOCKED（G5）；
   - task 分支提前删 fixture → rebind BLOCKED（G6）。
3. fixture 全绿后，再选一个 scope 严格不相交、**禁止契约改动**、回退成本低的双 owner 阶段实跑
   （GLM 后端 + Kimi 前端）。
4. 成功判据（在 §12 基础上补）：每个 fixture 路径都有落档；rebind 由测试证明而非人工断言；
   `prepare-review-2` 的 anti-stale-tip 与保留期检查在实跑中至少各触发一次回归用例。
5. 任一红线破 → 回退串行 bookkeeper 模式，本提案回 DRAFT。

## Footer

本地北京时间: 2026-07-08 19:01:37 CST
下一步模型: human（综合 round-2 各评审）→ 修订 DRAFT-2
下一步任务: 按 G1–G4（阻塞性契约缺口）修订 `10-independent-task-branch-mode-draft.md` 为 DRAFT-2
（重点：record-checkpoint 提交/head_sha 时序、§10.2 删"可选"、rebind 不变量对与 pathspec 冻结、
R1 重定义 + status.json 冲突解决）；DRAFT-2 评审通过后，先合 §10 改动 + 两脚本 + rebind fixture，
再上真双 owner 阶段。
