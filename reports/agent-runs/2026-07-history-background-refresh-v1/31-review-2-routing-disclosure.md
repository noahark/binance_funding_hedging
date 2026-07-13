# Review-2 Routing Disclosure

## Decision

Review-2（最终审查）拟路由至 Claude Fable5（provider `anthropic`），以 read-only
（只读）`code_reviewer`（代码审查）方式审查已绑定实现范围。

## Strong-Reviewer Override（强审查者披露覆盖）

- Preferred decision reviewer（首选决策审查者）Codex/OpenAI 在本阶段不可用作正式审查：
  当前 Codex 会话是设计作者且由用户授权担任 bookkeeper（台账员）；`AGENTS.md` 明确该
  session 不得实现、修复或签发 formal review verdict（正式审查结论）。这属于首选
  unrelated decision reviewer（无涉入决策审查者）的 design-conflict ineligibility（设计
  冲突不合格）。
- 唯一已注册的 fallback decision provider（回退决策供应商）Claude/Anthropic 与实现/修复
  作者 `zhipu_glm` provider 隔离；但 Anthropic Opus 4.8 在本阶段做过 design review（设计
  审查）并完成 development breakdown（开发拆解）。因此 Claude review-2 必须披露
  `reviewer_prior_involvement="breakdown"`。
- 没有其它已注册、provider-isolated、且未参与本阶段设计的 decision model（决策模型）可供
  review-2。Kimi 是合格的 review-1 交叉审查者，但不在 workflow（工作流）定义的 review-2
  decision-model 路由中。

## Binding

- Stage: `2026-07-history-background-refresh-v1`
- Base: `0db66d2a82c10139523a06af74679e756bd13e5a`
- Reviewed implementation head: `6c9f8f2f8a4e71dc59d1866b0f9acc616104ffbb`
- Diff fingerprint（差异指纹）:
  `6c9f8f2f8a4e71dc59d1866b0f9acc616104ffbb:f81403b21f91b1c7b7a9fbf167f423d02061773920fdee9b51711fa97c3bad96`
- Review-1: Kimi ACCEPT, `30-review-1.verdict.json`（schema-valid）

The final-review prompt（最终审查提示词）must treat user-approved task scope and
product requirements as the authority. Design and breakdown documents are reviewed
evidence, not the top-level authority.

本地北京时间: 2026-07-13 10:03:00 CST
下一步模型: Claude Fable5
下一步任务: 以 strong-reviewer disclosure 对绑定实现执行 read-only review-2
