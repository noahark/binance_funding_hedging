# Review-1 — Task A（backend）— 2026-07-phase2-borrow-sort-v1

## 元信息

- reviewer：Kimi（fresh 只读会话 `session_bfdbafa6-aa77-4fbe-a7d6-16d94980d99e`）
- role：`first_reviewer`（schema 合规——见核实注记 #2）
- model：kimi
- verdict：**REWORK**
- reviewer_prior_involvement：`none`（fresh 会话，与实现/设计/嵌入预审无关联）
- diff_fingerprint：`cc25148aa7924e7bb89364f4bba7c8fe978e91f9:9dc905d56fd003b1b5ebfa31cdebedd363b49f57ddd488b5bef85ac73f3fcb3a`
  （与 status.json 记载一致）
- completed_at：2026-07-04 23:40 CST（approx；Kimi session 刚结束）
- raw output：`30-review-1-backend.raw-output.md`（1844 行）

## findings（2）

- **P1 — fundingInfo live failure 不降级**（`backend/adapters/binance_public.py:90`）：
  `_fetch_live` 第 98 行 `_http_get("/fapi/v1/fundingInfo")` 无 try/except，
  `_http_get`（第 47-50 行）`urlopen`+`json.loads` 零捕获 → live 模式
  fundingInfo 任何失败 propagate → snapshot 崩溃（503），违反 design §2
  E1「缺省全 8h + warning」降级契约。
- **P2 — validate-stage worktree-clean**（stage dir 未追踪 review artifacts）：
  review-1 dispatch + raw-output 未 commit → pre-review/pre-accept
  worktree-clean 失败。

## bookkeeper 独立核实（CLAUDE.md「不信摘要」）

1. **P1 finding 成立** ✅：design §2 第 72 行 E1 失败模式 = 「缺省全 8h +
   warning」；§3 第 212 行「fundingInfo → 全 8h 默认…测试断言不崩溃」。
   实现 `_fetch_live` 第 98 行确无 try/except；`_http_get` 第 47-50 行
   urlopen 零捕获。offline 分支（第 76 行空 dict）降级正确，**live 分支
   漏降级**。Kimi finding 正确，Task A 实现缺口成立。
2. **role=first_reviewer schema 合规** ✅：`schemas/review-verdict.schema.json`
   第 47 行枚举 = `{designer_review, first_reviewer, final_reviewer,
   reality_checker}`，**无 second_reviewer**。模板 T1/T2 写
   `role=second_reviewer` 是 R1 预写笔误（不在 schema）。Kimi 自主选
   first_reviewer：在枚举内、语义正确（review-1 = 第一道正式评审门）。
   模板 bug 待 mode doc 修订，**非 reviewer 不合规**。
3. **P2 worktree-clean 成立** ✅：review artifacts 未 commit 属实，是
   bookkeeper 处置项（commit review evidence 分组落档），**非产品代码
   fix**；不计入 rework_count 的产品 fix。
4. **fingerprint 匹配** ✅：verdict diff_fingerprint 与 status.json 一致。

## next_action

- verdict=REWORK，next_action=`fix`。进入 fixing（Task A implementer
  dual-hat = claude_glm；rework_count=1）。
- 产品 fix 范围（P1）：`backend/adapters/binance_public.py`（live fundingInfo
  try/except → 空 dict + warning）+ `backend/services/snapshot_service.py`
  /`backend/domain/snapshot.py`（warning 传播进 `snapshot.warnings`）+
  `backend/tests/test_phase2_borrow_sort.py`（确定性降级测试：monkeypatch
  urlopen raise HTTPError for fundingInfo only，断言全 8h + warning）+
  `20-implementation-backend.md` fix note。
- P2 由 bookkeeper 处置（commit review evidence），非实现终端 fix。
- fix 后重跑 pytest（≥96 passed）+ self-check + 重算 fingerprint + review-1
  round 2。
- T2（frontend）verdict 待（并行 running）。

