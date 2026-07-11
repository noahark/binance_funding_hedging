# Stage Design Review: 2026-07-auto-review-pipeline-v1 (Fable5)

Status: **DESIGN REVIEW — ACCEPT-with-edits（2 处记录级设计修补 + 2 个 nit，不阻塞 12-development-breakdown 起草）**
Date: 2026-07-11
Reviewer: Claude Fable 5 (anthropic/claude-fable-5)
Reviewed artifacts: `00-task.md` / `10-design.md` / `11-adr.md`（stage-design commit
c38c5a8）、E1/E2 处置（345ba61）、`status.json` / `70-handoff.md` /
`60-test-output.txt`（checkpoint efdd0fb）
独立复核项（非转述核对）：345ba61 与 c38c5a8 原始 diff；冻结 40 表全文逐条
对照；AGENTS.md Hard Gates / `agents/registry.yaml` /
`workflows/templates/stage-delivery.yaml` / `scripts/validate-stage.py` /
`harness-manifest.yaml` 现行内容；validator/JSON/`git diff --check`/锁定词汇
负扫/25 行 traceability 全部本机复跑。

## 1. Verdict

**ACCEPT-with-edits。** E1/E2 两处 intake 修补确认关闭。三份设计文档对冻结
40 表（D1–D12 / P1–P13 / §C / 词汇 / 非目标）的转写忠实，与本仓库 Harness
现行环境（DRAFT-2 基线 + validator + registry）的每一处接口引用都真实存在。
两处记录级修补建议在 breakdown 动笔前或同轮完成；均为补写文字，不重开任何
冻结决策。

## 2. E1/E2 处置核验（关闭）

- **E1 关闭。** `status.json` review_1/review_2 的 `reviewer_prior_involvement`
  已置 `null` 并加 `reviewer_prior_involvement_pending: true`，与我 01 号评审
  建议的两个方案取了合集。已核 validator 兼容性：reviewer 未选定时
  designer-overlap 校验不触发；选定且与 designer 身份重合时 `null` 不在
  `REVIEWER_PRIOR_INVOLVEMENTS` 枚举内、直接 fail-closed
  （validate-stage.py:721-723），机械后盾成立。我建议的"两条 review-2 路线
  并列给操作者"在三处一致落实：00-task Human Gates、10-design Bootstrap 段
  （registry 预留 Gemini 候选 vs disclosure override，二选一显式列出）、
  ADR 决策 11。
- **E2 关闭（含一个 nit，见 §5）。** 00-intake 增补 4 行 Route deviation，
  status.json 同步 `evaluator_route_deviation` 字段，偏差理由（操作者指令 +
  冻结双评审链已定 HIGH，GLM 重分类无信息增量）如实。

## 3. 核对通过项

- **P1 fingerprint 零改动可证。** 10-design §Seal 公式与 AGENTS.md Hard
  Gates、`registry.yaml model_policies.diff_fingerprint`、
  `validate-stage.py compute_diff_fingerprint`（:160-176，含 exclude 仅
  status.json）四处逐字一致；回归测试要求"共享库抽取前后 byte-identical"
  （验收 8）把 canonical 化风险封住。
- **顶层状态兼容宣称成立。** 设计引用的 `paused`、
  `human_escalation_required`、`stage_accepted_waiting_user` 均为
  validator `ALLOWED_STATUSES` 现有成员；`runner_state` 五值为嵌套 substate，
  未新增顶层状态。验收 22 列的 checkpoint / dispatch-ready / pre-review /
  pre-accept 四个 phase 名在 validator 中全部真实存在。
- **registry 接口全部实证。** grok adapter 的
  `optional_review_command`（grok-build + plan mode）、
  `invalid_json_max_attempts_per_model: 2`、
  `future_review_2_fallback_candidates`（google/Gemini 3.1 Pro，validator
  PROVIDER_IDENTITIES 已含 gemini→google 映射）、adapters 预留的
  `invocation_owner: runner` 字段、codex `supports_write: false`——设计引用
  的每个 registry 事实都存在，无凭空接口。
- **冻结表忠实性逐条过。** D1（capture-at-cross-check / assert-at-seal 字节
  等价，无第二指纹字段）、D2（拓扑分裂 + integration unit）、D3（显式
  `required_attempt`，runner 不从 prose 推断——比冻结面更严的合理精化）、
  D4/§C（单账本 3 / auto ≤2 / invalid-JSON 2，authorization 三个数字强制
  相等或封顶）、D5（exclusive worktree + `paused` + mode_flip 证据）、
  D7×D2 修复（parallel tip cross-pool 空集 → `human_escalation_required`，
  即我 41 号评审 F1，正确落进 Review-1 Routing 与转移矩阵）、P3
  （final-and-only schema-valid block + fingerprint 匹配）、P5/P6/P7/P8
  （数字属 stage authorization 数据、无全局默认）、P9（authorization 显式
  `auto_high_end_dispatch_allowed: false`）、P13（receipt 禁字段 +
  untrusted-data 边界）。我在 41 号评审的 F1–F3 与 GPT 的 G1–G6 在设计中
  全部可追溯，无一回退。
- **D2 的 integration-unit 精化正当。** "仅 code-scope 非空才构成 integration
  unit、evidence/status-only 提交不算"是对 40 表的 refine 而非 reopen——
  否则 P5 允许的 verdict-record commit 会让每个 stage 恒多一个空单元；
  Edge Cases 已显式写明。
- **两商 seal 协议自洽。** H_snapshot→算指纹→原子写 status→H_bind 的顺序
  解决了 head_sha 自引用；crash 三分支 fail-closed；"formal reviewer 收
  recorded snapshot range 而非 moving HEAD"与 AGENTS Hard Gates 现行措辞
  对齐。
