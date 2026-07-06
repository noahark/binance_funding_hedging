# Review-1 · Task B（前端）— first_reviewer 评审

- stage: `2026-07-private-account-v1`
- role: `first_reviewer`（fresh Claude-GLM / glm-5.2，只读/plan 会话）
- 对象: Task B（前端）已提交状态
- base_sha: `6ca6ee1db61952c10d547aa73a79e0711b2ae64b`（H_A）
- head_sha: `6c1e992c4628c0d8e369ba648b0403f341037849`（H_B frontend）
- diff_fingerprint（重算）: `6c1e992c4628c0d8e369ba648b0403f341037849:50998c3a60afbae089f3e370e7ecbdd869256c70ff0cc1ae888b3f3abd6da2a2`
- 对照规格: `10-design.md` §1.1-§1.5 / §4 + status.json hard_constraints
- 隔离声明: 未读取 embedded-review-b-round1.raw-output.md / bookkeeper / Task A 实现上下文；独立形成判断。
- 本地北京时间: 2026-07-06 13:46 CST

## 0. 指纹与门禁

- 当前分支 `stage/2026-07-private-account-v1` ✓；base/head SHA 均存在 ✓。
- 按 status.json `diff_fingerprint_formula` 重算指纹 = `6c1e992…:50998c3a60afbae089f3e370e7ecbdd869256c70ff0cc1ae888b3f3abd6da2a2`，与 prompt 声明**逐字一致** ✓（不一致才会 BLOCKED，本项 PASS）。
- frontend 自 H_B(6c1e992) 至 HEAD 未变（`git diff 6c1e992..HEAD -- frontend/` 为空）；fixture 在 H_B 与工作树一致 → 在 HEAD 跑 self-check 等价于 H_B 提交态。

## 1. 必查清单（逐项 PASS/FAIL + 证据）

| # | 项 | 结论 | 证据 |
|---|---|---|---|
| 1 | 净收益列（string-shift 复用 / 格式化函数体零改动 / null→— / 负值样式 / source 徽标 + vip0 显著标注） | **PASS** | `formatFundingRate(row.net_daily_yield)` 复用（纯 string-shift，无 float）；diff 中 `formatFundingRate`/`formatBeijing*` 仅作新调用点出现，定义体零增删（git 独立印证 self-check §15）；undefined/null→`—`；负净收益 `negative` 红样式（self-check §20 构造用例 PASS）；`sourceBadge` 渲染四源，`vip0_reference` 走 `.vip0-reference` danger 样式 + 「基准利率」（self-check §21 PASS） |
| 2 | sort_basis 标注 + 零排序逻辑 | **PASS** | `sort-basis-badge` 渲染「基准: 净收益优先」+ title 注零客户端排序；`filteredRows()`(index.html:967) 纯 `.filter()` 保 payload 序，`renderTable` 用 `.map()`；全文件无 `.sort()/.reverse()/localeCompare`；控制区无排序控件（self-check §8 PASS） |
| 3 | 私有面板三态（verified=false 占位不白屏 / 结构齐 / 无杜撰字段） | **PASS** | `renderPrivatePanel`：verified≠true → 「私有通道未启用」占位（panel 不隐藏、附 error、不白屏）；verified=true → 总览+统一/现货余额+UM 持仓结构齐；仅用 §1.4 契约字段，无杜撰（self-check §23/§26/§27 PASS） |
| 4 | 隐私开关（默认隐藏 / 点击切换 / localStorage 仅布尔 / 隐藏态不入 DOM 外输出 / 无 console.log 账户数据） | **PASS** | `loadPrivacyHidden()` 空值返回 true（默认隐藏）；`savePrivacyHidden` 仅存 `'true'/'false'`；`maskAmount` 隐藏态 `****`（真实金额不入 DOM）；`togglePrivacy` 点击切换；**全文件无 `console.`**（self-check §24/§25 PASS） |
| 5 | 行联动只给方向标，不带数量/盈亏 | **PASS** | `directionBadgeForSymbol` 仅 多/空 `direction-badge`，不含 qty/pnl（self-check §28 验证不含 `1.5`/`数量`） |
| 6 | 降级：新字段全缺失（旧后端）页面行为不变 | **PASS** | 删全部新字段 → 日费率/净收益 `—`、无间隔徽标、私有面板隐藏、sort_basis 隐藏、不白屏（self-check §29 PASS；`formatFundingRate(undefined)→'—'` 源码确认） |
| 7 | self-check §4.7 断言全集 + 自跑全绿（含 net 反超顺序用例） | **PASS** | **独立 `node frontend/self-check.js` → 29/29 PASS，exit 0**；含 net 反超（渲染序==fixture 序） |
| 8 | 越界：diff 仅 frontend 两文件 + stage 报告；无 commit / 无 status.json 改动；中文口径不变 | **PASS** | diff = `frontend/index.html`+`frontend/self-check.js`+5 stage 报告（允许）；range 内无 status.json；实现终端未 commit（bookkeeper 落盘）；blocked/empty colspan 9→10；枚举「英文(中文)」未改（self-check §17 PASS） |

### review-1 附加项
- **self-check 自跑复现**：PASS — `node frontend/self-check.js` → 29/29 PASS，exit 0（本会话独立复现）。
- **隐私开关默认态实证（fixture 渲染检查）**：PASS — 默认隐藏态 DOM innerHTML 含 `****`，localStorage `funding_hedging_privacy_hidden='true'`。

