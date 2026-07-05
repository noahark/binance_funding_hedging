<!-- ============ RECEIPT（审计元数据，bookkeeper 回填；非任务内容） ============
status: pending            # pending | running | done | blocked | escalated
target_model: claude_glm (glm-5.2) 实现会话（独立于 bookkeeper 会话）
adapter_cmd: 用户向 fresh claude-glm 实现终端发「读文件执行 PROMPT BODY」一行指令
started_at:
completed_at:
session_id:
outputs:                   # 20-implementation-backend.md / R10 收尾产物
next_dispatch: R10 收尾段（executor: self——完成实现后必须机械执行，不得以等待结束）
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行） ---

你是 stage `2026-07-private-account-v1` 的 **Task A 实现者**（后端）。
权威规格 = 同目录 `10-design.md` §1/§2/§3（先通读全文 + `00-task.md` +
status.json hard_constraints + 10-design §2.A 附录/冻结预算表）。
冲突时 10-design 赢。当前分支应为 `stage/2026-07-private-account-v1`
（只核对，不切换）。

## 交付物

1. `private_client.py`：白名单扩至 status.json 12 项（base_url 按
   §2.A 附录逐端点冻结值）+ 对应 fetch 方法 + 两组 TTL 缓存（§1.6）；
   单一 HMAC 出口不变。
2. 成本腿四级链（§1.3）：快照级判定 + hourly×24 归一化 +
   `daily_interest_account` / `borrow_rate_source` 装配。
3. `net_daily_yield`（§1.1 定义 + §3.4 六向量全部在测）。
4. 排序 + `sort_basis`（§1.2；§3.5 两组向量在测，Phase 2 全序回归）。
5. 借币探测扩围 + coverage/warnings（§1.5；上限 50 可配、截断語义）。
6. `private_account` 块 + 防重复计算（§1.4 硬规则有测试断言）+
   ticker 价格 map 折算。
7. schema v0.3（wire version 不变）+ 契约 amendment（引 H_intake
   证据路径）。
8. §3.3 全部安全负向单测；既有测试零回归。
9. `20-implementation-backend.md`：改动清单、测试原始输出、自查表。

## 硬边界（违反即预审 blocker）

- 允许文件严格按 10-design §3.1；classify.py/normalize.py/frontend
  零触碰；scripts/ 不动（discovery 属 bookkeeper）。
- E1/E1b 本轮不进快照装配；禁止行循环内 HTTP；禁止新增端点（R3）。
- key 零片段；进 git 的 fixture 用脱敏值；Decimal 禁 float。
- 耦合面（00-task 七项）变更需求 → 停手上报 bookkeeper（R3）。
- **不 commit、不碰 status.json**；改动只留工作树。

## R10 收尾段（实现与自测完成后必须机械执行，路径已写死）

1. 自测：
   `python3 -m pytest backend/tests/ -q 2>&1 | tail -20`
2. 生成预审 diff：
   `git diff -- backend schemas docs/api > "reports/agent-runs/2026-07-private-account-v1/embedded-review-a-round1.diff.patch"`
3. 调用对侧 fresh 预审（Kimi）并落档 raw output：
   `kimi --model kimi-code/kimi-for-coding -p "$(cat 'reports/agent-runs/2026-07-private-account-v1/pre-review-task-a-by-kimi.prompt.md')" | tee "reports/agent-runs/2026-07-private-account-v1/embedded-review-a-round1.raw-output.md"`
4. 分支处理：
   - **PASS** → 输出「Task A 预审 PASS，等待 bookkeeper 串行落盘」+
     移交指令一行；
   - **BLOCKER 且在你 scope 内** → 修复 → 写
     `embedded-review-a-round1.fix-note.md` → 重新生成
     `embedded-review-a-round2.diff.patch` 并以同一命令（round2 文件名）
     再预审一次（封顶 2 轮）；
   - **BLOCKER 涉及契约/共享字段/越 scope，或 round2 仍 BLOCKER** →
     停手，输出升级报告给 bookkeeper；
   - **kimi 命令不可用/失败** → 写
     `reports/agent-runs/2026-07-private-account-v1/embedded-review-a-round1.dispatch.md`
     记录（unavailable|permission|command_error + 原始报错），声明
     escalated——**禁止只口头说等待**。

完成后输出：改动文件清单 + 测试摘要 + 预审结论 + 本地北京时间。
