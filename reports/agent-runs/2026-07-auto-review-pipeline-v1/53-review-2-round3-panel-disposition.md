# Review-2 Round 3 Parallel Panel — Bookkeeper Disposition (Fable5)

Date: 2026-07-12
Context: 操作者对 review-2 round 3（全 stage `a385c7a..a057d06`，指纹
`a057d06…:cd68035…`）并行分发三个会话，均经操作者显式授权自落各自两份
新文件（packet carve-out 条款；边界核验全部干净：恰好 6 个新增文件，
零既有文件触碰，无 commit）。操作者本轮**未指定 record**。

## 1. Panel 一览

| 评审者 | verdict | findings | 规则地位 |
|---|---|---|---|
| gpt-5-codex（openai；操作者声明 dispatch 目标=gpt-5.6-sol high） | **REWORK** | 1×P1（wall-clock 越期后仍产生 seal commits，附真实探针） | 注册决策模型轨道；披露合规；含完整 fix_start_prompt；**P1 经 bookkeeper 独立复现坐实（§3）** |
| claude-opus-4-8（anthropic） | ACCEPT | 2×P3（测试/文档卫生，自评不阻塞） | 注册决策模型轨道；dual-hat 风险显式评估+独立重跑；2×P3 经 bookkeeper 核验坐实（§4） |
| grok-4.5（xai） | ACCEPT | 0 findings，7 residuals | advisory（非注册决策模型；direction_synthesis 如实披露；与前两轮一致） |

三份指纹均与 stage 指纹逐字符一致；三份 verdict 均过 schema
Draft202012 校验；三份身份均如实（无 round-2 式伪造事件）。

## 2. 身份核对注记（gpt-5-codex）

操作者声明本轮 OpenAI 会话为 **gpt-5.6-sol (high)**；落档自报
`model: "gpt-5-codex"`（Codex CLI 产品线 slug）。Provider 身份一致
（openai/Codex），`reviewer_prior_involvement: "design"` 披露与 sol
round-1/round-2 记录一致，报告并主动声明"本会话真实标识"。判定：
**slug 级差异，非身份伪造**（未冒充他方、未借用他人身份记账）——与
round-2 Gemini 事件（冒充 claude-fable-5）有本质区别。落档文件名保留
自报 slug；本节记录操作者声明与自报 slug 的对应关系。后续引用以
"sol round-3（自报 gpt-5-codex）"消歧。

## 3. sol P1 独立复现（CONFIRMED）

**Finding**：`_check_wall_clock`（auto-review-runner.py:734）仅在四类
adapter 调用前被调（:1343/:1519/:1657/:1840）；`_node_seal`（:1564）传给
stage-seal 的 commit_guard 仅含 `_check_authorization_expiry`。wall-clock
预算在 adapter 返回后、blocking 后、seal 两个 commit 前均无检查点。

**Bookkeeper 探针**（真实 temp repo + 真实 stage-seal 模块 + 注入时钟；
完整输出在 60-test-output.txt）：`wall_clock_seconds=1`，deadline 记录为
`12:00:01Z`；implementation invoker 内把时钟推进到 `12:00:02`（越期）；
`unit_authors=("kimi","claude_glm")` 覆盖 SERIAL_FALLBACK_POOL 使
cross-check 走 skip 路径（零 model call、零检查点）；blocking 返回 0。
结果：**`git rev-list --count` 3→5（H_snapshot + H_bind 均已创建）、
`snapshot_commit`/`diff_fingerprint` 均已绑定**，runner 直到下一个
model-call 检查点（review 前 :1657）才抛 timeout escalation——副作用
先于 escalation 发生。与 sol 探针描述逐项一致。

**定性**：违反 00-task 验收 17（"call-count and wall-clock limits
**fail closed**"）与冻结 P8（超限→escalation）。这是 FX2 的姊妹缺陷：
round-2 P1#2 与其修复规格（FX2）只覆盖 authorization `expires_at`
guard，wall-clock 是同一 commit-guard 面上的另一时间维度——规格深度
不足的下一层，非 FX1–FX7 的回归或修复内缺陷。**P1 CONFIRMED，
required。**

