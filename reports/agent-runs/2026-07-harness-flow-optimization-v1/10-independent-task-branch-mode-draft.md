# 独立 task-branch 交付模式（human-operated independent task-branch trial mode）

状态：**DRAFT-2 rev c2**（2026-07-08）。试运行模式草案，供多模型再评审。**不修改**
`AGENTS.md` / `workflows/` / `scripts/validate-stage.py` / `schemas/`。评审通过后由
独立小型 harness 变更落地（§14 待改点）。

定位：`stage-delivery.yaml` 的执行编排变体，是
`docs/parallel-development-mode.md` §7「方案乙：worktree 分支制」的具体化。
**不新增指纹协议、不发明 worktree fingerprint、不发明新 status 枚举值**；所有 review
gate 仍锚在 committed 态。冲突时以 `AGENTS.md` + `stage-delivery.yaml` 为准。

修订记录：
- DRAFT-1 / DRAFT-2 / rev b：见 `status.json.decision_log` DEC-2026-07-08-001/002 与
  `05-harness-environment-snapshot.md`。
- **DRAFT-2 rev c（2026-07-08 20:17）**：落实 DRAFT-2 四家评审
  （`reviews/{gemini3.1pro,codex-gpt5,kimi-for-coding,glm52}-draft2.md`，均 REWORK、
  无 BLOCKED）的 8 项阻塞契约缝 + 建议项，并锁定用户四项决策：
  **A=checkpoint sidecar（不进 task 分支）**、**B=新独立 flag
  `independent_task_branch_mode`**、**C=canonical 不加 `--no-renames`、钉死复算调用**、
  **D=validator 读 task-local review-1**，及 **E=product task 分支禁
  `allow_harness_change`**（DEC-2026-07-08-003）。
- **DRAFT-2 rev c2（2026-07-08 20:28）**：落 draft2c 确认轮（`reviews/glm52-draft2c.md`=ACCEPT、
  `reviews/codex-gpt5-draft2c.md`=REWORK 两处执行时序）——§9 改为「先校验工作树候选→提交 C_e→对
  C_e committed 态跑测试」（codex R1，修 `base..branch` 提交前为空的时序 bug）；§10-7 钉死顺序
  `--no-ff` merge M1→M2→ingest M3、merge_head=M3 存在后再断言 rebind+全量测试、失败 `git reset
  --hard T0` 原子回滚（codex/glm R2）；§17 补 fixture ⑭/⑮/⑯ + R3 说明（glm P3）。DEC-2026-07-08-004。

---

## 1. Trial-mode 硬性要求（D1–D4 + E，hard gates）

- **D1** 双 owner task branch 不写顶层 `status.json`；顶层唯一由 `prepare-review-2`
  在集成分支写。单 owner 例外见 §7。
- **D2** `record-checkpoint` commit 范围 = product scope + 该 task 的 `evidence/<task-id>/`
  证据目录（§9）；禁 commit 顶层 status.json/70-handoff/对方 task 文件/顶层 60-test-output。
- **D3** pathspec **分发前**冻结于集成/base `status.json.tasks[].allowed_scope`
  （§3 拆分为 product_paths；唯一来源经 `git show <base_sha>:` 读取，实现者/CLI 不可改）。
- **D4** 首次试运行禁改 schema/API contract/shared fixture（forbidden shared paths 硬门）。
- **E** product task branch **禁** `allow_harness_change=true`；一切 Harness 改动只走
  串行 enablement stage（§9、§17）。

## 2. 目标

需求 + 执行文档冻结后，GLM/Kimi 从一次性分发**自走到 review-1**，人只在 review-2
介入。不变量：不用模型 bookkeeper（锚定是确定性脚本，产出从 git 独立可重算）；实现者
不能伪造/篡改 binding evidence 或 policy 输入；不引入 worktree fingerprint；不制造
dual-hat；双 owner 唯一串行点压缩为一条 `prepare-review-2` 并折进人本来就要做的 review-2
准备。

## 3. 适用条件与 scope 模型

启用双 owner 独立分支需全满足：① GLM+Kimi 两个实质任务；② 两任务 **product 路径两两
不相交**；③ 跨任务契约设计期冻结；④ 每任务有 registry provider 派生的可用交叉评审模型；
⑤（D4）不触碰 forbidden shared paths。不满足 → 单 owner（§7）或串行 parallel-mode。

