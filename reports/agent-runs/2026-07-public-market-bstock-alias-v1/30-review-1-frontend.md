# Review-1 (task-level) — Task B: Frontend bStock B-suffix alias display

- **Stage**: `2026-07-public-market-bstock-alias-v1`
- **Reviewer**: `first_reviewer` (fresh read-only Claude-GLM session, `glm-5.2[1m]`)
- **Subject**: Task B only — Kimi-authored frontend bStock alias display
- **Range**: `6ea4504` (Task-A checkpoint / `H_A`) → `5968c49` (`H_B`), single commit
- **Verdict**: **ACCEPT**

## 0. Fresh-session & provider disclosure

I am a brand-new read-only Claude-GLM session. I did NOT inherit the controller / Task-A conversation context — I read the raw artifacts and `git diff` directly and formed an independent judgment. The stage controller and the Task-A (backend) implementer share my provider (`claude_glm`); Task B's implementer is `kimi`, so I am the provider-level cross-review. My prior involvement is Task-A backend implementer + controller + controller-direct design (Fable5 unreachable); Task B is pure frontend with no code overlap with my Task-A work, and the cross-review pool routed Task-B review-1 to a fresh Claude-GLM because Task B's implementer is Kimi. Cross-review + fresh-session isolation justify this review.

## 1. Fingerprint recomputation (recomputed from clean shell)

```
sha256(git diff --binary 6ea4504..5968c499d990c3dfaa54f5fd8b38172b9a0a0ddb -- . ':(exclude)…/status.json')
= 8c5d685eb8a51ea3261cb85cda97cfa000b2fb66ccddf49d3b0f0031a4b7c7d0
```

→ recomputed `diff_fingerprint` = `5968c499d990c3dfaa54f5fd8b38172b9a0a0ddb:8c5d685eb8a51ea3261cb85cda97cfa000b2fb66ccddf49d3b0f0031a4b7c7d0`

**Matches** `status.json.tasks.B.diff_fingerprint` exactly. ✓

## 2. Diff scope / boundary

Files in the diff (exactly 5, `status.json` excluded):

```
frontend/fixture/public-market-snapshot.json
frontend/index.html
frontend/self-check.js
reports/agent-runs/2026-07-public-market-bstock-alias-v1/20-implementation-frontend.md
reports/agent-runs/2026-07-public-market-bstock-alias-v1/task-b-kimi-prompt.md
```

No `backend/**`, no `schemas/**`, no `docs/**`, no `reports/api-samples/**`, no `agents/**`/`workflows/**`/`scripts/**`. Exactly the 3 frontend files + 2 stage report/prompt files allowed by the brief. **No boundary crossing.** ✓

`git diff --stat` for `frontend/`: `index.html +4/-1` (5 lines net), `self-check.js +14/-7`, `fixture +21/-13` — surgical, no CSS rewrite.

## 3. Checkpoint-by-checkpoint findings

