# Review: glm52 (DRAFT-2 rev b)

> Reviewer: GLM-5.2（`zhipu_glm`，经 Claude Code `claude_glm` 适配器）。本会话由 Claude Code
> 运行于 glm-5.2 后端；按 `agents/registry.yaml` 的 provider 规则，`claude_glm` 的 provider
> identity 是 `zhipu_glm`，不是 Anthropic——即便经由 Claude Code 访问。故以 `glm52` 落款。
> **利益披露**：GLM 是本模式要扩大自主权的后端实现者之一（§4 backend_implementer），亦是
> bookkeeper 候选（`registry.yaml` `bookkeepers.glm52_candidate`）。凡涉及"实现者/候选记账者
> 对 git、证据写权、scope 输入的约束"的结论，请按轻度利益相关方审视。本评审未改任何产品代码
> 或 canonical Harness 文件。

## Verdict

REWORK（方向与 D1–D4 落地正确，比 DRAFT-1 有实质进步；但有 2 处 P1 契约精度缺口会让两个脚本
"照字面写就跑不通或门禁可绕过"，另有若干 P2 影响第 14 条/§17 fail-closed 完整性。补齐后即可
进入脚本实现 + Harness-only enablement stage。）

## Summary

DRAFT-2 把上一轮的主要阻塞都收掉了：放弃顶层 status.json（D1）消解了双分支 metadata 交集与
merge 冲突；recorder/integrator 改确定性脚本、按层各一个写者；不新增 status 枚举（已对照
`validate-stage.py:21-37` `ALLOWED_STATUSES` 全部命中）；review-1 维持 `claude_glm↔kimi` 交叉
（对照 `registry.yaml:464-466` 派生规则一致）；rebind hash 与 canonical 指纹分离。glm52-round2
的 G2（"可选"措辞）已在 §10-4/§10-6 改为强制 BLOCKED——确认解决。

但以"能不能照 §9/§10 把脚本写出来并真的过 validator、且红线不可被工作树侧绕过"为标准逐条核，
仍有 **2 处 P1**：(1) `checkpoint.json` 的提交/指纹时序与 canonical exclude 集不自洽——
`compute_diff_fingerprint`（`validate-stage.py:160-176`）只排除顶层 `status.json`，不排除
`checkpoint.json`，而 §9-6 在 §9-5 提交之后才写 `checkpoint.json`、§10-1 又要在 merge 后读它，
三者在"checkpoint.json 是否提交、提交后是否自指"上互锁未解；(2) immutable-script guard 的
**信任边界**未定——guard 由 recorder 自己执行，但 §9 没说跑的 recorder 必须是 base/main 的可信
副本而非 task worktree 的工作树副本，实现者改工作树里的 `scripts/record-checkpoint` 再就地跑，
§9-2 即被架空。另有 P2 涉及 `parallel_mode.enabled` 隐藏依赖、§17 仅正面 fixture、canonical
`--no-renames` 复现性、anti-stale-tip、worktree cwd、review-1 artifact 归属等。

以下凡与 `kimi-for-coding-round2.md`（审 DRAFT-2）重合处，标注其解决状态，不重复展开。

## Findings

### P1

#### F1（P1）`checkpoint.json` 提交/指纹时序 + canonical exclude 集不自洽
- §9-5 先 commit（范围 D2：source/test + `evidence/<task>/` + impl/embedded-review），§9-6 才计算
  `task_diff_fingerprint` 并写入 `evidence/<task>/checkpoint.json`。即 `checkpoint.json` 在 §9-5
  commit **之后**产生 → 它不在该 commit 内 → 留在工作树**未提交**。
- 但 §10-1 要求 prepare-review-2"读两分支 `evidence/<task>/checkpoint.json`"，且 §10-5 依次 merge
  两 task branch——merge 只带**已提交**文件，未提交的 `checkpoint.json` 不会进入集成分支 → §10-1
  在集成分支上**读不到**它。
