<!-- ============ RECEIPT（审计元数据；非任务内容） ============
status: pending             # pending | running | done | escalated
stage_id: 2026-07-private-account-ui-polish-v1
stage_branch: stage/2026-07-private-account-ui-polish-v1
node: review-1 (round-2 / v1.1-ui-polish-2)
target_model: codex         # first_reviewer；披露 prior_involvement=design（含 v1.1 增量设计）
role: first_reviewer        # 依 Hard Gates 非 implementer/fixer；本 review 不改码
role_chain: designer=Codex → implementer=Kimi → review-1=Codex(设计者复核实现保真) → review-2=Claude/Fable5
base_sha: 4549227e9f6528787fb8e69b72c0cd7c585611f4
head_sha: ec327466a9ec28be6158aedfc53541ea2b3e463c
diff_fingerprint: ec327466a9ec28be6158aedfc53541ea2b3e463c:7bee17041882e913317e1dc490e67862e8d00351308392d191a20f22a6a5997d
supersedes: round-1 review(30-review-1.md, fingerprint 71c9d89…, 已入 status.review_history)
adapter_cmd: 用户以「读此文件并执行 PROMPT BODY」一行指令发至 Codex 终端
bookkeeper_precheck: fingerprint 复算一致; 红线全held(schema 零改/仅排 balances_* 不碰 frozen rows/total 遍历原始 list 不受重排/契约 additive/后端时间字段不变); 160 pytest+self-check+schema 全绿; P3 观察见清单 12(仅供参考,你须自行复核)
next_dispatch: 通过 → Fable5 review-2 终审; REWORK → Kimi 按 fix_start_prompt 修
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行） ---

你是 stage `2026-07-private-account-ui-polish-v1` 的 **review-1（first_reviewer）**,复核
**round-2 / v1.1-ui-polish-2(item 5–10)** 的实现保真度与正确性。你也是本 stage 的
designer(含 round-1 与 v1.1 增量设计)——**须在 verdict 里披露
`reviewer_prior_involvement="design"`**。**红线:只评审、不改码**;若判 REWORK,产出可直接
派给 Kimi 的 `fix_start_prompt`。终审是独立 Fable5(review-2)。

本轮评审的是**合并 delivery**(round-1 value_usdt + 前 4 项,与 round-2 六项一并交付),
但请重点核 round-2 增量(round-1 已在 round-1 review ACCEPT 过,记录于
`status.review_history`;本轮 verdict 覆盖整个合并 diff)。

## 评审对象

```
git diff 4549227e9f6528787fb8e69b72c0cd7c585611f4..ec327466a9ec28be6158aedfc53541ea2b3e463c \
  -- . ':(exclude)reports/agent-runs/2026-07-private-account-ui-polish-v1/status.json'
```

先复算并核对 diff_fingerprint 是否 =
`ec327466a9ec28be6158aedfc53541ea2b3e463c:7bee17041882e913317e1dc490e67862e8d00351308392d191a20f22a6a5997d`
（定义见 `schemas/review-verdict.schema.json`）。不一致则 verdict=BLOCKED。
只想看 round-2 增量可另跑 `git diff 71c9d89..ec32746`。

须读:`00-task.md`(§Scope 增补)、`10-design.md#v1.1-ui-polish-2 Design Addendum`、
`11-adr.md#ADR-7/8/9`、`20-implementation.md`、`60-test-output.txt`、
`docs/api/public-market-contract.md`、`schemas/api/public-market/snapshot.schema.json`、
`backend/domain/snapshot.py`、`backend/tests/test_private_account_v1.py`、
`backend/tests/test_snapshot.py`、`frontend/index.html`、`frontend/self-check.js`。

## 复核清单(每条给结论;问题按 severity 记 finding)

红线:
1. **排序仅作用 `balances_*`**:`_balance_sort_key` 只排 `assemble_private_account` 的
   `unified_out`/`spot_out`;`sort_rows()`、市场 `rows` 顺序、`sort_basis` 未改;有回归断言守护。
