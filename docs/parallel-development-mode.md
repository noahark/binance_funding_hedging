# 双端并行开发模式（parallel_development_with_embedded_cross_review）

状态：**DRAFT-1**（Fable5 起草，2026-07-04；待 GPT/Codex review 后定稿。
定稿后由一个独立的小型 harness 变更把本模式指针写入 `AGENTS.md`；在此之前
本文档不具备规范效力，现行 `AGENTS.md` + `workflows/templates/
stage-delivery.yaml` 仍是唯一权威。）

起源：用户 2026-07-04 提议双终端并行开发以提速；GPT 补充任务内嵌交叉评审；
Fable5 补充与 Hard Gates 的兼容性修正（预审定性、预写 prompt 红线、本地轮次
记账规则）。三方结论已在对话中对齐，本文档是其正式化。

---

## 1. 目标与适用条件

**目标**：在不削弱既有证据纪律的前提下，把「实现」和「review-1」两个最耗
墙钟时间的环节并行化，并让 review-2 专注于整体一致性、接口契约、证据链与
回归风险，而非替 review-1 抓低级缺陷。

**适用条件**（全部满足才启用本模式；任一不满足则回退串行 stage-delivery）：

1. 阶段含 ≥2 个实现任务，且任务 scope 两两不相交（如 `backend/**` vs
   `frontend/**`）。
2. 任务间接口契约可在设计期冻结：任务书必须写死精确字符串、schema 字段、
   fixture 形状等一切跨任务消费物。任何"B 等 A 产出后才知道"的依赖存在，
   则该依赖项不得并行（整体回退或将该项后置）。
3. 每个实现任务有一个非本任务实现者的可用评审模型（交叉评审可成立）。

## 2. 角色

| 角色 | 承担者（当前配置） | 职责 | 禁止 |
|---|---|---|---|
| designer / breakdown author | Fable5 (anthropic) | 设计记录、双任务书、**双评审 prompt 预写**、H_intake | 写产品代码 |
| bookkeeper（记账者，即本模式下的 controller） | Fable5（或用户指定的单一会话） | 收证据、跑测试、**串行 commit**、算指纹、跑 validator、推进 status.json、调度正式 review-1 确认与 review-2 | 写产品代码；改写/摘要评审证据 |
| implementer-A | claude_glm | `backend/**` 等 A scope | commit、写 status.json、算最终指纹、越 scope |
| implementer-B | kimi | `frontend/**` 等 B scope | 同上 |
| embedded reviewer（嵌入预审） | 对侧模型的 **fresh read-only 会话** | 按预写 prompt 审对方任务的工作树 diff | 复用实现 transcript；审自己实现的任务 |
| final reviewer (review-2) | Codex/GPT（按排除规则定，见 §6） | 整体终审 | — |

**单一写者原则**：status.json、git 提交、指纹、状态机在任何时刻只有
bookkeeper 一个写者。两个实现终端全程不碰 git 与 status.json。

## 3. 流程

```text
Phase 0  设计（bookkeeper/designer）
  H_intake 提交：00-task.md（含冻结的接口契约）+ 10-design.md
  + 双实现任务书 + 双评审 prompt（预写，见 §4-R1）+ status.json(designing)

Phase 1  并行实现（两终端同时启动）
  implementer-A 开发 A-scope   ‖   implementer-B 开发 B-scope
  各自完成 → 写实现报告 → 停（不 commit）

Phase 2  嵌入交叉预审（两侧各自触发，可并行）
  A 完成后：A 终端机械执行预写 prompt-RA，启动 fresh 对侧模型
            read-only 会话，预审 A 的工作树 diff
  B 完成后：B 终端机械执行预写 prompt-RB，同理
  预审返回问题 → 实现者只修自己 scope → 可再预审一轮
  （本地循环封顶 2 轮，见 §4-R4）

Phase 3  串行落盘（bookkeeper）
  收两侧实现报告 + 全部预审落档 → 复跑测试 → 串行提交 H_A、H_B
  → 计算 task 级指纹 → validator(pre-review)

Phase 4  正式 review-1 确认（可并行）
  与 Phase 2 相同的评审模型，对 committed 指纹出正式 verdict
  （schema 合规 JSON，独立重算指纹）。因预审已清零问题，预期单轮 ACCEPT。
  返回 REWORK → 走正式 rework 流程（计入 rework_count）。

Phase 5  review-2 终审 + 终态
  bookkeeper 调度 final reviewer 对 stage 级指纹终审
  → validator(pre-accept) → stage_accepted_waiting_user → 用户验收
```

## 4. 红线（违反任一条，相关评审/交付无效）

**R1 预写评审 prompt。** 双评审 prompt 必须由 designer 在 H_intake 随任务书
提交入库，内容含：被审任务的 scope/forbidden、验收口径、必跑命令、落档路径；
仅留 diff 范围一个运行期参数。实现终端启动预审时**逐字使用**入库版本。
没有入库预写 prompt 的嵌入预审无效。
（理由：嵌入模式下派工方=被审代码作者，必须把作者对评审输入的裁量权压到零。）

**R2 fresh read-only 评审会话。** 预审与正式 review-1 都必须在全新会话中
进行，不得复用任何实现/controller transcript；评审依据只能是 raw diff 与
仓库内落档文件，不接受任何会话内转述。