**scope 拆分（F2，Kimi/Codex）**：`status.json.tasks[]` 每条含：
```json
"allowed_scope": {
  "product_paths": ["backend/**"],          // 交集校验 + product rebind hash 的唯一依据
  "test_command": "pytest backend/...",     // 冻结自测命令（record-checkpoint 复跑）
  "allow_harness_change": false             // E：product task 恒 false
}
```
每个 task 另**自动附带**证据所有权 `reports/agent-runs/<stage>/evidence/<task-id>/`
（允许 commit，但**不计入** product 交集/rebind；见 §6）。`product_paths` 与证据目录
之外的任何 `reports/**`/源码路径改动一律 BLOCKED。

## 4. 角色

| 角色 | 承担者 | 写产品代码 | 写 git/status | 职责 |
|---|---|---:|---:|---|
| dispatch_author | Codex 或 Claude 会话 | 否 | 否 | 设计/执行/评审 prompt、任务包、R10 收尾段、冻结 product_paths/test_command |
| human_stage_operator | 人 | 否 | 否（只跑脚本/dispatch） | 分发；读 review-1；记 human_decision；跑 `prepare-review-2`；手动 review-2；验收 merge；R9 dispatch 纪律（§11） |
| backend_implementer | claude_glm | 是(product_paths) | 否 | 后端实现/测试/embedded 预审/scoped fix（自己 worktree） |
| frontend_implementer | kimi | 是(product_paths) | 否 | 前端实现/测试/embedded 预审/scoped fix（自己 worktree） |
| embedded_pre_reviewer | 按 registry provider 派生的对侧 fresh read-only（`claude_glm→kimi`，`kimi→claude_glm`） | 否 | 否 | 提交前工作树 diff 预审（checkpoint，非正式门） |
| recorder（脚本） | `scripts/record-checkpoint`，**从可信检出运行** | 否 | 是（限本 task branch commit，范围 D2） | 机械锚定单 task branch 到 review-1 |
| integrator（脚本） | `scripts/prepare-review-2`，**cwd=集成 worktree** | 否 | 是（唯一顶层 status.json + 集成分支） | 合并、rebind、ingest review-1、备 review-2 |
| formal_review_1 | 交叉审 GLM↔Kimi（provider 派生） | 否 | 否 | 对 task fingerprint 出 schema JSON verdict |
| final_review_2 | 人选 Codex→Claude | 否 | 否 | 对 integration fingerprint 终审 |

## 5. 分支拓扑

```text
main
 └─ stage/<stage-id>                     # 集成分支，唯一顶层 status.json；亦作可信检出
task/<stage-id>/backend-glm              # GLM 独立 worktree 分支（独立 task/ 命名空间）
task/<stage-id>/frontend-kimi           # Kimi 独立 worktree 分支
```

> **git ref 约束（enablement stage dry-run 实证）**：task 分支**不得**嵌在集成分支
> ref 之下——git 无法同时持有 `stage/<id>` 与 `stage/<id>/backend-glm`（ref 文件会占用
> 同名 ref 目录）。故 task 分支放在独立 `task/<stage-id>/<owner>` 命名空间，集成分支保持
> `stage/<stage-id>`。`status.json.tasks[].branch` 记录完整 task 分支名。

- 两 task branch 从同一 base（= `stage/<id>` 建支点 = 记录 `base_sha`）出发。
- 血统（F5-orig）：`base_sha` 是每个 task `head_sha` 祖先；task branch 创建后**禁 merge
  兄弟分支/main**；review-1 用 `base_sha..task_head_sha`，禁符号 HEAD；出现 sibling/main
  merge commit → `prepare-review-2` BLOCKED。
- 命名/清理：retry 用 `…/backend-glm-r2`；review-2 验收前**不 force-delete** 任何 task
  branch（防 early-delete）；abandoned 分支名记 status.json。
- 单 owner 阶段不建 task branch（§7）。

## 6. 证据与指纹模型

