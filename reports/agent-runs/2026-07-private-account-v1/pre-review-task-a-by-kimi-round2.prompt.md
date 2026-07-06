<!-- ============ RECEIPT（审计元数据；非任务内容） ============
status: pending            # pending | running | done | escalated
target_model: kimi FRESH read-only 会话（不得复用 round1 / Task B 实现会话上下文）
round: 2                   # round1 结论 BLOCKER（scope 内两处），已修复 → round2 复审
round1_blockers:
  - A: §1.5 顶层 warnings 截断条目缺失（assemble_snapshot 已补，由 coverage.skipped>0 驱动）
  - B: §1.4 private_account 三态未挂 classic_ref（build_snapshot 已门控，classic_ref None 跳过 E3/E4/E6）
adapter_cmd: Task A 实现终端按 R10 收尾段以 kimi -p "$(cat 本文件)" 机械调用
outputs:                   # embedded-review-a-round2.raw-output.md
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行） ---

你是一个**全新的只读 Kimi 会话**，担任 stage
`2026-07-private-account-v1` Task A（后端）的**嵌入交叉预审者（round 2 复审）**。
这是 checkpoint 不是评审门：只产出 blocker 清单或放行意见，不产生
verdict JSON。

## 背景

- round 1（`embedded-review-a-round1.raw-output.md`）结论 **BLOCKER**，两项
  均在 Task A scope 内（`backend/domain/snapshot.py` + `backend/services/snapshot_service.py`）：
  - **A**：`coverage.skipped > 0` 时未向顶层 `warnings` 追加条目（§1.5 line 78
    明文「顶层 warnings 追加条目 + coverage 块」二者并列）。
  - **B**：`private_account` disabled 判定用 `unified is None and spot is None`，
    未挂 `classic_ref`；classic_ref 失败但 E3/E4/E6 成功时 verified=true，违反
    §1.4 heading「private_account 块（顶层，三态语义同 borrow_validation）」。
- 实现者已修复并加 2 个回归测试，全量 `147 passed`（round1 145 + 2）。
- 评审对象 = 同目录 **`embedded-review-a-round2.diff.patch`**（最新一轮；未提交
  工作树快照，非指纹）。对照规格 = `10-design.md` §1/§2/§3 + `00-task.md` +
  status.json hard_constraints 与 endpoint_whitelist。可读仓库任何文件；
  **禁止写文件、跑签名请求、改工作树**。

## round 2 必查清单（逐项 PASS/FAIL + 证据行号）

1. **[重点核验 round1 blocker A 已修且无副作用]** `assemble_snapshot` 在
   `borrow_validation_summary.coverage.skipped > 0` 时追加顶层 warning
   `borrow_validation: N candidate(s) truncated by rate_limit_budget
   (not_probed_this_round)`；offline（skipped=0）不触发，故
   `test_three_contract_warnings_preserved`（len==3）不受影响。回归
   `test_truncation_appends_top_level_warning` 在测。
2. **[重点核验 round1 blocker B 已修且无副作用]** `build_snapshot` 在
   `classic_ref is None` 时跳过 E3/E4/E6 + price_map，令 `private_account`
   进入 disabled 三态（verified=false、三数组空、total null、error 沿用
   `private_error`）。回归 `test_private_account_disabled_when_classic_ref_none_even_if_accounts_return`
   （服务级桩：classic_ref=None 但 unified/spot 有数据 → 仍 verified=false）在测。
   单源失败（classic_ref ok，E3/E6 单败）仍走 partial-failure 分支
   （verified=true、该数组空）未被回归。
3. 白名单 12 项与 status.json 完全一致；越界/非 GET 签名前 raise；负向单测齐。
4. 单一 HMAC 出口仍唯一（grep 断言更新且过）。
5. 成本腿四级链：命中判定/顺序/hourly×24 归一化；`borrow_rate_source` 合规；
   E1/E1b 未进快照装配。
6. net_daily_yield：§3.4 六向量逐一在测；Decimal 禁 float；负零归一。
7. 排序：§3.5 两组向量在测；sort_basis 快照级单一。
8. coverage/warnings：上限 50 可配、截断标 not_probed、禁静默 verified
   （与 item 1 的顶层 warning 是同一规格要求的两面）。
9. key/数值卫生：diff 与 fixture 无 key 片段、无真实账户数值（§2.A 脱敏表抽查）。
10. 越界检查：diff 只触碰 §3.1 允许文件；classify/normalize 零改动；
    无 commit、无 status.json 改动；无 websocket/listenKey 铺垫。

## 输出

逐项 PASS/FAIL 表 → blocker 清单（文件/行/缺陷/修法；若 round1 两处仍未修干净
务必标 BLOCKER）→ 总结论 `PASS（可落盘）` 或 `BLOCKER（需 round 3）`。
末尾注明模型身份与当前本地北京时间。你的输出将被逐字落档。
