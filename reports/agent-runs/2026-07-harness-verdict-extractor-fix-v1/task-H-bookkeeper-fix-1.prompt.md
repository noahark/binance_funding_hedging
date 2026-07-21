[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于 claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出 ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条执行记录都必须对应你本会话内真实发生的动作。
3. 你的修复依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的文件。

# Task H — Bookkeeper Intake Micro Fix 1 / BK-H-001

你是原 Task H 实现者 Claude-GLM / `zhipu_glm` / `glm-5.2[1m]`。可继续原
会话或 compact 后继续；不得启动或转派其他模型。正式 `rework_count` 保持 `0`，
因为 formal review-1 尚未开始。

## 必读

1. `AGENTS.md`
2. `agents/developer-discipline.md`
3. `reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/00-task.md`
4. `reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/10-design.md`
5. `reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/20-implementation.md`
6. `reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/20-implementation.bookkeeper-audit.md`
7. `reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/60-test-output.txt`
8. `scripts/validate-stage.py`
9. `scripts/tests/test_validate_stage_dispatch_protocol.py`
10. `docs/parallel-development-mode.md` R12

## 唯一阻塞 finding

`BK-H-001`: 当前只记录 decoded dict spans。最终 JSON 为
`[schema_valid_verdict]` 时，外层 list 不参与 containment，内层 verdict dict
被错误提升为 top-level，`_parse_review_artifact` 返回 `ACCEPT` 且零 errors。

必须以最小改动关闭：

- containment 必须识别成功 decoded 的 array/list span；任何完整 span 被 decoded
  dict 或 list container 严格包含的 dict candidate 都是 nested，不得胜出。
- 只返回非 nested 的 dict；不得把 list 当 verdict 返回，不得 schema-match 回退。
- 保留现有 findings-bearing verdict、prose/fence/footer、trailing malformed brace、
  string braces、ordering、final schema-invalid dict fail-closed 和 Session-ID tests。
- 修正 `scripts/validate-stage.py` 注释以及 R12 文档，将 “other dict span” 改成
  “decoded dict or list container span”；不要扩大协议。

新增至少以下 regression：

1. `[valid_verdict]` → extractor 不返回 contained verdict，parse gate fail closed；
2. `[[valid_verdict]]` 同样 fail closed；
3. 正常顶层 verdict + non-empty findings 仍返回完整 verdict；
4. footer 中无害 bracket 文本不破坏之前的有效 verdict；
5. 现有 `test_final_schema_invalid_does_not_fall_back_to_earlier_valid` 保持通过。

## File boundary

允许修改：

```text
scripts/validate-stage.py
scripts/tests/test_validate_stage_dispatch_protocol.py
docs/parallel-development-mode.md
reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/20-implementation.md
reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/60-test-output.txt
reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/task-H-bookkeeper-fix-1.dispatch.md
```

报告与 test log 只能 append；dispatch 只回填 receipt 与执行页脚。禁止其他所有文件，
特别是 `ACTIVE.json`、task/design/ADR、`status.json`、`70-handoff.md`、bookkeeper
audit、workflow/schema/registry、产品代码、Boundary C、`.env*`。不得 commit、push、
merge、rebase、切换 `main`、读取 credentials 或 dispatch 任何模型。

## 完成验证

真实执行并 append 全部输出：

```text
python3 -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
python3 -m pytest scripts/tests -q
python3 -m py_compile scripts/validate-stage.py
python3 scripts/test-validate-all-stages-compare.py --repo-root .
python3 scripts/validate-stage.py 2026-07-harness-verdict-extractor-fix-v1 --phase checkpoint
git diff --check
git status --short
```

在 `20-implementation.md` 追加 BK-H-001 finding→root cause→changed files→tests→
result 和残留风险，末尾写本 target runtime 真实六行页脚；回填 fix dispatch receipt
与页脚后停止，交回 bookkeeper。不得宣称 review 或 acceptance。

当前 Session ID: unavailable (prompt preparation runtime does not expose provider-native Session ID; target runtime must record its own verified ID or exact unavailable reason)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/task-H-bookkeeper-fix-1.prompt.md
本地北京时间: 2026-07-21 15:59:10 CST
下一步模型: human operator → original Claude-GLM / glm-5.2[1m]
下一步任务: execute BK-H-001 micro-fix, prove top-level array-wrapped verdicts fail closed, fill the receipt, and stop for bookkeeper