**证据布局（task-local，D1）**：
```text
reports/agent-runs/<stage>/evidence/<task-id>/
  ├── checkpoint.json        # sidecar（A2）：base_sha, head_sha(=C_e), task_diff_fingerprint,
  │                          #   product_rebind_hash, product_paths, test_status
  │                          #   —— 不提交进 task 分支，见下
  ├── 20-implementation.md   # committed（进 task_head）
  ├── 60-test-output.txt     # committed（进 task_head）
  ├── 30-review-1.md         # review-1 后产生，不提交回 task 分支（§13）
  ├── review-1.raw-output.md # 同上
  ├── review-1.attempts.json # 同上，schema 见 §11
  ├── embedded-review-*.{dispatch.md,diff.patch,raw-output.md,fix-note.md}
  └── record-checkpoint.log
```

**checkpoint.json 生命周期（A2，解 gemini①/codex②/glm F1 自指）**：
`record-checkpoint` 在 task 分支只做**一个证据 commit C_e**（= `task_head_sha`），内容为
product 改动 + `evidence/<task-id>/` 中**除 checkpoint.json 外**的证据文件。
`checkpoint.json` 含 `head_sha` 与指纹，**永不提交进 task 分支**——它作为 sidecar 留在 task
worktree 的 `evidence/<task-id>/`，由 `prepare-review-2` 走 §10 跨 worktree 机制读取并在
**集成分支**提交。故 `task_head=C_e` 单提交、无自指、`tip==head_sha`（anti-stale-tip 简单），
**不改动 canonical 排除集**。

**两级 canonical 指纹（唯一门禁锚）**，用**钉死的**调用形态（C，解 glm F6 复现漂移）：
```text
CANON_DIFF(base, head) =
  git -c diff.renames=true diff --binary <base>..<head> \
    -- . ":(exclude)reports/agent-runs/<stage>/status.json"
task_diff_fingerprint        = <task_head> ":" sha256(CANON_DIFF(base, task_head))
integration_diff_fingerprint = <merge_head> ":" sha256(CANON_DIFF(base, merge_head))
```
- canonical **不加** `--no-renames`（保持与现行 `compute_diff_fingerprint()` 一致、不使既有
  stage 指纹失效），但**三处复算**（record-checkpoint / review-1 评审者 / validator /
  prepare-review-2）必须用**上面逐字相同**的 `git -c diff.renames=true …` 形态，消除
  rename 检测因 config/版本不同导致的漂移。§14 把此调用形态钉进 validator 与两脚本。
- `evidence/<task-id>/`（含未提交的 checkpoint.json/review-1 产物）本就不在 task 分支
  committed 态里干扰 `task_head`，故 canonical 覆盖 `base..task_head` 即「product + 已提交
  证据」，仅排除顶层 status.json。

**非绑定 product_rebind_hash（F3-orig，仅供集成机械断言）**：
```text
PRODUCT_DIFF(base, head) = git diff --binary --no-renames <base>..<head> -- <product_paths>
<task>_product_rebind_hash             = sha256(PRODUCT_DIFF(base, task_head))
<task>_integration_product_rebind_hash = sha256(PRODUCT_DIFF(base, merge_head))
```
pathspec 严格取 `product_paths`；`evidence/**`/`reports/**` 不计入（解 Kimi/Codex 的
scope 矛盾）。加 `--no-renames` 保逐位可复现；**不用于任何门禁绑定**，只服务 §10 集成断言。
> 开放问题（§18）：canonical（含 rename 检测）与 rebind（`--no-renames`）在 product rename
> 下语义不同——rebind 仍逐位相等即可用于集成断言，但 §17 须有 rename fixture 双证。

## 7. 单 owner 路径（细化，解 Kimi P2）

无 task branch。单实现终端在 `stage/<id>` 上：实现 → embedded 预审 → scoped fix → 把
`record-checkpoint <stage> --single-owner --branch stage/<id>` 当预写收尾步自跑。单 owner 下
该脚本**直接写顶层 `status.json`**（只有一个写者、无交集/合并问题，D1 仅约束双 owner）、
提交单个候选 commit、算顶层 `diff_fingerprint`、跑 `validate-stage.py --phase pre-review`。
review-1 交叉审对顶层 fingerprint 出 verdict → 人决策 → review-2。**不使用
`prepare-review-2`，无集成步**。人从分发到 review-1 零介入。

