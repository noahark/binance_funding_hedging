# 16-design-review：需求/设计草稿审阅

## 审阅元数据

- stage_id: `2026-07-ui-filter-balance-metal-v1`
- reviewer_model: `glm-5.2`
- reviewer_provider: `zhipu_glm`
- via: `claude_glm`（Claude Code 适配器）
- 审阅时间: 2026-07-08 09:09:09 CST
- 审阅阶段: `designing`（尚未进入实现；本次为设计草稿审阅，非 review-1/review-2 正式 gate）
- 审阅依据（原始工件，非 bookkeeper 摘要）:
  - `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/00-intake.md`
  - `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/00-task.md`
  - `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/10-design.md`
  - `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/11-adr.md`
  - `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/12-development-breakdown.md`
  - `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/15-requirements-review.md`（Kimi 预实现审查；本审阅与之对照，非替代）
  - `backend/domain/normalize.py`、`backend/domain/snapshot.py`、`backend/domain/classify.py`
  - `backend/tests/test_normalize.py`、`frontend/index.html`、`frontend/self-check.js`
  - `schemas/api/public-market/snapshot.schema.json`、`docs/api/public-market-contract.md`
  - `frontend/fixture/public-market-snapshot.json`、`backend/tests/fixtures/private-account-v1-design.json`
- verdict: `not_ready_for_implementation`（方向正确，但有 2 个阻断性实现缺口 + 1 个契约语义矛盾需先解决）

## 与 15-requirements-review（Kimi）的关系

本审阅与 `15-requirements-review.md`（Kimi，verdict=REWORK）**互补不重复**：

- **分工**：15 偏产品文案/命名/格式澄清（Q1 文案绝对值语义、Q2 COPPER 命名分类、Q3 千分位规则）；本审阅偏代码实现风险与契约语义（S1/S2/M1/M2/M3）。两者 verdict 一致（均需澄清后方可实现）。
- **本审阅对 15 的增量**：
  - **S1 深化 15-Q4**：15-Q4 建议"加边界行 + 行数差值断言"，但未注意到**现有 design fixture 的 `CUSDT` `daily_funding_rate` 已是 `"0.00030000"` 边界值**（`self-check.js:227`），默认隐藏会立即让 #4（默认 6 行）及 #6/#19/#20/#28/#33/#34 共 6 个既有断言 throw。"加行"不足以解决既有基线破坏，需 S1 的 (A)/(B)/(C) 策略。
  - **M1 为 15 未覆盖**：METAL 与 `select_borrow_candidates`（`snapshot.py:364` 硬编码 `asset_tag=="CRYPTO"`）+ `negative_funding_status`（`classify.py:46`）的语义矛盾——METAL 永不进借币探测但 UI 显示"需私有验证"。15-Q2 仅讨论 METAL 命名/分类，未触及借币探测行为。
  - **M3 为 15 未覆盖**：self-check #35/#36/#37 硬编码旧行内格式 `【: ...】`，R2 改三行式后须同步替换。
- **本审阅对 15 的纠正**：
  - **S2 纠正 15-Q4 文件路径**：15-Q4 建议改 `frontend/fixture/public-market-snapshot.json`，但 `self-check.js:14` 实际加载 `backend/tests/fixtures/private-account-v1-design.json`，前者不被 self-check 加载（`index.html:1280` 浏览器场景 fetch `/api/public-market/snapshot`）。边界样本应加到后者或用独立 fixture。
- **采纳 15 的发现**：Q1（文案绝对值语义）、Q2（COPPER 命名/分类，与本审阅 L3 互补）、Q3（千分位规则，与本审阅 L2 互补）本审阅认可，已纳入下方待确认清单。

## 准确性核对

草稿对现有实现的描述大体准确，以下点已与代码核对一致：

- `asset_tag_for(contract_type)` 现状（`normalize.py:28-34`）：TRADIFI_PERPETUAL→BSTOCK、PERPETUAL→CRYPTO、otherwise→UNKNOWN。✅
- `state.filters` 结构（`index.html:673-675`）：search / assetTag / routeClass / showPerpOnly。✅
- `filteredRows()` 顺序（`index.html:993-1000`）：搜索→资产标签→路由分类→PERP_ONLY。✅
- `renderPrivatePanel()` 使用 `inlineUsdtSuffix`（`index.html:1170/1181/1190`）。✅
- schema `asset_tag` enum（`snapshot.schema.json:127-133`）：CRYPTO/BSTOCK/UNKNOWN。✅
- `negative_funding_status` 优先级（`classify.py:32-46`）与草稿 R3 描述一致。✅

