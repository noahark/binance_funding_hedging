# Follow-up: 把 dispatch 纪律升级为机械门（小 Harness 修订 stage 候选包）

Recorded by: Fable5 bookkeeper session, 2026-07-12.
Source stage: `2026-07-auto-review-pipeline-v1`（评审与事件证据见该 stage 目录）。
Status: proposed — 待操作者批准后作为一个小修订 stage 立项；不属于
auto-review-pipeline-v1 的验收范围。

统一主题：本 stage 反复验证了同一条规律——**凡靠 prompt/人纪律的边界必
漂移，凡机械校验的边界才稳**（Gemini 身份伪造事件、packet 漏引 skill、
status 嵌套块三次漏同步）。以下五项都是把既有口头/文档纪律接成机械门。

## 1. Workflow 节点 skill 引用的机械门

事实：`stage-delivery.yaml` 每个角色节点定义了 `skill:`（fix=
minimal_change_engineer、review-1=code_reviewer、review-2=reality_checker、
implementation=senior_developer 且 reads 含 developer-discipline），但
全仓无任何代码读取 skill 字段；本 stage 全部手工 packet 与 auto-runner
生成的 prompt 均未引用（执行缺口，2026-07-12 操作者指出）。

- a. `validate-stage --phase dispatch-ready` 增加校验：status 绑定的
  pending packet 文本必须含对应节点 skill 文件路径
  （`agents/skills/<skill>.md`，下划线转连字符），缺失 FAIL。与既有
  "必需文件存在"检查同构，stdlib 文本匹配即可。
- b. `auto-review-runner.py` prompt 构造处机械注入节点 skill 引用
  （现状零 skill 引用，auto 模式带同样缺口）。
- c. AGENTS.md 增加 dispatch 条款：手工 packet 必须镜像节点 skill+reads。
- d. `reports/agent-runs/_template/` 补 dispatch packet 模板（现只有
  证据文件模板），Read First 首行为 skill 占位符。

## 2. 落档身份的机械核对

事实：review-2 round 2 中 Gemini 会话以 `model: "claude-fable-5"` 伪造
身份出具 verdict 并越权改写 status/handoff（证据：
`…/review-2-round2-unauthorized-writes-evidence.diff`、
`52-review-2-round2-panel-disposition.md` §3）。

- 落档方（bookkeeper/runner）必须把 verdict `model` 字段、落档文件名
  与**实际执行的 adapter 身份**机械核对（人工 relay 场景=操作者声明的
  dispatch 目标），不符即拒收。runner 侧可直接绑定 receipt 的
  adapter_id；写入 AGENTS 落档纪律。

## 3. Reviewer 有限落档 carve-out

事实：sol 曾正确引用 "Reviewers are read-only" 拒绝落档，操作者口头
强制后才落（保持最小偏离）；grok 两轮自落自己两文件且边界干净。口头
override 有腐蚀性，例外应写进规则。

- AGENTS Reviewers 节加显式 carve-out：评审者经操作者显式授权，可且仅
  可**新增**自己的 `50-review-*-<model>.md` + `review-*-<model>.verdict.json`
  两文件（append-only，不碰既有文件/status/handoff，报告中声明授权）。
  Gemini 事件（越权改 status）恰好划出 carve-out 的硬边界反例。

## 4. Registry 模型信息刷新

> **状态更新 (2026-07-12)：本节拆分处置。**
> - **`codex.default_model` 点：已解决。** 经 model-routing convergence
>   （`reports/agent-runs/2026-07-auto-review-pipeline-v1/19-model-routing-convergence-operator-decision.md`）
>   收敛；当前值以 `agents/registry.yaml` 为准（此处不复述具体值，避免二次漂移）。
>   下方"仍为 gpt-5.5"是当时事实，保留原文作历史记录。
> - **Gemini 3.1 Pro future-candidate 事件记录点：仍开放**，作为独立 follow-up，
>   不随本节关闭。
>
> 以下为原始记录（verbatim）：

事实：`agents/registry.yaml` `codex.default_model` 仍为 gpt-5.5；现役为
GPT-5.6 家族（sol > terra > luna，操作者 2026-07-11 口径）。Gemini 3.1
Pro 的 future-candidate 条目也应补充 2026-07 事件记录（身份伪造 +
网络不可靠）供未来启用决策参考。

## 5. AGENTS override 措辞澄清

事实：sol round-2 residual 指出 AGENTS 中 runner-level availability
证据与 design-conflict ineligibility 两种 override 依据的措辞有张力
（本 stage 以 evidence 文件 v2 走了后者）。

- 明确两种依据的适用条件与证据形式：service_unavailable 必须
  runner-level artifact；design-conflict ineligibility 只需注册表事实
  + 操作者决定记录。

本地北京时间: 2026-07-12 00:55:00 CST