## 8. 流程（双 owner）

```text
Phase 0  设计冻结                         [人 + dispatch_author]
  00-task/10-design/11-adr/12-breakdown + 双任务书(含预写 R10 收尾段 + 预写
  record-checkpoint 调用) + 双 embedded 预审 prompt + 冻结 product_paths/test_command
  入 status.json.tasks[].allowed_scope + 冻结跨任务契约
  ▸ validator gate: --phase dispatch-ready（新 flag 下校验 allowed_scope 冻结 / R10 /
    交叉审派生 / forbidden shared paths；见 §14）

Phase 1  一次性分发                       [人：git worktree add 两分支 + 粘任务包]

Phase 2  并行实现 + 嵌入预审 + scoped fix  [GLM/Kimi 各自 worktree，不碰 git]
  实现 → 自测 → 执行预写对侧 fresh read-only 预审(R10) → 只在 product_paths 内修
  (verbatim 遵 parallel-mode R1–R10：2 轮封顶、契约/schema 禁本地 fix、失败分类升级)

Phase 3  单 task 机械锚定                 [scripts/record-checkpoint，每分支各一次]
  见 §9；产出 C_e(=task_head) + task-local checkpoint.json(sidecar) + task-local 证据
  （不写顶层 status.json；validator 不在 task 分支跑，脚本内部做证据完整性自检）

Phase 4  交叉 review-1（每 track 并行）    [人跑预写 dispatch，遵 §11 R9 纪律]
  GLM 分支→Kimi 审 ; Kimi 分支→GLM 审（fresh read-only；用 §6 钉死调用独立重算 task
  fingerprint；schema JSON verdict）→ 产物留各自 task worktree evidence/<task>/（不提交回）

Phase 5  人工决策落档                     [人，见 §12]
  记 human_decision(proceed_to_review_2 | assign_fix | escalate)

Phase 6  集成 + review-2 准备             [scripts/prepare-review-2，仅当 proceed]
  见 §10；ingest 两 worktree 的 checkpoint.json+review-1 产物 → anti-stale-tip →
  --no-ff merge（原子）→ rebind 断言 → 全量测试 → 写唯一顶层 status.json +
  integration fingerprint
  ▸ validator gate: --phase pre-review（cwd=集成 worktree）

Phase 7  review-2 终审 + 终态             [人手动 Codex→Claude，遵 §11]
  对 integration fingerprint 终审 → --phase pre-accept → stage_accepted_waiting_user
  → 用户验收 → merge main
```

## 9. `scripts/record-checkpoint` 契约（确定性；从**可信检出**运行）

`record-checkpoint <stage-id> --task <task-id> --branch <task-branch>
--task-worktree <path> [--single-owner]`。

**信任边界（F3，glm）+ 工作树候选处理（codex draft2c R1）**：脚本本体、policy 读取
（`allowed_scope`/`test_command` 经 `git show <base_sha>:`）、guard/scope/指纹判定必须从
**可信检出**（集成/main worktree，= base 冻结版本）运行；对 task worktree 只做 git 读取
（status/diff）与 stage/commit，**禁**跑其工作树 `scripts/` 副本。
**关键时序**：实现者不提交（R6），候选全在 task worktree **未提交**态——故 `base..<task-branch>`
在提交前**为空**，guard/scope 必须先校验工作树候选、提交 C_e 后再对 committed 态复算。步骤：

1. 校验 `<task-branch>` 从 base 出发、`base_sha` 是其祖先、无 sibling/main merge commit。
2. 读 frozen policy：`allowed_scope.product_paths`/`test_command` 一律
   `git show <base_sha>:reports/agent-runs/<stage>/status.json`（F4；禁工作树/CLI）。
3. **工作树候选校验（pre-commit）**：读 task worktree 未提交改动
   （`git -C <task-worktree> status --porcelain` / diff）：(a) **immutable-guard（F3）**：任一改动命中
   `AGENTS.md`/`workflows/**`/`agents/registry.yaml`/`docs/model-adapters.md`/
   `docs/parallel-development-mode.md`/`scripts/**`/`schemas/**` → BLOCKED（product task 恒禁
   `allow_harness_change`，E）；(b) **scope**：任一改动 ∉ (`product_paths` ∪ `evidence/<task-id>/`)
   → BLOCKED。
