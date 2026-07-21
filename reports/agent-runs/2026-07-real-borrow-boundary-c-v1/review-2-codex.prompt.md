[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于
   claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出
   ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条
   执行记录都必须对应你本会话内真实发生的动作。
3. 你的评审依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的
   文件。

# Boundary C — Formal Review-2 Final Gate

你是由 human operator 启动的全新、read-only Codex `gpt-5.5` final-review
会话。不得复用本阶段 bookkeeper/design session 的结论、tool state 或 transcript。
不得自行调用任何其他模型。

## 身份隔离与 Strong-Reviewer 披露

- Role: `final_reviewer`
- Provider identity: `openai`
- Model: `gpt-5.5`
- Implementation/fix provider: `zhipu_glm`
- Review-1 provider: `moonshot_kimi`
- 你没有参与 implementation 或 fix，满足不可覆盖的 anti-self-review gate。
- 你所属 Codex/OpenAI provider 参与过上游 direction synthesis 及本阶段
  task/design/ADR，因此必须在 verdict 中写
  `reviewer_prior_involvement: "design"`，并在
  `reviewer_prior_involvement_notes` 完整披露设计与方向综合经历。
- Anthropic 也不是 unrelated reviewer，因为 Opus4.8 编写并修订了 development
  breakdown。无关决策 provider 不存在的证据：
  `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/review-2-design-conflict-override.md`。
- 设计参与只允许披露，不允许降低审查标准。`00-task.md`、`10-design.md`、
  `11-adr.md` 和 `12-development-breakdown.md` 都是待审证据，不是最高权威。

## 最高权威与产品语义

按以下顺序判断：

1. `AGENTS.md`、workflow 和 schema 硬门禁；
2. 用户批准的方向与范围，尤其
   `reports/agent-runs/2026-07-real-borrow-execution-v1/06-direction-synthesis.md`；
3. `docs/product/PRD.md` 与 `docs/architecture/ARCHITECTURE.md`；
4. stage task/design/ADR/breakdown；
5. implementation、fix、review 和测试证据。

PRD/Architecture 的“current as-built read-only/no borrow”文字描述的是本 stage
被用户接受并合回主干之前的 canonical 状态。本分支实现是否足以改变该状态正是
本次 review 的对象；不得把“分支尚未被用户接受/部署”误判成实现缺失，也不得因
代码存在就宣称已经启动真实借币。即使本 review ACCEPT，也只能进入
`stage_accepted_waiting_user`，不授权 merge、部署、凭据读取或真实借币启动。

## 固定审查范围

- Stage: `2026-07-real-borrow-boundary-c-v1`
- Base SHA: `c9df14591ac4ca00977ce0e4d80c0950aae44c19`
- Head SHA: `87c19273c3f488cf6d9ca80f8541704bb198cb81`
- Diff fingerprint:
  `87c19273c3f488cf6d9ca80f8541704bb198cb81:29f0f587f3ef0dcc01261fa84047ff56fdbf717dcaa7cf20dddb13495229c162`
- Review-2 raw artifact destination:
  `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/50-review-2.md`

独立重算，不得使用移动 `HEAD`：

```text
git diff --binary c9df14591ac4ca00977ce0e4d80c0950aae44c19..87c19273c3f488cf6d9ca80f8541704bb198cb81 -- . ":(exclude)reports/agent-runs/2026-07-real-borrow-boundary-c-v1/status.json" | shasum -a 256
git diff --stat c9df14591ac4ca00977ce0e4d80c0950aae44c19..87c19273c3f488cf6d9ca80f8541704bb198cb81
git diff --check c9df14591ac4ca00977ce0e4d80c0950aae44c19..87c19273c3f488cf6d9ca80f8541704bb198cb81
```

hash 必须等于
`29f0f587f3ef0dcc01261fa84047ff56fdbf717dcaa7cf20dddb13495229c162`。
当前 `HEAD` 可能包含被审 head 之后的纯记账提交；只审固定范围。

## 必读 Raw Artifacts

必须直接读取：

1. `AGENTS.md`
2. `workflows/templates/stage-delivery.yaml` 的 test、review-1、fix、review-2、
   terminal 段
3. `schemas/review-verdict.schema.json`
4. `agents/skills/reality-checker.md` 的 Project Harness Overrides
5. `docs/product/PRD.md`
6. `docs/architecture/ARCHITECTURE.md`
7. `docs/parallel-development-mode.md` R11-R12
8. `reports/agent-runs/2026-07-real-borrow-execution-v1/06-direction-synthesis.md`
9. 本 stage 的 `status.json`、`00-task.md`、`10-design.md`、`11-adr.md`、
   `12-development-breakdown.md`、`14-design-review-synthesis.md`
10. `20-implementation.md`、`20-implementation-bookkeeper-audit.md`
11. 历史 `30-review-1.md` 与 `30-review-1.bookkeeper-intake.md`
12. `40-fix-report.md`、`40-fix-report.bookkeeper-audit.md`、fix-4/5/6 的全部
    prompt/dispatch
13. round-2 `30-review-1-round-2.md`、
    `30-review-1-round-2.bookkeeper-intake.md`、
    `review-1-kimi-round-2.dispatch.md`
14. `60-test-output.txt`、`70-handoff.md`、`main-sync-authorization.md`
15. `review-2-design-conflict-override.md`
16. Task H final review 与用户接受证据：
    `reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/50-review-2.md`、
    `80-user-acceptance.md`
17. Boundary C public API contract evidence index 及其四个 raw slices
18. 固定 diff 内全部产品代码、schema、前端、测试和 Harness 改动。

不得只看 Kimi ACCEPT 或 bookkeeper 摘要。Review-1 是证据，不是 final verdict。

## Final Gate 审查重点

至少独立判断：

1. 产品范围是否仍是 Boundary C 借币，不包含 order/repay/transfer/sell/hedge/
   close，也没有自动启动或部署。
2. 唯一真实写是否严格为 Portfolio Margin borrow exact POST；host/path/method/
   canonical query/HMAC/专用凭据/单次传输全部 fail closed，无第二 POST、hidden
   retry、retry-anyway 或 force-clear。
3. disabled/fake/live、显式 Start/Stop、`live_authorized`、ownership、单 worker、
   credential 缺失、启动恢复与 API/UI 是否不可绕过。
4. intent-before-send、结果分类、known rejection、unknown outcome、crash orphan、
   bounded reconciliation 与“不确定时绝不重发”是否全链路成立。
5. query loan record envelope、total、五字段、known txId、timestamp window、分页、
   malformed row、唯一候选和 cross-task attribution 是否严格 fail closed。
6. 418/429/-1003 cooldown、至少 300 秒隔离和 manual re-arm 是否能被 Start、
   restart、GET reconciliation 或普通 cooldown 清理绕过。
7. Round-1 F1/F2/F3 和 bookkeeper 残留 P1 是否真实关闭；Fix-4/5/6 是否引入
   竞态、错误成功、永久卡死、重复债务或前端误导。
8. Review-1 round 2 的两个 P3（`raw_body`、`.env.example`）是否确实非阻塞；若
   你认为它们影响安全/可运维性，必须给出独立证据和正确 severity。
9. API/schema/frontend 与静态守卫是否保持契约；日志、ledger、报告不得泄漏
   credentials、signature、full URL 或 private response body。
10. Task H extractor sync 是否只修 Harness，且 receipt/Session-ID/identity/
    fingerprint/clean-worktree/compare 门禁未弱化。
11. 测试是否具有证明力，而不只是数量全绿；报告与 committed code 是否一致。
12. ACCEPT 后的现实状态必须表述准确：程序代码具备 live borrow 能力但默认禁用，
    未配置/启动/验收/部署，也没有真实借币证据。

可在只读/fake-only 前提下复跑：

```text
python3 -m pytest backend/tests/test_binance_signing.py backend/tests/test_portfolio_margin_borrow_client.py backend/tests/test_live_borrow_executor.py backend/tests/test_borrow_store.py backend/tests/test_borrow_scheduler.py backend/tests/test_borrow_api.py backend/tests/test_config.py backend/tests/test_private_client.py backend/tests/test_private_account_v1.py backend/tests/test_service_health.py -q
python3 -m pytest backend/tests -q
node frontend/self-check.js
python3 -m pytest scripts/tests -q
python3 -m py_compile backend/services/binance_signing.py backend/services/portfolio_margin_borrow_client.py backend/services/live_borrow_executor.py backend/services/private_client.py backend/borrow_tasks/*.py backend/app/server.py backend/config.py
python3 scripts/test-validate-all-stages-compare.py --repo-root .
```

禁止读取凭据或运行任何可访问真实 Binance 的命令。

## 严格 JSON 输出合同

本 dispatch 使用 `codex exec --output-schema`。最终输出必须是一个且仅一个匹配
`schemas/review-verdict.schema.json` 的 JSON object，不得添加 schema 外字段。

六行导航 footer 必须放进 schema 允许的
`reviewer_prior_involvement_notes` 字符串末尾，格式如下；如果 runtime 看不到
provider-native Session ID，必须写带原因的 unavailable，禁止猜测：

```text
当前 Session ID: <provider-native id | unavailable (reason)>
Session ID 来源: <runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | unavailable>
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/50-review-2.md
本地北京时间: <本会话实际 date 命令的 YYYY-MM-DD HH:MM:SS CST>
下一步模型: bookkeeper
下一步任务: intake final verdict; ACCEPT only enters stage_accepted_waiting_user
```

固定 JSON 字段：

- `schema_version: 1`
- `stage_id: "2026-07-real-borrow-boundary-c-v1"`
- `role: "final_reviewer"`
- `model: "gpt-5.5"`
- `diff_fingerprint` 等于本 prompt 完整值
- `reviewer_prior_involvement: "design"`
- `reviewer_prior_involvement_notes` 必须同时包含 design/direction-synthesis
  disclosure、override evidence path 和上述六行 footer

`reviewed_artifacts` 只列实际读取/执行的 evidence。不得因 review-1 ACCEPT 自动
ACCEPT。若 verdict 为：

- `ACCEPT`：`required_fixes` 必须为空，`next_action` 为
  `stage_accepted_waiting_user`；
- `REWORK`：必须包含完整、可直接发送给原 Claude-GLM fix author 的
  `fix_start_prompt`，含 finding 证据、allowed/forbidden files、精确测试、禁止
  真实请求/凭据/第二 POST/commit/push/merge/model relay、报告映射和 stop for
  bookkeeper；
- `BLOCKED`：说明缺失证据或不可可靠判断的原因，不得猜测。

即使 ACCEPT，也不得宣称 merge、部署、产品验收或真实借币已发生。
