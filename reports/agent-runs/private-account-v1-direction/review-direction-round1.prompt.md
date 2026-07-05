<!-- ============ RECEIPT（审计元数据；非任务内容） ============
status: pending            # pending | running | done | escalated
target_model: gpt5.5 / claude_glm / kimi（三方各自 fresh 会话，独立评审互不可见）
adapter_cmd: 用户以「读文件并执行 PROMPT BODY」一行指令分发至各模型终端
started_at:
completed_at:
session_id:
outputs:                   # review-<model>.md（各模型评审落档，逐字保留）
next_dispatch: 三份评审齐 → Fable5 吸收出 DRAFT-2 → Codex 合成（executor: user 中转）
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行） ---

你是「私有账户数据接入 v1」方向草案的**独立评审者**（fresh 会话，
禁止参考其他模型的评审）。

## 评审对象与输入

1. `docs/private-account-v1-direction-draft.md`（DRAFT-1，评审对象）
2. `docs/phase2-direction-draft.md`（FROZEN 上游基线，冲突时基线赢）
3. `docs/api/public-market-contract.md` + `schemas/api/public-market/
   snapshot.schema.json`（现行契约 v0.2）
4. 可读仓库任何文件（如 `backend/services/private_client.py` 的白名单
   实现、`reports/agent-runs/2026-07-phase2-borrow-sort-v1/11-adr.md`
   的 ADR-5）；`llms-full.txt` 为官方文档 dump，端点主张须引行号。

## 评审要求

- 逐节（§1-§8）给 AGREE / REWORK（附一句话理由）；
- 重点核查：①净收益公式的方向语义（§3.4 负费率=借币做空现货腿）是否
  正确；②E1-E4 候选端点与统一账户（非 Pro）的适配性；③安全/隐私条款
  是否有漏洞（尤其账户数值落档脱敏）；④与永久禁令有无隐性冲突；
- 对开放问题 O1-O5 逐一给出你的建议答案 + 理由；
- 发现的新风险按 P1/P2/P3 列出（文件/条款定位 + 缺陷 + 建议修法）；
- 末尾给总结论：ACCEPT / REWORK（REWORK 须列必改清单）。

## 输出纪律

- 你的输出将逐字落档为
  `reports/agent-runs/private-account-v1-direction/review-<你的模型名>.md`，
  不要输出与评审无关的内容；
- 禁止写文件、改工作树、跑任何签名请求；
- 末尾注明模型身份与当前本地北京时间。