- 若想让 `checkpoint.json` 进 commit：canonical 公式（§6 / `compute_diff_fingerprint`）只
  `:(exclude)` 顶层 `status.json`，**不排除 `checkpoint.json`**。而 `checkpoint.json` 内含
  `head_sha` + `task_diff_fingerprint` → 提交它即自指（指纹依赖含指纹自身的那次 commit 的 hash，
  鸡生蛋），与 AGENTS.md"status.json excluded because it would otherwise be self-referential"
  同一类问题，只是换了文件。
- 唯一无矛盾的两段式（即 glm52-round2 G1 给 status.json 的解法，移植到 task-local 证据）：
  (a) 提交 C_e = 该 task 改动 + 证据（不含 `checkpoint.json`）；因 canonical 排除集不含它，
  `sha256(diff(base..C_e))` 稳定；(b) 算 `fp = C_e : sha256(...)`；(c) 写 `checkpoint.json`
  （`head_sha = C_e`——**不是后续 tip**，`diff_fingerprint = fp`）；(d) 提交 `checkpoint.json`
  为尾提交 C_s（分支 tip = C_s）。review-1 审 `base..<记录 head_sha=C_e>`，validator 用记录值 C_e
  重算（`validate_common`/`validate_tasks` 用 `task["head_sha"]`，不校验 HEAD==head_sha）。
- **但这要求 canonical exclude 集纳入 `evidence/<task-id>/checkpoint.json`**，即 §6 公式与
  `compute_diff_fingerprint` 都要加这条 `:(exclude)`，否则 C_s 进了 `base..C_s` 范围、
  自指再现。§14-2 当前未列此 validator 改动；§6/§9 也未写两段式与 `head_sha=C_e` 语义。
- 不解此条，recorder 写不出正确版本（任一实现路径都撞自指或工作树丢文件）。

