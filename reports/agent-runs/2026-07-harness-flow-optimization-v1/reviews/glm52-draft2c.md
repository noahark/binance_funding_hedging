# Review: glm52 (DRAFT-2 rev c)

> Reviewer: GLM-5.2（`zhipu_glm`，经 Claude Code `claude_glm` 适配器；身份与利益披露同
> `reviews/glm52-draft2.md`——GLM 是本模式扩权的后端实现者之一、bookkeeper 候选，涉"实现者/
> 候选记账者对 git/证据/scope 写权"的结论请按轻度利益相关方审视）。本确认轮只核实契约缝是否
> 闭合，未改任何产品代码或 canonical Harness 文件。

## Verdict

ACCEPT

## Summary

契约缝闭合到位，可以开始写两个脚本。rev c 用 A=checkpoint sidecar、B=独立 flag、C=钉死 canonical
调用、D=task-local review-1、E=product 分支禁 `allow_harness_change` 五项决策，把我前轮的 F1–F12
与四项共同项全部收口，且收法正确：sidecar 干净消解自指而不动 canonical 排除集（§6/§9-6/§10-1）；
immutable-guard 与 scope 读取钉到"从可信检出经 git ref 操作 task 分支、`git show <base_sha>:`
读 scope"（§9 开头/§9-2/§9-3），工作树侧已无法架空；anti-stale-tip 三元等式
（tip==checkpoint.head_sha==review_1.diff_fingerprint，§10-2）对 review-1 后 amend/追加严密；
§17 补齐 ⑥–⑬ 反向 fixture；§14 补齐 workflow YAML / `_template/` / 脚本测试。残留仅 P3（测试
执行时序、两分支 merge 机制措辞、共享 worktree 篡改窗口、单 owner fixture），均不阻塞写脚本，
且大多被 §10-7 集成全量测试这道绑定门兜住。建议接受，按 §17 进 Harness-only enablement stage。

## Findings

### 已确认闭合（我前轮 findings → rev c 落点）

- **F1 checkpoint 自指 → A sidecar（闭合）**：§9-5 只提交单个证据 commit C_e（= task_head，含
  `evidence/<task>/` 除 checkpoint.json 外），§9-6 写**未提交** sidecar checkpoint.json，
  §10-1 跨 worktree ingest、§10-7 在集成分支提交。task 分支单提交、`tip==head_sha`、canonical
  排除集不动（§6），集成分支提交的 checkpoint.json 记的是 **task** 指纹、不构成 integration 自指。
  无证据丢失、无自指。
- **F2 immutable-guard 信任边界 → §9 开头 + §9-2（闭合）**：recorder 从可信检出运行、经 git ref
  操作 task 分支、禁跑 task worktree 的 `scripts/` 副本；guard `git diff <base>..<task-branch> --
  <protected>` 作用于 ref 不作用于工作树。实现者改工作树 `scripts/record-checkpoint` 已无法影响
  **被运行**的那个副本。R4（§16）亦明示"从可信检出跑"。
- **F3 allowed_scope 来源 → §9-3（闭合）**：`git show <base_sha>:reports/agent-runs/<stage>/status.json`
  读取，禁工作树/CLI；changed files ∈ (`product_paths` ∪ `evidence/<task>/`)，越界 BLOCKED。工作树改
  status.json 扩 scope 的旁路已封。
- **F4 parallel_mode 归属 → B + §14-3（闭合）**：新 `independent_task_branch_mode.enabled`，
  dispatch-ready 在其下重写（§8 Phase 0、§14-3 明示现 `validate_dispatch_ready` 在
  `parallel_mode.enabled` 非 true 时 no-op 的问题）。该门用于首次真实双 owner 分发前，不阻塞写两脚本。
- **F5 反向 fixture → §17 ⑥–⑬（闭合）**：intersection/rebind-mismatch/stale-tip/early-delete/
  forbidden-path/immutable-guard/partial-merge/rename 八项齐备，编号干净。
- **F6 canonical 复现 → C + §6/§14-3（闭合）**：canonical 不加 `--no-renames`（不破坏既有指纹），
  但 §6 钉死 `git -c diff.renames=true …` 形态、三处复算逐字相同；rebind 用 `--no-renames`。跨环境
  漂移封住，§17-⑬ rename fixture 双证。
- **F7 anti-stale-tip → §10-2（闭合）**：三元等式（`git rev-parse <task-branch>` ==
  checkpoint.head_sha == 重算指纹 == review_1.diff_fingerprint），任一不等 BLOCKED。amend/追加均
  逮（即便同步改 checkpoint.json，review_1 指纹这一定锚由人记录、不可被实现者一致伪造）。
- **F8 review-1 ingest → §10-1/§10-7/§13（闭合）**：显式 `--backend-worktree`/`--frontend-worktree`
  + `git worktree list --porcelain` 校验归属与 tip、逐份 sha256+来源；review-1 产物不提交回 task 分支
  （§13，避免移 tip），由 prepare-review-2 在集成分支提交。
- **F9 worktree↔cwd → §4 表 + §9/§10/§14-3（闭合）**：recorder 从可信检出、integrator/validator
  cwd=集成 worktree。
- **F10 §14 完整性 → §14-1..6（闭合）**：补 `stage-delivery.yaml`（§14-2）、`_template/`（§14-5）、
  两脚本+fixture 测试（§14-6）；F2 文件映射 = D（task-local 30-review-1，去顶层必需）。
- **F11 partial-merge 原子性 → §10-7（闭合，见 R2 措辞）**：`--no-commit --no-ff`→断言→过才 commit，
  失败 `merge --abort`/reset 到原 tip，不留坏 commit。