4. `git add` 允许路径 → commit **C_e**（= `task_head`；范围 D2：product + `evidence/<task-id>/`
   除 checkpoint.json 外）；message 前缀 `[checkpoint:<task-id>]`。
5. **post-commit 完整性（codex R1）**：task worktree 对 `product_paths` 与已提交证据须 clean
   （仅 checkpoint.json / review-1.* 允许未提交），确保 `base..C_e` 完整反映候选、不漏未提交改动。
6. 从可信检出对 committed `base..C_e` 复算 guard/scope（defense-in-depth）+ 用 §6 钉死调用算
   `task_diff_fingerprint` 与 `product_rebind_hash`。
7. **测试对 C_e committed 态跑（codex R1）**（工作树已 == C_e）：从 `--task-worktree` 根以冻结
   `test_command` 复跑，输出**只**写 `evidence/<task-id>/60-test-output.txt`；命令缺失或写 evidence
   外路径 → BLOCKED。
8. 写**未提交 sidecar** `evidence/<task-id>/checkpoint.json`（`head_sha=C_e`）；备该 track review-1
   dispatch prompt（reviewer 按 provider 派生）。

任一步失败 → 非 0 退出 + 写 `evidence/<task-id>/record-checkpoint.BLOCKED.md`，停。

## 10. `scripts/prepare-review-2` 契约（确定性；cwd=集成 worktree）

`prepare-review-2 <stage-id> --backend-worktree <path> --frontend-worktree <path>
--human-decision proceed_to_review_2 --rationale "<reason>"`（显式 worktree 路径，不靠分支名
隐式发现；F5/codex/glm）：

1. **ingest（F5/F8，解跨 worktree 未提交产物）**：对每个 `--*-worktree`：`git worktree list
   --porcelain` 校验该路径确为该 stage 对应 task 分支的 worktree 且 tip 符合预期；读取其未提交
   `evidence/<task-id>/` 下 `checkpoint.json`、`30-review-1.md`、`review-1.raw-output.md`、
   `review-1.attempts.json`；对每份记 sha256+来源。
2. **anti-stale-tip（F6，四家共识）**：对每 task 断言
   `git rev-parse <task-branch> == checkpoint.head_sha`，且用 §6 钉死调用重算
   `task_diff_fingerprint(base, checkpoint.head_sha) == checkpoint.task_diff_fingerprint
   == review_1.diff_fingerprint`；任一不等 BLOCKED。
3. 校验两 track review-1 verdict 均 `ACCEPT`（schema-valid）；每 track `invalid_json_attempts ≤ 2`
   （读 attempts.json，§11）。
4. immutable-script guard（同 §9-2，作用于两分支合并集）。
5. 校验两分支 merge-base 一致且 == 记录 base_sha；无 sibling/main merge。
6. **product 交集为空**（R1，仅 `product_paths`；证据/metadata 不计入）。非空 → BLOCKED。
7. **原子集成（F11/kimi + codex/glm draft2c R2）**：记原集成 tip `T0`。`git checkout stage/<id>`
   → **顺序** merge（次序记 status.json，如 backend→frontend）：`git merge --no-ff <backend-branch>`
   （→ `M1`）→ `git merge --no-ff <frontend-branch>`（→ `M2`）；product_paths 不相交，无冲突。
   → **ingest 提交** `M3` = §10-1 取得的 checkpoint.json + review-1 产物（落集成分支
   `evidence/<task-id>/`）。`merge_head := M3`。**此时 merge_head 已存在**（解 codex/glm：
   `--no-commit` 下 merge_head 不存在无法断言），才做：(a) 每 task **rebind 断言**
   `integration_product_rebind_hash(base..M3, product_paths) == product_rebind_hash`（逐位）；
   (b) 复跑**全量**测试。任一失败 → `git reset --hard T0`（丢弃 M1/M2/M3）+ 写 BLOCKED，
   **不留残留**。全过 → 算 `integration_diff_fingerprint(base..M3)`。（集成分支提交的 sidecar 记的是
   **task** 指纹，不构成 integration 自指。）
