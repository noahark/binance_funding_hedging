# Review-2 Round 3 — 全 stage 终审（claude-opus-4-8）

- Reviewer model: `claude-opus-4-8`（如实；本会话真实模型标识）
- Reasoning effort: high
- Role: `final_reviewer`（fresh read-only session）
- Prior involvement: `design`（Anthropic provider 设计涉入；现任 bookkeeper 为 claude-fable-5，同 provider —— 双帽风险见 §0）
- Review range: `a385c7ad77da1611c6e952b2219aee56b49f442f..a057d063523664a2fcfa8cc4db9e9af789f15730`
- Diff fingerprint（本人独立复算核对）: `a057d063523664a2fcfa8cc4db9e9af789f15730:cd68035686acc794aac3065270530ec6d4846da18c25274458f478fd85b84e7e`
- Verdict: **ACCEPT** → bookkeeper 落 `stage_accepted_waiting_user`

## §0 落档授权声明 + 双帽风险处置

- **落档授权**：操作者显式指令"review 本 packet 并落档 review 内容"。据 packet §只读硬规则，本人仅**新增** `50-review-2-round3-claude-opus-4-8.md` 与 `review-2-round3-claude-opus-4-8.verdict.json` 两个文件，**未触碰任何既有文件**（无 git add/commit/push，无 status/handoff/既有 review 改动）。后续状态推进由 bookkeeper 执行。
- **双帽风险**：本人属 Anthropic，与 bookkeeper（claude-fable-5）同 provider，且本 stage 证据（8/8 复验、6/6 探针、破坏性验证记录）大量由该 bookkeeper 产出。据 packet 要求，本人**不采信任何 bookkeeper/Kimi 产出结论作为修复证据**，全部独立重跑：指纹复算、全套件、FX1 真实 shell 探针、FX5 破坏性还原、逐函数代码直读、budget 分支可达性核查。下述结论均建立在本人独立复现之上。
- **身份诚实**：`model` = `claude-opus-4-8`（真实）。已知 round-2 曾发生第三方会话伪造 claude-fable-5 身份出具 verdict 的事件（`52-...panel-disposition.md §3`，零效力处置）——本人如实披露，未借用任何他方身份。

## §1 冻结范围与指纹（先自行复算）

```text
git diff --binary a385c7a..a057d06 -- . ':(exclude)reports/agent-runs/2026-07-auto-review-pipeline-v1/status.json' | sha256
computed = a057d06...:cd68035686acc794aac3065270530ec6d4846da18c25274458f478fd85b84e7e
expected = a057d06...:cd68035686acc794aac3065270530ec6d4846da18c25274458f478fd85b84e7e   → 逐字节 MATCH（非 BLOCKED）
```

范围 head `a057d06` 是终审快照；其后 3 个 commit（04fe81d/f6b8a3a/2de3f73）均为 bookkeeper 簿记/re-review/round-3 packet 绑定，正确落在范围外。FINAL fix commit `a057d06` 经 `git diff --name-only` 核实**严格只改 4+2 文件**（`scripts/auto-review-runner.py`、`scripts/stage-seal.py`、`scripts/tests/test_auto_review_runner.py`、`scripts/tests/test_stage_seal.py` + `20-implementation.md`/`60-test-output.txt` append），无实现漂移，无 frozen 合同文件改动。

## §2 独立执行的检查（原始结论）

```text
python3 -m unittest discover -s scripts/tests -p 'test_*.py'          → Ran 161 tests, OK
python3 -m py_compile validate-stage/harness_stage_lib/stage-seal/auto-review-runner → exit 0
scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint → PASSED (status=review_2, fp MATCH)
git diff --check a385c7a..a057d06 → trailing whitespace 仅命中 raw model 证据（见 §4 residual），非 4+2 fix 文件、非 status/handoff
8 个 FX 测试类独立单跑（30 tests）→ OK
```

反例探针均使用 tempfile/本地 git/本地无害命令，无网络、无真实模型调用。

## §3 你要回答的 6 个问题

### Q1 — round-2 findings（5×P1+3×P2）是否全部以证据关闭？

**是。** 逐项独立复现（不凭记忆/报告）：