## 4. opus 2×P3 核验（均坐实，非 required）

1. **重名测试遮蔽**（test_auto_review_runner.py:2027/:2035）：
   `test_max_stage_rework_divergence_fails_closed` 定义两次，Python 仅保
   留第二个（schema-level 版本），第一个永不运行（类实跑 7 测试，
   bookkeeper verbose 复核一致）。且被遮蔽者断言方向本身有误
   （auth=99 会先被 schema const 拒为 authorization_invalid，到不了
   budget_mismatch）。opus 指出的**可达**分支是反方向：auth=3（schema
   合法）+ live status ≠3 → `budget_mismatch`（:1021-1023）——该方向
   无测试覆盖，但生产分支存在且同 loop 的 `max_auto_code_changes` 有
   全覆盖。**这一分析同时精化了 GLM FX6 阻塞点 3 的表述**（"runtime
   budget_mismatch 分支对该字段不可达"仅对 auth 侧成立；status 侧漂移
   可达）——裁定结论不变（ACCEPTED，schema 冻结 auth 侧），理由修正
   入档。bookkeeper 与 Kimi 复验均漏此点，如实记录。
2. **过期 docstring**（auto-review-runner.py:1113）：
   `_acquire_runner_lock` docstring 仍称 "A held lock is a recoverable
   preflight failure (awaiting_human + paused)"，与 FX4 零写 lock_busy
   行为矛盾。文档级。

两项均 P3 卫生项，随 escalation 处置一并进后续修复清单（若开）或
follow-up；不改变各自 verdict。

## 5. 深度差分析（ACCEPT×2 vs REWORK×1）

opus 与 grok 的 ACCEPT 建立在"round-2 findings 证据关闭 + FX1–FX7 无
新缺陷 + 验收对照"之上——两者对验收 17 均未构造 wall-clock 越期探针
（opus 的独立重跑覆盖 FX 面；grok 的探针覆盖 shell/路径面）。sol 的
REWORK 来自对验收 17 的对抗性探针。三者无事实矛盾——**深度差**，与
round-2（grok ACCEPT vs sol 探针 REWORK）同构。P1 经 bookkeeper 独立
复现后，fail-closed 原则下该 finding 的存在独立于 record 指定：坐实的
required P1 不能带进 accepted（round-2 处置 §2 同一原则）。

## 6. 处置

1. **P1 CONFIRMED + rework 账本 3/3 已耗尽** → 依 round-3 packet、
   status、handoff 三处预告的终格规则：**status →
   `human_escalation_required`**。该状态是"自动修复轮耗尽、处置权移交
   人类"的正式移交，不是 stage 失败判定。
2. 后续路径由操作者决定，选项（bookkeeper 梳理，非建议排序）：
   a. **授权新的有界人工修复处置**：sol verdict 内含完整
      `fix_start_prompt`（明确声明需人工显式批准才可用，建议 writable
      set = runner + runner tests，必要时申请 seal 两文件）；修后需
      新证据 commit → review-1 → 全 stage review-2；
   b. **操作者行使最终验收权**：知情接受 P1 为 residual（wall-clock
      仅越期约 1 个节点窗、最终仍会 escalation、且 auto pipeline 本
      stage default-off 未启用）并推进 stage 处置——该决定权在人，
      bookkeeper 仅记录；
   c. 其他（缩范围、abandon 等）。
3. opus 2×P3、round-3 packet"验收 1–29"笔误（实为 1–28，sol residual
   指出，bookkeeper 起草失误如实认领）、AGENTS 措辞类 residual → 并入
   follow-up 清单（`reports/follow-ups/2026-07-harness-mechanical-gates.md`
   已有同族条目，escalation 处置时一并考虑）。
4. 三份评审 verbatim 落档；`review_2.round3` 记录三份 + P1 复现 +
   终格应用；`next_action` = 操作者决定 escalation 处置。

本地北京时间: 2026-07-12 10:05:00 CST
下一步模型: human operator（escalation 处置决定）
下一步任务: 选择 §6.2 路径之一；若开新修复处置，bookkeeper 依 sol fix_start_prompt 冻结新 packet（需操作者显式授权，不占已耗尽的自动账本）