8. **写唯一顶层 `status.json`**：`tasks[]`（各含 base/head/task_diff_fingerprint/allowed_scope/
   review_1.verdict/review_1.diff_fingerprint）、顶层 `integration_diff_fingerprint`、
   `status=review_2`、`human_decision` 块（§12）。
9. `validate-stage.py <stage-id> --phase pre-review`（cwd=集成 worktree，F7）。
10. 备好 review-2 dispatch（Codex 主、Claude 备）。

任一步失败 → 非 0 退出 + 写 BLOCKED evidence，不进 review-2。

## 11. 人工 dispatch 纪律 + attempts schema（横切，继承 R9/R10）

- review-1/review-2/fix dispatch 必须走 dispatch 文件 + RECEIPT + raw-output 落档，禁无落档
  聊天窗口中转（R9）。
- **invalid-JSON（Kimi F3-orig/P2）**：由跑 dispatch 的人记
  `evidence/<task-id>/review-1.attempts.json`；`prepare-review-2` 读取校验每模型 ≤ 2、超限
  BLOCKED。schema：
  ```json
  {
    "invalid_json_attempts": { "kimi": 1, "claude_glm": 0 },
    "recorded_by": "human_stage_operator",
    "updated_at": "<ISO8601 from local date>"
  }
  ```
- 既有 Hard Gates（单一指纹协议、committed 态评审、raw 证据优先、契约修订须附 raw 公开样本、
  rework 上限、人工门等）一概不豁免。

## 12. 人工决策落档（独立于 `prepare-review-2`，具名，解 Kimi/glm F12）

`human_decision` 独立 required 块，review-1 后写，三分支都落，先于 `assign_fix` 或
`prepare-review-2 --human-decision proceed_to_review_2`：

```json
"human_decision": {
  "decided_by": "human",
  "decision": "proceed_to_review_2 | assign_fix | escalate",
  "rationale": "<reason>",
  "reviewed_task_fingerprints": {"backend": "<h:sha>", "frontend": "<h:sha>"},
  "timestamp": "<ISO8601 from local date>"
}
```
- `proceed_to_review_2` → 由 `prepare-review-2` 写入顶层 status.json。
- `assign_fix`/`escalate` →（`prepare-review-2` 不运行）人写入**具名文件**：task 级决策落
  `evidence/<task-id>/human-decision.json`，stage 级决策落顶层
  `reports/agent-runs/<stage>/human-decision.json`；schema 同上；validator 后续阶段校验其存在。

## 13. review-1 双 track artifact 与提交语义（D + F8）

```text
evidence/backend/30-review-1.md   evidence/backend/review-1.raw-output.md   evidence/backend/review-1.attempts.json
evidence/frontend/30-review-1.md  evidence/frontend/review-1.raw-output.md  evidence/frontend/review-1.attempts.json
```
- **提交语义**：`task_head` 于 record-checkpoint 冻结；review-1 产物在锚定**之后**产生，
  **不提交回 task 分支**（否则移动 tip、触发 §10-2 anti-stale-tip）；以未提交文件留在各自 task
  worktree，由 `prepare-review-2` §10-1 ingest、§10-7 在**集成分支**提交。
- **validator（D）**：task 模式读 task-local `evidence/<task-id>/30-review-1.md`，
  **去掉**对顶层 `30-review-1.md` 的必需要求；集成 `status.json.tasks[]` 每条含
  `review_1.verdict` 与 `review_1.diff_fingerprint`(== 该 task fingerprint)，validator 独立校验
  每 task review-1 指纹。

## 14. 与现行 Harness 的映射 & 待改点（本 stage 不应用，走 stage 分支落地）

**不发明新 status 值**：机器状态用现有枚举 `implementing → review_1 → review_2 →
stage_accepted_waiting_user`；post-review-1 暂停用 `paused` + 叙述。

1. `AGENTS.md`：新增本模式指针；明确「跑 git/pytest/validator/record-checkpoint/
   prepare-review-2 不算 model dispatch」；`human_decision`、R9 人工 dispatch、E（product 分支禁
   `allow_harness_change`）。
