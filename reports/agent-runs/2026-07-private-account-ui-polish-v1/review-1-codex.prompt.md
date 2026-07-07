<!-- ============ RECEIPT（审计元数据；非任务内容） ============
status: pending             # pending | running | done | escalated
stage_id: 2026-07-private-account-ui-polish-v1
stage_branch: stage/2026-07-private-account-ui-polish-v1
node: review-1
target_model: codex         # first_reviewer；披露 prior_involvement=design
role: first_reviewer        # 依 Hard Gates 不是 implementer/fixer；本 review 不改码
role_chain: designer=Codex → implementer=Kimi → review-1=Codex(设计者复核实现保真) → review-2=Claude/Fable5
base_sha: 4549227e9f6528787fb8e69b72c0cd7c585611f4
head_sha: 71c9d89e28c68d729658814a6f9c34d6a266eb1e
diff_fingerprint: 71c9d89e28c68d729658814a6f9c34d6a266eb1e:0f769162e4eb97d28f5e4e82048469ae9eba57c943ad12a722e9f3fd56c439c1
adapter_cmd: 用户以「读此文件并执行 PROMPT BODY」一行指令发至 Codex 终端
bookkeeper_precheck: HEAD/fingerprint 复算一致; 独立重跑 157 pytest + self-check 全绿; 实现抽验对齐设计(仅供参考,你须自行复核)
next_dispatch: 通过 → Fable5 review-2 终审; REWORK → Kimi 按 fix_start_prompt 修
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行） ---

你是 stage `2026-07-private-account-ui-polish-v1` 的 **review-1（first_reviewer）**。
你也是本 stage 的 designer——**须在 verdict 里披露 `reviewer_prior_involvement="design"`**。
本轮职责是复核 Kimi 的实现对设计的**保真度与正确性**。**红线：只评审、不改码**；
若判 REWORK，产出可直接派给 Kimi 的 `fix_start_prompt`，不要自己动手修。终审是独立
Fable5（review-2），你不做终审。

## 评审对象（delivery diff）

```
git diff 4549227e9f6528787fb8e69b72c0cd7c585611f4..71c9d89e28c68d729658814a6f9c34d6a266eb1e \
  -- . ':(exclude)reports/agent-runs/2026-07-private-account-ui-polish-v1/status.json'
```

先复算并核对 diff_fingerprint 是否 = `71c9d89e28c68d729658814a6f9c34d6a266eb1e:0f769162e4eb97d28f5e4e82048469ae9eba57c943ad12a722e9f3fd56c439c1`
（定义见 `schemas/review-verdict.schema.json`）。不一致则 verdict=BLOCKED。

须读原始工件：`00-task.md`、`10-design.md`、`11-adr.md`、`20-implementation.md`、
`60-test-output.txt`、`docs/api/public-market-contract.md`、
`schemas/api/public-market/snapshot.schema.json`、`backend/domain/snapshot.py`、
`frontend/index.html`、`frontend/self-check.js`、
`reports/api-samples/2026-07-private-account-ui-polish-v1/20260706T172648Z/`。

## 复核清单（对每条给出结论；发现问题按 severity 记 finding）

后端 / 契约：
1. 行级 `value_usdt` 语义：缺价/坏价/坏数量 → `null`（带 warning）；合法零 → `"0.00000000"`。
   实现须用独立于 `_usdt_value` 的变体（`_usdt_value_optional`），**不得**把「无价格」压成 0。
2. 顶层 `total_value_usdt` 聚合逻辑**未改**，anti-double-count 硬规则不回归。
3. `um_positions[]` **不带** `value_usdt`，形态不变。
4. schema：`value_usdt` = `decimal_string | null`，**未进 `required`**；`schema_version` 仍 `public-market-snapshot/v1`。
5. 契约文档：v0.4 amendment 为 **additive**，只加字段、不改既有字段/枚举语义。
6. 契约变更门证据：`reports/api-samples/<stage>/` 有 raw public `/api/v3/ticker/price` 样本 +
   `evidence-index.md` provenance；**非仅合成 fixture**。

前端：
7. 借币日息子行仅 `borrow_rate_source != null` 行展示；缺账户档回落 `daily_interest_vip0` 标「参考」；
   正费率/无成本腿行不展示。
8. `negative_funding_status` 派生**先结构优先级**（DISABLED_PERP_ONLY/BSTOCK/SPOT_ONLY 保持结构文案），
   **仅 PRIVATE_BORROW_VALIDATION_REQUIRED 行**按 `borrow_validation` 细分五文案；结构禁用行不派生「需私有验证」。
9. `#private-panel` 移到市场表 panel **之前**；缺失/`verified=false` 降级不白屏。
10. 每资产「折算 USDT」展示；null/缺失占位；隐私开关同时遮蔽余额与折算值。
11. UI 中文优先；前端零排序；前端不反算 total。

测试：
12. 断言覆盖：null vs `"0.00000000"`、稳定币计 1、缺价 warning、um 无 value_usdt、结构优先级五文案、
    成本腿门控、面板前置、各降级/占位路径。self-check 与 pytest 全绿。

## 产出

把 verdict 写入 `reports/agent-runs/2026-07-private-account-ui-polish-v1/30-review-1.md`：
- 顶部一个**严格 JSON**（合 `schemas/review-verdict.schema.json`），字段至少：
  `schema_version=1`、`stage_id`、`role="first_reviewer"`、`model=<你的模型id>`、
  `verdict=ACCEPT|REWORK|BLOCKED`、
  `diff_fingerprint="71c9d89e28c68d729658814a6f9c34d6a266eb1e:0f769162e4eb97d28f5e4e82048469ae9eba57c943ad12a722e9f3fd56c439c1"`、
  `reviewer_prior_involvement="design"`、`reviewer_prior_involvement_notes`（披露你是 designer）、
  `reviewed_artifacts`、`findings`（每条 severity/title/evidence/impact/recommendation）、
  `required_fixes`、`next_action`。
  **REWORK 必须带 `fix_start_prompt`**（可直接派 Kimi 的有界修复文案，保留原始路径/findings/文件边界/
  测试命令/成功判据）。
- JSON 下方可附中文说明。无效 JSON 每模型最多 2 次。

判定基准：ACCEPT 仅当实现忠实于 10-design/11-adr 且契约 additive 边界、null/0 语义、
结构优先级、成本腿门控、证据门全部满足；有 P0/P1 → REWORK；无法复核(如 fingerprint 不符/
缺工件) → BLOCKED。

（RECEIPT 由 bookkeeper 更新，你不改本 prompt 文件。）
