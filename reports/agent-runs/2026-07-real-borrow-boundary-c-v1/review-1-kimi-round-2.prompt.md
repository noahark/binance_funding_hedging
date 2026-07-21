[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于
   claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出
   ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条
   执行记录都必须对应你本会话内真实发生的动作。
3. 你的评审依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的
   文件。

# Boundary C Task C — Formal Review-1 Round 2

你是 fresh-context Kimi review-1 会话，模型固定为
`kimi-code/kimi-for-coding`，provider identity 为 `moonshot_kimi`。

人类操作员必须在新的 Kimi terminal 执行本 prompt；如果复用 terminal，必须先
执行 `/clear` 再执行 `/new`。不要继承 round-1 的结论、工具状态或 prompt 上下文。
实现和全部 fix 作者为 Claude-GLM / `zhipu_glm`，与你 provider 不同。你此前参与过
本阶段独立设计 review，因此 verdict 必须如实填写
`reviewer_prior_involvement: "design"`；这不放宽审查标准。

## 严格只读与安全边界

- 只读评审：禁止编辑、创建、删除、暂存、提交、推送、合并或部署任何文件。
- 禁止读取 `.env`、key file、cookie、credential store，禁止输出完整环境变量，
  禁止展开任何 adapter 环境。
- 禁止向 Binance 或任何外部服务发请求；尤其禁止真实、认证或 production-
  reachable 的借币请求。只能检查 committed 证据、本地代码和 fake-only tests。
- 不得调用或转派其他模型。跨模型 dispatch 只能由 human operator 执行。
- 当前 `HEAD` 可能晚于被审 head；必须只审固定 `base_sha..head_sha`，不得以移动
  `HEAD` 替代。

## 固定审查身份与范围

- Stage: `2026-07-real-borrow-boundary-c-v1`
- Role: `first_reviewer`
- Review round: `2`
- Base SHA: `c9df14591ac4ca00977ce0e4d80c0950aae44c19`
- Head SHA: `87c19273c3f488cf6d9ca80f8541704bb198cb81`
- Diff fingerprint:
  `87c19273c3f488cf6d9ca80f8541704bb198cb81:29f0f587f3ef0dcc01261fa84047ff56fdbf717dcaa7cf20dddb13495229c162`
- Author/fix provider identity: `zhipu_glm`
- Reviewer provider identity: `moonshot_kimi`
- Reviewer prior involvement: `design`, evidence:
  `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/design-review.raw-output-kimi.md`
- Raw review artifact destination（由 human operator 捕获完整输出）:
  `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/30-review-1-round-2.md`

必须独立重算标准指纹；`status.json` 仅因自引用而从 hash 输入排除：

```text
git diff --binary c9df14591ac4ca00977ce0e4d80c0950aae44c19..87c19273c3f488cf6d9ca80f8541704bb198cb81 -- . ":(exclude)reports/agent-runs/2026-07-real-borrow-boundary-c-v1/status.json" | shasum -a 256
git diff --stat c9df14591ac4ca00977ce0e4d80c0950aae44c19..87c19273c3f488cf6d9ca80f8541704bb198cb81
git diff --check c9df14591ac4ca00977ce0e4d80c0950aae44c19..87c19273c3f488cf6d9ca80f8541704bb198cb81
```

hash 必须等于
`29f0f587f3ef0dcc01261fa84047ff56fdbf717dcaa7cf20dddb13495229c162`。

## 必读原始工件

必须直接读取，不得只依赖 bookkeeper 摘要：

1. `AGENTS.md`
2. `workflows/templates/stage-delivery.yaml` 的 test、review-1、fix 段
3. `schemas/review-verdict.schema.json`
4. `agents/skills/code-reviewer.md`
5. `docs/parallel-development-mode.md` 的 R11-R12
6. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/status.json`
7. `00-task.md`、`10-design.md`、`11-adr.md`、
   `12-development-breakdown.md`、`14-design-review-synthesis.md`
8. `reports/agent-runs/2026-07-real-borrow-execution-v1/06-direction-synthesis.md`
9. `20-implementation.md`、`20-implementation-bookkeeper-audit.md`
10. round-1 原始 review 与 intake：`30-review-1.md`、
    `30-review-1.bookkeeper-intake.md`
11. `40-fix-report.md`、`40-fix-report.bookkeeper-audit.md`
12. `task-C-bookkeeper-fix-{4,5,6}.{prompt,dispatch}.md`
13. `60-test-output.txt`、`70-handoff.md`、`main-sync-authorization.md`
14. Task H 已接受证据：
    `reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/50-review-2.md`、
    `reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/80-user-acceptance.md`
15. `reports/api-samples/2026-07-real-borrow-boundary-c-v1/20260720T150836Z/evidence-index.md`
    及其列出的 raw public contract samples
16. 固定 diff 内所有产品代码、schema、前端、测试和 Harness 改动。

Round-1 REWORK 是历史证据，不是本轮结论。必须独立确认 F1/F2/F3 及
BK-R1-FIX4-001、BK-R1-FIX4-002、BK-R1-FIX5-001 是否真正闭合，并检查修复是否
引入新缺陷。F4/F5 为历史 P3，不得隐去；若仍存在，可继续作为 non-blocking
finding 或 residual risk，但不得自动升级/降级。

## 审查重点

至少逐项核验：

1. 唯一 live write 是否仍严格限定 portfolio-margin borrow exact path、POST、
   canonical query、唯一 HMAC 出口与专用凭据；不存在第二 POST、hidden retry、
   retry-anyway、force-clear、错误 URL 或敏感响应泄漏。
2. disabled/fake/live、credential 缺失、Start/Stop、ownership、单 worker、
   cooldown/manual re-arm 是否全部 fail closed；`live_authorized` 不得等同成功。
3. dispatch intent 原子落盘、known rejection、timeout/transport/malformed/unknown、
   crash orphan bounded reconciliation 是否永不盲重发借币 POST。
4. reconciliation 是否严格消费 `{"rows":[...],"total":N}`；total、五字段、
   txId、timestamp window、分页、malformed member、唯一候选全部 fail closed。
5. durable cross-task attribution 是否阻止同资产/同 Decimal 金额重叠任务重复
   认领，同时允许真正唯一匹配收敛。
6. 418/429/-1003、至少 300 秒隔离、manual re-arm、启动恢复和 GET 418 信号是否
   可被 Start、重启或普通 cooldown 清理绕过。
7. F3 修复：pending crash orphan 是否在 +5/+15/+60/+300/+900 秒队列内；成功、
   耗尽和跨重启计数/marker 生命周期是否一致，且零第二 POST。
8. F1/F2/Fix-6：过期 no-real-borrow 文案已删除；创建前预览准确显示
   amount×count、资产、次数和真实当前 interval；未加载、加载失败与 loaded→503
   均必须零 task POST，成功路径恰好一次 POST。
9. API/schema/UI contract 与 exact-path/HMAC/urlopen/import/UI guards 未弱化；启动
   观测只输出布尔、计数、枚举，不泄漏 credential、签名、完整 URL 或 body。
10. accepted `main` 的 Harness extractor sync 没有改变产品运行语义，也没有弱化
    receipt、Session-ID、identity、fingerprint、clean-worktree、historical compare
    gates；findings-bearing top-level verdict 必须可正确提取。
11. 报告、测试与 committed code 一致；尤其核对 post-sync 331/630/97/128、
    compare 11/11 与 `py_compile` 证据，不能因全绿而推定 ACCEPT。

允许在本地只读复跑以下 fake-only 命令；不得运行任何会读取真实凭据或访问外部
服务的命令：

```text
python3 -m pytest backend/tests/test_binance_signing.py backend/tests/test_portfolio_margin_borrow_client.py backend/tests/test_live_borrow_executor.py backend/tests/test_borrow_store.py backend/tests/test_borrow_scheduler.py backend/tests/test_borrow_api.py backend/tests/test_config.py backend/tests/test_private_client.py backend/tests/test_private_account_v1.py backend/tests/test_service_health.py -q
python3 -m pytest backend/tests -q
node frontend/self-check.js
python3 -m pytest scripts/tests -q
python3 -m py_compile backend/services/binance_signing.py backend/services/portfolio_margin_borrow_client.py backend/services/live_borrow_executor.py backend/services/private_client.py backend/borrow_tasks/*.py backend/app/server.py backend/config.py
python3 scripts/test-validate-all-stages-compare.py --repo-root .
```

## 裁决标准与输出合同

- `ACCEPT`：固定 diff 无 P0/P1，冻结契约和证据完整，所有必须先修的安全/正确性
  问题均闭合。
- `REWORK`：存在固定范围内可修复问题。必须给出 severity、文件/行、复现证据、
  影响、最小修复与完整 `fix_start_prompt`。
- `BLOCKED`：必要 raw evidence 不可读或无法可靠审查；不得猜测 ACCEPT。

先输出简洁 review narrative，再输出六行页脚，最后输出一个且仅一个可解析 JSON
object；JSON 后不得有任何文本。页脚必须位于 JSON 之前：

```text
当前 Session ID: <provider-native id | unavailable (reason)>
Session ID 来源: <runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable>
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/30-review-1-round-2.md
本地北京时间: <本会话实际执行 date 命令得到的 YYYY-MM-DD HH:MM:SS CST>
下一步模型: <bookkeeper | human operator → Claude-GLM>
下一步任务: <specific next task>
```

最终 JSON 必须严格匹配 `schemas/review-verdict.schema.json`，并固定：

- `schema_version: 1`
- `stage_id: "2026-07-real-borrow-boundary-c-v1"`
- `role: "first_reviewer"`
- `model: "kimi-code/kimi-for-coding"`
- `diff_fingerprint` 等于本 prompt 的完整固定值
- `reviewer_prior_involvement: "design"`
- `reviewer_prior_involvement_notes` 指向 Kimi 设计 review 工件

`reviewed_artifacts` 只能列出你实际读取的 raw artifact 和固定 diff。若 verdict 为
`REWORK`，`fix_start_prompt` 必须可直接交给原 Claude-GLM fix author，完整包含：

- stage、round-2 完整 fingerprint、raw review 路径；
- 每项 finding 的证据、required fixes、allowed/forbidden file boundaries；
- 禁止真实 Binance 请求、凭据读取、第二 POST、commit/push/merge/model relay；
- 上述精确测试命令和验收标准；
- 要求 append `40-fix-report.md` finding-to-fix 映射与 `60-test-output.txt`，然后
  stop for bookkeeper。

不得把 `fix_start_prompt` 写成“见上文”。
