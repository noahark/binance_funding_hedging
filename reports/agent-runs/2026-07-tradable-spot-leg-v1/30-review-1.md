评审完成。以下为完整 review-1 输出（按只读约定，我不创建文件，请人类操作员将本回复完整保存为 `reports/agent-runs/2026-07-tradable-spot-leg-v1/30-review-1.md`)。

---

# Review-1 — 2026-07-tradable-spot-leg-v1(Kimi / moonshot_kimi)

## 范围与身份核验

- 评审范围固定为 `9a03069fa9942739c7d8077d3a33d4387afde048..7522ec3645f7c51e0abb602268b7e1f89b5556da`（两个提交：`0e334e0` bookkeeper 准备、`7522ec3` 交付），未使用移动 HEAD。
- 我独立重算了 diff 指纹：`git diff --binary <base>..<head> -- . ':(exclude).../status.json' | shasum -a 256` = `79afe4f3c9a5cd7cc4ff3253183104679c91ffda36ac5672926e80b08162ac50`，与派工固定指纹完全一致。
- 当前分支 `stage/2026-07-tradable-spot-leg-v1`，工作区干净（`git status --short` 为空），评审基于已提交状态。
- 评审方 `moonshot_kimi` 与实现方 `zhipu_glm` 无任何共享 provider/session/transcript/tool 状态；本人此前未参与本阶段设计、综合或拆解。

## 门禁项逐项核验（全部通过）

