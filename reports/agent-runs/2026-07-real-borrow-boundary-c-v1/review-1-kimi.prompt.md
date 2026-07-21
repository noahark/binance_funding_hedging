[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于
   claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出
   ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条
   执行记录都必须对应你本会话内真实发生的动作。
3. 你的评审依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的
   文件。

# Boundary C Task C — Formal Review-1

你是 fresh Kimi review-1 会话，模型固定为
`kimi-code/kimi-for-coding`，provider identity 为 `moonshot_kimi`。
实现与三轮 intake fix 的作者均为 Claude-GLM / `zhipu_glm`，因此不存在
implementation/fix provider self-review。你此前参与过本阶段的独立设计 review，
必须在 verdict 中如实填写 `reviewer_prior_involvement: "design"`；该事实不
放宽任何审查标准。

## 严格只读与安全边界

- 只读评审。禁止编辑、创建、删除、暂存、提交、推送、合并或部署任何文件。
- 禁止读取 `.env`、key file、cookie、credential store 或展开任何 adapter
  环境。
- 禁止向 Binance 或任何外部服务发请求；尤其禁止真实、认证或 production-
  reachable 的借币请求。只能检查已落档证据和本地代码。
- 不要复用先前设计 review 的结论；必须针对固定 committed diff 独立审查。
- 当前工作树可能存在晚于被审 head 的纯记账提交。审查范围必须固定为下述
  `base_sha..head_sha`，不得使用移动的 `HEAD` 代替。

## 固定审查身份

- Stage: `2026-07-real-borrow-boundary-c-v1`
- Role: `first_reviewer`
- Base SHA: `c9df14591ac4ca00977ce0e4d80c0950aae44c19`
- Head SHA: `61ce536dfba6ddd347586cf324209acdfdc6afd9`
- Diff fingerprint:
  `61ce536dfba6ddd347586cf324209acdfdc6afd9:449b46378a324fa3c8bdd9ec9425b1e59b7509cb55e6c129d8991322dcb1a984`
- Author provider identity: `zhipu_glm`
- Reviewer provider identity: `moonshot_kimi`
- Reviewer prior involvement: `design`, evidence:
  `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/design-review.raw-output-kimi.md`
- Review artifact destination (human operator captures your full raw output):
  `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/30-review-1.md`

## 必读原始工件

先读取并以这些文件本身为依据，不得只依赖 bookkeeper 摘要：

1. `AGENTS.md`
2. `workflows/templates/stage-delivery.yaml` 的 test、review-1、fix 段
3. `schemas/review-verdict.schema.json`
4. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/status.json`
5. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/00-task.md`
6. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/10-design.md`
7. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/11-adr.md`
8. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/12-development-breakdown.md`
9. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/14-design-review-synthesis.md`
10. `reports/agent-runs/2026-07-real-borrow-execution-v1/06-direction-synthesis.md`
11. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/20-implementation.md`
12. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/20-implementation-bookkeeper-audit.md`
13. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-claude-glm.dispatch.md`
14. 三个 fix prompt/dispatch：
    `task-C-bookkeeper-fix-{1,2,3}.{prompt,dispatch}.md`
15. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/60-test-output.txt`
16. `reports/api-samples/2026-07-real-borrow-boundary-c-v1/20260720T150836Z/evidence-index.md`
    及其列出的 raw public contract samples
17. 实际产品代码、schema、前端改动及相关测试文件

## 固定 diff

必须实际运行或等价检查：

```text
git diff --binary c9df14591ac4ca00977ce0e4d80c0950aae44c19..61ce536dfba6ddd347586cf324209acdfdc6afd9 -- . ":(exclude)reports/agent-runs/2026-07-real-borrow-boundary-c-v1/status.json"
git diff --stat c9df14591ac4ca00977ce0e4d80c0950aae44c19..61ce536dfba6ddd347586cf324209acdfdc6afd9
```

不要把 prompt 后续纯记账提交纳入产品 diff，也不要遗漏固定范围内任何产品、
测试、schema、设计或证据文件。

## 审查重点

至少逐项核验：

1. 唯一 live write 是否严格限定为冻结的 portfolio-margin borrow exact path、
   POST method、canonical query、唯一 HMAC 出口与专用凭据；是否存在第二 POST、
   隐藏 retry、错误 URL 拼接、签名漂移或凭据/响应泄漏。
2. disabled/fake/live 模式、专用 credential 缺失、ownership 与单 worker 边界是否
   fail closed；API/UI 是否可能绕过显式 Start 或把 `live_authorized` 误当成
   已执行成功。
3. dispatch intent 的原子持久化、响应分类、known rejection、timeout/transport/
   malformed/unknown outcome，以及崩溃恢复是否遵守“不得盲重发第二次 POST”。
4. reconciliation 是否严格消费冻结的 `{"rows":[...],"total":N}` envelope；
   total、每行五字段、known txId、timestamp window、唯一候选、分页与 malformed
   member 是否全部 fail closed。
5. durable cross-task attribution 是否能阻止同资产/同 Decimal 金额的重叠未决任务
   重复认领同一借币记录，同时不把清晰唯一正例永久禁用。
6. 418/429/-1003 cooldown、300 秒最低隔离、manual re-arm、reconcile GET 的 418
   信号是否可被 Start、重启或普通 cooldown 路径绕过。
7. scheduler/store/service 的租约、并发、恢复、状态迁移与事件日志是否有竞态、
   重复借债、卡死或错误成功归因。
8. API/schema/frontend 契约、exact-path/HMAC/urlopen/import/UI guards 是否未被
   弱化；`live_authorized` 与 execution-status contract 是否向后兼容且测试充分。
9. 启动观测是否只输出布尔/计数/枚举，不泄漏 credential 值、签名、完整 URL、
   response body 或环境值。
10. 测试证据是否真实覆盖上述边界，尤其 fix-3 的两条完整候选歧义测试与独立
    malformed-row 测试；报告声明是否与 committed code/diff 一致。

若发现问题，必须给出 severity、文件/行、可复现证据、影响和最小修复建议。
不要因为自测全绿而推定通过。ACCEPT 仅在固定 diff 无 P0/P1、契约与证据完整、
且不存在必须先修的安全/正确性问题时给出。

## 输出合同

输出简洁 review narrative，随后写六行页脚，最后写一个且仅一个可解析 JSON
object，JSON 后不得再有任何文本。页脚必须位于 JSON 之前：

```text
当前 Session ID: <provider-native id | unavailable (reason)>
Session ID 来源: <runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable>
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/30-review-1.md
本地北京时间: <使用本会话实际执行的本地 date 命令，格式 YYYY-MM-DD HH:MM:SS CST>
下一步模型: <bookkeeper | human operator → Claude-GLM>
下一步任务: <specific next task>
```

最终 JSON 必须严格匹配
`schemas/review-verdict.schema.json`，并固定：

- `schema_version: 1`
- `stage_id: "2026-07-real-borrow-boundary-c-v1"`
- `role: "first_reviewer"`
- `model: "kimi-code/kimi-for-coding"`
- `diff_fingerprint` 为本 prompt 的完整固定值
- `reviewer_prior_involvement: "design"`
- `reviewer_prior_involvement_notes` 指向前述 Kimi 设计 review 工件

`reviewed_artifacts` 必须列出你实际读取的核心 raw artifact 与固定 git diff。
若 verdict 为 `REWORK`，`fix_start_prompt` 必须是可直接交给原始
Claude-GLM fix author 的完整修复 prompt，包含：

- stage 与完整 diff fingerprint；
- raw review 路径 `30-review-1.md`；
- 按 finding 排序的证据、required fixes 与验收标准；
- 原 Task C allowed/forbidden file boundaries；
- 禁止真实 Binance 请求、凭据读取、第二 POST、commit/push/merge/模型转派；
- 精确测试命令；
- 要求写 `40-fix-report.md` finding-to-fix 映射并追加
  `60-test-output.txt`，然后停给 bookkeeper。

不得把 `REWORK` 的 `fix_start_prompt` 省略或替换成“见上文”。若证据不可读或
无法可靠审查，使用 `BLOCKED`，不得猜测 ACCEPT。
