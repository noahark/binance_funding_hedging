# Review-1 (rework round 1, Task A) dispatch — fix diff

你是 **first_reviewer（code_reviewer）**，复审阶段
`2026-07-public-market-bstock-alias-v1` 的 **rework round 1 fix**。

## 背景（已发生在你复审之前，逐字证据可查）

本阶段原已通过 review-1（双 ACCEPT）+ review-2 recheck（Codex ACCEPT）。之后一次
**user-directed 外部 post-review**（reviewer = anthropic/`claude-fable-5`，本阶段此前无参与）
发现一个 **P1 回归** `spot_leg_quote_asset_hardcode`：`backend/domain/snapshot.py:70` 把
`resolve_spot_leg(...)` 的 `quote_asset` 实参硬编码为字面量 `"USDT"`，而非该行的
`obj.get("quoteAsset")`；且上游 universe 过滤器未按 `quoteAsset` 过滤。后果：非 USDT 计价的
永续合约把现货腿错误解析为 `baseAsset + "USDT"` 并标 `match_type="exact_symbol"`（如
`BTCUSDC`->`BTCUSDT`、`ETHBTC`->`ETHUSDT`），`PNUTUSDC` 路由还被错误翻转。

rework round 1（rework_count=1，max 3）已落实 fix（commit `548ae0d`，即本阶段新的
`tasks.A` head），由 `claude_glm`（Task A owner）实现。原 finding/fix 调度原文：
`reports/agent-runs/2026-07-public-market-bstock-alias-v1/post-review-quote-asset-hardcode-finding.md`
与
`reports/agent-runs/2026-07-public-market-bstock-alias-v1/fix-start-prompt-spot-leg-quote-asset.md`。
**请逐字读这两个文件，不要依赖本摘要。**

实现者是 `claude_glm`；跨审查池把 Task A 的 review-1 分配给 Kimi（你）。你是只读审查者：
可读任何文件、跑 `git diff`/`shasum`/测试来核对，但**不要修改任何产品代码**。你的唯一写操作
是生成 `reports/agent-runs/2026-07-public-market-bstock-alias-v1/30-review-1-fix.md`。

仓库根：`/Users/ark/Desktop/ai code/funding_hedging`。

## 第一步：重算 diff_fingerprint（不要信任控制器给的值）

跑：

```bash
git diff --binary d240e43e75034a6718ede79bc295d39e77cd860e..548ae0d382c0010c9ab1d0dc26f11ca7a0f47de9 -- . ':(exclude)reports/agent-runs/2026-07-public-market-bstock-alias-v1/status.json' | shasum -a 256
```

得到 sha256 后，拼成 `548ae0d382c0010c9ab1d0dc26f11ca7a0f47de9:<sha256>`，与
`status.json.tasks.A.diff_fingerprint` 比对。**必须在报告里记录你重算的值并声明是否匹配。**
若不匹配 → verdict=REJECT（fingerprint 绑定失败），并把 `fingerprint_matches_status=false` 写入 JSON。

## 第二步：边界检查（fix delta）

跑 `git diff --name-only b1894406cf50173fc110f92b63fc3fe2f7ad7fc1..548ae0d382c0010c9ab1d0dc26f11ca7a0f47de9`。

预期**只**落在以下范围（本 rework 的允许写入边界）：

- `backend/domain/snapshot.py`（**仅** line 70 的 `resolve_spot_leg(...)` 调用点的 `quote_asset` 实参；
  `snapshot.py:99` 的 `"quote_asset": "USDT"` 输出行保持不变——过滤后恒为真）。
- `backend/services/snapshot_service.py`（**仅** universe 过滤新增 `and s.get("quoteAsset") == "USDT"`
  一个子句 + 模块 docstring 的忠实更新）。
