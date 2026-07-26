<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: pending
target_model: codex/GPT-5 Codex
adapter_cmd:
executor: human_operator
started_at:
completed_at:
session_id: unavailable:pending human execution
outputs: reports/agent-runs/2026-07-hedge-open-real-api-v1/75-review-2-r3.md
next_dispatch: none
routing_reason: Codex is now the ONLY eligible reviewer of any kind for this stage. anthropic is hard-barred twice over (Claude Sonnet 5 authored the accepted frontend rework; Claude Opus 5 authored the r8 validator fix under review here), zhipu_glm is hard-barred as the backend author, kimi and grok are quota-unavailable. Codex never wrote delivery or fix code (model_routing.excluded_from_core_implementation_and_fix = ["codex"]). Full analysis: 46-review-2-routing-disclosure.md.
special_condition: THE REVIEWED RANGE NOW CONTAINS CODE THE BOOKKEEPER WROTE. The 77c75bd..1c09db4 delta is the r8 fix to scripts/validate-stage.py authored by Claude Opus 5 — the sitting bookkeeper and the author of six Review-1 rounds — and it was merged under a user special approval with NO model cross-review of any kind. This dispatch asks Codex to review it as first-and-only reviewer, not as a re-check.
design_conflict_override: used. Codex is this stage's designer (00-task.md, 10-design.md, 11-adr.md), direction synthesizer (06-direction-synthesis.md), author of three prior Review-2 rounds (50, 69, 74) and this stage's bookkeeper until 2026-07-25. reviewer_prior_involvement must be "design". Evidence: 46-review-2-routing-disclosure.md.
second_opinion_check: not a second opinion. 74-review-2-r2.md returned REWORK on the 77c75bd range with one P1; that P1 was fixed and this is the first final-gate review of the new 28c550d..1c09db4 range.
r10_checklist: task_prompt_path=75-review-2-r3.dispatch.md; self_tests_command per the body; next_dispatch_executor=bookkeeper; pass_branch=write 75-review-2-r3.md ending in a schema-valid JSON verdict and stop; blocker_branch=stop and escalate, the reviewer changes no business file; unavailable_branch failure_classes=[model_unavailable, adapter_missing, command_error, permission_error, timeout] escalating to this dispatch file.
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable） ===== -->

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本 stage 的正式 Review-2（终审门），本轮针对 packet 72 修复 + r8 特批修复之后的新范围。禁止调用、启动或转派任何其他模型会话或 adapter。

【可写】只有一个文件你可以写：
  reports/agent-runs/2026-07-hedge-open-real-api-v1/75-review-2-r3.md
【只读】除该文件外：绝不修改任何业务文件、绝不 commit、绝不读取凭据、绝不连接 Binance、绝不发送真实 POST、绝不启用 live 或 Start。

（上一轮 packet 74 把这条例外写在长句尾部，导致执行者误以为"只读"与"产出报告"矛盾。此处拆开写明。）

## ⚠️ 本轮最重要的一件事：被审范围里有 bookkeeper 自己写的代码

`77c75bd..1c09db4` 这段增量是 **`scripts/validate-stage.py` 的 r8 修复**，作者是
**Claude Opus 5 —— 本 stage 现任 bookkeeper，同时是 r2–r6 六轮 Review-1 的作者**。
它是在**用户特批、跳过全部模型评审**的情况下合入的（`29-user-special-approval-r8.md`）。

**你是这段代码的第一个也是唯一一个审查者，不是复核者。** 请像审任何未经评审的实现一样审它：

- 实现是否正确：`_collect_all_dispatch_refs()` 遍历整个 `status.json` 收集所有
  `*.dispatch.md` 引用，review 引用保留 `review_key` 继续参与根状态检查，其余传 `None`。
  这个设计是否有漏检、误报、性能或递归风险？标签是否可能与真实字段错位？
- 它是否**真的**修好了 `74-review-2-r2.md` 的那条 P1（packet 72 未被检出）？
- 新增的 5 条测试是否真能钉住修复，还是又一次"空回归"（本 stage 出现过这个问题，
  见 `66-review-1-backend-r4.md` P2-1）？请自己做反向验证。
- **bookkeeper 顺带做的 18 条历史回执封存**（14 条 `completed` + 4 条 `superseded`）
  是否只用了真实证据？它声称"未发明任何时间或 Session ID"、无记录字段一律
  `unavailable` 加原因、packet 72 用文件 mtime 并已标注"非模型自报"。**请抽验若干条**，
  比对 `*.dispatch.md` 回执与对应报告 footer 是否逐字一致。