- **F12 human_decision 具名 → §12（闭合）**：task 级 `evidence/<task>/human-decision.json`、stage 级
  顶层 `human-decision.json`，validator 后续校验存在。

### 残留（均为 P3，不阻塞写脚本）

#### R1（P3）§9-4 测试在 commit 前跑——证据可能不反映 C_e
- §9-4 以冻结 `test_command` 在 `--task-worktree` 跑测试，§9-5 才提交 C_e。测试对象是**提交前工作
  树**，而非 C_e committed 态。实现者可用未提交（gitignore/`.git/info/exclude`）的 `conftest.py`
  等在运行期弱化测试，使 `60-test-output.txt` 标 pass 而 C_e 的提交态测试本应 fail。
- **降级理由**：绑定测试门是 §10-7 集成**全量**测试，跑在**人控制的集成 worktree**、对 `--no-commit`
  merge 态（= 将提交内容），实现者无此 worktree 写权 → 真实失败在此被兜住。故 §9-4 仅为 checkpoint，
  非绑定门。
- 建议（非阻塞）：写 recorder 时让 §9-4 对 **C_e committed 态**跑测试（先提交 C_e 或在 C_e 的干净
  检出里跑），使 per-task 证据也 provably 反映 C_e。§18-1 已自陈此点，按此收口即可。

#### R2（P3）§10-7"对两分支 git merge --no-commit --no-ff"机制措辞偏粗
- 两分支无法都 `--no-commit` 顺序 merge（未提交态会挡住第二次）。应钉死其一：octopus
  `git merge --no-commit --no-ff <A> <B>`（不相交 product_paths 无冲突、给单一稳定 merge_head），
  或"先 --no-ff 提交 M1 → 对 B `--no-commit --no-ff` → 断言 → 过提交 M2 / 失败 reset--hard 到原 tip
  （连 M1 一起回滚）"。§10-7 已含"reset 到集成分支原 tip"，覆盖回滚，仅顺序/策略需写明。

#### R3（P3）checkpoint.json / review-1 产物在共享 task worktree 的 pre-ingest 篡改窗口
- 这些未提交文件物理留在 task worktree（实现者有文件系统访问权），§10-1 的 sha256+来源是 ingest
  时记录、不能防 pre-ingest 篡改。指纹值篡改被 §10-2 三元等式（从 git ref 重算）兜住；但 verdict
  **文本**（REWORK→ACCEPT）若被改成 schema-valid 且指纹一致的伪造 ACCEPT，prepare-review-2 无法
  区分。信任锚是人按 R9 记录的 dispatch receipt——与既有 dispatch 模型一致，属既定信任假设。
- 建议（非阻塞）：若要再收紧，让人把 review-1 raw output 落到实现者无写权的路径（集成 worktree 或
  人独占目录），或把 reviewer 会话 receipt 与 ingest 的 sha256 在 status.json 交叉登记。

#### R4（P3）§17 fixture 全为双 owner；单 owner record-checkpoint 路径（§7，写顶层 status.json）无 smoke fixture
- 单 owner 路径更接近现行串行模式、风险低，但它是同一 `record-checkpoint` 脚本的不同代码路径
  （`--single-owner` 写顶层 status.json）。建议 §17 至少加一条单 owner smoke（提交→顶层指纹→pre-review
  过），避免该路径首跑即在真实 stage 暴露问题。

### 对 §18 开放问题的判断
- §18-1（测试隔离）：见 R1，建议测试对 C_e committed 态跑——收口后闭合。
- §18-2（canonical vs rebind rename 语义）：§17-⑬ fixture + C 钉死调用已足；建议 fixture 含
  rename+modify（纯 rename 是最易情形）。
- §18-3（新 flag dispatch-ready 继承清单）：validator 编写期裁量，不阻塞两脚本；写 validator 时清单化即可。
- §18-4（原子集成覆盖）：见 R2，钉死 merge 策略后闭合。
- §18-5（⑥–⑬ 是否足够门槛）：足够。建议把 R1（per-task 测试对 C_e）与 R2（merge 策略）作为 fixture
  ⑭/⑮ 补进，零成本。

## Required Changes

无阻塞项（ACCEPT）。写脚本/落 §14 时顺手收口的非阻塞建议：
1. (R1) recorder 让 §9-4 测试对 C_e committed 态跑（或先提交 C_e 再测），§18-1 同步收口。
2. (R2) §10-7 钉死两分支 merge 策略（octopus `--no-commit --no-ff` 或 M1→B `--no-commit`→reset 回滚）。
3. (R3/R4) review-1 产物落点 / 单 owner smoke fixture——可推迟到 enablement stage 实跑前。

## Open Questions

1. (R2) 两分支原子 merge 选 octopus 还是 M1→B 顺序？影响 merge_head 稳定性与回滚实现，建议写
   prepare-review-2 前定。
2. (R3) 是否要求 review-1 raw output 落实现者无写权路径？这是既定人操作信任模型的加固项，非必需。
3. （沿用 §18-5）R1/R2 是否升格为 §17 fixture ⑭/⑮？建议是——零成本、堵住两个已识别窗口。

## Footer

本地北京时间: 2026-07-08 20:36:39 CST
下一步模型: human（综合 draft2c 确认轮）→ 若 GLM+GPT 均 ACCEPT，按 §17 启动 Harness-only enablement stage
下一步任务: 在常规串行 stage 分支落 §14 待改点（含钉死 canonical 调用、新 flag dispatch-ready 重写、
workflow YAML、`_template/`、schema）+ 实现两脚本（采纳 R1 测试时序、R2 merge 策略）+ §17 含 ⑥–⑬
（建议补 ⑭/⑮）的 dry-run，全绿后再选真实双 owner 阶段。