2. **排序不影响聚合**:`total`/`total_value_usdt` 仍遍历原始 `unified_list`/`spot_list`,
   重排 out 数组不改总额;anti-double-count 不回归。
3. **无契约字段/枚举/`schema_version` 变更**:schema 本轮零改动;`value_usdt`/`priced_at`/
   `checked_at`/`price_source` 字段不变;契约仅追加 additive 展示顺序说明。
4. **排序语义**:`(null-flag, -value, asset, idx)` → value DESC、null 末位、asset ASC、
   同 asset 稳定;pytest 覆盖 unified 与 spot。
5. **后端时间字段不变**:item 9 纯前端;`valuation.priced_at = checked_at` 与顶层
   `checked_at` 后端输出不变。

前端:
6. item 5 行内折算 `【: xxx.xx USDT】`:2 位 ROUND_HALF_UP 走 decimal-string(非
   `Number.toFixed`);null/缺失 → `【: — USDT】`;合法零 → `【: 0.00 USDT】`;隐私开关同时遮蔽
   金额与折算值;前端不重算/不反推 total。
7. item 7 删「估值来源」卡;payload `price_source` 仍在。
8. item 8 删侧栏运行约束「不连接 Binance」;无「无 key/不连接」替代文案。
9. item 9 副标题 verified=true→`资产更新时间 <时间>`(checked_at→priced_at→—)、
   verified=false→`私有账户未读取`;删「估值时点」「检查时点」两张卡。
10. item 10 审计文案:区分「行情公开 / 账户私有只读」,保留「只读=不下单/不划转」,
    删除与私有 signed HMAC 通道矛盾的旧表述;逐条与 backend 真实行为一致。
11. UI 中文优先;前端零排序(只渲染 payload 顺序);各降级/占位不白屏。

清理:
12. bookkeeper 预检发现两处 P3(请定性,非阻塞前置判断):
    (a) DOM `.sidebar-footer` 块已删,但 CSS `.sidebar-footer` 规则(约 index.html:135、498)
        成孤儿死样式;
    (b) 静态占位 `<p id="private-panel-subtitle">只读资产视图</p>`(约 index.html:570)仍在,
        虽 verified=true/false 两分支 JS 均覆盖、面板 display:none 至渲染故永不可见,但与新文案
        矛盾的死文本。
    判断这些是否需要 P3 清理(要求 Kimi 顺手删)或可接受为残留。

测试:
13. 断言覆盖:排序 DESC/null-last/asset-ASC/同 asset 稳定、市场 rows 顺序回归、formatUsdt2
    2 位 half-up/null 占位/合法零、副标题资产更新时间、删卡与删文案、隐私遮蔽折算值。
    self-check 与 pytest 全绿。

## 产出

verdict 写入 `reports/agent-runs/2026-07-private-account-ui-polish-v1/30-review-1-v1.1.md`:
- 顶部**严格 JSON**(合 `schemas/review-verdict.schema.json`):`schema_version=1`、`stage_id`、
  `role="first_reviewer"`、`model=<你的模型id>`、`verdict`、
  `diff_fingerprint="ec327466a9ec28be6158aedfc53541ea2b3e463c:7bee17041882e913317e1dc490e67862e8d00351308392d191a20f22a6a5997d"`、
  `reviewer_prior_involvement="design"`、`reviewer_prior_involvement_notes`(披露你是 designer)、
  `reviewed_artifacts`、`findings`(severity/title/evidence/impact/recommendation)、
  `required_fixes`、`next_action`。**REWORK 必带 `fix_start_prompt`**。
- JSON 下方可附中文说明。无效 JSON 每模型最多 2 次。

判定基准:ACCEPT 仅当 round-2 实现忠实于 Addendum/ADR-7-9、五条红线全守、契约 additive、
排序语义正确;有 P0/P1 → REWORK;无法复核(fingerprint 不符/缺工件)→ BLOCKED。P3 单独列
findings 不必然阻断 ACCEPT,由你按工程判断给 required_fixes 或 residual_risks。

（RECEIPT 由 bookkeeper 更新,你不改本 prompt 文件。）
