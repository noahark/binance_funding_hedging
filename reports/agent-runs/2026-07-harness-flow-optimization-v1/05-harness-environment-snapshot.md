# Harness 环境快照（DRAFT-2 决策基线）

本地北京时间: 2026-07-08 19:20:21 CST
仓库: `main` @ `41c6ba5`（工作树仅本 stage 目录未跟踪，canonical Harness 文件未改动）

本快照冻结「独立 task-branch worktree 模式」DRAFT-2 撰写前的环境事实与已锁定决策，
供 DRAFT-2 与后续多模型评审引用。**本快照不修改任何 canonical Harness 文件。**

---

## 1. 当前 canonical Harness 文件清单（DRAFT-2 的改动都相对这些文件）

| 文件 | 现状/版本 | 与本模式相关的现约束 |
|---|---|---|
| `AGENTS.md` | 现行 | bookkeeper=单一写者；committed-state 评审；单一指纹协议；禁 worktree fingerprint；未知 status fail-closed；model dispatch 须 human |
| `workflows/templates/stage-delivery.yaml` | v1 | `require_committed_state_before_review`、`forbid_worktree_fingerprint`、stage 分支门、review_1 交叉池、review_2 codex→claude |
| `agents/registry.yaml` | v1 | `review_1_cross_review_pool:[kimi,claude_glm]`、`review_1_selection_rules`（按 provider 派生）、`model_dispatch_execution`（human 执行） |
| `docs/parallel-development-mode.md` | **v0.4 ADOPTED-TRIAL** | R1–R10（预写 prompt / fresh read-only / 本地 fix 限界 / 2 轮封顶 / 落盘前对账 / 单一写者 / dispatch 文件+RECEIPT）；§7 方案乙=worktree（本模式即其具体化） |
| `docs/harness-design.md` | 现行 | 「Deferred Work」明确：**尚无 runner**；无自动模型调用；无脚本化 recorder |
| `docs/model-adapters.md` | 现行 | 各 adapter 命令；codex `-p`=profile；review 用 read-only |
| `scripts/validate-stage.py` | 871 行 | `ALLOWED_STATUSES`、`require_clean_worktree`（pre-review/pre-accept）、`compute_diff_fingerprint`、必需文件硬清单、parallel-mode / dispatch-ready / review-identity 校验 |
| `schemas/review-verdict.schema.json` | 现行 | verdict schema；prose 仍残留 "controller" 字样（cosmetic） |
| `scripts/` 其他 | — | **无** `record-checkpoint`、**无** `prepare-review-2`（本模式需新建） |

## 2. 本 stage 评审轮结果（`reports/agent-runs/2026-07-harness-flow-optimization-v1/`）

| 评审文件 | 实际评审对象 | verdict | 备注 |
|---|---|---|---|
| `reviews/codex-gpt5.md` | ✅ 新 worktree 草案 `10-...draft.md`（DRAFT-1） | REWORK | 9 条实现契约缺口（F1–F9），是 DRAFT-2 的主改动源 |
| `reviews/glm52.md` | ❌ 旧 `00-context-and-proposal.md`（Option A） | REWORK | P0（Option A）/单一写者真空/review-1=Codex —— **DRAFT-1 已从设计解决**；仅横切项仍适用 |
| `reviews/kimi-for-coding.md` | ❌ 旧 `00-context-and-proposal.md` | REWORK | 同上；横切项：validator gate 编入流程、embedded R1–R10 verbatim、终态写者 |
| `reviews/claude-opus4.8.md` | 旧提案 | REWORK | F1–F8，已在转向 DRAFT-1 时吸收 |

结论：**四篇一致认可方向、无 BLOCKED**；真正针对新设计的改动 = codex-gpt5 9 条 + glm/kimi 中仍适用于新设计的横切项。

## 3. 已锁定决策（DEC-2026-07-08-002）——DRAFT-2 的 trial-mode 硬性要求

以下四点为 GPT 与 Opus 4.6 一致意见，用户已拍板，**作为 trial mode 的硬性要求（hard gates），非建议**：

### D1 — task branch 不写顶层 `status.json`
- task branch 只产 **task-local evidence snapshot**；顶层 `status.json` 唯一由 integration branch 的 `prepare-review-2` 写入。
- 采用目录形态：
  ```text
  reports/agent-runs/<stage>/evidence/<task-id>/
    ├── checkpoint.json        # base_sha, head_sha, task_diff_fingerprint, scope, test_status
    ├── 60-test-output.txt     # 该 task 的测试输出
    └── record-checkpoint.log  # 脚本执行日志
  ```
  `checkpoint.json` **不是** `status.json`，仅由 `prepare-review-2` 在集成阶段读取校验。