**R3 本地 fix 限界。** 预审发现的问题，实现者只能在自己任务的 scope 内修。
凡涉及接口契约、schema、跨任务消费字段、共享文件的改动，一律不得本地 fix，
必须升级 bookkeeper 决策（必要时回到设计层修任务书）。

**R4 本地循环封顶 2 轮且全落档。** 每个任务的「预审→fix」循环最多 2 轮；
每轮的评审 prompt 执行记录、评审 raw output、fix 说明必须按 §5 命名落档。
2 轮仍未清零 → 停止并升级 bookkeeper（可能定性为任务书缺陷或正式 REWORK）。
本地循环**不计入** stage 的 `rework_count`（该配额保留给正式门后的 REWORK），
但轮次与落档必须在 status.json 中如实记录，不存在账外迭代。

**R5 嵌入预审是 checkpoint，不是评审门。** 预审对象是未提交工作树，依据
Hard Gates 属于 "in-progress checkpoint before a review gate"，其结论
**不能**作为 review-1 verdict 落档。正式 review-1 必须在串行提交后对
committed 指纹出 schema 合规 verdict（Phase 4）。预审的价值是把问题在
进正式门之前修掉，不是替代正式门。

**R6 单一写者。** 见 §2。实现终端提交 git、修改 status.json、宣称指纹，
任何一项发生即整个任务定性 REWORK。

**R7 review-2 排除规则不变。** 设计者（含本模式的 designer/bookkeeper）
所属 provider 不得担任 review-2；两实现 provider hard-ban；先前披露机制
（strong-reviewer disclosure）照旧。当前配置下：Fable5 设计+记账 →
review-2 必为 Codex/GPT。

**R8 既有 Hard Gates 全部继续适用。** 单一指纹协议、committed 态评审、
raw 证据优先、validator 前置、契约修订须附 raw 公开样本等，本模式一概
不豁免。

## 5. 落档命名约定（stage 目录内）

```text
task-a-<model>.prompt.md            # A 实现任务书（H_intake）
task-b-<model>.prompt.md            # B 实现任务书（H_intake）
embedded-review-a.prompt.md         # A 的预审 prompt（H_intake，预写）
embedded-review-b.prompt.md         # B 的预审 prompt（H_intake，预写）
20-implementation-{backend,frontend}.md
embedded-review-a-round<N>.raw-output.txt
embedded-review-b-round<N>.raw-output.txt
embedded-fix-a-round<N>.md          # 每轮 fix 说明（改了什么、为何）
embedded-fix-b-round<N>.md
30-review-1-{backend,frontend}.md   # 正式 review-1（Phase 4）
50-review-2.md
```

status.json 增加记录块（示意）：

```json
"embedded_reviews": {
  "A": {"rounds": 1, "reviewer": {"provider": "kimi", "fresh_session": true},
         "artifacts": ["embedded-review-a-round1.raw-output.txt"],
         "escalations": []},
  "B": {"rounds": 2, "reviewer": {"provider": "claude_glm", "fresh_session": true},
         "artifacts": ["embedded-review-b-round1.raw-output.txt",
                        "embedded-fix-b-round1.md",
                        "embedded-review-b-round2.raw-output.txt"],
         "escalations": []}
}
```

## 6. 与现行 workflow 的关系

- 本模式是 `stage-delivery.yaml` 的**执行编排变体**，不新增状态机状态：
  Phase 1-2 发生在 `implementing`，Phase 3 结束进 `review_1`，其后与现行
  流程完全一致（`review_1 → review_2 → stage_accepted_waiting_user`）。
- 不新增指纹协议、不新增 verdict schema。预审落档是证据增强，不是新门。
- review-2 的 `reviewer_prior_involvement` 披露与回退路径
  （`decision_models_exhausted` 等）不变。

## 7. 升级路径（非本次采纳范围）

**方案乙：worktree 分支制。** 每任务独立 git worktree 分支开发并提交，
预审直接绑分支 committed 指纹（消除 R5 的 checkpoint/正式门两段式），
bookkeeper 串行落主干后做机械 rebind（diff 哈希逐位一致，参照
bstock-alias-v1 evidence-backfill 的 rebind 先例）。待方案甲跑通 ≥2 个
阶段且两段式确认开销成为主要痛点时再评估。

## 8. 采纳条件与试运行

1. 本文档经 GPT/Codex review（对象：与 AGENTS.md/Hard Gates 的一致性、
   护栏完备性、可执行性）。verdict 与修订意见落档
   `reports/agent-runs/harness-parallel-mode-v1/`（轻量记录，无代码）。
2. ACCEPT 后：状态改 ADOPTED-TRIAL，在接下来 1-2 个双任务阶段试运行。
3. 试运行通过后：一个独立小变更把指针写入 `AGENTS.md`（引用本文档），
   状态改 ADOPTED。
4. 试运行中任何红线被突破 → 回退串行模式，本文档回到 DRAFT 修订。

---

本地北京时间: 2026-07-04 16:20 CST
起草: Fable5 (anthropic/claude-fable-5)
下一步: 用户将本文档交 GPT/Codex review；意见回传后由 Fable5 修订定稿。
