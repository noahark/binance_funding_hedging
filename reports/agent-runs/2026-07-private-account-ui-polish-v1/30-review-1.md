```json
{
  "schema_version": 1,
  "stage_id": "2026-07-private-account-ui-polish-v1",
  "role": "first_reviewer",
  "model": "gpt-5-codex",
  "verdict": "ACCEPT",
  "diff_fingerprint": "71c9d89e28c68d729658814a6f9c34d6a266eb1e:0f769162e4eb97d28f5e4e82048469ae9eba57c943ad12a722e9f3fd56c439c1",
  "reviewer_prior_involvement": "design",
  "reviewer_prior_involvement_notes": "Codex/GPT produced the stage design artifacts 10-design.md and 11-adr.md for this stage. This review-1 is therefore a design-involved fidelity review, not final review. Codex/GPT remains ineligible for review-2; final review is routed to independent Claude/Fable5.",
  "reviewed_artifacts": [
    "reports/agent-runs/2026-07-private-account-ui-polish-v1/00-task.md",
    "reports/agent-runs/2026-07-private-account-ui-polish-v1/10-design.md",
    "reports/agent-runs/2026-07-private-account-ui-polish-v1/11-adr.md",
    "reports/agent-runs/2026-07-private-account-ui-polish-v1/20-implementation.md",
    "reports/agent-runs/2026-07-private-account-ui-polish-v1/60-test-output.txt",
    "docs/api/public-market-contract.md",
    "schemas/api/public-market/snapshot.schema.json",
    "backend/domain/snapshot.py",
    "backend/tests/test_private_account_v1.py",
    "frontend/index.html",
    "frontend/self-check.js",
    "frontend/fixture/public-market-snapshot.json",
    "reports/api-samples/2026-07-private-account-ui-polish-v1/20260706T172648Z/api-v3-ticker-price.json",
    "reports/api-samples/2026-07-private-account-ui-polish-v1/20260706T172648Z/evidence-index.md"
  ],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [
    "This is a design-involved review-1 focused on implementation fidelity. Review-2 must be performed by independent Claude/Fable5 and should re-check the same raw artifacts and committed diff.",
    "The current working branch has bookkeeper commits after the reviewed delivery head. This verdict intentionally binds only to the prompt-specified delivery diff 4549227e9f6528787fb8e69b72c0cd7c585611f4..71c9d89e28c68d729658814a6f9c34d6a266eb1e."
  ],
  "next_action": "continue"
}
```

## 中文复核说明

结论：ACCEPT。

我按 `review-1-codex.prompt.md` 指定的 delivery diff 进行复核：

```bash
git diff 4549227e9f6528787fb8e69b72c0cd7c585611f4..71c9d89e28c68d729658814a6f9c34d6a266eb1e \
  -- . ':(exclude)reports/agent-runs/2026-07-private-account-ui-polish-v1/status.json'
```

独立复算 fingerprint：

```text
71c9d89e28c68d729658814a6f9c34d6a266eb1e:0f769162e4eb97d28f5e4e82048469ae9eba57c943ad12a722e9f3fd56c439c1
```

与 prompt 记录一致。

复核清单结论：

- 后端新增 `_usdt_value_optional()`，行级 `value_usdt` 正确区分缺价/坏价/坏数量为 `null`，合法零为 `"0.00000000"`。
- 顶层 `total_value_usdt` 仍使用原 `_usdt_value()`，anti-double-count 规则未改。
- `um_positions[]` 未新增 `value_usdt`。
- schema 只在 `balances_unified[]` / `balances_spot[]` item properties 增加 optional nullable `value_usdt`，未加入 required，`schema_version` 保持 `public-market-snapshot/v1`。
- 契约 v0.4 amendment 为 additive，写明 `um_positions[]` 仍是 exposure view。
- 当前 stage 路径下有 raw public `/api/v3/ticker/price` 样本与 provenance index，不是仅合成 fixture。
- 前端借币日息子行仅在 `borrow_rate_source != null` 行展示，VIP0 fallback 标「参考」，正费率/无成本腿行不展示。
- `negative_funding_status` 已改为 row-aware 结构优先级派生，结构禁用行不会误派生为「需私有验证」。
- `#private-panel` 已移动到市场表之前，关闭/失败态仍不白屏。
- 余额卡片展示 `折算`，null/缺失显示 `-`，隐私开关遮蔽余额与折算值。
- 前端保持中文优先、零排序、不反算 total。

独立复跑测试：

```bash
python3 -m pytest backend/tests/test_private_account_v1.py -q
# 51 passed

python3 -m pytest backend/tests/test_snapshot.py -q
# 19 passed

python3 -m pytest backend/tests -q
# 157 passed

node frontend/self-check.js
# 全部自检通过

python3 -c "jsonschema.validate(fixture, schema)"
# schema validation OK
```

本地北京时间: 2026-07-07 CST
下一步模型: Claude/Fable5
下一步任务: 独立 review-2 终审，按 raw artifacts 与 committed delivery diff 复核后给出 final verdict。
