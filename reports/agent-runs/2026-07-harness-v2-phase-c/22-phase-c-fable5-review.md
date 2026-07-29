# Harness v2 阶段 C 独立评审（Fable5）

- 评审任务：harness-v2-phase-c-review（dispatch：21-phase-c-fable5-review.dispatch.md，status_revision 2）
- 固定范围：a15368c8ff9c0989968100e874e9ecb799a01c7d..0412ba16e2fa5003c087be9c4a824cb4e022d4b4，分支 codex/harness-v2-rebuild
- 评审身份说明：Fable5 参与过此前的设计评审与阶段 B 评审，但未参与阶段 C 交付的编写，符合"不自审"要求。本次为只读评审，未修改、未提交、未推送任何仓库文件。
- 出具说明：2026-07-29 首次评审因评审终端上下文耗尽，完整原文未能送达；本文为按同一固定范围重新校验后重新出具的正式原文，结论与当日一致。

## 实际效果（先说结论）

阶段 C 把 v2 的运行时路径补成了一条自洽的闭环：ACTIVE.json → status.json → dispatch → roles.md → skill，全程不再需要读任何 v1 的 workflow/registry/schema 文件。阶段 B 评审留下的两条建议都已修复。v1 旧集群按计划冻结未删。交付严格停留在 Harness 文档和 stage JSON 内，没碰业务代码、没碰 main、没推送、没有实盘动作。

结论：ACCEPT。零必须修改项。

## 十个评审问题逐条回答

1. 阶段 B 两条建议是否修复且未削弱入口契约？ 是。PROJECT_STATE.md 的证据指针已钉死到历史基线（ACTIVE.json at commit 5c6ac65），不再指向已被清空的当前文件；AGENTS.md 启动措辞 disclose 已改为 load。AGENTS.md 仍为 153 行（120–180 区间内）、十章结构完整，入口契约未变弱。
2. ACTIVE/status/dispatch/roles/TASK_RESULT 是否构成一条连贯的恢复与交接路径？ 是。ACTIVE.json 单字段指向 2026-07-harness-v2-phase-c；status.json（delivery_sha 处 revision 1，评审 dispatch 对应 revision 2）与 dispatch 的 status_revision 对得上；roles.md 新增的 "Minimal State And Dispatch Shape" 提供了可拷贝的 status 模板和 dispatch 六要素（Identity/Goal/Allowed Files/Inputs/Acceptance Checks/Stop），一个新会话仅凭这条链即可恢复。
3. 十二个 status 字段是否充分且自洽，尤其 ledger_sha？ 是。实测 delivery_sha 处 status.json 恰好 12 个顶层字段。ledger_sha 定义为"最后一次已验证提交的基线，不试图指向包含自身的提交"——刻意非自指，规避了 v1 evidence_sha256 死锁；本 stage 内已实际演练（a15368c 被后续提交记录）。delivery_sha 固定不随 HEAD 移动，评审锚点成立。
4. 实现者/评审者是否还可能经可达的 discipline/skill 文件被拉回 v1 语义？ 不会。我在 delivery_sha 上独立 grep 了 fix_start_prompt、review-verdict.schema、stage-delivery.yaml、registry.yaml、70-handoff、Session ID：命中仅在 agents/registry.yaml（冻结的旧集群自身，dispatch 明确排除）和 agents/skills/UPSTREAM.md（vendored 来源说明，非角色路由文件，见建议修改）。所有角色命名的 skill 与 developer-discipline.md 的权威链均已改为 "AGENTS.md + 有效 dispatch + 当前 status.json"。
5. 评审类 skill 是否保持只读并维持最小 ACCEPT|REWORK 闭合？ 是。code-reviewer / reality-checker / security-reviewer 均为只读，要求以 [TASK_RESULT v2] 收尾并给出 verdict: ACCEPT | REWORK；REWORK 必须附 findings_path 与 fix_requirements_path；证据缺失时 outcome: blocked、永不 ACCEPT。complexity-evaluator 缩为 LOW_RISK|HIGH_RISK，direction-panel 路由已退役。
6. docs/model-adapters.md 是否正确移出 Human 启动路径？ 是。已从 AGENTS.md 的启动文件表中移除；模型启动指令归入人工投递的 dispatch packet，符合 Human 边界（Human 不读技术文档）。
7. 推迟到阶段 D 后再整体删除旧集群是否更安全？ 是，且是正确选择。旧集群当前对 v2 路径不可达但仍被 main 上的 v1 stage 引用；部分删除会制造一个既非 v1 可用、又非 v2 干净的中间态。整体冻结→演练证明零读取→一次性删除，是可审计的最小方案。
8. 验证是否正确以 Git 而非 v1 叙事状态作为 main 合并权威？ 是，且这一立场当场被现实验证：20-phase-c-validation.md 在 15:42:47 检查时 main 为 05ee1b9、叙事声称已合并——validation 正确拒绝采信叙事。我独立复核的新事实：main 现已前进到 7180f61，且 git merge-base --is-ancestor 证明其包含 3113a5d（hedge-order-truth-v1 的正式合并提交）。即 status.json 中的 phase_e blocker 所述前置条件现已被 Git 证明满足，应由 Stage Recorder 按新事实更新（这是事实更新，不是交付缺陷）。
9. 交付是否停留在 Harness 文件内？ 是。固定范围 diff 共 17 个文件、+228/−60 行，全部为 AGENTS.md、PROJECT_STATE.md、agents/ 下文档与 skill、ACTIVE.json、phase-c stage 目录。无业务源码、无测试、无 main、无推送、无部署。git diff --check 通过。
10. 是否存在无当前执行需求支撑的新结构？ 无。新增内容（roles.md 的最小状态/dispatch 模板、status.json 本体、dispatch 文件）都直接服务于自举演练；未见投机性抽象。

