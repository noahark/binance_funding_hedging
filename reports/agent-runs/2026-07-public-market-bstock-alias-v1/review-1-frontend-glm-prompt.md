# Review-1 (Task B) dispatch — Frontend bStock alias display

你是 **first_reviewer（code_reviewer）**，一个**全新的只读 Claude-GLM 会话**（不继承控制器/Task A
的对话上下文）。审查阶段 `2026-07-public-market-bstock-alias-v1` 的 **Task B（前端 bStock 别名显示）**。
实现者是 Kimi；跨审查池把 Task B 的 review-1 分配给 fresh Claude-GLM（你）。

仓库根：`/Users/ark/Desktop/ai code/funding_hedging`。只读审查：可读文件、跑 `git diff`/`shasum`/
`node`，**不要改产品代码**。唯一写操作是生成
`reports/agent-runs/2026-07-public-market-bstock-alias-v1/30-review-1-frontend.md`。

## 你在审查什么

Task B 让前端在期货 symbol 经 B 后缀别名 join 到不同现货 symbol 时，显示实际现货腿 + 来源标识。
commit 范围：`6ea4504..5968c49`（H_A 指纹绑定 commit..H_B，不含 status.json）。

## 第一步：重算 diff_fingerprint（不要信任控制器给的值）

```bash
git diff --binary 6ea4504..5968c499d990c3dfaa54f5fd8b38172b9a0a0ddb -- . ':(exclude)reports/agent-runs/2026-07-public-market-bstock-alias-v1/status.json' | shasum -a 256
```

拼成 `5968c499d990c3dfaa54f5fd8b38172b9a0a0ddb:<sha256>`，与 `status.json.tasks.B.diff_fingerprint`
比对。不匹配 → REJECT。

## 第二步：边界检查

`git diff --name-only 6ea4504..5968c49` 应**只在** Task B scope：`frontend/index.html`、
`frontend/self-check.js`、`frontend/fixture/public-market-snapshot.json`、
`reports/agent-runs/2026-07-public-market-bstock-alias-v1/20-implementation-frontend.md`、
`reports/agent-runs/2026-07-public-market-bstock-alias-v1/task-b-kimi-prompt.md`。

**必须没有**：`backend/**`、`schemas/**`、`docs/**`、`reports/api-samples/**`。越界 → REJECT。

## 第三步：审查重点

1. **`frontend/index.html`**：标的列**仅当** `row.spot.match_type === "bstock_b_suffix_alias"` 且
   `row.spot.symbol` 存在且 `!== row.symbol` 时显示实际现货腿 + B 后缀别名标识。exact_symbol / 无腿
   行保持原样。用已有 badge 样式，无大改 CSS。无交易/开仓/账户 UI。默认同源
   `fetch('/api/public-market/snapshot')`。
2. **`frontend/fixture/public-market-snapshot.json`**（前端静态演示数据，非 frozen 证据）：
   - 每个 spot 块有 `match_type`（BTC/ETH/XVG=exact_symbol；XMR/MSTR=null）。
   - TSLAUSDT 行改为 alias 接通的 candidate：`route_class=MARGIN_SPOT_CANDIDATE`、
     `positive_funding_enabled=true`、`negative_funding_status=DISABLED_BSTOCK`、正费率、
     `spot.symbol=TSLABUSDT`、`match_type=bstock_b_suffix_alias`、ui_flags 去掉 `PERP_ONLY_NO_SPOT_LEG`。
   - MSTRUSDT 保持 PERP_ONLY（无 alias 对照）。
   - `summary` 计数与 6 行一致；`warnings[2]` 同步后端新文案（含 `TRADIFI_PERPETUAL` + "not hard-coded"）。
3. **`frontend/self-check.js`**：默认行数 3→4；新增 alias 断言（含 `TSLABUSDT` 与 "B 后缀别名"）；
   BSTOCK 行数仍 2；所有既有断言保留（同源请求、warnings、北京时间、列名"最近更新的资金费率"、
   不含"已结算/预测"、无交易按钮）。
4. **重跑**：`node frontend/self-check.js` 必须"全部自检通过" exit 0。贴原始输出。

## 第四步：写报告 `30-review-1-frontend.md`

格式参考 `reports/agent-runs/2026-07-public-market-impl-v1/30-review-1-frontend.md`。末尾 JSON：

```json
{
  "role": "first_reviewer",
  "model": "glm-5.2[1m]",
  "verdict": "ACCEPT 或 REJECT",
  "diff_fingerprint": "你重算的 <head>:<sha256>",
  "fingerprint_matches_status": true/false,
  "json_schema_valid": true,
  "reviewer_prior_involvement": "task_a_backend_implementer_and_controller",
  "reviewer_prior_involvement_notes": "我是本阶段 Task A（后端）实现者兼控制器，也做了 controller-direct design（Fable5 不可达）。我审查的是 Task B（前端，Kimi 实现），前后端无代码重叠。跨审查池因 Task B 实现者是 Kimi 而把 review-1 分配给 fresh Claude-GLM。本审查是一个全新只读会话，未继承控制器/Task A 对话上下文，直接读原始 artifacts 与 diff。",
  "findings": [],
  "required_fixes": [],
  "residual_risks": [],
  "next_action": "continue 或 rework"
}
```

verdict=ACCEPT 当且仅当：fingerprint 匹配、边界干净、alias 显示逻辑正确、fixture/self-check 一致、
同源默认、无交易 UI、self-check 全过。否则 REJECT。

完成后只输出一句结论 + verdict。
