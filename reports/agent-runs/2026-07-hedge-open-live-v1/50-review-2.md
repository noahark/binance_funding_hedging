# Review-2 Raw Artifact — Whole Stage (Codex/GPT)

Archived by the bookkeeper from the human-operator-returned raw output of the
Codex/GPT (`openai`) final review. Operator-reported local time 2026-07-23
08:12:19 CST. Executor: human operator (dispatch only). Unrelated reviewer (no
design/breakdown/implementation/fix involvement). Content preserved verbatim.

---

终审结论：**REWORK**。发现一处 P1 跨 FE/BE 的 `leg_exposure` 契约漂移，会在单腿
敞口时向操作员错误展示已成交腿与数量。未修改任何文件。

已复现固定指纹一致；前端自检 108 PASS。python 不在 PATH，使用 `.venv/bin/python`
定向运行全部 hedge 测试为 111 passed。后端全套阶段证据记录为 787 passed，但本会话
无法以 PATH 中的指定 python 完成全量复跑。

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-v1/50-review-2.md
本地北京时间: 2026-07-23 08:12:19 CST
下一步模型: Claude-GLM
下一步任务: 按 fix_start_prompt 修复 leg_exposure 冻结接口漂移并重新进入 review

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-open-live-v1",
  "role": "final_reviewer",
  "model": "openai/codex",
  "verdict": "REWORK",
  "diff_fingerprint": "bd01eb52e9ec5464bb9f026f5ce666bc883db441:48b8545d53b607c4ce1f396e0f76e81bc1c95d2cae9147aad695d2933278e22b",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "GPT/Codex did not participate in this stage's design, breakdown, implementation, or prior fixes. Provider isolation from Claude-GLM and Kimi delivery authors holds.",
  "reviewed_artifacts": [
    "workflows/templates/stage-delivery.yaml (review-2 section)",
    "reports/agent-runs/2026-07-hedge-open-live-v1/{00-task,10-design,11-adr,12-development-breakdown,design-inputs,20-implementation,20-implementation-hedge-be,20-implementation-hedge-fe,r4-reconciliation,40-fix-1-hedge-be,30-review-1-hedge-be,30-review-1-hedge-be-round-2,30-review-1-hedge-fe,60-test-output}.md",
    "reports/api-samples/2026-07-hedge-open-live-v1/{websocket-bookticker-recon,order-endpoints-filters-recon}.md",
    "git diff 6639b002..bd01eb52; fingerprint independently recomputed and matched",
    "backend/hedge_open_tasks/{domain,executor,service,store,scheduler}.py","backend/app/server.py","backend/tests/test_hedge_*.py","frontend/{index.html,self-check.js}","schemas/review-verdict.schema.json",
    "independent runs: node frontend/self-check.js -> 108 PASS; .venv/bin/python -m pytest backend/tests/test_hedge_*.py -q -> 111 passed"
  ],
  "findings": [
    {
      "severity": "P1",
      "title": "Single-leg exposure Task JSON drifts from the frozen FE/BE contract and misstates the operator safety alert",
      "file": "backend/hedge_open_tasks/domain.py",
      "line": 556,
      "evidence": "Frozen breakdown §3.2 requires leg_exposure:null|{leg,qty,price,ts}. Backend emits {filled_leg,spot,perp,ts} in build_leg_exposure (domain.py:556-563), and the HTTP test locks that divergent shape with doc['leg_exposure']['filled_leg'] (test_hedge_api.py:290-300). The frontend instead reads task.leg_exposure.leg/qty/price (index.html:3599-3601), as does its mock fixture (self-check.js:3664-3665).",
      "impact": "For an injected or future real spot-only fill, the UI treats missing leg as the perp branch and displays an undefined quantity/price rather than the actual exposure. Safety-critical operator-information seam: the task is paused correctly, but the alert for human decisioning is materially wrong.",
      "recommendation": "Restore one frozen representation across backend, frontend, and tests. Do not silently amend the API contract. Add an end-to-end HTTP-level assertion for the Task leg_exposure shape and a frontend fixture derived from that exact shape; cover both spot-only and perp-only exposure. If quantity-mismatch needs a richer representation than §3.2 permits, stop for bookkeeper/user contract handling before extending the frozen schema."
    }
  ],
  "required_fixes": [
    "F-007: Align Task.leg_exposure emitted by the backend with frozen §3.2 and frontend consumption; add regression tests proving the HTTP task response renders the correct filled leg, quantity, and price for both single-leg directions."
  ],
  "residual_risks": [
    "Recorded review-1 follow-ups F-003 through F-006 remain deferred to the live-executor round; record transport still has no real order POST path.",
    "The prompt's literal python command is not runnable in this environment (python absent from PATH); the project virtualenv ran the focused hedge suite (111 passed)."
  ],
  "fix_start_prompt": "See task-hedge-be-fix-2.prompt.md (bookkeeper materialized the reviewer's fix_start_prompt into the dispatch packet).",
  "next_action": "fix"
}
```
