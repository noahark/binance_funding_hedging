# Codex MILESTONE 方向合成裁定 — Phase 2 direction (DRAFT-2.1)

Provenance: GPT/Codex 对 `docs/phase2-direction-draft.md` DRAFT-2.1
（commit `abbd2e6`）的方向合成结论，用户于 2026-07-04 逐字转达。
Disposition: ACCEPT-FREEZE → 文档冻结为 Phase 2 方向基线（FROZEN），
等待用户批准进入 stage design。

---

gpt合成结论：ACCEPT-FREEZE

1. GPT/Codex round-1 required fixes 已落实。DRAFT-2.1 已把 /
   sapi 降级为 classic_margin_reference，账户级可借性以 /papi/
   v1/margin/maxBorrowable 为准；安全门补齐单一签名出口、GET-
   only、exact-path 白名单、直连守卫、审计日志、脱敏与降级测
   试；negative_funding_status 保持零改动，新增
   borrow_validation 独立块；端点矩阵与实抓冻结被放入 H_intake
   硬门；前端私有展示已剥离，本轮只做公开字段展示。

2. claude_glm / kimi27 的 P1/P2 吸收完整。GLM 的端点族 P1 已由
   Gemini + Fable5 对 llms-full.txt 原文核验否定，并在文档中记
   录 dissent；其余 P2 已吸收。Kimi 的安全、实抓、VIP0、
   MILESTONE、三态、脱敏、contract v0.2 等要求均已落入正文或明
   确 dissent。Kimi 的枚举扩展建议被多数意见覆盖为"独立块 + 枚
   举零改动"，记录方式可接受。

3. 端点族证据链成立。gemini-endpoint-research.md 明确给出 /
   papi 属 Portfolio Margin/统一账户端点族，PM Pro 才对应"统一
   账户专业版"；DRAFT-2.1 同时保留 H_intake 持 key 只读实抓作
   为运行时确认。设计层可冻结，执行层仍 fail-closed。

4. §7 MILESTONE 等效履行接受。严格说这不是标准 registered
   direction panel 形态，但本轮已有三方独立评审、Gemini 端点考
   证、Fable5 修订、Codex 最终合成，并且用户显式要求采用该等效
   流程。此裁定仅适用于本 milestone，不自动替代以后 MILESTONE
   的 registered panel 规则。

结论：docs/phase2-direction-draft.md DRAFT-2.1 冻结为 Phase 2
方向基线。等待用户批准后，可进入 stage design。stage design 时
必须把 H_intake discovery、端点矩阵、脱敏样本、contract v0.2、
parallel-mode dispatch packet 和 review gates 一次性写清。
