[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于 claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出 ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条执行记录都必须对应你本会话内真实发生的动作。
3. 你的实现依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的文件。

# Task H — Harness Final Top-Level Verdict Extractor

你是 Claude-GLM / `zhipu_glm` / `glm-5.2[1m]`，是本任务唯一实现者。
这是轻量但 gate-critical 的 Harness 修复。Codex 仅准备任务和记账，不写实现。

## 启动断言

开始前执行并记录：

```text
git branch --show-current
git status --short
```

当前分支必须是 `harness/dispatch-review-reform-v1`。如果不是，或存在无法归因
的重叠修改，立即停止并报告 blocker；不要 checkout、switch、reset 或清理文件。

## 必读 raw artifacts

1. `AGENTS.md`
2. `agents/developer-discipline.md`
3. `docs/parallel-development-mode.md`（R9、R11、R12）
4. `workflows/templates/stage-delivery.yaml`（test、review-1 gate authority）
5. `scripts/validate-stage.py`（`extract_last_json_object`、`_parse_review_artifact`、Session-ID consistency）
6. `scripts/tests/test_validate_stage_dispatch_protocol.py`
7. `reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/00-intake.md`
8. `reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/00-task.md`
9. `reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/10-design.md`
10. `reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/11-adr.md`
11. `reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/60-test-output.txt`
12. 原始 Boundary C finding 的 committed blob：
    `git show 9ee2439:reports/agent-runs/2026-07-real-borrow-boundary-c-v1/harness-review-verdict-extractor.follow-up.md`

## 必须修复

当前实现从文件末尾反向找 `{`，遇到第一个可被 `raw_decode()` 解码为 dict 的
suffix 就返回。findings 非空时，最后一个 finding 自身也是合法 dict，导致它覆盖
外层 verdict。

实现 `00-task.md` 与 `10-design.md` 定义的 final top-level-object 语义：

- 完整 verdict 必须覆盖零、一个和多个 findings。
- nested dict 不得胜出；不得把 extractor 改成“找到第一个 schema-valid verdict”，
  以免 final schema-invalid object 回退到更早的旧 verdict。
- 保留 prose、JSON fence、footer、trailing whitespace、字符串内 braces/escaped
  quotes、Unicode 和尾部不可解析 brace 兼容性。
- 后置 schema 校验继续 fail closed。
- 保持函数接口、零第三方依赖，并用最小改动完成。
- 更新 R12 的一处语义说明，使文档不再描述已知错误的 nested-object 行为。

测试必须包含：

1. zero / one / multiple findings；
2. finding 内嵌 metadata object；
3. braces 与 escaped quotes 位于字符串中；
4. prose + fence + footer + trailing whitespace / malformed brace；
5. 较早独立 JSON object + final verdict；
6. 较早 schema-valid verdict + final schema-invalid top-level object，证明不 fallback；
7. `_parse_review_artifact` 对 findings-bearing REWORK 的集成通过；
8. Session ID unavailable explanation 分别由 ASCII space 和全角标点引入时的
   consistency regression。

## File boundary

允许修改：

```text
scripts/validate-stage.py
scripts/tests/test_validate_stage_dispatch_protocol.py
docs/parallel-development-mode.md
reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/20-implementation.md
reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/60-test-output.txt
reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/task-H-claude-glm.dispatch.md
```

`60-test-output.txt` 只能 append；dispatch 文件只回填 receipt 和执行页脚。

禁止修改其他所有文件，特别是：

```text
backend/**
frontend/**
schemas/**
AGENTS.md
agents/registry.yaml
workflows/**
reports/agent-runs/ACTIVE.json
reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/{00-intake.md,00-task.md,10-design.md,11-adr.md,status.json,70-handoff.md}
reports/agent-runs/2026-07-real-borrow-boundary-c-v1/**
docs/product/**
docs/architecture/**
.env*
```

不得 commit、push、merge、rebase、checkout/switch `main`、dispatch 任何模型、
弱化 schema/receipt/identity/fingerprint/clean-worktree gate，或宣称 review / acceptance。

## 完成验证

按顺序真实执行，把完整输出 append 到 `60-test-output.txt`：

```text
python3 -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
python3 -m pytest scripts/tests -q
python3 -m py_compile scripts/validate-stage.py
python3 scripts/test-validate-all-stages-compare.py --repo-root .
python3 scripts/validate-stage.py 2026-07-harness-verdict-extractor-fix-v1 --phase checkpoint
git diff --check
git status --short
```

若任何命令失败，保留真实输出，修复范围内问题后重跑；不得隐藏失败历史。

## 收尾

在 `20-implementation.md` 追加：root cause、算法与取舍、逐项 requirement→test
映射、改动文件、真实命令结果、残留风险、`git status --short`。报告末尾必须使用
本 runtime 可核验的 Session ID；不可见则写精确 unavailable 原因，绝不猜测：

```text
当前 Session ID: <provider-native id | unavailable (reason)>
Session ID 来源: <runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable>
原始输出路径: reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/20-implementation.md
本地北京时间: <local date command> CST
下一步模型: bookkeeper
下一步任务: independently audit Task H, rerun Harness tests, create committed evidence and prepare fresh Kimi review-1 only if all gates close
```

随后回填 `task-H-claude-glm.dispatch.md` receipt 与执行页脚并停止。不要自行启动
Kimi、Codex、Claude 或任何其他模型。

当前 Session ID: unavailable (prompt preparation runtime does not expose provider-native Session ID; target runtime must record its own verified ID or exact unavailable reason)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/task-H-claude-glm.prompt.md
本地北京时间: 2026-07-21 14:36:22 CST
下一步模型: human operator → Claude-GLM / glm-5.2[1m]
下一步任务: execute Task H as the sole implementer, append all raw evidence, fill the receipt, and stop for bookkeeper
