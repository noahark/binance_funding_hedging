[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。禁止调用/启动/转派任何其他模型会话或 adapter 命令；
禁止编造未执行的命令结果或未读取的文件内容；只依据本 prompt 列出的 raw artifact
路径与你实际读取的文件。

# Review-2 Round 2（整 stage 终审）— Hedge Open Live v1（Codex/GPT）

你是本 stage review-2 第 2 轮，read-only，GPT/Codex（`openai`），未参与本 stage
任何设计/breakdown/实现/fix，`reviewer_prior_involvement` 填 `none`。第 1 轮你给
REWORK（F-007 leg_exposure 契约漂移）；Claude-GLM 已完成 hedge-be fix-2。本轮确认
F-007 是否修好、bookkeeper 对 both-mismatched 的处理是否可接受、有无回归。

## 严格只读与安全边界
同第 1 轮：只读、不读凭据、不发外部请求、不转派；只审固定 `base_sha..head_sha`。

## 固定审查身份与范围（更新到 fix-2 后）
- Stage `2026-07-hedge-open-live-v1`，Role `final_reviewer`，Round 2
- Base `6639b0025682f406f9a726104ef8d3b9e6f8fadd`
- Head `f05b61dfd688616dd7e4f6d39db1460b19f6232c`
- Fingerprint `f05b61dfd688616dd7e4f6d39db1460b19f6232c:24f505b87d6985d8cec21c8003923ca6532aa9d3af8910b8226e8e0a58dfc7c8`
- 看改动：`git diff 6639b002..f05b61d`；fix-2 增量 `git diff bd01eb52..f05b61d`
- 自复现 fingerprint 逐字符比对：
  `sha256(git diff --binary <base>..<head> -- . ':(exclude)reports/agent-runs/2026-07-hedge-open-live-v1/status.json')`
- 环境注：python 可能不在 PATH，用 `.venv/bin/python -m pytest backend/tests -q`
  跑全量（应 790 passed）；`node frontend/self-check.js`（应 108）。

## 必读
- `reports/agent-runs/2026-07-hedge-open-live-v1/`
  `{50-review-2.md（你的第 1 轮 verdict）,40-fix-2-hedge-be.md（fix 报告 + both-
  mismatched ESCALATED 说明）,12-development-breakdown.md §3.2,60-test-output.txt
  fix-2 段}`
- 源码：`backend/hedge_open_tasks/domain.py`（build_leg_exposure）、
  `backend/tests/test_hedge_{api,domain,service}.py`、`frontend/index.html`
  （leg_exposure 消费，未改）
- `schemas/review-verdict.schema.json`

## 本轮重点
1. **F-007 已修** ✅ 核对：`build_leg_exposure` 现 emit §3.2 `{leg,qty,price,ts}`；
   spot-only→`leg="spot"`、perp-only→`leg="perp"`，`qty`/`price` 取该腿实际值
   （decimal string，与 Fill §3.3 一致）；前端 `index.html:3600` 消费 leg/qty/price
   现与后端一致。新增 HTTP 级 spot-only + perp-only 两方向回归。
2. **both-filled-but-mismatched 的处理**：§3.2 单值无法无歧义表达双腿数量错配；
   fix-2 降级为 `leg_exposure=null` + 任务仍 `exposure_alert` 暂停 + 双腿细节留
   fills（ADR-4），未擅自扩展冻结 schema。**bookkeeper 已接受此降级并记为 live 轮
   契约 follow-up**（status.both_mismatched_contract_gap）。请判断该处理在**本 dry-run
   轮**是否可接受（任务正确暂停、不丢信号、不扩展契约），还是你认为本轮必须解决。
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