- 那 4 条改为 `superseded` 的判定是否成立（它们声称"执行前即被取代，其 outputs 文件
  由后续 packet 产出"）？依据取自 `status.json` 的既有记录，请核对。

## 你的身份与必须如实披露的六件事

你是 GPT-5 Codex（provider `codex`）。你**从未**为本 stage 写过交付代码或修复代码，
终审的硬性 provider 禁令对你成立。以下六点必须在报告中如实披露：

1. **你是本 stage 的设计者与方向综合者**。适用 design-conflict 强审查者披露，
   `reviewer_prior_involvement` 写 `design`。按 `AGENTS.md`：**用户批准的方向综合与 PRD 是最高权威**；
   `10-design.md` / `11-adr.md` / breakdown 是**被审证据，不是权威**。
2. **你写了前三轮 Review-2**（`50`、`69`、`74`）。本轮仍在检查你自己此前的 finding 是否被正确解决 ——
   请**从代码重新推导**，不要复述旧报告；若你自己某条判错或夸大了，请**明说**。
3. **你曾是本 stage 的 bookkeeper**（至 2026-07-25），编号 66 之前的部分簿记是你自己写的。
4. **现任 bookkeeper 是 Claude Opus 5**，同一模型写了 r2–r6 六轮 Review-1，**现在又成了 r8 的
   代码作者**。请独立判断这个三重身份是否损害证据链：Review-1 的 ACCEPT 是否被簿记方不当影响、
   bookkeeper 的"独立复核"是否实际构成自证、reviewer 的 `fix_start_prompt` 是否被摘要替换、
   多轮 `status.json` 降级/重锚是否掩盖了任何证据。
5. **你现在是本 stage 唯一还有资格的审查者**（其余供应商或为代码作者、或无额度）。
   这意味着没有人能复核你 —— 请相应提高自我审慎，并在报告中说明这一点。
6. **`rework_count` 已 8/8 用尽**：若 verdict=REWORK，任何代码变更都需用户**新的书面授权**，
   bookkeeper 不能自行派发；请在报告中明说。

## 固定审查锚点（只审此已提交范围；不要改用移动的 HEAD）

- base: 28c550d87c1ca90983d5bde9c7102d42cffecd4e
- head: 1c09db491e8f89426b811be990929148f01c1d3c
- fingerprint: 1c09db491e8f89426b811be990929148f01c1d3c:a5b08463fb690d52687934ec6227783689e94aebc55a39ed51af461c941e7b78

其中 `77c75bd..1c09db4` 的业务改动仅两文件：`scripts/validate-stage.py`（+49/-4）与
`scripts/tests/test_validate_stage_dispatch_protocol.py`（+62）。`backend/**` 与 `frontend/**`
在该增量内零改动 —— 请自行复核这一点。

## 必须实际阅读

1. `AGENTS.md`；`workflows/templates/stage-delivery.yaml`；`schemas/review-verdict.schema.json`；
2. **最高权威**：`docs/product/PRD.md`、用户批准的 `06-direction-synthesis.md`，以及用户冻结的运行时合同
   `15`、`21`、`24`、`26`、`27`、**`28-user-authorized-r7-repair.md`**、**`29-user-special-approval-r8.md`**；
3. **被审证据（非权威）**：`00-task.md`、`10-design.md`、`11-adr.md`、`16-replacement-development-breakdown.md`；
4. 评审与修复链：**`74-review-2-r2.md`（你上一轮，其唯一 P1 是本轮重点）**、`69-review-2.md`、
   `73-review-1-backend-r6.md`（后端 ACCEPT）、`71-fix-review-2-backend-r7.md`、
   `59-review-1-frontend-r2.md`（前端 ACCEPT）、`60-test-output.txt`；
5. 实际 `git diff --binary 28c550d87c1ca90983d5bde9c7102d42cffecd4e..1c09db491e8f89426b811be990929148f01c1d3c`，
   以及 `backend/hedge_open_tasks/**`、`backend/services/**`、`backend/app/server.py`、`backend/config.py`、
   `frontend/index.html`、`frontend/self-check.js`、`backend/tests/**`、`scripts/validate-stage.py`。

## 用户冻结的业务合同（高于旧草案与你自己的设计稿）

- 每张任务卡独立；同一张卡严格先让第 N 组走到终态/对账结束，才可开始第 N+1 组。一组内两腿并发。
- `target_n` 是计划尝试组数硬上限，不因失败或单腿结果补发超出授权数量。
- 不得到 `orderId` 的未知结果必须按 clientOrderId 查询，绝不盲目重发；已受理订单继续查到终态。
- 429、余额/保证金/可用数量不足只暂停当前任务，等待人工恢复；不联动其它任务。
- 实时模式没有长期全局守护扫描器：启动时一次恢复交接；人工 Start/recover 只能启动指定卡。
- 固定 base `quantity=q_common` 并发两腿；不用 `quoteOrderQty`；常规统一账户。
- 默认关闭。没有本次实盘、Start、凭据或真实 Binance 请求授权。