## 2. Findings（仅 P3 残余风险，非阻断）

1. **[P3] 设计期 fixture 行序非严格 net 降序**
   - 文件: `backend/tests/fixtures/private-account-v1-design.json`
   - 证据: fixture 序 AUSDT(net 0.00040000) > BUSDT(net 0.00010000) > CUSDT(net 0.00030000)：CUSDT net 更大却排后，违反 §1.2 严格 net 降序。§3.5 显式命名的反超对（AUSDT 排 BUSDT 之前）仍成立。
   - 影响: 无前端运行时影响——前端零排序、按 payload 顺序渲染（self-check §9 PASS），运行时排序由后端 sort_rows 保证。属合成设计期数据质量问题，已在 ADR-8 标记 OPEN。
   - 建议: 非 Task B 缺陷，无需前端改动；归 Task A/fixture 侧 ADR-8 跟踪。

2. **[P3] formatPrice/maskAmount 输出经 innerHTML 未显式 escapeHtml**
   - 文件: `frontend/index.html`（renderPrivatePanel）
   - 证据: `maskAmount(...)`（内部 formatPrice）结果直接拼入 innerHTML；金额隐藏态被 `****` 替换。
   - 影响: 与既有 mark_price/index_price 渲染同模式（既有亦未 escape），值为后端可控 Decimal 串，且金额受隐私开关 mask；未引入新 XSS 面。
   - 建议: 保持与既有模式一致即可；如后续统一加固可对所有数值串过 escapeHtml。

无 P0/P1/P2 发现。

## 3. 总结论

**ACCEPT（可推进 review-2）**。Task B 前端实现满足 10-design §4 全部要求与 hard_constraints；
指纹一致、self-check 29/29 独立复现、隐私默认隐藏实证通过、零排序红线守住、降级与三态齐备、
越界干净。2 项 P3 为已披露/沿用既有模式之残余风险，不构成阻断。

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-private-account-v1",
  "role": "first_reviewer",
  "model": "claude_glm (glm-5.2)",
  "verdict": "ACCEPT",
  "diff_fingerprint": "6c1e992c4628c0d8e369ba648b0403f341037849:50998c3a60afbae089f3e370e7ecbdd869256c70ff0cc1ae888b3f3abd6da2a2",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "Fresh claude_glm (glm-5.2) read-only/plan 会话担任 Task B first_reviewer，未参与 direction synthesis / breakdown / design / Task A 实现 / 嵌入预审。status.json model_routing review_1.B = claude_glm fresh。Task B 实现者为 kimi（与评审不同模型）；bookkeeper 同为 claude_glm 模型但独立会话（dual_hat_disclosure: 记账不产生代码作者身份），本评审会话不可见其上下文。该模型重名披露交 review-2 评估。",
  "reviewed_artifacts": [
    "frontend/index.html (diff 6ca6ee1..6c1e992)",
    "frontend/self-check.js (diff 6ca6ee1..6c1e992)",
    "backend/tests/fixtures/private-account-v1-design.json",
    "reports/agent-runs/2026-07-private-account-v1/10-design.md",
    "reports/agent-runs/2026-07-private-account-v1/status.json",
    "schemas/review-verdict.schema.json"
  ],
  "findings": [
    {
      "severity": "P3",
      "title": "设计期 fixture 行序非严格 net 降序（CUSDT 排在 BUSDT 之后）",
      "file": "backend/tests/fixtures/private-account-v1-design.json",
      "evidence": "fixture 行序 AUSDT(net 0.00040000) > BUSDT(net 0.00010000) > CUSDT(net 0.00030000)：CUSDT net 更大却排在后，违反 §1.2 严格 net 降序；§3.5 命名反超对 AUSDT>BUSDT 仍成立。",
      "impact": "无前端运行时影响：前端零排序、按 payload 顺序渲染（self-check §9 PASS），运行时排序由后端 sort_rows 保证。合成设计期数据质量问题，已在 ADR-8 标记 OPEN。",
      "recommendation": "非 Task B 缺陷，无需前端改动；归 Task A/fixture 侧 ADR-8 跟踪。"
    },
    {
      "severity": "P3",
      "title": "formatPrice/maskAmount 输出经 innerHTML 未显式 escapeHtml",
      "file": "frontend/index.html",
      "evidence": "renderPrivatePanel 中 maskAmount(...)（内部 formatPrice）直接拼入 innerHTML；金额隐藏态被 **** 替换。",
      "impact": "与既有 mark_price/index_price 渲染同模式（既有亦未 escape），值为后端可控 Decimal 串，金额受隐私 mask；未引入新 XSS 面。",
      "recommendation": "保持与既有模式一致；如后续统一加固可对所有数值串过 escapeHtml。"
    }
  ],
  "required_fixes": [],
  "residual_risks": [
    "ADR-8: fixture 全行非严格 net 降序（合成数据，运行时由后端排序保证；§3.5 命名反超对保留）。",
    "formatPrice 数值串经 innerHTML 未显式转义，沿用既有模式；后端可控输入 + 隐私 mask 兜底。"
  ],
  "next_action": "continue"
}
```

---
模型身份: claude_glm (glm-5.2)，fresh 只读/plan first_reviewer 会话
本地北京时间: 2026-07-06 13:46 CST
