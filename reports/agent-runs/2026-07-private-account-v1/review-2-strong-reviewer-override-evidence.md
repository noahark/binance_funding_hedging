# Review-2 Strong-Reviewer Disclosure Override — 证据

> 本文件为 stage `2026-07-private-account-v1` review-2 启用 strong-reviewer
> disclosure override 的「unrelated reviewer unavailable」证据，依
> `AGENTS.md` line 181-194（Strong-reviewer disclosure override）与 line 267-269
> （review-2 fallback/override 合法理由）落档。`scripts/validate-stage.py`
> `validate_review_identity` 在 designer-overlap 时要求此证据路径存在。

## review-2 reviewer 身份

- reviewer: **Codex (gpt5.5 / openai)**，`codex exec -s read-only`
- `reviewer_prior_involvement`: **direction_synthesis**
  - Codex 合成并冻结了本 stage 方向基线（`docs/private-account-v1-direction-draft.md`），
    且为方向评审五人组之一、参与用户 8 点问答（见 `status.json.direction_synthesizer` +
    `frozen_inputs.direction_baseline`）。
  - **未**参与实现、修复、breakdown 拆解、stage 设计包撰写（design packet 为 Fable5）。

## 为什么没有 unrelated decision model 可用（design-conflict ineligibility）

`AGENTS.md` line 170-176 要求 review-2 优先 provider-level 隔离 designer /
direction synthesizer / breakdown author；line 267-269 允许在 "design-conflict
ineligibility of the preferred unrelated reviewer" 时启用 override。本 stage
决策模型池中，**每一个** candidate 都有阻断性 involvement：

| candidate model | provider identity | involvement | review-2 资格 |
|---|---|---|---|
| claude_glm (glm-5.2) | zhipu_glm | **Task A implementer**（owner） | ❌ hard-ban（line 151-152，implementer/fix author 禁评审，无 disclosure override） |
| kimi | moonshot_kimi | **Task B implementer**（owner） | ❌ hard-ban（同上） |
| Fable5 (claude-fable-5) | anthropic | **designer + breakdown_author** | ❌ design-conflict ineligibility（line 173-176） |
| Codex (gpt5.5) | openai | **direction_synthesizer** | ⚠️ 唯一非 implementer 的决策模型；direction involvement 经 strong-reviewer override 启用 |

池中**不存在**「既非 implementer、又非 designer/direction/breakdown」的 unrelated
decision model —— 所有非 hard-ban 的 candidate 都因 design/direction involvement
而 design-conflict ineligible。此即 line 267-269 的「design-conflict ineligibility
of the preferred unrelated reviewer」，构成 unrelated reviewer unavailable 的证据
（无 runner-level 失败可记录，因模型池内根本无 unrelated candidate 可跑）。

## override 合规性（line 181-194）

- ✅ 仅适用于 prior direction synthesis 参与（line 183-184）—— 不涉 implementation/fix authorship。
- ✅ verdict 含 `reviewer_prior_involvement=direction_synthesis` + `reviewer_prior_involvement_notes`（见 `review-2-round1.raw-output.md`）。
- ✅ stage status 记录 `fallback_reason` + 本证据文件（line 189）。
- ✅ review-2 prompt（`review-2-stage-by-codex.prompt.md`）将用户批准的方向基线作为 top-level 要求、设计/breakdown 作 reviewed evidence（line 190-192）。
- ✅ Codex 无 code authorship conflict（未写任何 delivery code）→ 不触发 hard-ban（`collect_implementer_identities` 不含 openai）。

## 独立性缓解措施

Codex 本次 final review 未锚定 direction synthesis 结论，独立完成：

- committed raw diff `fce1452..6c1e992` 独立重算 stage 指纹 → 与 `status.json` 一致；
- 后端 147 passed / 前端 self-check 独立复现；
- 独立 findings（3 项 P3，含对 Task A Kimi 隔离偏差的**独立**判定：存在但未实质推翻 ACCEPT）；
- 独立核查 bookkeeper dual_hat 披露（充分）。

## 路由依据

- `status.json.model_routing.review_2`：`codex gpt5.5 first; disclosure
  reviewer_prior_involvement=direction_synthesis+direction_review; strong-reviewer
  override per AGENTS.md; fallback claude per existing rules`
- `AGENTS.md` line 145-149：review-2 用 GPT/Codex first，Claude fallback；quota-exhausted
  或 strong-reviewer override 时启用。
- fallback 路径（claude = Fable5 = designer）同样 design-conflict ineligible，不优于 Codex。

---

本地北京时间: 2026-07-06（bookkeeper 续任会话落档；Codex review-2 完成于 17:35 CST）
作者: bookkeeper (claude_glm)