## 用户明确排除项（不得因其未修而给 P0/P1 或据此 REWORK）

用户产品方向原话：「我们的目标是尽快上线验证，在实盘中再发现问题做优化。不要在设计阶段太关注低概率场景发生的事情」。

- **你上一轮的 F3**（人工 delete/pause 被迟到 worker 结果覆盖）—— 用户裁定暂不修。
- **你上一轮的 F5**（账户健康 `accountStatus`/`uniMMR` + 现货 `MIN_NOTIONAL`）—— 用户裁定不做；
  七端点 allowlist 保持冻结；用户以「输入端自行保证数量足够」作为操作约定
  （bookkeeper 已提示：输入的是数量、交易所卡的是名义金额＝数量×价格，需留余量；用户接受）。
- `73-review-1-backend-r6.md` 的两条 P2（计划组用尽后 Start 停在 running；validator 根状态检查单向）
  与全部既有 P3 —— 后置 follow-up。

若你认为其中任何一条的风险被低估，写入 `residual_risks` 或 P3 并说明理由即可。

## 终审必须覆盖的范围

1. **上文"最重要的一件事"** —— r8 代码 + 18 条回执封存的首次审查。
2. **`74-review-2-r2.md` 唯一 P1 的三条 `required_fixes` 是否全部完成**：
   (a) bookkeeper 依真实证据封存 packet 72 回执；(b) 取得用户新的书面授权；
   (c) 实现并测试 validator 修复使当前活跃实现/修复派发也被检查。
3. **交付是否满足用户批准的方向与 PRD**：即时开单闭环、开单日志/entries 分页、持仓面板、风险与实盘门控。
4. **安全门**：默认关闭；七端点冻结 allowlist；签名前置门；凭据绝不出现在日志/响应/前端；
   real POST 未授权时不可达；`frontend/` 无跨域、无外域 fetch、无 Binance 直连。
5. **交易正确性**：两腿并发与同卡串行；`target_n` 原子硬上限；ADR-2 绝不重发；clientOrderId-only 查询；
   对账绝不放弃；429 / 余额不足只暂停本卡；fatal 只停本卡；单腿敞口如实记录；
   `consecutive_submission_failures` 对 `single_leg` 增长的语义变更是否与 `16` §I-2 一致。
6. **证据链与治理**：八次用户授权是否都有落盘证据；`rework_count` 8/8 是否如实；
   `29-user-special-approval-r8.md` 是否**如实记录了跳过评审的代价**而非淡化；
   两个已完成评审（`73`、`74`）的锚点是否被正确钉在它们实际审的范围上。
7. **测试**：核对 918 backend / 72 validator / 前端自检 / `git diff --check` 的原始证据，并独立复跑。

## 自测命令（供你独立复跑）

```bash
.venv/bin/python -m pytest backend/tests -q
node frontend/self-check.js
.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
.venv/bin/python scripts/validate-stage.py 2026-07-hedge-open-real-api-v1 --phase pre-review
git diff --check
```

输出完整原始评审到：
`reports/agent-runs/2026-07-hedge-open-real-api-v1/75-review-2-r3.md`

先写中文叙述、findings（P0/P1/P2/P3）与可核对证据，再写标准 Session footer。文件最后一个顶层 JSON 对象必须严格匹配 `schemas/review-verdict.schema.json`：`role=final_reviewer`、`model=GPT-5 Codex`、`reviewer_prior_involvement=design`、`diff_fingerprint` 必须逐字等于上面值，并在 `reviewer_prior_involvement_notes` 中写明上文六点披露。

若 verdict=ACCEPT，请明确说明：本次 ACCEPT **不**解除任何实盘门（`APP_HEDGE_EXECUTOR=live`、
Start 闸门、第一笔真实订单仍是三道独立的人类授权），并说明 stage 是否可以进入用户验收与实盘测试。
完成后停止等待 bookkeeper。

当前 Session ID: report provider-native ID, or unavailable:<reason>
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/75-review-2-r3.md
本地北京时间: obtain from local date command
下一步模型: bookkeeper
下一步任务: validate this final-gate verdict and route the stage to user acceptance or a newly authorized fix
```

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/75-review-2-r3.dispatch.md
本地北京时间: 2026-07-27 CST
下一步模型: human operator
下一步任务: run the prompt body in a fresh read-only Codex session