| # | Checkpoint | Result | Evidence |
|---|---|---|---|
| 1 | **Alias conditional fires only for `bstock_b_suffix_alias`** | ✓ PASS | `index.html:702-704`: `const spotAlias = row.spot && row.spot.match_type === 'bstock_b_suffix_alias' && row.spot.symbol && row.spot.symbol !== row.symbol ? '<br/>现货腿: …' : ''`. Three guards AND-ed: exact match_type, truthy `spot.symbol`, and `spot.symbol !== row.symbol`. Inserted into the 标的 `<td>` at `:707` only as `${spotAlias}`. No other render path touches it. |
| 2 | **`exact_symbol` / no-leg rows unaffected** | ✓ PASS | BTC/ETH/XVG have `spot.symbol === row.symbol` (e.g. BTCUSDT===BTCUSDT) → `!== row.symbol` is false → `spotAlias=''`. XMR/MSTR have `spot.symbol: null` → truthy guard fails → `spotAlias=''`. Only TSLAUSDT (spot.symbol `TSLABUSDT` !== `TSLAUSDT`) qualifies. Verified via `match_type` distribution in fixture (3×`exact_symbol`, 2×`null`, 1×`bstock_b_suffix_alias`). |
| 3 | **Reuses existing badge styles, no CSS rewrite** | ✓ PASS | Uses existing classes `.muted.small` and `.badge.compact.info` (defined at `index.html:191,194,312-313`). No new CSS variables, no `<style>` changes in the diff. Chinese workstation visual style preserved (sidebar/topbar/badge palette untouched). |
| 4 | **Same-origin default fetch** | ✓ PASS | `loadApi()` invoked unconditionally at `index.html:816` (bottom of IIFE); does `fetch('/api/public-market/snapshot')` — relative, same-origin. `loadFixture()` is wired only to the "加载离线 fixture" button (`:796`) and is never the default. Hardcoded-external-host grep returned no hits. Data-source label defaults to `数据源: /api/public-market/snapshot` (`:412,:739`). |
| 5 | **No trading / open-position / account UI** | ✓ PASS | Forbidden-terms grep (`下单｜买入｜卖出｜借(币｜入)｜还款｜划转｜开仓｜账户余额｜持仓管理｜place.?order｜borrow｜repay｜transfer｜open.?position`) returns exactly one hit — `index.html:566`, the `PRIVATE_BORROW_VALIDATION_REQUIRED` enum rendered as the status badge `需验证借币`. This is the explicitly-allowed display label (a negative-funding-status badge), not a borrow action. No order/buy/sell/repay/transfer/open-ticket/account/position entry. Self-check enforces absence of `手动开仓/下单/开仓` (`self-check.js:169`). |
| 6 | **Fixture: TSLAUSDT alias candidate wired correctly** | ✓ PASS | `fixture:259-297` — TSLAUSDT has `route_class:"MARGIN_SPOT_CANDIDATE"`, `positive_funding_enabled:true`, `negative_funding_status:"DISABLED_BSTOCK"`, positive `last_funding_rate:"0.00010000"`, `spot.symbol:"TSLABUSDT"`, `spot.match_type:"bstock_b_suffix_alias"`, and `ui_flags:["MARGIN_PUBLIC_UNVERIFIED","TRADIFI_BSTOCK"]` — i.e. `PERP_ONLY_NO_SPOT_LEG` removed. Matches the brief's candidate spec item-for-item. |
| 7 | **Fixture: MSTRUSDT stays PERP_ONLY, every spot has match_type** | ✓ PASS | MSTRUSDT (`fixture:219-258`): `route_class:"PERP_ONLY_EXCLUDED"`, `spot.exists:false`, `match_type:null`, no alias. All 6 spot blocks carry `match_type`: BTC/ETH/XVG=`exact_symbol`, XMR/MSTR=`null`, TSLA=`bstock_b_suffix_alias`. |
| 8 | **Fixture: summary counts consistent with 6 rows** | ✓ PASS | Independently recomputed from `rows[]`: route `{MARGIN_SPOT_CANDIDATE:3, SPOT_ONLY_CANDIDATE:1, PERP_ONLY_EXCLUDED:2}`; asset_tag `{CRYPTO:4, BSTOCK:2}`; neg_status `{PRIVATE_BORROW_VALIDATION_REQUIRED:2, DISABLED_SPOT_ONLY:1, DISABLED_BSTOCK:1, DISABLED_PERP_ONLY:2}`; `total_rows:6`. All four match `summary` verbatim. |
| 9 | **Fixture: `warnings[2]` synced to backend new copy** | ✓ PASS | `fixture:302` == `backend/domain/snapshot.py:20` verbatim: `"TRADIFI_PERPETUAL (bStock) spot legs are joined via the baseAsset+B+quoteAsset alias (e.g. futures TSLAUSDT -> spot TSLABUSDT); bStock collateral ratio is dynamic/unknown and is not hard-coded; asset_tag is independent of route_class."` Contains both required markers `TRADIFI_PERPETUAL` and `not hard-coded`. |
| 10 | **self-check.js assertions updated correctly** | ✓ PASS | Default row count 3→4 (`:120`); show-PERP still 6 (`:131`); BSTOCK still 2 (`:138`); new alias assertions `TSLABUSDT` and `B 后缀别名` (`:144-149`); all prior assertions retained — same-origin request (`:93`), data-source label (`:100`), warnings content incl. `TRADIFI_PERPETUAL` (`:112`), Beijing time `2026-07-03 16:00:00` (`:153`), column name `最近更新的资金费率` (`:163`), no `已结算/预测` (`:160`), no `手动开仓/下单/开仓` (`:169`). |
| 11 | **Self-check rerun** | ✓ PASS | `node frontend/self-check.js` → 11/11 PASS, prints `全部自检通过`, `EXIT=0`. Raw output:

