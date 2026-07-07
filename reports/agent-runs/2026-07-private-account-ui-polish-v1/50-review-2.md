```json
{
  "schema_version": 1,
  "stage_id": "2026-07-private-account-ui-polish-v1",
  "role": "final_reviewer",
  "model": "claude-fable-5",
  "verdict": "ACCEPT",
  "diff_fingerprint": "71c9d89e28c68d729658814a6f9c34d6a266eb1e:0f769162e4eb97d28f5e4e82048469ae9eba57c943ad12a722e9f3fd56c439c1",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "Fable5 兼 bookkeeper 与 final reviewer,并在实现前对 designer(Codex)产出的 10-design/11-adr 做过 design_review(ACCEPT 门,非设计著作)。非 designer/direction_synthesizer/breakdown-author,非 implementer/fix-author;reviewer≠implementer、final≠designer 硬红线不破。designer_identities={codex},本审 provider identity=anthropic,不落 designer 重叠 override 路径。",
  "reviewed_artifacts": [
    "reports/agent-runs/2026-07-private-account-ui-polish-v1/00-task.md",
    "reports/agent-runs/2026-07-private-account-ui-polish-v1/10-design.md",
    "reports/agent-runs/2026-07-private-account-ui-polish-v1/11-adr.md",
    "reports/agent-runs/2026-07-private-account-ui-polish-v1/20-implementation.md",
    "reports/agent-runs/2026-07-private-account-ui-polish-v1/30-review-1.md",
    "reports/agent-runs/2026-07-private-account-ui-polish-v1/60-test-output.txt",
    "git diff 4549227..71c9d89 (delivery source): backend/domain/snapshot.py, schemas/api/public-market/snapshot.schema.json, docs/api/public-market-contract.md, frontend/index.html, frontend/self-check.js",
    "backend/domain/classify.py (negative_funding_status 枚举与优先级)",
    "reports/api-samples/2026-07-private-account-ui-polish-v1/20260706T172648Z/api-v3-ticker-price.json",
    "reports/api-samples/2026-07-private-account-ui-polish-v1/20260706T172648Z/evidence-index.md"
  ],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [
    "本 stage 未合并 main(base 4549227 落后当前 main v0.4 之前锚点);合并时按 stage 分支制走 main 合入,合并 SHA 回填 status.json.stage_branch。",
    "value_usdt 估值依赖 P5 /api/v3/ticker/price 全量价图;真实无价资产行按契约返回 null 占位(已由 self-check null 用例覆盖),生产环境价图缺失面与既有 total_value_usdt 一致,无新增暴露。"
  ],
  "next_action": "stage_accepted_waiting_user"
}
```

## 中文终审说明（Fable5 / review-2 / final reviewer）

结论：**ACCEPT**。作为独立终审，我不复用 review-1 结论,直接对 committed delivery diff `4549227..71c9d89` 逐红线复核。

**Fingerprint**：独立复算 `git diff --binary <base>..<head> -- . ':(exclude).../status.json'` 的 sha256 = `0f769162…c439c1`,与 status.diff_fingerprint 及 review-1 记录一致。

**后端 / 契约（backend/domain/snapshot.py）**
- 新增 `_usdt_value_optional()`:缺 asset/amount、坏 amount、缺价、坏价 → `None`(各带 warning);合法值(含零)→ `Decimal`,序列化 `_quantize_rate` 为 8 位串。与 `_usdt_value`(缺价压 0)独立,**null vs "0.00000000" 语义正确区分**。
- 稳定币(USDT/USDC)计价 1。
- 顶层 `total`(snapshot.py:587–597)仍用原 `_usdt_value`,`total_value_usdt` 输出未改,anti-double-count 硬规则无回归;`um_positions` 无 `value_usdt`,notional 不计入 total。
- spot 行 amount = `_add_dec(free, locked)`;两者皆空 → None → value_usdt=null,合理。

**Schema / 契约门**
- schema:`value_usdt = decimal_string | null` 仅加入 `balances_unified[]`/`balances_spot[]` item,**未进 required**,`schema_version` 保持 `public-market-snapshot/v1`;v0.1/v0.2/v0.3 样本仍验证。
- 契约:v0.4 amendment 纯 additive,明确 `um_positions[]` 仍为 exposure view 且不带该字段、不计入 total;前端 display-only、不得反算 total。
- 契约变更门:`reports/api-samples/<stage>/20260706T172648Z/` 有 raw no-key `GET /api/v3/ticker/price` + `evidence-index.md` provenance,**非仅合成 fixture**。

**前端（frontend/index.html）**
1. `#private-panel` 已移至市场表 panel **之前**;`display:none` 缺失/降级不白屏。
2. `badgeForNegativeFundingStatus(row)` 改为 row-aware:DISABLED_PERP_ONLY / DISABLED_BSTOCK / DISABLED_SPOT_ONLY **结构态提前返回**结构文案;仅 `PRIVATE_BORROW_VALIDATION_REQUIRED` 落 `borrow_validation` 五文案细分。独立核 `classify.py` + schema:`negative_funding_status` 是**闭合 enum 且 required**(4 值),三结构态 early-return,默认分支只可能是 PRIVATE_BORROW_VALIDATION_REQUIRED,**不会对非负/结构禁用行误派生「需私有验证」**。
3. 借币日息子行仅 `row.borrow_rate_source != null`(成本腿命中)展示;优先 `daily_interest_account`,回落 `daily_interest_vip0` 标「参考」,再缺显 `-`;正费率/无成本腿行无子行。
4. 每资产「折算 USDT」:`value_usdt` null/空 → `折算: -` 占位,否则 `maskAmount(value_usdt)`,隐私开关经 `maskAmount` 同时遮蔽余额与折算值。中文优先、前端零排序、不反算 total。

**测试(终审独立复跑)**
- `python3 -m pytest backend/tests -q` → 157 passed
- `node frontend/self-check.js` → 全部自检通过(含 五文案 row-aware / 余额折算+隐私遮蔽 / value_usdt null 占位)
- fixture ↔ schema jsonschema.validate → OK

无 P0/P1/P2/P3 finding。两轮 review 均 ACCEPT,进入 pre-accept,等待用户显式验收后按 stage 分支制合入 main。

本地北京时间: 2026-07-07 CST
下一步: pre-accept 门校验 → 用户验收(human gate)→ 合并 stage→main
