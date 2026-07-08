# 70-handoff — 2026-07-borrowability-error-zero-mapping-v1

## 阶段状态

`status = review_2`。review-1(Kimi) **ACCEPT** 已落档核验。review-2(Codex) round-1
= BLOCKED，但**仅因过时 gate 状态**（未跟踪 raw output 致工作区不 clean + status 还 review_1
+ 30-review-1 未落档 → pre-review 失败），**非代码 REWORK**；bookkeeper 已修复门禁（commit
`10618a3`）并复验 `pre-review` PASSED，备 round-2 重派。stage 分支
`stage/2026-07-borrowability-error-zero-mapping-v1`，**未推送 / 未合 main**。

## 冻结区间（review 用）

```text
base_sha=41c6ba542e040cb3d1e82c046d9a9406bd11860d
head_sha=ea631bf1dbf23662db37f491d92cb3f10685d720
diff_fingerprint=ea631bf1dbf23662db37f491d92cb3f10685d720:31efea285e557d074f8f49d30146b07a285e3ecdb1a19d776b170479983251aa
```

diff 命令：
`git diff --binary 41c6ba5..ea631bf -- . ':(exclude)reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/status.json'`

## 提交序（stage 分支）

- `a851708` freeze design + GLM dispatch packet
- `2f31408` SCOPE-001（allowlist `test_phase2_borrow_sort.py`）
- `125e496` SCOPE-002（收窄 ADR-2 按码正负分类 + allowlist `test_private_client.py`）
- `ea631bf` **H1 实现**（implementer=claude_glm，bookkeeper 提交）← head_sha
- `2d0adbf` H2 bookkeeper：冻结 fingerprint + status=review_1
- （本文件所在 H3 handoff 提交）

## 角色与 provider 隔离

- designer/bookkeeper：anthropic（本会话）
- implementer：claude_glm / zhipu_glm
- review_1：kimi / moonshot_kimi（fresh，prior_involvement=none）
- review_2：codex / openai（designer 是 anthropic，故 review_2 走 openai 保隔离）

## bookkeeper 独立复核结论

- 11 改动文件全部在冻结允许列表内（含 SCOPE-001/002 追加的两测试文件），无越界、无 untracked。
- diff 逐个核：private_client 正/负码分类正确、`test_private_client.py:238`(-2015) 金标准未动；
  snapshot 折算 8dp 口径同 balance value_usdt、assemble 三出口 additive；schema additive+required；
  前端 badge/subline 对版；两 amended 测试严格按 SCOPE 口径。
- 独立重跑：`pytest backend/tests -q` => 190 passed；`node frontend/self-check.js` => 全部自检通过
  （含「借币三态」）；`git diff --check` => clean。证据 `60-test-output.txt`。

## 交付摘要

- 51061 借光 → `max_borrowable="0"` + `error_code="51061"`（确定 0，非 null）；前端 badge 转
  `warn`「可借 0(已借完)」，不再绿色「已验证可借」。
- 业务/系统分界 = Binance 码正负号：正数非零集 → distinct discovery log；负数/无 code → `max_borrowable_failed`。
- additive：`portfolio_account` +`error_code` +`max_borrowable_value_usdt`（8dp ≈USDT 折算）。
- residual R1 注释补正 `{CRYPTO, METAL}`。`verified` 语义未变。

## 下一步

1. 用户在 fresh Kimi 会话用 `review-1-kimi.prompt.md` 派发只读 review-1，产出
   `review-1-kimi.raw-output.md`（末尾 schema-valid verdict JSON）。
2. ACCEPT → bookkeeper 落 `30-review-1.md`，派 review-2（Codex/openai）；REWORK → 回 GLM 修复。
3. review-2 ACCEPT 后 → `pre-accept` 校验 → **用户显式验收** → `--no-ff` 合并 main + 推送。

## Out-of-scope / residual

- 权限类/非 51061 业务错误映射、第四态：无样本，走 distinct 日志发现，未实现。
- residual R2（METAL 借币候选 live sample）：挂等公开金属现货腿。R3（行尾空格）：忽略。

本地北京时间: 2026-07-09 06:54:10 CST
下一步模型: kimi（review-1）
下一步任务: 只读 review-1，产出 schema-valid verdict JSON。