| # | round-2 finding | 修复锚点（代码直读） | 独立复现关闭证据 |
|---|---|---|---|
| P1#1 | adapter 命令 shell 不安全（本仓路径含空格失效） | `auto-review-runner.py:_default_invoke:899-909` 对 `<prompt-file>`/`<repo>`/`@PROMPT@`/`@REPO@` 先 `shlex.quote()` 再替换 | **本人独立真实-shell 探针**：在含空格+`$;'` 元字符的临时目录，两种生产模板 `echo "$(cat <pf>)"` 与 `cat <pf>` quote 后均 exit 0；raw 未 quote 则 exit 2。本仓真实根 `…/ai code/funding_hedging` 亦 exit 0 |
| P1#2 | seal 两 commit 间无 expiry 重查 | `stage-seal.py:seal(commit_guard=…)`，fresh 的 create_snapshot 前(:622)+create_bind 前(:628)、marker branch2 bind 前(:576)、unbound bind 前(:604) 全覆盖；runner `_node_seal` 传 `_check_authorization_expiry` | `CommitGuardTests`/`SealCommitGuardWiringTests` 独立跑绿；代码核实每个 git commit 点紧前均有 guard |
| P1#3 | 崩溃恢复可绑定介入提交 + 孤儿 marker | `stage-seal.py` 三分支穷尽(:560-593)：parent→fresh、精确 child→续 bind、其余→fail-closed 保留 marker；孤儿 marker 经 `_bind_evidence_complete` 验证(:533-547) | `SealMarkerHardeningTests`（介入提交 fail-closed 保留 marker / 孤儿清除抛 already-sealed）独立跑绿 |
| P1#4 | 锁竞争失败方写权威状态 | `run():1155-1162` 锁失败仅 stderr+`RunResult(lock_busy)`，**零** `_handle_preflight_failure`/`_persist`/transition/receipt | `RunnerLockTests`：全 stage-dir 逐文件 sha256 before==after、`calls==0`、无 escalation artifact、status≠awaiting_human，独立跑绿 |
| P1#5 | running 恢复重派 implementation | `_run_body:1214-1223`：resume 且 `_unit_has_started_receipts`（implementation/cross_check/fix 任一 receipt）→ `RecoverableFallback` fail-closed 到 awaiting_human；干净单元正常 | `ResumeIdempotencyTests` 5 崩溃边界均断言 `calls==0`；**本人独立破坏性验证**：scratchpad 副本还原 FX5（禁用 guard）→ 6 测试中 5 个 FAIL（guard 真承重） |
| P2#1 | 授权绑定仅子集判断 | `_verify_authorization_binding:1075-1095` 双向集合相等（`live-auth` 与 `auth-live` 均拒）+ topology + allowed/forbidden pathspec | `AuthorizationExactBindTests`（authorized_but_absent/topology/allowed/forbidden）独立跑绿 |
| P2#2 | rework 账本瞬时 max+1 | `_charge_auto_change:701-715` 先算 proposed 值，任一超 cap 即 escalate **不写任一计数器**，两者仅在允许时原子更新 | `ReworkLedgerAndExpiryTests`：拒绝分支双计数器不变(2/0、1/0)、恰达 cap 合法、e2e 共享账本，独立跑绿 |
| P2#3 | status 残段 + gemini 报告 whitespace | bookkeeper 机械项（commit aa9f7c1），**不在本 fix 范围** | 本人复核 `model_routing.review_2` 已同步；`50-review-2-gemini.md:3` 已清 |

### Q2 — 修复自身质量：FX1–FX7 是否引入新缺陷？（对抗性视角）