1. **exact 与 B-suffix 候选仅对 `status == "TRADING"` 解析** — `backend/domain/normalize.py:70-84` 新增 `_tradable_spot`，`resolve_spot_leg`(normalize.py:115、119）对 exact 与 alias 均经该 helper，严格字符串相等。
2. **missing/unknown/`BREAK`/`HALT`/一切非 `TRADING` 失败关闭** — `spot.get("status") == "TRADING"` 对缺失键返回 `None`、对任意其他值不相等，均返回 `None`；测试 case 2/3/6(BREAK、HALT、缺 `status`、`AUCTION_MATCHING`）直接断言 `(None, None)`。
3. **TRADIFI 非交易 exact 不阻塞交易 alias** — exact 经 helper 返回 `None` 后进入 alias 分支；`test_spot_leg_non_trading_exact_does_not_block_trading_alias`(test_snapshot.py:502-509）断言解析到 `TSLABUSDT` / `bstock_b_suffix_alias`。
4. **既有 match-type 字符串与可交易 exact/alias 行为不变** — 字符串未改；`test_normalize.py` 三个旧测试语义原样（仅 fixture 补 `status`);`test_snapshot.py` 既有 25 个测试未动且通过。
5. **无可用现货腿序列化为既有 no-leg 形状** — `build_rows`(snapshot.py:141-200）未改，spot 为 `None` 时 `exists=false`、`symbol/status/match_type=null`;classify.py 未改，`PERP_ONLY_EXCLUDED` / `DISABLED_PERP_ONLY` / `positive_funding_enabled=false`。case 2 测试（test_snapshot.py:466-490）端到端驱动 `build_rows` 断言全部字段。
6. **授权的 test_normalize.py 修复仅为三处测试、四个 fixture 字段** — diff 确认恰好 4 行 `"status": "TRADING"` 添加（test_normalize.py:99、107、131-132)，断言、测试名、生产代码零改动；`test_resolve_spot_leg_alias_not_triggered_for_perpetual` 按报告说明有意保持不变。与 `07-scope-extension-authorization.md` 授权范围精确一致。
7. **测试矩阵、原始证据、文档一致且无 schema/frontend 漂移** — 6 个新测试覆盖设计矩阵 5 行 + missing/unknown 补充；冻结样本经我直接解析确认 AERGOUSDT/XMRUSDT/LITUSDT 全部 `status=BREAK`、`isMarginTradingAllowed=false`、现货 bookTicker 双边为零、对应永续报价正常，足以支撑合约修订的 raw-sample 硬门禁；PRD 与 contract 文档措辞（`spot.exists` = 当前可交易已解析腿）与实现行为一致；`schemas/`、`frontend/` 在 diff 中零改动。
8. **无交易执行、私有账户、凭据、适配器、schema、前端行为新增** — diff 仅限 `normalize.py`、两个测试文件、两个文档、阶段 reports 与冻结样本、`ACTIVE.json` 指针。

## 回归面核查

- `resolve_spot_leg` 全部调用方已排查：仅 `build_rows` 与两个测试文件，无其他生产调用方。
- `_attach_opening_quotes`(snapshot_service.py:487-497）按 `row.spot.symbol` 联接报价，`None` 腿得 `incomplete`；此前 BREAK 腿零报价同样得 `incomplete`，渲染结果无回归，前端自检含 incomplete 用例并通过。
- `select_borrow_candidates` 只取 `MARGIN_SPOT_CANDIDATE`;BREAK 行此前为 `SPOT_ONLY_CANDIDATE` 本就不入探借池，现为 `PERP_ONLY_EXCLUDED`，行为一致。
- `default_view_history_symbols` 排除 `PERP_ONLY_EXCLUDED` 行：这些行不再预热历史，属本次排除语义的预期一致后果。

## 独立复跑证据（只读，禁用字节码/缓存写入）

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider` → **381 passed**,exit=0
- `node frontend/self-check.js` → 全部自检通过，exit=0
- `git diff --check <base>..<head>` → clean
- 与 `60-test-output.txt` 中实现方修复运行（17/31/381 passed）及 bookkeeper 独立复核一致；早前 `3 failed` 运行按审计要求原样保留。

## 发现

仅一条 P3 信息性发现，不构成修复要求：设计矩阵第 5 行字面变体"exact 缺失 + alias BREAK"未被单测字面覆盖——case 5 覆盖的是"exact BREAK + alias HALT",exact 缺失由 `test_resolve_spot_leg_none_when_no_spot`（空 dict）覆盖。两者合起来语义覆盖充分，可选地补一条字面变体用例。

## 结论

实现、测试、文档、原始证据与授权边界全部与门禁要求一致，测试与指纹经我独立复核通过。 verdict 为 **ACCEPT**，流转 review-2。

当前 Session ID: 27b4389b-4fed-471f-8c98-c3b48575fe41
Session ID 来源： transcript_path（本地会话存储路径出现于本次运行工具输出 `…/.kimi-code/sessions/wd_funding_hedging_312b78e68b47/session_27b4389b-4fed-471f-8c98-c3b48575fe41/…`，操作员可核对）
原始输出路径： reports/agent-runs/2026-07-tradable-spot-leg-v1/30-review-1.md
本地北京时间： 2026-07-18 14:11:50 CST
下一步模型： Codex bookkeeper → review-2（计划 Fable5，规避 Codex 设计重叠）
下一步任务： bookkeeper 校验本 verdict JSON 与 schema/指纹一致性，按 preflight 准备并派工 review-2 固定指纹终审

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-tradable-spot-leg-v1",
  "role": "first_reviewer",
  "model": "kimi-code/kimi-for-coding",
  "verdict": "ACCEPT",
  "diff_fingerprint": "7522ec3645f7c51e0abb602268b7e1f89b5556da:79afe4f3c9a5cd7cc4ff3253183104679c91ffda36ac5672926e80b08162ac50",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml",
    "agents/skills/code-reviewer.md",
    "schemas/review-verdict.schema.json",
    "reports/agent-runs/2026-07-tradable-spot-leg-v1/00-intake.md",
    "reports/agent-runs/2026-07-tradable-spot-leg-v1/00-task.md",
    "reports/agent-runs/2026-07-tradable-spot-leg-v1/05-live-sample-analysis.md",
    "reports/agent-runs/2026-07-tradable-spot-leg-v1/07-scope-extension-authorization.md",
    "reports/agent-runs/2026-07-tradable-spot-leg-v1/10-design.md",
    "reports/agent-runs/2026-07-tradable-spot-leg-v1/11-adr.md",
    "reports/agent-runs/2026-07-tradable-spot-leg-v1/20-implementation.md",
    "reports/agent-runs/2026-07-tradable-spot-leg-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-tradable-spot-leg-v1/70-handoff.md",
    "reports/api-samples/2026-07-tradable-spot-leg-v1/20260718T042314Z/request-manifest.md",
    "reports/api-samples/2026-07-tradable-spot-leg-v1/20260718T042314Z/raw/api-v3-exchangeInfo-symbols.json",
    "reports/api-samples/2026-07-tradable-spot-leg-v1/20260718T042314Z/raw/api-v3-ticker-bookTicker-symbols.json",
    "reports/api-samples/2026-07-tradable-spot-leg-v1/20260718T042314Z/raw/fapi-v1-ticker-bookTicker-AERGOUSDT.json",
    "reports/api-samples/2026-07-tradable-spot-leg-v1/20260718T042314Z/raw/fapi-v1-ticker-bookTicker-LITUSDT.json",
    "reports/api-samples/2026-07-tradable-spot-leg-v1/20260718T042314Z/raw/fapi-v1-ticker-bookTicker-XMRUSDT.json",
    "git diff 9a03069fa9942739c7d8077d3a33d4387afde048..7522ec3645f7c51e0abb602268b7e1f89b5556da (fingerprint independently recomputed and matched)",
    "backend/domain/normalize.py",
    "backend/domain/snapshot.py",
    "backend/domain/classify.py",
    "backend/services/snapshot_service.py",
    "backend/tests/test_normalize.py",
    "backend/tests/test_snapshot.py",
    "docs/product/PRD.md",
    "docs/api/public-market-contract.md"
  ],
  "findings": [
    {
      "severity": "P3",
      "title": "Design matrix row 5 literal variant (absent exact + BREAK alias) not literally tested; coverage is adequate via composition",
      "file": "backend/tests/test_snapshot.py",
      "line": 520,
      "evidence": "10-design.md matrix row 5 is 'TRADIFI/TRADING | exact absent | alias BREAK -> none'. test_spot_leg_non_trading_alias_does_not_resolve (call at line 520) uses exact BREAK + alias HALT; the exact-absent case is covered separately by test_normalize.py::test_resolve_spot_leg_none_when_no_spot with an empty spot map.",
      "impact": "None functional: the alias gate and the absent-exact path are each directly asserted, so the composed behavior is pinned. This is a test-completeness nit only, not a required fix.",
      "recommendation": "Optional: add one literal case with no exact record and a non-TRADING alias asserting (None, None). Not required for acceptance."
    }
  ],
  "required_fixes": [],
  "residual_risks": [
    "Rows whose spot leg becomes non-trading now resolve to no-leg: they leave default_view_history_symbols prewarm and their opening_quotes spot side renders incomplete (previously the BREAK zero book also rendered incomplete). Both are consistent, frontend-covered consequences of the intended exclusion semantics.",
    "A non-TRADING spot record serializes as the no-leg shape without preserving the raw status (e.g. BREAK) in the row; this overloading was consciously deferred in 11-adr.md alternative 3 and would need a future contract amendment if observation metadata is wanted."
  ],
  "next_action": "continue"
}
```