## 分类清单

### 必须修改

无。

### 建议修改

1. status.json 的 phase_e blocker 已过时：main 已前进到 7180f61 并包含 3113a5d（order-truth 正式合并）。建议 Stage Recorder 在下一次状态更新中按 Git 事实改写该 blocker，并可着手"合最新 main 入 v2 分支→重检兼容"这一步。
2. agents/skills/UPSTREAM.md 残留 v1 措辞：仍引用 agents/registry.yaml 的 source: local 与"schema-valid JSON"收尾要求。它是 vendored 来源说明、不在任何角色路由上，故非操作性依赖、不阻塞验收；建议在阶段 D/E 删除旧集群的同一提交中顺带更新，避免死链。

### 可接受风险

1. 单次终审而非双审：本交付不触碰资金/下单/闸门，属 LOW_RISK，dispatch 已记录一次独立终审的理由，阶段 D 另有真实演练兜底。可接受。
2. token 预算仍为字节估算（11683 bytes ≈ 2.9K tokens）：真实模型上下文测量已明确推迟到阶段 D。可接受。
3. 旧集群冻结期间的双轨并存：v1 stage 在 main 上仍可引用旧集群，v2 分支上二者共存但互不可达。窗口期短且有明确删除计划。可接受。

[TASK_RESULT v2]
task_id: harness-v2-phase-c-review
outcome: completed
summary: 阶段 C 使 v2 运行时路径自洽闭环：两条阶段 B 建议已修复，12 字段 status 链自举成立，v1 语义在可达文件零操作性残留，评审 skill 只读且 ACCEPT|REWORK 闭合，交付未越出 Harness 文件。零必改项；phase_e blocker 需按 Git 新事实（main=7180f61 含 3113a5d）更新。
artifacts:
- reports/agent-runs/2026-07-harness-v2-phase-c/22-phase-c-fable5-review.md
checks:
- git diff a15368c8ff9c0989968100e874e9ecb799a01c7d..0412ba16e2fa5003c087be9c4a824cb4e022d4b4: pass
blockers:
- none
verdict: ACCEPT
findings_path: reports/agent-runs/2026-07-harness-v2-phase-c/22-phase-c-fable5-review.md
fix_requirements_path: none
[/TASK_RESULT]