逐函数直读，对抗面无坐实缺陷：
- **FX1 quoting 绕过**：`shlex.quote` 对所有 runner-owned 替换值统一应用，`$()` 内单引号有效、裸词单 token——本人真实探针含 `$;'` 元字符仍安全；receipt 仍只记 `command_ref` 不记展开命令（P13 边界保持）。
- **FX2 guard 时序窗**：guard 位于**每个** git commit 系统调用紧前（含两条恢复路径），无遗漏 commit 点；guard 纯"检查即抛"无副作用。
- **FX3 三分支恢复漏网**：分支穷尽（parent / 精确 child / 其余），"其余"（多 commit 或路径集不符）一律 fail-closed 保留 marker，不清不 commit——正是 finding 事故形态的反面；孤儿 marker 验证不过亦保留。
- **FX4 lock_busy 语义**：`lock_busy` 仅存在于返回值/stderr，未进 status 与 AUTO_TRANSITIONS（锁竞争先于任何状态转换，语义上 run 未开始）——正确，未污染状态机。
- **FX5 fail-closed 误伤面**：仅对"非 ACCEPT 且有 started receipt"单元 fail-closed；干净单元（零 receipt）仍正常 fresh 执行（`test_resume_clean_unit_runs_from_scratch` 证），未过度收紧。
- **FX6 双向绑定兼容性**：runtime caps（max_model_calls/wall_clock）**刻意不绑定**（契约"caps come FROM auth"，`test_runtime_cap_divergence_is_not_bound` 证），仅 ledger caps 精确绑定——与 frozen 契约一致。
- **FX7 账本边界**：`proposed > cap` 语义等价旧 `used >= cap`，恰达 max 合法、超 max 拒绝，边界未漂移。

### Q3 — 裁定复核（GLM 3 个 append 阻塞点 + bookkeeper ACCEPTED + Kimi 同意）

三项本人**独立**核对后均同意：
1. **FX4 既有测试契约替换**：旧断言 codified 缺陷行为（锁 loser 写 status），FX4 要求零写，替换必需；新测试断言全目录字节一致，契约正确。
2. **FX6 runtime caps 不绑定**：代码 `:1010-1023` 仅绑 ledger caps；绑 runtime caps 会破坏 `test_runtime_caps_come_from_authorization_not_status` 契约。成立。
3. **FX6 max_stage_rework schema-frozen（const 3）**：schema 校验(:965)使非-3 auth 早于 runtime budget_mismatch 分支即被 `authorization_invalid` 拒（`test_...`(:2035) 用值 4 证 authorization_invalid）。成立——但正是此处埋下一个 P3 测试卫生缺陷（见 §4 findings）。

### Q4 — residual 复核（非 required 定性是否成立）

- **R1（seed receipt call_budget 方向）**：成立。`_unit_has_started_receipts:826-833` 只消费 `node`+`review_unit_id`，call_budget 方向对谓词无影响。
- **R2（FX1 字符串枚举 5/6）**：成立。`shlex.quote` 对所有替换统一应用，与具体命令无关；本人真实-shell 探针已覆盖两种生产上下文，缺一个 shape-identical 命令的字符串级枚举无行为缺口。
- **verbatim 证据 whitespace**：成立（详 §4）。

### Q5 — 全 stage 验收（00-task 1–29 对照 40-表）+ frozen 面

- **default-off / no-self-host（验收 1、2）**：`auto_review_pipeline.enabled` 未置真（=None）→ 现行人工 DRAFT-2 dispatch，bootstrap 不自托管。checkpoint validator PASSED 佐证。
- **frozen 面未被侵蚀**：FINAL fix commit `a057d06` 经 name-only 核实**未触碰** AGENTS.md / stage-delivery.yaml / registry.yaml / validate-stage.py / harness_stage_lib.py / schemas / manifest——fingerprint 公式、AUTO_TRANSITIONS、review-1 三对路由、seen-diff bind、post-cross-check blocking rerun、pilot 谓词、显式路径 git add 全部逻辑上不可能被本 fix 改动。指纹逐字节 MATCH 二次佐证。
- 验收 3/5/7/9/10/11/13/14/15/16/19/26/27/28 对应的负测试类在 161 套件内独立跑绿（authorization、seal 崩溃点、resume、provider isolation、verdict parsing、seen-diff bind、ledger、mode mutex、post-cross-check blocking、nullable/expired expiry 等）。

### Q6 — 回归

全套件 161 独立重跑 OK；`validate-stage --phase checkpoint` PASSED；`git diff --check` 结论与 Kimi 注记一致（whitespace 仅在 raw Grok review 落档 `30-review-1-review2-fix-round1-grok.md`/`50-review-2-round2-grok.md` 与 `review-2-round2-unauthorized-writes-evidence.diff`，属 raw model 证据，AGENTS.md 不 rewrite）。

