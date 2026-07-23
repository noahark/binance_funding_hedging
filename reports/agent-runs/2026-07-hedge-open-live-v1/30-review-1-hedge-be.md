# Review-1 Raw Artifact — Task hedge-be (Kimi)

Archived by the bookkeeper from the human-operator-returned raw output of the
fresh-context Kimi (`moonshot_kimi`, `kimi-code/kimi-for-coding`) review-1 of
task hedge-be. Operator-reported local time 2026-07-23 07:15:34 CST. Executor:
human operator (dispatch only). Reviewer is the hedge-fe implementer (disclosed
parallel cross-review; not the hedge-be author), cross-provider from the
hedge-be implementer Claude-GLM. Content preserved verbatim.

---

固定范围 `6639b002..b773a470`，指纹独立重算逐字匹配
`b773a470…:d904f8f08e787a238dac2cf1790a01fca03279e7c213c4d429b6a6f61857bd28`。
当前分支 HEAD 在 b773a470 之上有 3 个 bookkeeper chore 提交（仅 status/证据），
审查锚定固定 range，工作树干净。

## 实际读取/运行的证据
- 必读 artifact 全部读取（00-task/10-design/11-adr/12-breakdown/design-inputs/
  20-implementation-hedge-be/r4-reconciliation/60-test-output/order-endpoints-
  filters-recon/review-verdict.schema）。
- 源码逐行：`backend/hedge_open_tasks/{__init__,domain,store,service,executor,
  scheduler}.py`、`server.py` 的 hedge 路由 diff（borrow 零改动）、5 个
  `test_hedge_*.py`。
- 独立重跑 `python -m pytest backend/tests -q` → 785 passed, exit 0。
- 独立 grep：`backend/hedge_open_tasks/` 无 urllib/requests/socket/hmac/hashlib/
  ssl 命中（+ 测试内 AST 证明 + urllib monkeypatch 运行期证明）。
- 实证脚本（临时 sqlite）复现 F-001/F-002。

## 审查重点结论
1. 共同网格取整（ADR-2）— 通过（decimal_lcm/floor_to_grid/两腿同一 q_common，
   逐腿 min/max/minNotional 校验，测试覆盖相等/不等/互质/整数 step）。
2. 安全闸门（ADR-5）— 通过（live 也只构造 RecordTransportExecutor，真实 POST
   结构性不可达；Start gate 默认关且 tick 受门控；record 无 apiKey/signature/
   timestamp/recvWindow）。
3. 单腿敞口状态机（ADR-4）— 通过（dry-run 语义内；对账钩子随 live 轮接入，与
   10-design §7 括号注一致）。
4. NO_SIDE_EFFECT/反向不自动借币（ADR-3）— 通过。
5. API 契约（§3）— **两项违反 F-001(P1)/F-002(P2)**；其余符合。
6. 契约保真 + 无回归 — 通过（server.py 仅新增；785 全绿；镜像 borrow_tasks；零网络）。

## 发现
- **F-001（P1）** `GET /api/hedge-open-tasks?status=all` 不含 deleted，违反 §3.1
  （'default excludes deleted unless status=deleted|all'）。`filter_status_for_list
  ('all')` 返回 None → `list_tasks(None)` 执行 `WHERE status != 'deleted'`，all
  = 默认。实证：删一个任务后 `list_tasks('all')` 返回空。FE `index.html:3323-3327`
  固定拉 `?status=all` 依赖 deleted 在其中（已删除筛选永远为空）。BE 自测
  `test_filter_status_for_list_mapping` 把错误行为钉成断言——与 R4-001 同类
  mock-masked seam-drift。
- **F-002（P2）** `mode="smooth"` 被 BE 接受且会被 immediate 引擎执行。契约 §3.1
  冻结 `mode="immediate"` 本轮；FE 已本地拒绝 smooth。`validate_mode` 接受 smooth，
  `list_eligible_tasks` 不过滤 mode。实证：`mode:'smooth'` 创建返回 201 且被 1s
  调度。fail-open。应在 `create_task` 拒绝非 immediate。
