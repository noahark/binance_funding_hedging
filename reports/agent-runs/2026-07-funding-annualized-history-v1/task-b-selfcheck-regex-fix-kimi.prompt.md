# Dispatch: Task B Bounded Fix — self-check #11 dead regex (Kimi)

Stage: `2026-07-funding-annualized-history-v1`
Owner/executor: Kimi (`kimi-code/kimi-for-coding`, `moonshot_kimi`) — frontend owner of Task B.
Origin: review-1 Task B verdict = REWORK (fresh claude-glm reviewer), independently
confirmed by review-2 audit (anthropic/claude-opus-4-8). Both preserved under this
stage's evidence path.

---

## RECEIPT BLOCK (fill and return at the top of your raw output)

```text
本地北京时间: <YYYY-MM-DD HH:MM:SS CST>
执行模型: kimi-code/kimi-for-coding
任务: Task B 定界修复 — frontend/self-check.js #11 表头判别死正则
改动文件边界: frontend/self-check.js（仅此一个文件）
自测命令结果: node frontend/self-check.js -> <PASS/FAIL 摘要>
diff.patch 生成: <路径>
结论: <PASS / BLOCKER：原因>
```

---

## IMMUTABLE FIX BODY (do not renegotiate scope)

You are a bounded Task B fix session. Fix exactly ONE defect. Do NOT touch product/UI
code (`frontend/index.html`), backend, schema, fixture values, canonical docs,
`status.json`, or any unrelated file. Do NOT create a git commit. Do NOT invoke another
model. `frontend/self-check.js` is the ONLY file permitted to change.

**Fixed range (unchanged, for reference only):**
`base_sha=744ce5f0b9445a891c1322bcb34e06ce94c83446`,
`head_sha=f9f86bb6bcc2040844ad55f4f85937e85d393e5d`.

**Defect (review-1 Task B P2, confirmed by review-2):**
`frontend/self-check.js` test #11 (around line 441) is meant to assert that
non-annualized table headers (资金费率 / 日费率 / …) do NOT contain `已结算` or `预测`,
while allowing `年化 7D` / `年化 30D` headers (which legitimately carry `已结算` in their
titles). Its regex `/<th[^>]*>([^<]*)\/>th>/g` has tail `/>th>` which can never match a
real closing tag `</th>`. Verified in Node: `matchAll` returns 0 matches against the
rendered `<thead>`, so `headers` is always `[]`, `nonSettledHeaders` always `[]`, `bad`
always `undefined`, and the `throw` never fires — the check prints `[PASS]`
unconditionally, silently removing the AC5 label-discrimination guard. The shipped
product UI is correct; this is a test-integrity defect only.

**Required fix:**
1. Replace the regex so it matches real `<th ...>...</th>` including the title
   attribute, e.g.
   `const headers = [...tableSection.matchAll(/<th[^>]*>[\s\S]*?<\/th>/g)].map(m => m[0]);`
2. Keep the existing `年化 7D` / `年化 30D` exclusion and the `find(bad)` logic.
3. Add a positive assertion that `headers.length` equals the rendered `<th>` count so
   the check can never silently empty out again.

## SUCCESS CRITERIA (all must hold)

1. `node frontend/self-check.js` prints `全部自检通过` and test #11 still logs `[PASS]`
   on the real (correct) headers.
2. Negative proof: temporarily inject `已结算` or `预测` into a non-annualized header
   (e.g. a `资金费率` / `日费率` title) and confirm test #11 now THROWS; then revert the
   injection. Confirm the `headers.length == rendered <th> count` assertion holds.
3. `git diff --check` passes and the diff is limited to `frontend/self-check.js`.
4. `python3 -m pytest backend/tests -q` stays at `244 passed` (do not touch backend;
   only re-run if your diff strays outside the frontend file).

Do NOT turn this into a Task D change (no endpoint fetch, no loading state) and do NOT
address the P3 residual risks (focus-trap, dead close branch, `badgeForRouteClass`
orphan) here.

## CLOSING — how to hand back (paste-first discipline)

- Do NOT commit and do NOT edit `status.json`.
- Generate the reviewer-visible patch:
  `git diff -- frontend/self-check.js > reports/agent-runs/2026-07-funding-annualized-history-v1/task-b-selfcheck-regex-fix-kimi.diff.patch`
- Return your full raw output (with the receipt block filled) so the bookkeeper can land
  it. The bookkeeper will commit the fix on a new Task B range, then dispatch a fresh
  claude-glm Task B re-review before review-2.
- If you cannot run the required commands, STOP and report a BLOCKER with the failure
  class instead of guessing.
