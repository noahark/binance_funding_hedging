# Review 2

## Dispatch Receipt

- Human-dispatched Claude Session ID:
  `d4039913-9a87-4b9e-9e49-cf24e420c358`
- Requested model: `claude-fable-5`
- Operator-reported model fallback: Fable5 quota exhausted
- Actual reviewer model recorded by the local session: `claude-opus-4-8`
  (verdict literal `opus4.8`)
- Provider identity remains `anthropic`; reviewer prior involvement in this
  stage remains `none`
- The local session container also contains an earlier stage review. Only the
  final assistant response for this stage is preserved below.
- Session dispatch metadata reports `permissionMode=bypassPermissions`, not
  the requested plan mode. A current-stage tool audit found only Read and Bash
  inspection/test commands, no edit/write/commit/network tool calls, and the
  reviewer reported a clean worktree. This procedural variance is disclosed
  rather than hidden.
- Raw-response handling: the substantive final assistant response and exact
  final JSON are preserved verbatim below.

## Raw Reviewer Response

全部证据独立核实完毕，包括 bookkeeper 的对抗性复现（1500 早刷失败→旧条目经 1799 仍发布、1800 才过期），与代码读证一致。下面输出终审结论。

---

# Review-2 终审 — Funding History Refresh-Ahead（`2026-07-history-refresh-ahead-v1`）

## 执行者身份声明（重要偏差）

本 prompt 预设执行模型为 `claude-fable-5`。操作者告知 **fable5 额度已耗尽**，指派我（Anthropic Claude，实际模型 **opus4.8**）代为执行。因此我**不会**在 verdict 中谎标 `claude-fable-5`，而如实标注 `model: opus4.8`。资格不受影响：review-2 的 anti-self-review 回退是按 **provider 身份**判定的——设计者/簿记 Codex(`openai`)、实现 Claude-GLM(`zhipu_glm`)、review-1 Kimi(`moonshot_kimi`)与决审 provider `anthropic` 全部隔离；fable5→opus4.8 仍属同一 `anthropic` provider，`anti_self_review_ineligible` 回退成立。我在本 stage 无任何实现/设计/簿记参与（`reviewer_prior_involvement: none`），全新只读会话，未编辑/提交/联网/调用 Binance 或其他模型。

## 绑定核验

- base `12b8e1c` → head `2cb72fd` 均存在；分支 `stage/2026-07-history-refresh-ahead-v1`，worktree 干净。
- 独立重算指纹 = `2cb72fd870b1ef29cc4787e7dff102ab56bf8601:a1406bde574ed193c12ee826f56102e99d6db029f6742d4412b44fea344b1ef3`，与权威值**完全一致**。
- 代码作用面极小：仅 `snapshot_service.py`(+24) 与 `test_background_worker.py`(+95)，其余为报告/ACTIVE.json，未越三文件边界。

## 焦点项独立核验

1. **刷新/发布 TTL 真正分离，`_all_valid_history()` 未继承 1500**：`_all_valid_history()`（`snapshot_service.py:815`）仍用完整 `self.config.funding_history_cache_ttl_seconds`(1800) 判发布过期；新增 `_history_refresh_ttl()`(853) = `max(0, ttl-300)` 仅供刷新判定。分离成立。

2. **两处刷新判定同源**：`_history_is_fresh()`(868) 与 `_fetch_history_for()` 复用守卫(836) 均用 `_history_refresh_ttl()`。二者一致，不存在"判 due 但复用旧缓存"的错配。测试 `test_history_1499_reuses_cache_without_public_call`（1499 复用、`history_calls` 不增）与 `test_history_1500_performs_real_public_call`（1500 触发真实 I/O 且缓存重戳到 1500）证明边界。

3. **早刷失败保旧、不制造假新鲜、不覆盖**：`_fetch_history_for` 异常时在写缓存**之前** `return None`(848-849)，失败绝不入缓存；成功才在 850 行以 `now` 重戳。`test_all_valid_history_publishes_old_entry_through_1799` + bookkeeper 对抗复现（1500 早刷 OSError→旧条目 1500/1799 仍发布、1800 过期）双证。

4. **成功早刷消除 1800 后的正常空窗**：1500 成功早刷把缓存重戳到 1500，原 1800 边界处刷新条目仍可发布。`test_successful_early_refresh_keeps_history_present_after_1800`（1801 仍在 overlay）证明。

5. **borrow/max-borrowable 仍 1800，其余路径未动**：`_sweep_group_c`(1163) `component_ttl = funding_history_cache_ttl_seconds`(1800) 驱动 `_borrow_rate_due`/`_max_borrowable_due`(1181/1184)，本 stage 未改。`test_borrow_components_not_due_at_1500`（1500 时 history I/O +1，而 `next_hourly_calls`/`max_borrowable_calls` 不增）证明组件独立。config 默认/env、coverage/re-entry、Group B、私有传输、cursor≤10、API/schema/前端/交易均未触及（git diff 已证 config.py 等未变）。