## 🔴 严重（阻断实现）

### S1. R1 默认隐藏连锁破坏 self-check 现有基线，草稿未给策略

`self-check.js:199-202` 硬断言默认渲染 **6 行**。但 design fixture 中 `CUSDT` 的 `daily_funding_rate = +0.03% = "0.00030000"`（`self-check.js:227`），按 R1 阈值 `abs <= 0.00030000` **正好落在隐藏边界**，默认隐藏后行数 6→5，#4 直接失败。

更严重的是 `CUSDT` 被多个**用默认 tbody** 的既有断言引用，默认隐藏后 `getRowCell(tbody, 'CUSDT', ...)` 会 throw `未找到 CUSDT 行`：

- `#6` 日费率格式化（`:233`）、`#19` 净收益（`:411`）、`#20` 负净收益样式（`:428`）、`#28` 方向标（`:584`）、`#33` 正费率无借币子行（`:681`）、`#34` 六文案派生（`:688-738`，操作 `rows[2]`=CUSDT）。

`10-design.md` §1 测试只写"增加 0.0003 / -0.0003 / 0.00030001 三行"，**完全未提既有 6 行基线如何处理**。必须先定策略，三选一：

- (A) 调整 design fixture 让全部默认行 `abs > 0.0003`（需同步改 #6 期望 `+0.03%`，且放弃用 0.0003 边界值做样例）；
- (B) 低费率隐藏用**独立 fixture** 专项测试（仿 `#20`/`#21` 的 deep-copy 改字段模式），不污染默认 6 行；
- (C) 在用默认 tbody 的既有断言前显式关闭 `hideLowDailyRate` 并 re-render。

**推荐 (B)**：最不扰动既有基线。需在 `10-design.md` §1 明确写出。

### S2. 文件边界漏了 self-check 实际加载的 fixture

`self-check.js:14` 实际加载 `backend/tests/fixtures/private-account-v1-design.json`，**不是** `frontend/fixture/public-market-snapshot.json`。后者仅 6 行（BTC/ETH/XVG/XMR/MSTR/TSLA，`daily_funding_rate` 全 `None`，asset_tag 仅 CRYPTO/BSTOCK），且 `index.html:1280` 浏览器场景 fetch `/api/public-market/snapshot`，**不引用** `frontend/fixture/`。

但 `00-task.md` 文件边界只列 `frontend/fixture/public-market-snapshot.json`，**漏掉** `backend/tests/fixtures/private-account-v1-design.json`——这才是 R1/R2 测试真正要改的 fixture。实现者按草稿边界执行会改错文件。

**建议**：文件边界补上 `backend/tests/fixtures/private-account-v1-design.json`；并澄清 `frontend/fixture/public-market-snapshot.json` 角色（文档样例则只需为 R3 加一行 METAL 样本保持一致，不承担测试）。

## 🟡 中等（契约语义/一致性，需澄清）

### M1. METAL 与借币探测的语义矛盾——草稿"待确认点"比想象的更深

草稿 R3（`00-task.md:68`）把"金属是否像 bStock 一样禁用负费率借币"列为待确认，但未注意到现有代码已隐含决定 METAL 行为：

- `snapshot.py:364` `select_borrow_candidates` 硬编码 `asset_tag == "CRYPTO"` 作为借币探测候选条件 → **METAL 永不进入 rate_probe / borrowability_probe**，后端永远不会为 METAL 取借币利率；
- 但 `classify.py:46` 的 `negative_funding_status` 对 METAL（MARGIN_SPOT_CANDIDATE + 非 BSTOCK）落到 `PRIVATE_BORROW_VALIDATION_REQUIRED` → UI 显示**"需私有验证"**；
- 于是 METAL 负费率行 `net_daily_yield` 永远 `null`（无 borrow rate），`borrow_validation.verified=false/error=null`，UI 却显示"需私有验证"——**文案暗示可验证可借，实际后端从不探测**。

这与 bStock（`DISABLED_BSTOCK`，UI 明确"禁用"）的清晰语义不一致。两个自洽选项，草稿须二选一并写入 ADR：

- (A) METAL 也给禁用态（新增 `DISABLED_METAL` 进 `negative_funding_status` enum + schema + classify 优先级 + contract），UI 显示"金属:不支持借币套利"；
- (B) 维持现状但显式记录"METAL 不进借币探测，'需私有验证'对 METAL 含义为'人工评估'"，并在 self-check 增断言：`XAU` 负费率行 `net_daily_yield=null` 且不在 `rate_probe_assets`。