#### F2（P1）immutable-script guard 的信任边界未定——recorder 可被工作树侧架空
- §9-2 的 guard **由 recorder 自己执行**。§9 首行"`scripts/record-checkpoint …，用在 task
  branch`"未规定**从哪个工作树/检出**调用。
- 若"用在 task branch"= `cd` 进 task worktree 再 `python scripts/record-checkpoint …`，则运行的
  是 task worktree **工作树副本**——实现者可编辑该副本（删掉 guard 步骤、放宽 pathspec 来源），
  然后跑被篡改的版本，§9-2 自检形同虚设。diff（base..head）虽含 `scripts/**` 改动，但 guard
  要先运行才检测，而运行的恰恰是被去掉 guard的那个副本。
- 解法（须写进 §9）：recorder 必须从**可信检出**（integration/main，即 base 冻结的那个版本）
  调用，并通过 ref 操作 task branch（如 `git diff <base>..<task-branch>`、`git show
  <base>:...`），而非进入 task worktree 跑其工作树里的 `scripts/`。或等价地，guard 作为独立
  不可变预检（operator 先在可信检出跑 `git diff <base>..<task-branch> -- scripts/ schemas/
  AGENTS.md ...`）再调用任何 task 侧代码。
- 这是 glm52-round2 F4 未触及的层次（F4 守"脚本文件被改"，本条守"被改的脚本不能是被运行的那个"）。

### P2

#### F3（P2）`allowed_scope` 来源机制未钉死 → 工作树改 status.json 可扩大 scope
- §9-2"allowed_scope 一律来自 base 冻结的 `status.json.tasks[].allowed_scope`，不接受 CLI 覆盖"
  只说了**来源**，没说**读法**。
- 若 recorder 读**工作树** `status.json`，实现者可就地（不提交）编辑它，把自己想加的越界路径塞
  进 `allowed_scope`，再提交该路径的代码。因 D2 禁止 commit 顶层 `status.json`，该编辑不进
  `base..head`、不算 §9-3 的 changed file；但 §9-3 读到的是**被改过的** scope → 越界文件"合法"。
- 须在 §9 钉死：`allowed_scope` 一律 `git show <base_sha>:reports/agent-runs/<stage>/status.json`
  读取，禁止读工作树文件或 CLI 入参。这是 §9 焦点"实现者能否篡改 recorder 的 policy 输入"的直接
  答案：**当前规格下能（经工作树 status.json），钉死到 git-show-base 后不能**。

#### F4（P2）`parallel_mode.enabled` 隐藏依赖未决——dispatch-ready/D3 门可能整条失效
- `validate_dispatch_ready`（`validate-stage.py:534-536`）在 `parallel_mode.enabled` 非 true 时
  **直接 return（no-op）**；`validate_parallel_mode`（:359-378）同理，且 enabled=true 时会强制全套
  R10 证据（`r10_dispatch_tail_required`、`r4_diff_reconciliation_required`、`embedded_reviews`
  逐轮 `dispatch_path`/`worktree_diff_path`/`raw_output_path`，:404-430）。`stage-delivery.yaml`
  task-breakdown 的 dispatch-ready preflight（:393）也以 `parallel_mode.enabled=true` 为前提。
- DRAFT-2 §8 Phase 0 把 dispatch-ready 当 D3（`allowed_scope` 冻结）的门，§8 Phase 2 复用 embedded
  R1–R10，但**全文未说本模式是否置 `parallel_mode.enabled=true`**：
  - 置 true → dispatch-ready/D3 门生效，但本模式 evidence 命名（`evidence/<task>/...`）须对齐
    parallel-mode 的 `embedded_reviews` 具名字段，否则 pre-review fail-closed；
  - 置独立 flag → dispatch-ready 是 no-op，D3 冻结门**不存在**，embedded R10 纪律退化为自觉执行
    （又一个 fail-closed 缝）。
- §14 当前未列此项决策（glm52-round2 G7 未解）。须在 §14 显式二选一并清单化"继承/移植哪些
  parallel-mode validator 校验"。

#### F5（P2）§17 dry-run 只有正面 fixture，无法证明 fail-closed
- DRAFT-2 §17 仅列 5 条**正面**断言（① metadata 不撞 product 交集 ② task 指纹可重算 ③ rebind
  匹配 ④ integration 指纹可重算 ⑤ review-1 非 ACCEPT 时 prepare-review-2 拦住）。
- enablement stage 的全部价值在于证明各 BLOCKED 路径**真的会拦**：product 交集非空、rebind
  不等、immutable-script guard 命中、D4 forbidden shared paths、stale-tip、task 分支早删、
  partial-merge 失败。仅正面跑通的 fixture 不能证伪"红线被绕过"。
- 须把负面 fixture 写进 §17（prompt 焦点列了 ⑥–⑩，但 DRAFT-2 §17 正文缺；附带提一句：prompt
  里 ⑥–⑩ 是 5 个符号装 6 个条目，落 fixture 时统一编号）。

#### F6（P2）canonical 指纹未 `--no-renames`——跨环境复现有漂移风险
- §6 刻意让 canonical（`task_diff_fingerprint`/`integration_diff_fingerprint`，绑定门禁锚）沿用
  `compute_diff_fingerprint`（:160-176，**默认 rename 检测**、排除 status.json），而**非绑定**的
  `product_rebind_hash` 才用 `--no-renames`。
- 但 canonical 是**绑定**锚，要被 record-checkpoint、review-1 评审者**独立重算**、validator 三处
  复算。git 默认 rename 检测依赖 `diff.renames`/`merge.renames` 配置与版本——不同环境复算可能
  一处显示 rename、一处显示 delete+add，hash 不一致 → 假 mismatch（误 BLOCKED）或更糟的假 match。
  rebind 用 `--no-renames` 正是为字节稳定，可它恰恰是**非绑定**的那个。
- 须二选一并落 §6/§14：(a) canonical 也加 `--no-renames`（注意会改变**既有** stage 已记录指纹，
  需迁移说明）；或 (b) 规格**钉死** canonical 复算的 git 调用（`-c diff.renames=true ...` 或统一
  config），三处复算必须同形。现状的"绑定锚反而不字节稳定"是设计倒挂。

#### F7（P2）§10 缺显式 anti-stale-tip——rebind 只部分覆盖
- §10-3 校验 ancestry/无 sibling merge（F5），但未校验"task 分支当前 tip == `checkpoint.json`
  记录的 `head_sha` == review-1 实际审计的 head"。§10-5 `git merge <task-branch>` 合的是**当前
  tip**；若 review-1 后 task 分支被追加提交，merge 会带入未审代码。
- §10-6 rebind 用 `checkpoint.json` 的 `base..task_head` 计算，能逮住**触碰 scope** 的追加提交；
  但 evidence-only 的追加（不动 scope）rebind 看不见，却仍会被 merge 进集成分支。
- 须在 §10 增一步：merge 前 `git rev-parse <task-branch> == checkpoint.head_sha`，不等即 BLOCKED
  （glm52-round2 G5；rebind 是 defense-in-depth，不能替代显式 tip 校验）。

#### F8（P2）review-1 artifact 的归属/ingest 未规格化 → 指纹漂移或读不到
- §8 Phase 4"落 `evidence/<task>/30-review-1.md`"，§13 列同路径。但 §10（prepare-review-2
  step 1–10）**无任何一步** ingest 或 commit 这两份 review-1 文件（§10-1 只读 `checkpoint.json`，
  §10-8 只写 `status.json` 的 `review_1.verdict`）。
- 若在 task branch 上 commit 它们 → task tip 越过 `task_head`（review-1 审的是 `base..task_head`，
  但 tip 已漂移，触发 F7）。若留在 task worktree 未提交 → prepare-review-2 在**集成 worktree** 跑、
  读不到。
- prompt §13 焦点断言"rev b 由 prepare-review-2 在集成分支 commit"——但 §10 步骤里**没有**这一步。
  须显式写：人把 review-1 raw output 放到集成 worktree 的 `evidence/<task>/`，prepare-review-2
  新增一步 commit 之（在集成分支，进 `integration_diff_fingerprint`，无自指问题，因其记录的是
  task 指纹而非 integration 指纹）。

#### F9（P2）worktree cwd 未规格——validator 会校验错工作树
- `repo_root()`（:99-101）= `git rev-parse --show-toplevel` @ `Path.cwd()`；`current_branch`
  （:139）、`require_clean_worktree`（:124）、`compute_diff_fingerprint`（:160）全部 `cwd=root`。
- 若 operator 从**主仓库目录**跑 `validate-stage.py`，而集成分支在另一 worktree，则
  `current_branch` 返回主仓库分支、`require_clean_worktree` 查主仓库 porcelain、指纹按主仓库
  工作树算——全部错位，`validate_stage_branch`（:504 `branch != name`）直接误杀。
- 须在 §10/§14 钉死：validator 与两脚本必须以**对应 worktree 根**为 cwd 运行（kimi-round2
  Critical #2，未解；prompt §14 已点名）。

#### F10（P2）§14 清单漏项
- (a) `workflows/templates/stage-delivery.yaml` 未列——本模式是其执行编排变体，即使不新增 status
  枚举，也需新增模式指针/task-branch 执行变体引用（kimi-round2 High #3）。
- (b) `reports/agent-runs/_template/` 未列——需 task-branch `status.json` 模板、`human_decision`
  示例、`tasks[]` 指纹示例。
- (c) 两脚本的 fixture/单元测试未列——它们担单一写者 + rebind 证明，真实 stage 前必须有测试。
- (d) F2 文件映射（`validate_required_files` :689-698 要求顶层 `20/30/50/60`）：§14-2 列了但留
  "二选一"未决。双 owner 下顶层 `30-review-1.md`（review-1 是 per-task 两条）如何对应必须钉死，
  否则 pre-accept fail-closed。

### P3

#### F11（P3）脚本部分失败原子性未定义
- §9/§10"任一步失败→非0退出+BLOCKED"，但未定义 all-or-nothing 回滚。如 §10-5 merge 已落集成
  分支、§10-6 rebind 失败 → 集成分支残留坏 merge commit，规格未说保留/回滚/标 abandoned。
  建议 prepare-review-2 先 `git merge --no-commit --no-ff` → rebind → 通过才正式 commit
  （kimi-round2 Critical #1/#4，部分解决）。

#### F12（P3）`human_decision` 非 proceed 分支的落档位置偏松
- §12 对 `assign_fix`/`escalate` 说"由人写入受影响 track 的 evidence 或临时 stage 决策文件"。
  "临时 stage 决策文件"无具名路径，审计链有缝。建议钉一个具名文件（如
  `evidence/<task>/human-decision.json` 或顶层 `human-decision.json`）。

## Required Changes

**阻塞性（写脚本前必须落规格）：**
1. **(F1)** §6 canonical exclude 集纳入 `evidence/<task-id>/checkpoint.json`；§9 写两段式提交
   （C_e 证据 commit = `task_head` → 算稳定指纹 → 写 `checkpoint.json`(`head_sha=C_e`) → 尾提交
   C_s）；§14-2 列出 `compute_diff_fingerprint` 对应 exclude 改动；review-1 审 `base..<记录 C_e>`。
2. **(F2)** §9 钉死 recorder 信任边界：从可信检出（base/integration/main）调用、经 ref 操作 task
   branch；禁止在 task worktree 跑其工作树 `scripts/` 副本。
3. **(F3)** §9 钉死 `allowed_scope` 读取 `git show <base_sha>:<status_rel>`，禁工作树/CLI。
4. **(F8)** §10 增 review-1 artifact ingest+commit 一步（集成 worktree 落 `evidence/<task>/`）。
5. **(F9)** §10/§14 钉死 validator 与两脚本 cwd = 对应 worktree 根。
6. **(F4)** §14 显式决定 `parallel_mode.enabled` 归属（或新 flag）并清单化继承/移植的校验。

**强烈建议（落 §14 / 跑 §17 前）：**
7. **(F5)** §17 增负面 fixture（intersection / rebind-mismatch / stale-tip / early-delete /
   forbidden-path / immutable-guard / partial-merge）。
8. **(F7)** §10 增 `task tip == checkpoint.head_sha` 显式校验。
9. **(F6)** §6/§14 对 canonical `--no-renames` 二选一（加 `--no-renames` 含迁移，或钉死复算 git
   调用）。
10. **(F10)** §14 补 `stage-delivery.yaml` / `_template/` / 两脚本测试；钉死 F2 文件映射选择。
11. **(F11/F12)** §10/§12 补 partial-merge 原子性与 `human_decision` 具名落档路径。

## Open Questions（需人拍板）

1. **(F4)** 本模式是 `parallel_mode.enabled=true`（继承全套 R10/embedded 校验，命名须对齐）还是
   独立 flag（则 dispatch-ready/D3 门需新写）？这决定 §14 清单边界。
2. **(F6)** canonical 指纹是否加 `--no-renames`？加则既有 stage 指纹失效需迁移；不加则须钉死三处
   复算的 git 调用形态。
3. **(F10-d)** 双 owner 下顶层 `30-review-1.md` 取 backend / 合并 / 别名？需在写 validator 前定。
4. **(F1)** 首个试运行 `allowed_scope` 的冻结值是什么？须分发前写死（不可实现后推断）。
5. （沿用）rebind 若通过但全量测试失败，状态回退 `fixing` 还是直接 BLOCKED？

## Footer

本地北京时间: 2026-07-08 19:57:57 CST
下一步模型: human（综合 draft2 各评审）→ 修订 DRAFT-2 rev c
下一步任务: 按 F1–F3/F8/F9（阻塞性契约精度）与 F4（开关归属）修订
`10-independent-task-branch-mode-draft.md`；rev c 评审通过后先合 §14 改动 + 两脚本（含 F1 两段式、
F2 信任边界、F3 git-show-base）+ §17 含负面 fixture 的 rebind dry-run，再上真实 GLM/Kimi 双 owner
阶段。