- **F-003（P3）** `_qty_bounds` 单源取 min/max，偏离 recon §C（未被 MARKET_LOT_SIZE
  覆盖的约束仍按 LOT_SIZE）；零值字符串 `"0.00000000"` 漏判。live 轮前修。
- **F-004（P3）** 限频节流只存不 enforce；preflight snapshot_record 丢
  rate_limit_order。live 轮缺口。
- **F-005（P3）** AttemptContext docstring 称"persist attempt first"与代码（先
  execute 后 insert_fill）不符；live 轮按此接线会违反 ADR-4「发送前持久化」。
- **F-006（P3）** `post_fill_all` 对 ATTEMPT_DISABLED 空转至 guard=10_000（仅进程内
  注入 DisabledHedgeExecutor 可达，HTTP 不可达）；fill-once/fill-all 绕过 Start gate
  是文档化本轮决策，live 轮必须重审。

F-001/F-002 需修 → REWORK；F-003~F-006 记录为 live 轮 follow-up。

当前 Session ID: unavailable (Kimi CLI 会话内无可观测 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-v1/30-review-1-hedge-be.md
本地北京时间: 2026-07-23 07:15:34 CST
下一步模型: bookkeeper（随后 fix 实现者 Claude-GLM）
下一步任务: bookkeeper 收 REWORK → 派 hedge-be fix-1（F-001/F-002）→ 复跑 → 重算指纹 → 重进 review-1

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-open-live-v1",
  "role": "first_reviewer",
  "model": "moonshot_kimi/kimi-code/kimi-for-coding",
  "verdict": "REWORK",
  "diff_fingerprint": "b773a470de62053207b85e58148bbf7c285026fd:d904f8f08e787a238dac2cf1790a01fca03279e7c213c4d429b6a6f61857bd28",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "Parallel cross-review: Kimi is the implementer of sibling task hedge-fe, zero involvement in hedge-be design/breakdown/implementation (Claude-GLM, different provider); provider-level isolation holds, no self-review.",
  "reviewed_artifacts": [
    "00-task.md","10-design.md","11-adr.md","12-development-breakdown.md","design-inputs.md","20-implementation-hedge-be.md","r4-reconciliation.md","60-test-output.txt","order-endpoints-filters-recon.md","review-verdict.schema.json",
    "git diff 6639b002..b773a470 (fingerprint independently recomputed and matched)",
    "backend/hedge_open_tasks/{__init__,domain,store,service,executor,scheduler}.py","backend/app/server.py (hedge routes only)","backend/tests/test_hedge_*.py",
    "independent run: pytest backend/tests -q -> 785 passed exit 0",
    "independent grep: no urllib/requests/socket/hmac/hashlib/ssl under hedge_open_tasks/",
    "empirical repro script (temp sqlite) confirming F-001 and F-002"
  ],
  "findings": [
    {"severity":"P1","title":"GET ?status=all excludes deleted, violates frozen §3.1 and breaks FE deleted-filter seam","file":"backend/hedge_open_tasks/domain.py","line":702,"evidence":"filter_status_for_list('all')->None; store.list_tasks(None) runs WHERE status!='deleted'; all == default. Repro: after delete, list_tasks('all')=[] while list_tasks('deleted') returns it. FE index.html:3323-3327 fetches ?status=all relying on deleted presence; that filter is permanently empty against real BE. BE test_filter_status_for_list_mapping pins the wrong behavior — same mock-masked class as R4-001.","impact":"Cross-task frozen-contract violation; FE soft-delete visibility silently breaks; both suites green because each mocks its own side.","recommendation":"Make status=all include deleted; fix test_filter_status_for_list_mapping; add HTTP-level test."},
    {"severity":"P2","title":"mode=smooth accepted by BE and dispatched by immediate engine instead of rejected","file":"backend/hedge_open_tasks/domain.py","line":609,"evidence":"§3.1 freezes mode=immediate; FE rejects smooth locally. validate_mode accepts smooth; list_eligible_tasks doesn't filter mode. Repro: create mode:'smooth'->201 running, appears in list_eligible_tasks(); executed by 1s immediate scheduler.","impact":"Fail-open at the API: a client bypassing FE creates a smooth-labeled task executed as immediate — wrong semantics for a real-funds surface.","recommendation":"Reject mode!='immediate' in create_task with invalid_field('mode',...); add test."},
    {"severity":"P3","title":"_qty_bounds single-source min/max instead of LOT_SIZE fallback","file":"backend/hedge_open_tasks/domain.py","line":290,"evidence":"Recon §C: constraints not covered by MARKET_LOT_SIZE still validated by LOT_SIZE. _qty_bounds picks one source for both min/max; market max=0 disabled -> no max. Source test misses zero strings like '0.00000000'.","impact":"Latent filter gap; no impact this round; weakens live-round rejection.","recommendation":"Per-constraint fallback + normalize zero-valued step strings before live round."},
    {"severity":"P3","title":"Rate-limit throttle stored but never enforced; snapshot drops rate_limit_order","file":"backend/hedge_open_tasks/store.py","line":549,"evidence":"PreflightSnapshot.rate_limit_order and set_rate_limit_order have no caller; snapshot_record omits rate limit. 1s fixed, no real POST -> inert.","impact":"Design-fidelity gap for live round only.","recommendation":"Wire rateLimit/order into preflight + make throttle authoritative at live round."},
    {"severity":"P3","title":"AttemptContext docstring claims persist-before-send but dispatch persists after execute","file":"backend/hedge_open_tasks/executor.py","line":36,"evidence":"docstring 'attempt row persisted first, ADR-4 §7.1'; service._dispatch_one_for_task executes then insert_fill. Harmless this round; misleads live wiring where persist-before-send is a hard ADR-4 requirement.","impact":"Doc/code mismatch on a safety-ordering invariant; materializes at live executor.","recommendation":"Correct docstring or introduce persist-before-send seam with the live round."},
    {"severity":"P3","title":"post_fill_all spins to 10_000 guard on ATTEMPT_DISABLED","file":"backend/hedge_open_tasks/service.py","line":290,"evidence":"apply_attempt_outcome no-ops ATTEMPT_DISABLED; fill-all loop terminates only at guard=10_000, inserting up to 10k rows. Reachable only with in-process DisabledHedgeExecutor (not HTTP). fill-once/fill-all bypass Start gate = documented round-1 posture; re-audit at live.","impact":"Bounded write amplification in operator-only config; no HTTP reachability.","recommendation":"Break fill-all loop on ATTEMPT_DISABLED; record start-gate-bypass re-audit as live-round gate item."}
  ],
  "required_fixes": [
    "F-001: make GET ?status=all include deleted per frozen §3.1 (default still excludes); fix test_filter_status_for_list_mapping; add HTTP-level deleted-visibility test.",
    "F-002: reject mode!='immediate' in create_task with 400 invalid_field('mode',...); add tests asserting smooth rejected."
  ],
  "residual_risks": [
    "F-003/F-004/F-005/F-006 accepted round-1 residual risks to resolve before live executor.",
    "fill-once/fill-all bypass durable Start gate by documented round-1 design; safe only because record transport never POSTs — re-audit mandatory at live.",
    "Position JSON financial fields are stable '0' placeholders pending data sources (disclosed in impl report)."
  ],
  "fix_start_prompt": "See task-hedge-be-fix-1.prompt.md (bookkeeper materialized the reviewer's fix_start_prompt verbatim into the dispatch packet).",
  "next_action": "fix"
}
```