## §4 本轮新增 findings（均 P3，非 required；不阻断 ACCEPT）

### P3 — 重复的测试方法名遮蔽了一个预期负测试
`scripts/tests/test_auto_review_runner.py` 在 :2027 与 :2035 两处定义了**同名** `test_max_stage_rework_divergence_fails_closed`。Python 中后者覆盖前者，:2027（断言 `budget_mismatch`）**永不执行**（verbose 运行仅列出一次为证）。生产 exact-bind 分支 `:1021-1023` 对 `max_stage_rework` 的可达 divergence（`auth=3` schema-valid、live status≠3）**在代码中确实 fail-closed**，且孪生键 `max_auto_code_changes` 走同一循环分支已被 `test_max_auto_code_changes_divergence_fails_closed`(:2046) 覆盖——**故无生产保护缺口**，仅是 FX6 packet 要求的"每个 budget 字段不等负测试"里 `max_stage_rework` 那条被同名 typo 意外丢失。建议 follow-up：将 :2027 重命名（如 `..._when_auth_valid_status_diverges`）并改为构造 `auth=3 / status=2` 的 status-divergence 场景以覆盖 :1023 该臂。

### P3 — 陈旧 docstring 与 FX4 行为矛盾
`auto-review-runner.py:_acquire_runner_lock` docstring(:1113) 仍写"A held lock is a recoverable preflight failure (awaiting_human + paused)"，与 FX4 实际零写/`lock_busy` 行为矛盾（run() :1155-1162 已改）。纯文档陈旧，无功能影响。建议 follow-up 一并勘误。

## §5 结论

round-2 的 5×P1+3×P2 全部以**本人独立复现的证据**关闭；FX1–FX7 未引入新的 P0/P1/P2 required finding；GLM 三阻塞点裁定与 R1/R2 残留定性成立；default-off 与 DRAFT-2 共存、frozen 面完整、指纹逐字节匹配、161 套件+checkpoint 全绿。新增两项均为 P3 测试/文档卫生缺陷，无生产保护缺口，不阻断验收。

**Verdict = ACCEPT。** 据终格语义，bookkeeper 应落 `stage_accepted_waiting_user`（等待用户/操作者最终处置；本人与 bookkeeper 均无 merge 权）。两项 P3 建议进 follow-up，不占 rework、不改变本判定。