- `backend/tests/test_snapshot.py`（**仅新增** 2 个 rework 测试；不得改动既有测试）。
- `backend/tests/fixtures/bstock-alias-raw/fapi-v1-exchangeInfo.json`、
  `api-v3-exchangeInfo.json`（各新增一个 `BTCUSDC` 条目）。
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/40-fix-report.md`、
  `60-test-output.txt`（Section 6 追加）、`status.json`（簿记）。

**必须没有**：`backend/domain/normalize.py`、`backend/domain/classify.py`、
`backend/config.py`、`schemas/**`、`docs/**`、`frontend/**`、`reports/api-samples/**`（历史证据
只读）。任何越界 → verdict=REJECT 并列 required_fixes。

特别核对：

- `git diff b189440..548ae0d -- backend/domain/normalize.py` **应为空**（`resolve_spot_leg` 纯函数零改动）。
- `git diff b189440..548ae0d -- backend/domain/classify.py` **应为空**（回归保护，priority 不变）。
- `git diff b189440..548ae0d -- schemas docs frontend` **应为空**（无契约/文档/前端修订）。

## 第三步：审查重点（逐条核对 fix 的 4 个落点）

1. **`backend/domain/snapshot.py:70` 调用点**：第三个实参现在是 `obj.get("quoteAsset", "")`
   （原为字面量 `"USDT"`）。喂入 `resolve_spot_leg(contract_type, base_asset, quote_asset, spot_by_sym)`
   的语义正确：exact = `base+quote`→`exact_symbol`；仅 `TRADIFI_PERPETUAL` 时 alias
   `base+"B"+quote`→`bstock_b_suffix_alias`。`snapshot.py:99` `"quote_asset": "USDT"` 输出
   保持原样（理由：过滤后每行 quoteAsset 恒为 USDT，写常量不构成新缺陷）。确认没有顺手改
   `resolve_spot_leg`/`classify_route`/`negative_funding_status`。
2. **`backend/services/snapshot_service.py` universe 过滤**：新增 `and s.get("quoteAsset") == "USDT"`，
   且 `ELIGIBLE_CONTRACT_TYPES` 常量未被重复定义（应从 service 导入/定义一次）。这是用户
   2026-07-04 决策（Phase 1 仅覆盖 USDT 计价交易对），兑现既有冻结
   `snapshot.schema.json` 的 `row.quote_asset = {"const": "USDT"}`，**不构成契约修订**（无
   schema/doc 改动）。docstring 的更新与代码一致。
3. **合成 fixture + 双层断言**：`bstock-alias-raw` 现含一个 USDC 计价 PERPETUAL
   （期货 `BTCUSDC` + 现货 `BTCUSDC` 与既有 `BTCUSDT` 并存）。
   - `test_build_rows_usdc_perp_exact_match_not_aliased_to_usdt`：把 `BTCUSDC` 期货行**直接**喂入
     `build_rows`（绕过 universe 过滤），断言 `spot.symbol=="BTCUSDC"`、`match_type=="exact_symbol"`、
     `exists is True`、且 `spot.symbol != "BTCUSDT"`（pre-fix bug 的精确回归锁）。
   - `test_service_universe_filter_excludes_non_usdt_quote`：用真实 `SnapshotService` 管道（stub
     client 注入 bstock fixture），断言 `BTCUSDC` 被过滤、`BTCUSDT` 保留、每行 `quote_asset=="USDT"`。
   - 既有 bStock alias 用例（`test_bstock_alias_classification` 等）与 BTCUSDT exact 用例
     （`test_crypto_exact_match_not_aliased`）**未被改动且仍应通过**。
4. **离线 live-raw 复验**（`60-test-output.txt` Section 6，禁止新 HTTP）：重放**已提交的 live raw**
   （`reports/api-samples/public-market-bstock-alias-v1/20260703T170827Z/raw/`）过修复后的管道，
   断言：universe == 648 行全 USDT（43 个非 USDT 被排除）；**零** `match_type=="exact_symbol"` 且
   `spot.symbol != futures.symbol` 的行；15/15 bStock alias 不变。核对脚本是可重放的 heredoc，
   `ELIGIBLE_CONTRACT_TYPES` 从 service 导入而非重复定义。

## 第四步：decimal/float 纪律 + 测试重跑

- `grep -rn "float(" backend/domain backend/services` 应 **CLEAN**（十进制字段仍为字符串）。
- `.venv/bin/python -m pytest backend/tests -q` 应**全绿**（预期 54 passed：原 52 + 2 rework 测试）。
  把原始输出尾部贴进报告。

## 第五步：写报告 `30-review-1-fix.md`

格式参考 `reports/agent-runs/2026-07-public-market-impl-v1/30-review-1-backend.md`，包含：
Fingerprint 重算与匹配声明、fix delta 边界检查、Artifacts inspected（含 finding/fix-start-prompt
原文路径）、逐条审查发现、测试输出尾部、residual_risks。

**末尾必须有一个严格 JSON 代码块**（字段对齐 `schemas/review-verdict.schema.json`）：

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-public-market-bstock-alias-v1",
  "role": "first_reviewer",
  "model": "kimi-2.7",
  "verdict": "ACCEPT 或 REWORK",
  "diff_fingerprint": "548ae0d382c0010c9ab1d0dc26f11ca7a0f47de9:<你重算的 sha256>",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "我是本阶段 Task B（前端）实现者，且做过原 Task A 的 review-1；但本次复审的是 rework round 1 的 fix diff（由 claude_glm 实现），我未参与该 fix 的实现，也未参与本阶段的 direction synthesis / development breakdown / design。跨审查池因 Task A 实现者是 claude_glm 而把 review-1 分配给 Kimi。",
  "reviewed_artifacts": ["<列出你实际读过的原始文件路径，含 finding/fix-start-prompt>"],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [],
  "next_action": "continue 或 fix"
}
```

`verdict=ACCEPT` 当且仅当：fingerprint 匹配、fix delta 边界干净（normalize.py/classify.py/
schemas/docs/frontend/api-samples 零改动）、调用点 fix 正确（传 `obj.get("quoteAsset","")`）、
universe 过滤正确、双层断言 + live-raw 复验通过、测试全绿、无新增 float()、margin_public.source
仍 unverified、无硬编码抵押率。否则 `verdict=REWORK`，列出 `required_fixes`，并必须提供
`fix_start_prompt`（schema 要求）。

完成后只输出一句结论 + verdict。
