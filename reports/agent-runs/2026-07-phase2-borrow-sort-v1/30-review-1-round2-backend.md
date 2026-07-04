# Review-1 Round-2 — Task A（backend）— 2026-07-phase2-borrow-sort-v1

## 元信息

- reviewer：Kimi（fresh 只读会话 `session_bc79ad49-4c8f-43bc-8365-1fb41bf6320b`；
  与 round-1 评审会话 `session_bfdbafa6`、实现、设计、fix 均无关联）
- role：`first_reviewer`（schema 合规——schema role 枚举
  = {designer_review, first_reviewer, final_reviewer, reality_checker}，
  **无 second_reviewer**；模板 T1/T2 的 second_reviewer 是笔误，见
  round-1 两 reviewer 独立标记的 F2）
- model：kimi（kimi-code/kimi-for-coding）
- verdict：**ACCEPT**
- reviewer_prior_involvement：`none`
- diff_fingerprint：`2a793a9c35e8e5fe8cdebe8875cada9b85f335d0:9b92cc4595982f0e09ce33d179019fa54a370aa30aeeaa977772eca33fb433e9`
- raw output：`30-review-1-round2-backend.raw-output.md`（370 行；含 Kimi
  思考过程叙述，本文件为提取后的 clean verdict）

## 独立重算指纹

按 status.json 公式：

```
sha256(git diff --binary 4d47ad2d..2a793a9c -- . ":(exclude)reports/.../status.json")
= 9b92cc4595982f0e09ce33d179019fa54a370aa30aeeaa977772eca33fb433e9
```

组合指纹 `2a793a9:9b92cc45...` 与 status.json 记载一致，指纹检查通过。

## E1 fix 复审

### 1. E1 降级实效

`backend/adapters/binance_public.py` `_fetch_live`：

- `fundingInfo` 调用包裹在 `try/except (urllib.error.URLError, OSError, ValueError)` 内。
- 失败时 `funding_interval_by_sym = {}`，追加含 `fundingInfo` 与 `8h` 的 warning。
- 异常**不向上传播**，snapshot 构建不会因此 503。
- 其余公开端点（exchangeInfo / premiumIndex / spot）仍直接 `_http_get`，失败即 raise
  ——符合「仅 fundingInfo 可降级」契约。

### 2. warning 透传链

- `fetch_raw()` 返回 `warnings`（`_fetch_live` 追加 / `_fetch_offline` 空 list）。
- `SnapshotService.build_snapshot` 读 `fetch_warnings = raw.get("warnings", [])`。
- 以 `extra_warnings=fetch_warnings` 传入 `assemble_snapshot`。
- `assemble_snapshot`：`warnings = list(CONTRACT_WARNINGS) + list(extra_warnings or [])`
  ——保留三条固定契约警告 + 追加运行时降级警告。

### 3. 新测试覆盖

`backend/tests/test_phase2_borrow_sort.py::test_live_fundinginfo_failure_degrades_to_8h_with_warning`：

- monkeypatch `urllib.request.urlopen`，仅对 `/fapi/v1/fundingInfo` raise `HTTPError(503)`。
- 断言 `raw["funding_interval_by_sym"] == {}`。
- 断言 warnings 含 fundingInfo/8h。
- 用空 interval map 调 `build_rows`，断言全行 `funding_interval_hours == 8`。
- 调 `assemble_snapshot(extra_warnings=...)`，断言 snapshot.warnings 含降级提示。
- **测试独立重跑通过**（reviewer 自执行）。

### 4. 测试与 self-check 可重放性（reviewer 独立重跑）

- `python3 -m pytest backend/tests/` → **96 passed**（reviewer 本会话自执行确认）。
- `node frontend/self-check.js` → **20 PASS**（reviewer 本会话自执行确认）。

### 5. round-1 零回归清单

fix 仅触 4 文件：`binance_public.py` / `snapshot.py` / `snapshot_service.py` /
`test_phase2_borrow_sort.py`。未触碰：

- `private_client.py`（单一 HMAC 出口 / 白名单三态 / key 卫生）；
- `classify.py` / `normalize.py`（路由 / 资产标签 / 三态语义）；
- `snapshot.py` 中 `compute_daily_funding_rate` / `sort_rows` /
  `assemble_borrow_validation`（Decimal 向量 / 排序全序 / 三态语义）；
- `snapshot.schema.json`（warnings 仍开放 string array，追加合法）；
- `docs/api/public-market-contract.md` 与 `reports/api-samples/**`（契约证据链）；
- frontend 任何文件。

### 6. schema/contract 未改

`snapshot.warnings` 仍为开放 `array of string`，无 minItems/maxItems。fix 未改
schema 与契约文档。

## bookkeeper 独立核实

1. **指纹三方 MATCH** ✅：reviewer 重算 = bookkeeper 重算 = status.json，
   均为 `2a793a9:9b92cc45...`（bookkeeper 独立执行 `git diff | shasum` 复核）。
2. **reviewer 独立性** ✅：fresh session `bc79ad49` ≠ round-1 `bfdbafa6`；
   reviewer 在本会话**独立重跑** pytest（96 passed）+ node self-check（20 PASS），
   非仅采信实现者报告——强独立验证信号。
3. **schema 合规** ✅：role=`first_reviewer`（枚举内）；verdict=ACCEPT；
   findings/required_fixes/residual_risks 均空 array（schema 无 minItems，
   键存在即满足 required）；next_action=`continue`（枚举内）。ACCEPT 无需
   fix_start_prompt。
4. **verdict=ACCEPT 不增 rework_count**：round-2 复审通过，round-1 的 E1 fix
   成立。stage review-1 全通（A round-2 ACCEPT + B round-1 ACCEPT）。

## next_dispatch

- review-1 **完成**：A round-2 ACCEPT + B round-1 ACCEPT（backend-only fix，
  不影响 frontend，B 无需 round-2）。
- → **review-2**（final gate，T3 Codex，用户交，`direction_synthesis` 披露）。
  dispatch：`review-2-task-c-by-codex.prompt.md`（base=`4d47ad2`,
  head=`2a793a9`）。
- review-2 ACCEPT → `stage_accepted_waiting_user`（pre-accept gate）。

## verdict JSON（schema 合规）

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-phase2-borrow-sort-v1",
  "role": "first_reviewer",
  "model": "kimi",
  "verdict": "ACCEPT",
  "diff_fingerprint": "2a793a9c35e8e5fe8cdebe8875cada9b85f335d0:9b92cc4595982f0e09ce33d179019fa54a370aa30aeeaa977772eca33fb433e9",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "Fresh read-only Kimi session for review-1 round 2; no prior design, implementation, fix, embedded pre-review, or round-1 review involvement for Task A.",
  "reviewed_artifacts": [
    "backend/adapters/binance_public.py",
    "backend/domain/snapshot.py",
    "backend/services/snapshot_service.py",
    "backend/tests/test_phase2_borrow_sort.py",
    "schemas/api/public-market/snapshot.schema.json",
    "reports/agent-runs/2026-07-phase2-borrow-sort-v1/status.json",
    "reports/agent-runs/2026-07-phase2-borrow-sort-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-phase2-borrow-sort-v1/30-review-1-backend.md"
  ],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [],
  "next_action": "continue"
}
```

---

本地北京时间: 2026-07-05 00:16 CST
落档: bookkeeper (claude_glm)；reviewer = Kimi fresh session（bc79ad49）；
verdict 从 raw output 提取，bookkeeper 独立核实指纹三方 MATCH + schema 合规 +
reviewer 自跑测试通过