- 效果：消解 F1（metadata 交集）与 F6（human_decision 位置的一部分）的根因；`prepare-review-2` 的 merge 变纯机械；validator 只在集成分支跑（review-1 不需 validator gate，review-2 需要）。

### D2 — `record-checkpoint` commit 范围 = source/test + task-local evidence 目录
- **允许 commit**：该 task 的 source、test、`evidence/<task-id>/` 目录、implementation report、embedded-review 文件。
- **禁止 commit**：顶层 `status.json`、`70-handoff.md`、对方 task 文件、顶层 `60-test-output.txt`。
- commit message 结构化前缀：`[checkpoint:<task-id>] <summary>`。
- 效果：强化 R6 单一写者按层隔离；简化 rebind 断言（F3）。

### D3 — backend/frontend pathspec 必须在分发前冻结
- pathspec 写入分发前的 `status.json.tasks[].allowed_scope`（集成分支），由 `validate-stage.py --phase dispatch-ready` 校验。
- 首次试运行用简单顶层目录划分（`backend/**` vs `frontend/**`）。
- 效果：解决 F1 的 scope 来源；防实现者事后改 scope；是 R1「不相交」成立的前提。

### D4 — 第一个试运行禁止改 schema / API contract / shared fixture
- 明确列出 forbidden shared paths，作为 trial mode 的 hard gates。
- 若需改 schema/contract → 回退单 owner 串行模式。
- 效果：确保跨任务契约设计期冻结；降低首次试运行风险；写入 §12 试运行选择标准与 R1 加严条件。

### 叠加效果
| 决定 | 消解/简化 |
|---|---|
| D1 task-local snapshot | 消解 F1、F6 根因；validator 只跑集成分支 |
| D2 commit 范围隔离 | 强化 R6；简化 F3 rebind |
| D3 pathspec 冻结 | 解决 F1 scope 来源，dispatch-ready 校验 |
| D4 禁 schema/contract | 强化 R1，降低首跑风险 |

F1/F4/F6 基本消解，F3 大幅简化。**剩余 codex findings（F2 validator 文件映射、F4 immutable-script guard、F5 分支血统、F7 review-1 双 track artifact、F8 单 owner 节、F9 分支命名）+ 横切项仍需在 DRAFT-2 落规格。**

## 4. DRAFT-2 必须覆盖的剩余项（快照锁定，逐条落规格）

- **F2** validator task 模式接受 task-specific 证据路径（或 record-checkpoint 造 canonical 别名）——列入 §待改点。
- **F4** `record-checkpoint`/`prepare-review-2` immutable-script guard：task branch 改动 `AGENTS.md`/`workflows/**`/`registry.yaml`/`scripts/**`/`schemas/**` 即 fail（allowed scope 来自 base 冻结 metadata）。
- **F5** 分支血统：base 为每个 task head 祖先；创建后禁 merge 兄弟分支/main；review-1 用 `base..task_head`。
- **F7** review-1 双 track artifact 路径 + `tasks[].review_1.{verdict,diff_fingerprint}`。
- **F8** 单 owner 节：无 task branch、record-checkpoint 在 `stage/<id>` 跑、不用 prepare-review-2、review-1 仍交叉审。
- **F9** 分支命名/清理/重试（`-r2` 后缀、验收前不 force-delete、abandoned 记录）。
- 横切：人工 dispatch 继承 R9/R10 receipt + raw-output + invalid-JSON attempt 计数归属；embedded pre-review verbatim 引 parallel-mode R1–R10；validator gate 画进流程图；「opposite implementer」改为按 provider 派生；不发明新 status 值（post-review-1 暂停用 `paused`）；rebind hash 与 canonical fingerprint 分离。

## 5. 试运行前置（几家一致，写入 DRAFT-2 §12）

第一个实跑阶段 = **Harness-only enablement stage**（非产品阶段）：先实现两个脚本 + 改 validator + 一个合成 dry-run fixture（两个不相交 toy 分支），验证 5 件事——① metadata 不撞 product 交集 ② task 指纹可重算 ③ product rebind hash 匹配 ④ integration 指纹可重算 ⑤ 任一 review-1 非 ACCEPT 时 prepare-review-2 拦住——**再**跑真实 GLM/Kimi 双 owner。

## Footer

本地北京时间: 2026-07-08 19:20:21 CST
下一步模型: claude（撰写 DRAFT-2）
下一步任务: 按本快照 §3 四项硬要求 + §4 剩余 findings + §5 试运行前置，将
`10-independent-task-branch-mode-draft.md` 修订为 DRAFT-2。