无论选哪个，`select_borrow_candidates:364` 的 `asset_tag == "CRYPTO"` 过滤行为都要在契约文档写清（METAL 被排除）。当前 `contract.md:348-351` 只说"asset_tag != CRYPTO 不探测"，措辞需对齐 METAL。

### M2. `snapshot.py` 文件边界描述前后不一致

`00-task.md:82` 写 `snapshot.py`（仅 warnings/summary 受 enum 自然影响时；不改资金费率计算）；但改 `asset_tag_for` 签名后，**`snapshot.py:86` 调用点必须改**为传 `base_asset`。`12-development-breakdown.md:14` 的"仅必要接线"更接近事实，但两处措辞应统一，否则 review-1 会就"是否越界"产生争议。

### M3. self-check #35/#36/#37 硬编码旧行内格式，R2 必须同步替换

R2 把 `【: value USDT】` 改为独立 `≈ value USDT` 行，但 `self-check.js` 仍断言旧格式：`:742` `【: ****】`、`:748` `【: 123.45 USDT】`、`:750` `【: 67.89 USDT】`、`:770` `【: — USDT】`、`:793` `【: 0.00 USDT】`。

`12-development-breakdown.md` 提到"Update self-check cases for display, null, zero, hidden"算覆盖，但 `10-design.md` §2 测试清单未点名这 5 处替换。建议在 design 里显式列出，避免漏改。

## 🟢 轻微（建议）

- **L1. `asset_tag_for` 签名加默认参数是有意兼容**：`test_normalize.py:13/21/29` 三处既有调用都是单参数。草稿设计 `base_asset: str = ""` 可保持向后兼容不 break 既有测试，但 ADR 未点明。建议 ADR-4 补"用默认参数保持单参数调用兼容"。
- **L2. 现货卡片 amount 行语义未明**：`10-design.md` §2 目标 HTML 只有一个 `amount` 行 + `locked` 行 + `value-usdt` 行，但现货有 free/locked 两个数量（`snapshot.py:585-592` value_usdt 是 free+locked 合计）。应明确 amount 行展示 **free**，否则实现者需自行推断。
- **L3. COPPER/XPT/XPD baseAsset 真实性**：`10-design.md` §4 已提风险。建议至少用公开行情样本确认 `XAU`/`XAG` 的 baseAsset 命名并落到 `reports/api-samples/<stage>/`（AGENTS.md Hard Gate 倾向契约变更有 raw sample 佐证）；`COPPER`/`XPT`/`XPD` 若无实盘样本，应在 contract 注明"待样本确认"。
- **L4. 流程合规（非需求内容）**：`status.json` 中 bookkeeper = stage_designer = breakdown_author = `codex`。按 AGENTS.md，review-2 final reviewer 应异于 designer/breakdown author；若 review-2 仍用 codex，须走 strong-reviewer disclosure override 并记录失败证据路径，否则 review-2 应换 Claude。`prior_involvement_disclosure` 已记录，留意执行时落地。

## 待用户确认清单（建议合并为一次确认）

1. **S1 策略**：R1 低费率隐藏测试选 (A)/(B)/(C) 哪种？（推荐 B）
2. **M1 METAL 行为**：新增 `DISABLED_METAL` 禁用态，还是维持"需私有验证"并显式记录不探测？
3. **阈值边界语义**：`abs == 0.00030000` 即 `+0.03%` 是否隐藏？（草稿 ADR-2 是"是"，但 CUSDT 正好此值，与 S1 互动，需明确确认）
4. **METAL 仅标签、不进借币探测**是否为最终决定（对应 `open_questions[3]`）。
5. 现货 locked 是否保留单独"冻结:"行（对应 `open_questions[4]`，草稿已倾向保留）。

## 结论

**不建议直接进入实现**。草稿产品方向 OK，但 S1（self-check 连锁失败策略）、S2（文件边界缺口）、M1（METAL 借币探测语义）三处必须先补进 `00-task.md` / `10-design.md` / `12-development-breakdown.md` 并经用户确认。M2/M3/L1-L3 可在补丁时一并修正。补齐后这是一份可执行的 MEDIUM serial 草稿。

---

本地北京时间: 2026-07-08 09:09:09 CST
下一步模型: human（决策上述 5 个确认点）→ 随后可交 GPT/Codex 复核本审阅
下一步任务: 用户审阅本 design review；确认 S1/S2/M1 后由 bookkeeper 补入草稿，再进入 serial implementation。