```text
本地北京时间: 2026-07-12 09:52:16 CST
下一步模型: Claude Fable 5（bookkeeper）
下一步任务: 落档 round-3 verdict → ACCEPT=stage_accepted_waiting_user / REWORK=human_escalation_required
```

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-auto-review-pipeline-v1",
  "role": "final_reviewer",
  "model": "claude-opus-4-8",
  "verdict": "ACCEPT",
  "diff_fingerprint": "a057d063523664a2fcfa8cc4db9e9af789f15730:cd68035686acc794aac3065270530ec6d4846da18c25274458f478fd85b84e7e",
  "reviewer_prior_involvement": "design",
  "reviewer_prior_involvement_notes": "Anthropic provider had prior design involvement in this stage, and the current bookkeeper is claude-fable-5 (same provider) — a dual-hat risk explicitly assessed in the report. This session shares no implementation/fix authorship with the reviewed FINAL fix unit. To mitigate the dual-hat risk, all closure evidence was independently reproduced (fingerprint recompute, full 161-test suite, an independent real-shell FX1 probe with space+metacharacter paths, an independent destructive FX5 revert in a scratchpad copy that reddened 5 tests, per-function code reads, and budget-branch reachability checks) rather than trusting bookkeeper/Kimi-produced artifacts. model is filled with the true identity claude-opus-4-8; no borrowed identity, per the round-2 identity-forgery incident on record.",
  "reviewed_artifacts": [
    "reports/agent-runs/2026-07-auto-review-pipeline-design-review/40-operator-decision-table.md",
    "reports/agent-runs/2026-07-auto-review-pipeline-v1/00-task.md",
    "reports/agent-runs/2026-07-auto-review-pipeline-v1/50-review-2-round2-gpt-5.6-sol.md",
    "reports/agent-runs/2026-07-auto-review-pipeline-v1/review-2-round2-gpt-5.6-sol.verdict.json",
    "reports/agent-runs/2026-07-auto-review-pipeline-v1/task-review2-round2-fix-final-claude-glm.prompt.md",
    "reports/agent-runs/2026-07-auto-review-pipeline-v1/30-review-1-review2-round2-final-fix.md",
    "reports/agent-runs/2026-07-auto-review-pipeline-v1/review-1-review2-round2-final-fix.verdict.json",
    "reports/agent-runs/2026-07-auto-review-pipeline-v1/52-review-2-round2-panel-disposition.md",
    "agents/skills/reality-checker.md",
    "scripts/auto-review-runner.py",
    "scripts/stage-seal.py",
    "scripts/tests/test_auto_review_runner.py",
    "scripts/tests/test_stage_seal.py",
    "schemas/review-verdict.schema.json",
    "git diff a385c7ad77da1611c6e952b2219aee56b49f442f..a057d063523664a2fcfa8cc4db9e9af789f15730"
  ],
  "findings": [
    {
      "severity": "P3",
      "title": "Duplicate test method name shadows an intended negative test (no production coverage gap)",
      "file": "scripts/tests/test_auto_review_runner.py",
      "line": 2027,
      "evidence": "test_max_stage_rework_divergence_fails_closed is defined twice (lines 2027 and 2035); Python keeps only the second, so the first (asserting budget_mismatch) never runs — confirmed by verbose test discovery listing it once. The reachable production exact-bind branch at auto-review-runner.py:1021-1023 does fail closed for a max_stage_rework divergence (auth=3 schema-valid, live status != 3), and its sibling key max_auto_code_changes traverses the identical loop branch and is covered by test_max_auto_code_changes_divergence_fails_closed at line 2046.",
      "impact": "Test-hygiene only. No production authorization path is left unprotected; the FX6 packet's 'negative test per budget field' requirement loses only its max_stage_rework status-divergence case to a duplicate-name typo. No acceptance criterion is violated.",
      "recommendation": "Rename the line-2027 method (e.g. test_max_stage_rework_status_divergence_fails_closed) and rewrite it to construct auth.max_stage_rework=3 with live status max_stage_rework!=3 so it exercises the reachable budget_mismatch arm at :1023. Track as a follow-up; does not consume rework."
    },
    {
      "severity": "P3",
      "title": "Stale _acquire_runner_lock docstring contradicts FX4 zero-write behavior",
      "file": "scripts/auto-review-runner.py",
      "line": 1113,
      "evidence": "_acquire_runner_lock docstring still states 'A held lock is a recoverable preflight failure (awaiting_human + paused)', but FX4 changed the contended path (run() lines 1155-1162) to write nothing and return lock_busy via return-value/stderr only.",
      "impact": "Documentation only; no functional effect. A future reader could misjudge the lock-contention behavior.",
      "recommendation": "Update the docstring to describe the FX4 zero-write lock_busy return semantics. Track as a follow-up; does not consume rework."
    }
  ],
  "required_fixes": [],
  "residual_risks": [
    "R1 (seed receipt call_budget direction) confirmed non-required: _unit_has_started_receipts consumes only node + review_unit_id.",
    "R2 (FX1 string-level enumeration 5/6) confirmed non-required: shlex.quote is applied uniformly to all substitutions; an independent real-shell probe covered both production template contexts (double-quoted command substitution and bare word).",
    "Trailing whitespace in the review range is confined to raw Grok review artifacts (30-review-1-review2-fix-round1-grok.md, 50-review-2-round2-grok.md) and an evidence diff (review-2-round2-unauthorized-writes-evidence.diff); per AGENTS.md raw model evidence is not rewritten. None occurs in the 4+2 fix files, status.json, or handoff.",
    "Two P3 test/doc-hygiene findings above should enter follow-ups; they carry no production risk and do not change this ACCEPT.",
    "Dual-hat residual: reviewer and bookkeeper share the Anthropic provider; mitigated here by full independent re-run, but the AGENTS.md wording around same-provider reviewer/bookkeeper isolation (and runner-level availability vs design-conflict ineligibility, per the round-2 residual) should be tightened in a later Harness-contract stage."
  ],
  "next_action": "stage_accepted_waiting_user"
}
```