2. `workflows/templates/stage-delivery.yaml`（**新增，gemini③/codex/glm F10a**；它是高于 DRAFT
   的可执行契约）：加可选模式 `independent_task_branch_mode`（task-branch 拓扑、recorder/
   integrator 脚本门、task-local 证据路径、review-1 ingest、集成 pre-review 门）。
3. `scripts/validate-stage.py`：
   - 允许集成分支上「current=集成分支、tasks[].branch 指向 task 分支」上下文（**非**简单放开
     task-branch 形态，glm F10-P3）；
   - **B 新 flag**：`independent_task_branch_mode.enabled` 下**重写** `--phase dispatch-ready`
     校验（allowed_scope 冻结 + forbidden shared paths），因现 `validate_dispatch_ready` 在
     `parallel_mode.enabled` 非 true 时 no-op（glm F4）；显式清单化从 parallel-mode 继承/移植
     哪些校验；
   - **F2 文件映射（D）**：task 模式接受 task-local 证据路径、读 task-local 30-review-1.md；
   - 集成 `--phase pre-review` 增：product 交集为空、rebind 断言、每 task review-1 指纹、
     `human_decision` 存在且 attempts ≤ 2、anti-stale-tip；
   - **钉死 canonical 复算调用**（C）为 §6 的 `git -c diff.renames=true …` 形态；
   - **worktree↔cwd（F7）**：脚本与 validator 以对应 worktree 根为 cwd 运行。
4. `schemas/`：`human_decision`、`review-1.attempts.json`、`tasks[].allowed_scope`
   (`product_paths`/`test_command`/`allow_harness_change`)、`task_diff_fingerprint`、顶层
   `integration_diff_fingerprint`；清理 verdict schema 残留 "controller" prose。
5. `reports/agent-runs/_template/`（**新增，glm F10b**）：task-branch `status.json` 模板、
   `human_decision` 示例、`tasks[]` 指纹/allowed_scope 示例、`evidence/<task-id>/` 骨架。
6. 新增 `scripts/record-checkpoint`、`scripts/prepare-review-2` + 二者的 fixture/单元测试
   （glm F10c；仓库当前无 runner）。

## 15. 失败模式与回退

- product 交集非空 / 触碰 forbidden shared paths / immutable-guard 命中 → BLOCKED → 人工或回退单 owner。
- 某 task branch review-1 REWORK → 仅该分支内 fix + 重跑 record-checkpoint，不影响另一 track；计入 rework_count。
- anti-stale-tip 失配 / rebind 失配 → 有未审/夹带改动 → BLOCKED。
- partial-merge：§10-7 原子（`--no-commit --no-ff`→断言→过才 commit，失败 `merge --abort`），不留坏 commit。
- 对侧预审不可用 → `failure_classes.embedded_checkpoint` 升级，实现者不得自审自填。
- rebind 过但全量测试失败 → 回 `fixing`（走正式 rework），非直接 BLOCKED（开放问题 §18-5 已定此默认）。
- review invalid JSON / 双决策模型耗尽 → 现行 `decision_models_exhausted` 路径。
- 任一红线破 → 回退串行模式，本文档回 DRAFT 修订。

## 16. 红线

- **R1** product 交集为空是硬校验（仅 `product_paths`）；触碰 forbidden shared paths（D4）BLOCKED。
- **R2** review-1 审 task fingerprint，review-2 审 integration fingerprint。
- **R3** rebind 机械可证（§6/§10）。
- **R4** recorder/integrator 是脚本：不调模型、不判断；含 immutable-guard（从可信检出跑，§9）；失败非 0 退出并写 BLOCKED。
- **R5** review-1 交叉审、不默认 Codex（`claude_glm↔kimi` provider 派生）。
- **R6** 单一写者按层：task branch 只有 record-checkpoint 写（范围 D2）；集成分支只有 prepare-review-2 写顶层 status.json。实现终端自行 commit/写 status 即该 task REWORK。
- **R7** 既有 Hard Gates 全部继续适用。

## 17. 试运行计划与成功判据

**已定路线**：直接上 worktree 分支制。首个实跑 = **Harness-only enablement stage**（非产品
阶段，走**常规串行** stage 分支落 §14；**不经 record-checkpoint**，故 §9 immutable-guard 不作用
于它自身；product task 分支恒禁 `allow_harness_change`——E）：