6. **TTL≤300 的 clamp 一致**：`max(0,...)` 使 refresh_ttl=0，`_history_is_fresh` 恒 False→每次 cursor 访问都刷新，与冻结公式一致；压力仍受 ≤10/tick cursor 上限约束，非默认路径（默认 1800），不构成阻塞性回归。

7. **测试有意义、证据可信**：5 个新测试用 monkeypatch monotonic + 计数真实 stub 调用，非重言；覆盖 1499/1500、1800 发布边界、连续发布、私有隔离。我**独立重跑**：focused `37 passed`、full `335 passed`、`py_compile` OK、`git diff --check` 干净、`git status --short` 干净——与记录的 37/335 一致；bookkeeper 对抗复现有效。

8. **review-1 合规且不盲从**：Kimi JSON schema 合法、指纹绑定、provider 隔离(`moonshot_kimi`)、findings 空、`reviewer_prior_involvement: none`。我独立复核了其全部核对项，结论一致，但判决基于我自己的读证而非其结论。

## 结论

需求保真、正确性、无回归、测试充分、无隐藏网络工作、边界受控。无任何须修正项。判 **ACCEPT**，`next_action: stage_accepted_waiting_user`（不授权合并到 `main`，等待操作者处置）。作为 review-2 决审为本 gate 终局，不请求二次意见。

两条非阻塞观察（列入 residual_risks，不构成 finding）：① 继承的 `_fetch_history_for` pre-fetch 时间戳 P3 —— 冻结非目标，本 stage 明确不修，方向安全（略早过期，不会陈旧冒充新鲜）；② `60-test-output.txt` 记录派发期有一次凭证在终端展开的操作事故，评审确认**未写入任何仓库工件**、操作者已知情选择不轮换 —— 属运维事项、在本 diff 范围外，仅如实转述提示操作者。

```text
本地北京时间: 2026-07-15 12:32:30 CST
下一步模型: human
下一步任务: 操作者处置 ACCEPT——决定是否将已验收 stage 分支合并入 main；并注意 verdict 实际由 opus4.8 代 fable5 执行(同 anthropic provider)，簿记如需可据此更正 review-2 模型记录
```

{"schema_version":1,"stage_id":"2026-07-history-refresh-ahead-v1","role":"final_reviewer","model":"opus4.8","verdict":"ACCEPT","diff_fingerprint":"2cb72fd870b1ef29cc4787e7dff102ab56bf8601:a1406bde574ed193c12ee826f56102e99d6db029f6742d4412b44fea344b1ef3","reviewer_prior_involvement":"none","reviewer_prior_involvement_notes":"This prompt was authored for claude-fable-5, but the operator reported fable5 quota exhausted and directed Anthropic Claude opus4.8 to execute as substitute. The verdict truthfully records model=opus4.8 rather than falsely stamping claude-fable-5. Review-2 eligibility is provider-based: opus4.8 shares the same anthropic provider identity as fable5, so the documented anti_self_review_ineligible fallback (Codex/openai is the stage designer/bookkeeper; unrelated registered anthropic provider selected) still holds. Fresh read-only session; no implementation/design/bookkeeping involvement by this reviewer in stage 2026-07-history-refresh-ahead-v1; provider isolation from implementer zhipu_glm, designer openai, and reviewer-1 moonshot_kimi preserved.","reviewed_artifacts":["AGENTS.md","workflows/templates/stage-delivery.yaml","agents/skills/code-reviewer.md","schemas/review-verdict.schema.json","reports/agent-runs/2026-07-history-refresh-ahead-v1/00-intake.md","reports/agent-runs/2026-07-history-refresh-ahead-v1/00-task.md","reports/agent-runs/2026-07-history-refresh-ahead-v1/10-design.md","reports/agent-runs/2026-07-history-refresh-ahead-v1/11-adr.md","reports/agent-runs/2026-07-history-refresh-ahead-v1/20-implementation.md","reports/agent-runs/2026-07-history-refresh-ahead-v1/30-review-1.md","reports/agent-runs/2026-07-history-refresh-ahead-v1/60-test-output.txt","backend/services/snapshot_service.py","backend/tests/test_background_worker.py","git diff 12b8e1c1ea5d86bf692bbba2183de08ee9429af4..2cb72fd870b1ef29cc4787e7dff102ab56bf8601"],"findings":[],"required_fixes":[],"residual_risks":["继承的 _fetch_history_for pre-fetch success-timestamp P3 属本 stage 冻结非目标、未修；方向安全(略早过期，绝不使陈旧冒充新鲜)，非阻塞。","TTL<=300 配置下 refresh_ttl 被 clamp 为 0，每次 cursor 访问都会刷新历史；受 <=10/tick cursor 上限约束、非默认(默认1800)，非阻塞。","60-test-output.txt 记录派发期一次凭证在终端展开的操作事故；评审确认未写入任何仓库工件、操作者已知情选择不轮换——运维事项、在本 diff 范围外。","执行模型偏差: 本 verdict 实际由 opus4.8 代 claude-fable-5 执行(同 anthropic provider，资格不变)；合并前簿记如需应据此更正 review-2 模型记录。"],"next_action":"stage_accepted_waiting_user"}