- **bootstrap 路由合规。** GLM 单一实现 owner + Kimi fresh read-only
  review-1 = 现行 cross-pool 规则；Codex 排除于 core work 与 registry
  `codex_eligible_for_implementation_or_fix: false` 一致；下一步 breakdown
  作者 = Fable5（quota 耗尽后 Opus4.8）正是 registry
  `rotation_defaults.development_breakdown` 的注册路由，非临时指派。
- **机械面本机复跑全 PASS。** `python3 -m json.tool`、
  `validate-stage.py --phase checkpoint`（HEAD efdd0fb，clean tree）、
  `git diff --check`、"formal-1" 负扫（唯一出现处为 60-test-output 描述扫描
  本身的行）、10-design traceability 表 25 行（D1–D12 + P1–P13）计数吻合。
- **manifest 影响面已被验收覆盖。** `harness-manifest.yaml` 的 scripts/docs
  为逐文件列出（schemas/、workflows/ 为整目录），新增 `scripts/tests/`、
  三个新脚本与 `docs/auto-review-pipeline.md` 必须逐项入 manifest——验收 23
  已锁住该要求。

## 4. Minimal edits（2 处，记录级，均为补写文字）

1. **[10-design + 00-task] §D 主路径的 "Re-run blocking"（cross-check 之后、
   seal 之前）在 serial 序列中无落点，且未记录读法选择。** 冻结 40 表内部
   存在松紧差：§D 主图为 `block → cross-check → Re-run blocking → seal`，
   而 serial summary 为 `implement → block → cross-check? → seal_A`（无
   re-block）。设计的 Serial Topology（步骤 3 blocking → 4 cross-check →
   5 seal）取了 summary 读法但未声明；Parallel Topology（cross-check →
   unified blocking → seal）反而天然满足主图。等效性论证其实成立——
   seen-diff bind 的 byte-equality 断言保证 cross-check 前后 code-scope
   逐字节未变，故上一次 blocking 结果对 seal 时代码仍有效——但该论证依赖
   一个未写明的前提：**blocking 检查只读 code-scope，不读 stage evidence
   路径**（cross-check 本身会向 evidence 目录写入 prompt/raw-output/seen
   patch）。修补：在 10-design Serial Topology 加一段显式声明（省略
   re-run blocking 的依据 = bind byte-equality + blocking 仅依赖
   code-scope，并把后者列为 runner/测试的一个校验点），或恢复该步骤。
   不重开决策，但 runner 状态机与测试矩阵会照 10-design 实现，这个隐式
   前提必须显形。
2. **[00-task 验收 24 / 10-design] P11 冻结的 pilot metrics 未转写。**
   40 表 P11 明确冻结了两个 pilot 的评估指标：Grok schema-valid rate、
   escalation shape、RECEIPT completeness。三份设计文档均无 metrics 字样，
   交付物 `docs/auto-review-pipeline.md` 的内容要求里也没有。若不转写，
   验收 24 的 two-pilot gate 在 pilot 阶段将没有判据可执行。修补：在
   00-task 交付物 2（docs 契约）或验收 24 中补一句"文档必须包含 P11 的
   pilot 评估指标与默认翻转前置条件"。

## 5. 非阻塞 nit（2 个）

- **E2 修补的出处措辞。** 00-intake/status.json 写 "registry 默认 complexity
  evaluator 为 Claude-GLM / Registry default is claude_glm"；实际定义在
  `workflows/templates/stage-delivery.yaml` 的 `rotation.complexity_evaluator`
  （provider claude_glm，glm-5.2[1m]），`agents/registry.yaml` 并无该条目。
  事实内核（默认 GLM、本次 Codex 代行、偏差已诚实记录）完全正确，仅出处
  标注不准；下次触碰 00-intake 时顺手改为 "workflow rotation default" 即可。
- **authorization `expires_at: null` 语义未定义。**（null = 永不过期，还是
  必须给值？）"Runner refuses an expired artifact" 的判定需要 schema 写死
  null 语义；建议 breakdown 把它列入 schema 任务的验收点，不必回改设计。

## 6. 对 development breakdown 的前置提示

- 按 registry 注册路由，12-development-breakdown 由 Fable5（本评审方）起草。
  按 AGENTS.md，breakdown 属 review-2 disclosure 意义上的 design
  involvement：anthropic 的先前参与将从"direction patch 进冻结表正文"进一步
  加深到 breakdown 作者。这不改变设计正确性（E1 修补后的 pending 语义正是
  为如实记录而设），但操作者在 review-2 路线二选一时应计入：届时两家高端
  provider 均为双重涉入，registry 预留的 Gemini 独立评审路线相对权重上升。
- 本评审不授权实现或任何模型 dispatch；§4 两处修补为文字补写，可由
  bookkeeper 与 breakdown 同轮落盘，无需回退 stage 状态。

## 7. 结论

设计三件套把冻结 40 表转写成了可实现、可测试、fail-closed 的机械契约，
对现行 Harness 环境的全部引用（状态枚举、phase、fingerprint 公式、adapter
命令、第三决策模型预留）经本机实证无一悬空。完成 §4 两处补写后，进入
12-development-breakdown。

```text
本地北京时间: 2026-07-11 12:15:01 CST
下一步模型: Codex/GPT（bookkeeper，落盘本评审 + §4 两处设计补写）→ Claude Fable 5（12-development-breakdown）
下一步任务: bookkeeper 提交本评审文件并处置 §4 修补；随后 Fable5 起草 development breakdown（冻结 owner/file/test/review 边界，不实现）
```
