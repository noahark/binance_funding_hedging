# Review-2 Recheck Correction — Same Session And Full-Diff Coverage

继续在当前 Claude/Anthropic Opus 4.8 reviewer session
`cced0347-7f53-4626-958b-ecffba5d10b6` 中工作。不要重做整个 review，也不要修改文件。

你的 substantive `ACCEPT` JSON 已通过 schema 与 fingerprint 校验，但暂不能作为接受证据，
原因有两点：

1. 当前实际复用了旧的 dedicated review session，JSON notes 却写成
   `fresh read-only session`。请如实改为：这是同一个 dedicated read-only reviewer
   session 的 recheck；该 Session 从未实现或修复代码，仍与 `zhipu_glm` delivery/fix
   provider 隔离。
2. 本轮计算了完整 diff hash/stat 并查看 P2 delta，但没有按 recheck 合同实际展开检查完整
   固定 diff；部分 unchanged 文件依赖旧回合上下文。请补齐下面的当前读取与完整 diff。

## 只读补查

在当前回合重新读取以下文件的当前版本，不得仅依赖旧上下文：

```text
agents/skills/reality-checker.md
schemas/review-verdict.schema.json
reports/agent-runs/2026-07-local-service-launchd-v1/00-task.md
reports/agent-runs/2026-07-local-service-launchd-v1/10-design.md
reports/agent-runs/2026-07-local-service-launchd-v1/status.json
reports/agent-runs/2026-07-local-service-launchd-v1/80-escalation-real-launchd-desktop-tcc-20260713T134341Z.md
reports/agent-runs/2026-07-local-service-launchd-v1/manual-review-1-T1-launchd-service.verdict.json
backend/app/server.py
deploy/launchd/com.aoke.funding-hedging.server.plist.template
scripts/service-control.py
```

然后实际检查以下完整固定 diff，不得只计算 hash、stat 或只看
`85ab501..ed7d9e0` delta：

```text
git diff --binary 3bb253a489bf2854d8b9d81060a45ca056e1cea2..ed7d9e0a71d05aab15cc1ecad2f8197989b54b9d -- . ':(exclude)reports/agent-runs/2026-07-local-service-launchd-v1/status.json'
```

若工具输出截断，请按文件或行范围分块继续，直到完整 diff 的所有 changed paths 均已检查；
不得把 hash 匹配当作内容检查的替代。

仍然禁止写文件、读取 `.env`、启动服务、访问网络/私有渠道或执行真实 `launchctl`。

## 替换 JSON

补查后，只输出一个完整 JSON object，不要 Markdown fence、不要 JSON 前后说明。JSON 必须：

- 继续匹配 `schemas/review-verdict.schema.json`；
- 固定 `model=claude-opus-4-8`；
- 固定 `reviewer_prior_involvement=breakdown`；
- 固定 fingerprint：
  `ed7d9e0a71d05aab15cc1ecad2f8197989b54b9d:75d865afaa68b0895e8c2843d8d5fcc264a4ab1b9feddb36dd2529a9ce49100e`；
- 在 `reviewer_prior_involvement_notes` 中明确写明
  `same dedicated read-only reviewer session reused for the post-fix recheck; not a fresh session`；
- 在 `reviewed_artifacts` 中只列实际已读/已检查内容，并包含完整固定 diff；
- 若补查不改变结论，可保持 `ACCEPT`、`required_fixes=[]`、
  `next_action=stage_accepted_waiting_user`；若发现新问题则按 schema 如实改变 verdict。

本地北京时间: 2026-07-13 23:25:31 CST
下一步模型: Codex bookkeeper
下一步任务: 从同一 Session 提取替换 JSON，复核 disclosure/read-set/schema/fingerprint
