[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。禁止调用/启动/转派任何其他模型会话或 adapter 命令；
禁止编造未执行的命令结果或未读取的文件内容；只依据本 prompt 列出的 raw artifact
路径与你实际读取的文件。

# Review-2 Round 2（整 stage 终审）— Hedge Open Live v1（Codex/GPT）

你是本 stage review-2 第 2 轮，read-only，GPT/Codex（`openai`），未参与本 stage
任何设计/breakdown/实现/fix，`reviewer_prior_involvement` 填 `none`。第 1 轮你给
REWORK（F-007 leg_exposure 契约漂移）；Claude-GLM 已完成 hedge-be fix-2（F-007）
与 fix-3（用户澄清 DI-6：去掉成交数量校验，双腿成交即 success）。本轮确认 F-007
修好、fix-3 语义正确、both-mismatched 已由 fix-3 自然消解、无回归。

## 严格只读与安全边界
同第 1 轮：只读、不读凭据、不发外部请求、不转派；只审固定 `base_sha..head_sha`。

## 固定审查身份与范围（更新到 fix-2 后）
- Stage `2026-07-hedge-open-live-v1`，Role `final_reviewer`，Round 2
- Base `6639b0025682f406f9a726104ef8d3b9e6f8fadd`
- Head `02bcc24abe134dcdb0541af462cea765ffc5cbdf`
- Fingerprint `02bcc24abe134dcdb0541af462cea765ffc5cbdf:1b771bc938a907d3cd024421dc35d070f821f57a312296ae9b88dee7d2c95bbf`
- 看改动：`git diff 6639b002..02bcc24`；fix-2+fix-3 增量 `git diff bd01eb52..02bcc24`
- 自复现 fingerprint 逐字符比对：
  `sha256(git diff --binary <base>..<head> -- . ':(exclude)reports/agent-runs/2026-07-hedge-open-live-v1/status.json')`
- 环境注：python 可能不在 PATH，用 `.venv/bin/python -m pytest backend/tests -q`
  跑全量（应 790 passed）；`node frontend/self-check.js`（应 108）。

## 必读
- `reports/agent-runs/2026-07-hedge-open-live-v1/`
  `{50-review-2.md（你的第 1 轮 verdict）,40-fix-2-hedge-be.md,40-fix-3-hedge-be.md,
  design-inputs.md（DI-6 下单参数模型缺陷，明确留真实 API 轮）,
  12-development-breakdown.md §3.2,60-test-output.txt fix-2/fix-3 段}`
- 源码：`backend/hedge_open_tasks/domain.py`（build_leg_exposure + classify_attempt）、
  `backend/tests/test_hedge_{api,domain,service,executor}.py`、`frontend/index.html`
  （leg_exposure 消费，未改）
- `schemas/review-verdict.schema.json`

## 本轮重点
1. **F-007 已修** ✅ 核对：`build_leg_exposure` 现 emit §3.2 `{leg,qty,price,ts}`；
   spot-only→`leg="spot"`、perp-only→`leg="perp"`，`qty`/`price` 取该腿实际值
   （decimal string，与 Fill §3.3 一致）；前端 `index.html:3600` 消费 leg/qty/price
   现与后端一致。新增 HTTP 级 spot-only + perp-only 两方向回归。
2. **fix-3：classify_attempt 去成交数量校验**（用户澄清 DI-6）：双腿都 FILLED →
   `ATTEMPT_SUCCESS`（不再比较成交数量）；恰一腿 FILLED → `single_leg_exposure`；
   都没 → `failed`；累计 >3 → 暂停。核对语义正确、与 DI-6 一致（正反向下单方式
   差异——现货市价买传 quoteOrderQty、其余传 quantity——使成交基础币数量不可预先
   对齐，故本轮不做数量校验）。**注**：fix-3 使双腿成交一律 success，fix-2 那个
   both-filled-but-mismatched→exposure/leg_exposure=null 路径自然消解。DI-6 的下单
   参数模型重构（现货买用 quoteOrderQty、共同网格取整在正向不适用等）明确留真实
   API 轮——确认本轮未擅自改它。
3. **无回归**：F-001/F-002/R4-001 等已修项仍成立；borrow 零改动；无真实网络/下单；
   dry-run record transport 不含密钥/签名；确认无第四处同类 seam 漂移。
4. 独立跑全量 pytest（790）与 self-check（108），结果写入正文。

## 输出
- 终审正文写实际读取/运行的证据与判断。
- 结尾唯一 schema-valid JSON：`role:"final_reviewer"`、`diff_fingerprint`（上面新串）、
  `reviewer_prior_involvement:"none"`、findings/required_fixes/next_action。若 F-007
  修好且 both-mismatched 降级本轮可接受、无回归 → `ACCEPT`；否则 `REWORK` +
  `fix_start_prompt`。
- 追加 Output Footer 六行置于 JSON 前。写完即停。
