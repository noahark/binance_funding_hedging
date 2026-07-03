# Review-1 (Task A) dispatch — Backend bStock alias amendment

你是 **first_reviewer（code_reviewer）**，审查阶段
`2026-07-public-market-bstock-alias-v1` 的 **Task A（契约修订 + 后端 bStock 别名修复）**。
实现者是 claude_glm；跨审查池把 Task A 的 review-1 分配给 Kimi（你）。

仓库根：`/Users/ark/Desktop/ai code/funding_hedging`。你是只读审查者：可以读任何文件、跑
`git diff` / `shasum` / 测试来核对，但**不要修改任何产品代码**。你的唯一写操作是生成审查报告
`reports/agent-runs/2026-07-public-market-bstock-alias-v1/30-review-1-backend.md`。

## 你在审查什么

Task A 把 impl-v1 的 post-review P1 finding（bStock B 后缀现货腿别名）从描述性注释升级为
冻结契约修订 + 可运行后端修复。核心：TRADIFI 期货 symbol（`TSLAUSDT`）通过
`baseAsset + "B" + quoteAsset` 别名 join 到 bStock 现货 symbol（`TSLABUSDT`）。

commit 范围：`H_intake..H_A` = `d240e43..1f94c84`（不含 status.json）。

## 第一步：重算 diff_fingerprint（不要信任控制器给的值）

跑：

```bash
git diff --binary d240e43e75034a6718ede79bc295d39e77cd860e..1f94c842a67ac75b170f796b17cb08172457b5d7 -- . ':(exclude)reports/agent-runs/2026-07-public-market-bstock-alias-v1/status.json' | shasum -a 256
```

得到 sha256 后，拼成 `1f94c842a67ac75b170f796b17cb08172457b5d7:<sha256>`，与
`status.json.tasks.A.diff_fingerprint` 比对。**必须在报告里记录你重算的值并声明是否匹配。**
若不匹配 → REJECT（fingerprint 绑定失败）。

## 第二步：边界检查

跑 `git diff --name-only d240e43..1f94c84`，确认路径**只在** Task A scope 内：
`schemas/api/public-market/snapshot.schema.json`、`docs/api/public-market-contract.md`、
`backend/domain/normalize.py`、`backend/domain/snapshot.py`、`backend/tests/**`、
`backend/tests/fixtures/bstock-alias-raw/**`、
`reports/agent-runs/2026-07-public-market-bstock-alias-v1/20-implementation-backend.md`、
`reports/agent-runs/2026-07-public-market-bstock-alias-v1/60-test-output.txt`。

**必须没有**：`frontend/**`、`backend/domain/classify.py`、`backend/config.py`、
`reports/api-samples/**`（frozen 证据只读）。任何越界 → REJECT。

## 第三步：审查重点（逐条核对）

1. **`backend/domain/normalize.py:resolve_spot_leg`**：三分支正确——
   exact `base+quote`→`exact_symbol`；仅 `TRADIFI_PERPETUAL` 时 alias `base+"B"+quote`→
   `bstock_b_suffix_alias`；否则 `(None,None)`。**关键**：alias 必须只对 TRADIFI 触发，不能污染
   普通 PERPETUAL。exact 必须优先于 alias（即使 TRADIFI 同时有 exact spot 也不用 alias）。
2. **`backend/domain/snapshot.py:build_rows`**：用 `resolve_spot_leg` 替代旧的
   `spot = spot_by_sym.get(sym)`；`spot.match_type` 已填入 spot 块；`classify_route` /
   `negative_funding_status` 调用未改。`CONTRACT_WARNINGS[2]` 文案已更新且仍含
   `TRADIFI_PERPETUAL` 关键词、声明抵押率动态未知不硬编码。
3. **`classify.py` 必须未被修改**：`git diff d240e43..1f94c84 -- backend/domain/classify.py`
   应为空。priority 序列（PERP_ONLY→BSTOCK→SPOT_ONLY→PRIVATE_BORROW）不变。这是硬约束。
4. **schema**：`spot.match_type` 是 nullable enum
   `["exact_symbol","bstock_b_suffix_alias",null]`，且**不在 required**（保证 frozen sample
   向后有效）。
5. **语义闭环**：bStock 经 alias 进 `MARGIN_SPOT_CANDIDATE`（正费率候选，`positive_funding_enabled=true`），
   但因 `asset_tag=BSTOCK` priority 第 2 位，`negative_funding_status=DISABLED_BSTOCK`（不可借币，负费率禁用）。
   这应**完全由现有 classifier + 别名 join 实现，无需改 classify**。
6. **测试**：`backend/tests/fixtures/bstock-alias-raw/**` 是合成离线 fixture（有 `_synthetic` 标记，
   非 live、非 frozen 证据）；`test_normalize.py`（5 个 resolve_spot_leg）、`test_snapshot.py`
   （6 个 bstock）、`test_negative_schema.py`（match_type reject + null valid）覆盖完整。
   `test_classify.py` 未改（回归保护）。
7. **decimal/float 纪律**：`grep -RnE '\bfloat\(' backend --include='*.py'` 应 CLEAN；十进制字段为字符串。
8. **重跑测试**：`.venv/bin/python -m pytest backend/tests -q` 应全绿。把原始输出尾部贴进报告。

## 第四步：写报告 `30-review-1-backend.md`

格式参考 `reports/agent-runs/2026-07-public-market-impl-v1/30-review-1-backend.md`。包含：
Fingerprint 重算、边界检查、Artifacts inspected、逐条审查发现、`json_schema_valid`（schema 是否对
合成 fixture 产出的 snapshot 合法——你跑 Task C 的集成脚本或 test 验证）、residual_risks。

**末尾必须有一个 JSON 代码块**，字段：

```json
{
  "role": "first_reviewer",
  "model": "kimi-2.7",
  "verdict": "ACCEPT 或 REJECT",
  "diff_fingerprint": "你重算的 <head>:<sha256>",
  "fingerprint_matches_status": true/false,
  "json_schema_valid": true/false,
  "reviewer_prior_involvement": "task_b_frontend_implementer",
  "reviewer_prior_involvement_notes": "我是本阶段 Task B（前端）实现者；未参与 Task A 的 direction/breakdown/design，未写任何 Task A 代码。跨审查池因 Task A 实现者是 claude_glm 而把 review-1 分配给 Kimi。",
  "findings": [],
  "required_fixes": [],
  "residual_risks": [],
  "next_action": "continue 或 rework"
}
```

verdict=ACCEPT 当且仅当：fingerprint 匹配、边界干净、classify.py 未改、语义闭环正确、测试全绿、
schema 合法、无硬编码抵押率、margin_public.source 仍 unverified。否则 REJECT 并列 required_fixes。

完成后只输出一句结论 + verdict。
