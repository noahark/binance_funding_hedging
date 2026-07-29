# Context Guard Note — paste-in for the running Claude-GLM session

**Purpose**: the implementation session (`2b5e8d01-45cb-4219-a96f-b0d8604bb6d3`)
reached ~65% of its 1M context before starting work. The user chose to let it run
all six steps. If it compacts, the first things lost are the frozen constraints —
which is precisely the failure mode that produced three cross-seam drifts in an
earlier round of this programme.

**How to use**: the human operator pastes the block below into the running
session if it compacts, or before W4 (the largest step) as a precaution. It is
deliberately short so it does not itself consume meaningful budget. It adds no
new requirement — every line restates something already in `00-task.md`,
`10-design.md` or `13-implementation.dispatch.md`.

**Do not paste it repeatedly.** Once before W4 is enough.

---

```text
上下文守护提醒（不是新要求，全部是已冻结的约束，逐条复核）：

1. 总原则：宁可显式失败/显式未知，也不要落一个与真实值无法区分的替代值。
   本 stage 四个缺陷全是"用说得通的值顶替已有信息"。

2. T2：51169 → 类别 `collateral_cap`，pause_reason=`collateral_cap_full`。
   **不是** insufficient_funds，**不得**复用 insufficient_margin
   （它渲染的"保证金不足"对 51169 是伪事实——根因是平台级抵押上限打满，加钱无效）。
   上卷优先级：fatal > auth > collateral_cap > insufficient_funds > unclassified > absent。
   未识别码落 `unclassified`，不再是 NULL。
   除 51169 外**任何负数码的判定都不许变**，回归矩阵要能证明。

3. 10-design §2(d) 的中文操作员文案是**冻结逐字**的，测试逐字断言，不要改写措辞。

4. T1：取不到权威金额时禁止落 "0"（与真实零无法区分）→ 用 NULL + 非终态。
   margin 有 cummulativeQuoteQty、UM/CM 没有，这个不对称要写成**有意的按产品分流规则**，
   不是顺手的 or 链。

5. T5：回归测试必须真的走 service._dispatch_to_outcome（**实盘路径**）。
   只测 executor.py 不算数——那条路径今天就是对的，正是它掩盖了这个 bug。

6. T3：raw 落库失败**不得**把成功的单变成失败；凭据/签名/API key 一律不落库。

7. 文件边界：禁改 hedge_open_live_client.py / binance_signing.py /
   wire_constraints.py / scheduler.py / server.py / config.py /
   test_hedge_purity.py / test_hedge_open_live_client.py / frontend/** /
   schemas/** / scripts/** / docs/** / data/**。
   未列出的默认禁止。hedge_open_live_client.py 确需改动 = 契约修订，停下交回 bookkeeper。

8. 实盘面开着（服务 PID 96409 live 运行中、Start 闸门=1）：不下单、不建卡、
   不碰凭据、不启停服务、不写 data/hedge-open-tasks.sqlite3（迁移只在测试临时库跑）。

9. 测试用 `.venv/bin/python -m pytest`（**不是** python3，系统 python3 是 3.9.6）。

10. 收尾：跑测试生成 60-test-output.txt、写 20-implementation.md（含 T2(c) 判定变化清单
    与 T5(c) 关于 leg_exposure.price 是否恢复的**实测**陈述）、然后停下等 bookkeeper。
    不 commit，不自己派评审。
```

---

## Bookkeeper's own mitigation (independent of whether this note is used)

Because compaction risk was accepted rather than removed, the R4 boundary
reconciliation after this session stops will **not** rely on the implementation
report's word for any of the following. Each is verified directly against the
diff and the code:

1. `git diff --name-only` contains no forbidden path — especially
   `hedge_open_live_client.py`, `wire_constraints.py`, `test_hedge_purity.py`,
   `test_hedge_open_live_client.py`, and anything under `data/`.
2. The frozen Chinese operator copy appears byte-identical to `10-design.md`
   §2(d), and a test asserts it verbatim.
3. `51169` maps to `collateral_cap` / `collateral_cap_full`, and
   `insufficient_margin` appears nowhere on its path.
4. The roll-up priority includes `collateral_cap` in the specified position.
5. No path can still store a fabricated `"0"`: check `_decimal_str`'s default,
   every branch of `_leg_final_fields`, and migration M1.
6. The T5 regression genuinely drives `service._dispatch_to_outcome`, not
   `executor.py`.
7. The negative-code regression matrix exists and covers the codes it claims to.
8. The production database is untouched (`data/` mtimes and git status).
9. Nothing was committed by the implementer and `status.json` / `70-handoff.md`
   are unmodified.

Recorded so the verification is planned before the evidence arrives, not
improvised after it.
