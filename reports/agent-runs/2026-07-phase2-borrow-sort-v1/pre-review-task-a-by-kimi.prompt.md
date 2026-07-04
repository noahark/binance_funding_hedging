<!-- ============ RECEIPT（审计元数据，bookkeeper 填写；非任务内容） ============
status: pending            # pending | running | done | blocked
target_model: kimi (FRESH read-only session; 不得复用 Task B 实现会话上下文)
adapter_cmd: 用户粘贴 PROMPT BODY + 当轮 diff.patch 路径至全新 Kimi 会话
started_at:
completed_at:
session_id:
outputs:                   # embedded-review-a-round<N>.raw-output.md
next_dispatch: 无 blocker → bookkeeper 串行落盘；有 blocker → Task A 修复后 round 2（封顶）
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行） ---

你是一个**全新的只读 Kimi 会话**，担任 stage
`2026-07-phase2-borrow-sort-v1` Task A（后端）的**嵌入交叉预审者**。
这是并行开发模式的 **checkpoint，不是评审门**：你的结论不产生
review verdict JSON，只产生「blocker 清单或放行意见」。

## 评审对象

- 当轮工作树 diff：`reports/agent-runs/2026-07-phase2-borrow-sort-v1/
  embedded-review-a-round<N>.diff.patch`（调用方会给出 N；这是未提交
  改动的快照，**不是 fingerprint**）
- 对照规格：同目录 `10-design.md` §1/§2/§3、`00-task.md`、
  status.json `hard_constraints` + `endpoint_whitelist`
- 可读仓库任何文件；**禁止写文件、跑签名请求、改工作树**。

## 必查清单（逐项给 PASS/FAIL + 证据行号）

1. 单一 HMAC 出口：diff 中签名构造仅出现于 `private_client.py`；
   grep 单测存在且正确。
2. 白名单 deny-by-default：`(method, exact-path)` 二元组、四端点与
   status.json 完全一致；越界 path / 非 GET 在签名构造前 raise；
   负向单测三态齐全。
3. key 卫生：diff 与测试 fixture 中无任何 key/secret/signature 片段；
   审计日志字段合规（无完整 query）。
4. daily_funding_rate：Decimal 实现、禁 float；10-design §3.3 六个
   测试向量逐一在测；负零归一化。
5. 排序：abs 降序 + null 末尾 + symbol tie-break 的全序测试存在。
6. borrow_validation 三态语义正确；portfolio_account 仅 bounded top-N；
   bStock 不做账户级探测；classify.py/normalize.py 零改动（diff 必须
   不含这两个文件）。
7. 越界检查：diff 只触碰 10-design §3.1 允许文件；无 commit、无
   status.json 改动。
8. 契约 v0.2 与 schema 扩展同步、引用 discovery 证据路径。

## 输出格式

逐项 PASS/FAIL 表 → blocker 清单（每条：文件/行/一句话缺陷/建议修法）
→ 总结论 `PASS（可落盘）` 或 `BLOCKER（需修复后 round 2）`。
末尾注明你的模型身份与当前本地北京时间。你的输出将被逐字落档。
