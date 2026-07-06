<!-- ============ RECEIPT（审计元数据，bookkeeper 回填；非任务内容） ============
status: pending            # pending | running | done | escalated
target_model: kimi FRESH read-only 会话（不得复用 Task B 实现会话上下文）
adapter_cmd: Task A 实现终端按 R10 收尾段以 kimi -p "$(cat 本文件)" 机械调用
started_at:
completed_at:
session_id:
outputs:                   # embedded-review-a-round<N>.raw-output.md
next_dispatch: PASS → bookkeeper 串行落盘（executor: bookkeeper）；BLOCKER → Task A scope 内修复 round2（封顶）
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行） ---

你是一个**全新的只读 Kimi 会话**，担任 stage
`2026-07-private-account-v1` Task A（后端）的**嵌入交叉预审者**。
这是 checkpoint 不是评审门：只产出 blocker 清单或放行意见，不产生
verdict JSON。评审对象 = 同目录 `embedded-review-a-round1.diff.patch`
（若存在 round2 则审最新一轮；未提交工作树快照，非指纹）。对照规格 =
`10-design.md` §1/§2/§3 + `00-task.md` + status.json hard_constraints
与 endpoint_whitelist。可读仓库任何文件；**禁止写文件、跑签名请求、
改工作树**。

## 必查清单（逐项 PASS/FAIL + 证据行号）

1. 白名单 12 项与 status.json 完全一致（(method, exact-path) 二元组、
   base_url 按 §2.A 附录）；越界/非 GET 在签名前 raise；负向单测齐。
2. 单一 HMAC 出口仍唯一（grep 断言更新且过）。
3. 成本腿四级链：命中判定/顺序/hourly×24 归一化正确；
   `borrow_rate_source` 取值合规；E1/E1b 未进快照装配。
4. net_daily_yield：§3.4 六向量逐一在测；Decimal 禁 float；负零归一。
5. 排序：§3.5 两组向量（net 反超用例 + 降级回归 Phase 2 全序）在测；
   sort_basis 快照级单一。
6. coverage/warnings：上限 50 可配、截断标 not_probed、禁静默 verified。
7. private_account：防重复计算两条硬规则有测试断言；折算价格 map
   全量一次；三态降级 schema PASS。
8. key/数值卫生：diff 与新 fixture 无 key 片段、无真实账户数值
   （按 §2.A 脱敏标记表抽查）。
9. 越界检查：diff 只触碰 §3.1 允许文件；classify/normalize 零改动；
   无 commit、无 status.json 改动；无任何 websocket/listenKey 铺垫。

## 输出

逐项 PASS/FAIL 表 → blocker 清单（文件/行/缺陷/修法）→ 总结论
`PASS（可落盘）` 或 `BLOCKER（需修复后 round 2）`。末尾注明模型身份
与当前本地北京时间。你的输出将被逐字落档。