```
[PASS] 内联脚本语法检查
[PASS] 默认请求 /api/public-market/snapshot
[PASS] 数据源标签显示后端 API
[PASS] warnings 可见且内容已渲染
[PASS] 默认隐藏 PERP_ONLY_EXCLUDED，渲染 4 行
[PASS] 显示 PERP_ONLY_EXCLUDED 后渲染全部 6 行
[PASS] BSTOCK 行标识正确
[PASS] alias 行显示实际现货腿与 B 后缀别名标识
[PASS] 时间转换正确
[PASS] 列名/文案符合契约
[PASS] 无交易按钮/开仓票据

全部自检通过
```

|

## 4. Conclusion

No P0/P1/P2/P3 defect found. Every acceptance criterion in the brief holds: fingerprint matches `status.json`, diff boundary is clean (frontend-only + 2 stage docs), the alias display fires only for `bstock_b_suffix_alias` rows with a differing spot symbol, `exact_symbol` and no-leg rows are untouched, same-origin default fetch is preserved, no trading/open-position UI exists, the fixture's TSLAUSDT candidate is wired exactly as specified, summary counts are internally consistent, `warnings[2]` is synced to the backend verbatim, and the self-check passes with exit 0.

## 5. Residual risks (carry-forward, non-blocking)

1. The 6-row fixture cannot exercise every production alias case; live endpoints may serve additional `bstock_b_suffix_alias` rows (or other `match_type` values the frontend silently ignores for alias display, which is correct — only `bstock_b_suffix_alias` is contracted to render the badge).
2. The alias display trusts `row.spot.symbol` as already-validated backend output; the frontend does no further symbol-shape validation (correct division of labor — backend owns the alias join).
3. No pagination/virtualization (carry-forward from impl-v1); row-count-agnostic `rows.map` will render all returned rows.

```json
{
  "role": "first_reviewer",
  "model": "glm-5.2[1m]",
  "verdict": "ACCEPT",
  "diff_fingerprint": "5968c499d990c3dfaa54f5fd8b38172b9a0a0ddb:8c5d685eb8a51ea3261cb85cda97cfa000b2fb66ccddf49d3b0f0031a4b7c7d0",
  "fingerprint_matches_status": true,
  "json_schema_valid": true,
  "reviewer_prior_involvement": "task_a_backend_implementer_and_controller",
  "reviewer_prior_involvement_notes": "我是本阶段 Task A（后端）实现者兼控制器，也做了 controller-direct design（Fable5 不可达）。我审查的是 Task B（前端，Kimi 实现），前后端无代码重叠。跨审查池因 Task B 实现者是 Kimi 而把 review-1 分配给 fresh Claude-GLM。本审查是一个全新只读会话，未继承控制器/Task A 对话上下文，直接读原始 artifacts 与 diff。",
  "findings": [],
  "required_fixes": [],
  "residual_risks": [
    "6-row fixture only exercises one bstock_b_suffix_alias row (TSLAUSDT); live endpoint may serve additional alias rows. Rendering is row-count-agnostic and will render all returned rows correctly.",
    "Alias display trusts row.spot.symbol as backend-validated output; frontend performs no further symbol-shape validation (correct division of labor — backend owns the alias join).",
    "No pagination/virtualization (carry-forward from impl-v1); acceptable for this read-only market-table stage."
  ],
  "next_action": "continue"
}
```