1. 合入 §14 待改点（含钉死 canonical 调用、新 flag dispatch-ready、workflow YAML、_template、
   schema）。
2. 实现两个脚本（无模型调用）+ 其单元/fixture 测试。
3. 合成 dry-run fixture（两个不相交 toy 分支）：
   - **正向**：① metadata 不撞 product 交集 ② task 指纹可重算 ③ product rebind 匹配
     ④ integration 指纹可重算 ⑤ 任一 review-1 非 ACCEPT → prepare-review-2 拦。
   - **反向/fail-closed（四家共识）**：⑥ product 交集非空→BLOCKED ⑦ rebind 失配（注入夹带）
     →BLOCKED ⑧ anti-stale-tip（review-1 后 task 分支追加 commit）→BLOCKED ⑨ task 分支
     early-delete→prepare-review-2 拒 ⑩ 触碰 forbidden shared path→BLOCKED ⑪ immutable-guard
     命中（改 scripts/**）→BLOCKED ⑫ partial-merge（M1/M2/M3 后故意让全量测试挂）→`git reset
     --hard T0` 无残留 ⑬ **product rename fixture**（C/kimi）→ canonical 独立可重算且 rebind 逐位过。
   - **draft2c 追加（codex/glm）**：⑭ record-checkpoint 留一处未提交 product 改动 / 注入未提交
     conftest → §9-5 post-commit clean 拦截、且测试对 C_e 跑（codex R1）；⑮ 集成 merge/rollback：
     M3 后故意让全量测试挂 → `git reset --hard T0` 无残留、且断言在 merge_head(M3) 存在后进行
     （codex/glm R2）；⑯ **单 owner smoke**：单 owner record-checkpoint 在 `stage/<id>` 直接写顶层
     status.json + 顶层 fingerprint 路径跑通（glm R4）。
   - **R3 说明（非 fixture）**：未提交产物在 task worktree 的 pre-ingest 篡改由 §10-2 三元等式
     （指纹值）兜住；verdict 文本层伪造属既定人操作信任假设，不在脚本门禁范围。
4. 通过后，选 scope 严格不相交、不改 schema/contract/shared fixture（D4）、回退成本低的双 owner
   阶段实跑。

成功判据：每门 `validate-stage.py` 通过且不依赖未知 status；review-1/review-2/validator 三处用
钉死调用独立重算指纹一致；anti-stale-tip 与 rebind 逐位通过；⑥–⑬ 全部 fail-closed；每转移
（含 human_decision）有落档；单 owner 分发到 review-1 零介入 / 双 owner 仅一条 prepare-review-2。
任一红线破 → 回退串行 bookkeeper 模式并重开为 DRAFT。

## 18. 给评审模型的开放问题（rev c2 剩余）

1. ✅ 已闭合（codex R1）：§9 改为先校验工作树候选→提交 C_e→测试对 C_e committed 态跑；§17-⑭ 覆盖。
2. §6 canonical（含 rename 检测）vs rebind（`--no-renames`）在 product rename 下语义差异，§17-⑬
   fixture 是否足以证明无误用风险？
3. §14 新 flag 下 dispatch-ready 重写 + 从 parallel-mode 继承的校验清单是否完整、有无 fail-closed 缝？
4. ✅ 已闭合（codex/glm R2）：§10-7 改为顺序 `--no-ff` merge（M1→M2）→ ingest 提交 M3 → merge_head=M3
   存在后再断言 rebind + 全量测试，失败 `git reset --hard T0` 原子回滚；§17-⑮ 覆盖。
5. §17 正向①–⑤ + 反向⑥–⑯ 是否足够作为放行真实双 owner 的门槛？

## Footer

本地北京时间: 2026-07-08 20:17:24 CST
下一步模型: external reviewers（对 DRAFT-2 rev c，写 `reviews/<model-id>-draft2c.md`）
下一步任务: 评审 §9/§10 脚本契约（信任边界/ingest/anti-stale-tip/原子集成）、§6 指纹钉死调用、
§14 待改点完整性；通过后按 §17 先做 Harness-only enablement stage。