## verdict JSON（schema 合规，verbatim from raw-output 1784-1842）

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-phase2-borrow-sort-v1",
  "role": "first_reviewer",
  "model": "kimi",
  "verdict": "REWORK",
  "diff_fingerprint": "cc25148aa7924e7bb89364f4bba7c8fe978e91f9:9dc905d56fd003b1b5ebfa31cdebedd363b49f57ddd488b5bef85ac73f3fcb3a",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "Fresh read-only Kimi session; no prior design, implementation, fix, or embedded pre-review involvement for Task A.",
  "reviewed_artifacts": [
    "backend/adapters/binance_public.py",
    "backend/config.py",
    "backend/domain/snapshot.py",
    "backend/services/private_client.py",
    "backend/services/snapshot_service.py",
    "backend/tests/test_private_client.py",
    "backend/tests/test_phase2_borrow_sort.py",
    "schemas/api/public-market/snapshot.schema.json",
    "docs/api/public-market-contract.md",
    "reports/agent-runs/2026-07-phase2-borrow-sort-v1/10-design.md",
    "reports/agent-runs/2026-07-phase2-borrow-sort-v1/11-adr.md",
    "reports/agent-runs/2026-07-phase2-borrow-sort-v1/60-test-output.txt",
    "reports/api-samples/2026-07-phase2-borrow-sort-v1/20260704T133406Z/evidence-index.md"
  ],
  "findings": [
    {
      "severity": "P1",
      "title": "fundingInfo live failure does not fall back to 8h + warning",
      "file": "backend/adapters/binance_public.py",
      "line": 90,
      "evidence": "10-design.md §2 E1 failure mode requires default 8h + warning; _fetch_live calls _http_get for /fapi/v1/fundingInfo without try/except, so any HTTP/network error propagates and breaks snapshot build instead of degrading.",
      "impact": "Public fundingInfo outage causes entire snapshot service to fail with 503, violating the design's degradation contract.",
      "recommendation": "Wrap the fundingInfo call in try/except in _fetch_live, return empty funding_interval_by_sym on failure, and surface a warning in snapshot.warnings via SnapshotService."
    },
    {
      "severity": "P2",
      "title": "validate-stage.py fails due to untracked review-1 artifacts in stage dir",
      "file": "reports/agent-runs/2026-07-phase2-borrow-sort-v1/",
      "line": null,
      "evidence": "scripts/validate-stage.py --phase pre-review reports ?? review-1-task-a-by-kimi.prompt.md, review-1-task-b-by-glm.prompt.md, 30-review-1-backend.raw-output.md, 30-review-1-frontend.raw-output.md as uncommitted changes.",
      "impact": "The pre-accept validator gate will fail even though the product code diff is committed and the fingerprint matches.",
      "recommendation": "Bookkeeper should commit these review artifacts separately, add them to .gitignore, or move them outside the stage evidence dir before running validate-stage.py pre-accept."
    }
  ],
  "required_fixes": [
    "Implement E1 failure fallback in backend/adapters/binance_public.py: if GET /fapi/v1/fundingInfo fails, return empty funding_interval_by_sym so all rows default to 8h.",
    "Propagate a fundingInfo warning into snapshot.warnings (via SnapshotService or assemble_snapshot) when the fallback is triggered.",
    "Add a deterministic test in backend/tests/test_phase2_borrow_sort.py that monkey-patches urllib.request.urlopen to raise HTTPError for fundingInfo only, asserts all rows have funding_interval_hours==8, and asserts snapshot.warnings contains a fundingInfo/default-8h warning.",
    "Ensure all existing 95 tests continue to pass; update 20-implementation-backend.md with the fix note."
  ],
  "residual_risks": [
    "bounded portfolio strategy leaves portfolio_account null for all rows in current market conditions; this is a design-layer observation (ADR-5 DEFERRED), not an implementation defect.",
    "validate-stage.py worktree-clean check may reject the stage if untracked review artifacts remain in reports/agent-runs/2026-07-phase2-borrow-sort-v1/."
  ],
  "fix_start_prompt": "You are the Task A fix implementer (claude_glm) for stage 2026-07-phase2-borrow-sort-v1.\n\nRequired fix:\n- Implement the E1 failure mode specified in reports/agent-runs/2026-07-phase2-borrow-sort-v1/10-design.md §2: if GET /fapi/v1/fundingInfo fails in backend/adapters/binance_public.py, the snapshot must degrade to funding_interval_hours=8 for all rows and include a warning in snapshot.warnings, instead of propagating an exception.\n- Add/update deterministic tests in backend/tests/test_phase2_borrow_sort.py covering live-mode fundingInfo failure fallback (e.g., monkeypatch urllib.request.urlopen to raise HTTPError for fundingInfo only, assert all rows have funding_interval_hours==8 and snapshot.warnings contains a warning mentioning fundingInfo/default 8h). Keep existing tests passing.\n\nFile boundaries:\n- Allowed: backend/adapters/binance_public.py, backend/services/snapshot_service.py, backend/domain/snapshot.py, backend/tests/test_phase2_borrow_sort.py, reports/agent-runs/2026-07-phase2-borrow-sort-v1/20-implementation-backend.md (update after fix).\n- Forbidden: backend/domain/classify.py, backend/domain/normalize.py, frontend/**, schemas/**, docs/api/**, reports/api-samples/**, status.json.\n\nAuthority:\n- reports/agent-runs/2026-07-phase2-borrow-sort-v1/10-design.md §2 (E1 failure mode: default 8h + warning) and §3.3.\n- schemas/api/public-market/snapshot.schema.json must still validate; contract and schema must remain unchanged except for the dynamic warning string.\n\nExact test command:\npython3 -m pytest backend/tests/ -v\n\nSuccess criteria:\n1. backend/adapters/binance_public.py catches fundingInfo failure and returns empty funding_interval_by_sym plus a warning string.\n2. SnapshotService propagates that warning into snapshot.warnings.\n3. New deterministic test asserts the fallback behavior.\n4. All 95 existing tests still pass; no new failures.\n5. Do not change contract/schema/frontend; do not touch forbidden files.\n6. Do not commit; leave changes in working tree; update 20-implementation-backend.md with the fix note.\n\nBase/head context:\n- base_sha: 4d47ad2d3f2068e86b634b5e39d5063dc4ed526f\n- head_sha: cc25148aa7924e7bb89364f4bba7c8fe978e91f9\n- diff_fingerprint: cc25148:9dc905d56fd003b1b5ebfa31cdebedd363b49f57ddd488b5bef85ac73f3fcb3a",
  "next_action": "fix"
}
```

---

本地北京时间: 2026-07-04 23:40 CST
落档: bookkeeper (claude_glm)；reviewer = Kimi fresh session_bfdbafa6
