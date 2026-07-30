# Raw Reviewer Output — task0-plan-review

Verbatim as transferred by the Human operator on 2026-07-30 13:01 CST. Model
self-identified as `gpt5.6-terra` (Codex session, provider `openai`). Nothing
below is edited, reordered, or summarised; the Bookkeeper's verification of these
claims is a separate file (`07-plan-review-verdict.md`).

---

gpt5.6-terra 回执：评审结论：REWORK（返工）。计划按现状不能闭合该缺陷族，会留下至少一个新的金额零值站点。

### J1 — Exhaustiveness：否

独立扫描发现计划遗漏了 `prepare_attempt` 为尚未获得交易所回报的两个预备腿写入 `cumulative_quote_amt='0'`：

- store.py:748
- store.py:765

两处腿尚未下发、没有任何交易所金额，却会由 API 投影为金额 `"0"`。这不在 §4a 或 §4c，且 D5 的模式也抓不到 SQL 字面量。因此 §4 的“闭合集合”主张不成立。

独立扫描命令及原始输出：

```text
$ rg -n -e '_num\(' -e "or ['\"]0['\"]" -e "get\([^)]*['\"]0['\"]" -e 'Decimal\(0\)' backend/hedge_open_tasks backend/services/live_hedge_executor.py

backend/hedge_open_tasks/executor.py:180:        cumulative_quote = (filled_qty * price) if price is not None else Decimal(0)
backend/hedge_open_tasks/domain.py:947:        available = snapshot.balances.get(QUOTE_ASSET, Decimal(0))
backend/hedge_open_tasks/domain.py:950:        available = snapshot.balances.get(base, Decimal(0))
backend/hedge_open_tasks/domain.py:1050:        "qty": str(leg.get("filled_qty", "0")),
backend/hedge_open_tasks/service.py:214:    base = D.Decimal(leg.get("cumulative_base_qty") or "0")
backend/hedge_open_tasks/service.py:252:    spot_base = D.Decimal((spot_leg or {}).get("cumulative_base_qty") or "0")
backend/hedge_open_tasks/service.py:253:    perp_base = D.Decimal((perp_leg or {}).get("cumulative_base_qty") or "0")
backend/hedge_open_tasks/service.py:284:    base = D.Decimal(leg.get("cumulative_base_qty") or "0")
backend/hedge_open_tasks/service.py:310:    base = D.Decimal(leg.get("cumulative_base_qty") or "0")
backend/hedge_open_tasks/service.py:774:        spot_base = D.Decimal((spot_leg or {}).get("cumulative_base_qty") or "0")
backend/hedge_open_tasks/service.py:775:        perp_base = D.Decimal((perp_leg or {}).get("cumulative_base_qty") or "0")
backend/hedge_open_tasks/store.py:292:def _num(value) -> Decimal:
backend/hedge_open_tasks/store.py:294:        return Decimal(str(value)) if value is not None else Decimal(0)
backend/hedge_open_tasks/store.py:296:        return Decimal(0)
backend/hedge_open_tasks/store.py:810:        filled_qty = _num(leg_outcome.get("filled_qty"))
backend/hedge_open_tasks/store.py:1335:        base = _num(leg_row["cumulative_base_qty"])
backend/hedge_open_tasks/store.py:1336:        quote = _num(leg_row["cumulative_quote_amt"])
backend/hedge_open_tasks/store.py:1605:                    str(outcome.spot.get("filled_qty", "0")),
backend/hedge_open_tasks/store.py:1610:                    str(outcome.perp.get("filled_qty", "0")),
backend/hedge_open_tasks/store.py:1924:                q = _num(row["spot_filled_qty"])
backend/hedge_open_tasks/store.py:1926:                b["spot_notional"] += q * _num(row["spot_avg_price"])
backend/hedge_open_tasks/store.py:1928:                q = _num(row["perp_filled_qty"])
backend/hedge_open_tasks/store.py:1930:                b["perp_notional"] += q * _num(row["perp_avg_price"])
backend/hedge_open_tasks/store.py:1937:            if _num(row["cumulative_base_qty"]) <= 0:
backend/hedge_open_tasks/store.py:1940:            q = _num(row["cumulative_base_qty"])
backend/hedge_open_tasks/store.py:1946:            notional = None if quote_raw is None else _num(quote_raw)
```

```text
$ rg -n -C 5 "VALUES \(\?, \?, \?, \?, \?, \?, NULL, NULL, '0', '0'" backend/hedge_open_tasks/store.py

743-                "INSERT INTO hedge_open_leg"
746-                "  cumulative_base_qty, cumulative_quote_amt, fee_amount,"
748:                " VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, '0', '0', NULL, NULL,"
760-                "INSERT INTO hedge_open_leg"
763-                "  cumulative_base_qty, cumulative_quote_amt, fee_amount,"
765:                " VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, '0', '0', NULL, NULL,"
```

### J2 — Non-goals：不充分，需 Human 作范围决定

`filled_qty` / `cumulative_base_qty` 的零默认值不仅覆盖“已接受但未成交”，还覆盖 PREPARED、无订单号、尚未有交易所回报的腿；随后 `service.py:214,252-253,284,310,774-775` 对 `NULL` 数量投影为 `"0"`。这会制造可见的“已成交数量为零”陈述。

建议先由 Human 明确选择：

- 继续限定本阶段为“金额未知不为零”，并在计划中承认数量未知仍是已接受限制；或
- 将未知数量纳入同一规则和测试。

不要由实现者静默扩 scope。

### J3 — D4：可接受，且应保留

删除镜像的 exposure 构建器有直接漂移证据，属于最小充分去重，不是推测性抽象。`ts_us <= 0` 在 reconcile 路径改为抛错是合理的 fail-closed 行为：直接路径已经使用同一 domain backstop，且调用方的 `now_us` 本应为正。D4 的“不得改动 domain contract，无法适配即阻塞”约束充分；需保留负时间戳回归测试。

### J4 — D5：否，规格不够紧且有实质漏洞

D5 没有精确定义扫描方式、语法边界、allow-list 标记格式和覆盖范围，两个实现者可以写出不同守卫。

它不能覆盖四个历史类别：

- r4 位于 `backend/services/live_hedge_executor.py`，被 D5 的目录范围排除；
- r5 是迁移 SQL/历史重写，并非“赋值或 dict value”的 `_num` / `or "0"` 形式；
- r6 的 `service.py` 位于范围内，原则上可覆盖；
- r7 的 `store.py` 可覆盖，但新的 SQL `'0'` 漏点已证明现有文字不足。

必须在实现前把 D5 改为可执行的精确规则，并覆盖 `backend/services/**` 的交易所金额解析，以及 SQL 写入/迁移中的金额默认值；同时加入对漏点 S4 的反向探针。

### J5 — D6：只对现存 M2 部分充分；计划事实错误

当前代码只剩 M2：`_migrate()` 在 store.py:473 更新 `leg_exposure`。M1 已在 `95ac1a5` 被有意删除；历史状态也明确记录“M1 is gone with zero remnants”。

因此计划/dispatch 所称“将 M1/M2 都移出构造”不准确，可能诱导实现者恢复已删除的 M1。应改为：仅将现存 M2 的行更新置于显式 opt-in，并测试默认构造不会改写可修复的 M2 行。

残余风险也需准确命名：构造仍会执行 `DROP TABLE` + `RENAME` 的 leg-table rebuild（store.py:412），它不是单纯“additive DDL”。该残余可以由 Human 接受，但 D6 并不能保证“构造生产库绝不写入”；它只防止过去事故中的现存 M2 语义行改写。

### J6 — Packet integrity：文件范围足够；验收条件不充分

Allowed Files 可完成 D1–D6，也能通过测试扫描 `backend/services/**`，无需放宽源码文件范围。

但 Acceptance Checks 尚不能证明闭合缺陷族：没有要求 PREPARED 腿的 `cumulative_quote_amt is None` 回归；D5 也没有精确、可反证的检查，现有规则可全绿却留下 `store.py:748/765`。应先补 S4、精确 D5 规则和对应故意回归探针。

### J7 — Process deviations：部分披露正确，但“违规”判断错误

`roles.md` 规定 Planner “Select at most one skill”，共享规则也允许零或一个；因此没有加载 skill 不是 D-4 所称的规则违规。事后对两个 skill 的适用性判断大体合理：`task-planner` 大量 Laravel/FluxUI 内容不相关，`software-architect` 的反过度设计、权衡和可逆性原则在计划中已有体现。应把 D-4 更正为“零技能的合规选择及其理由”，而非偏差。

Planner/Bookkeeper 同会话没有违反当前角色隔离规则。推荐 Fable 5 作为 review-2 也符合实现者供应商隔离和“避免设计参与者”偏好，但仍须 Human 明确选择其付费额度；Codex 只能作为披露过设计参与的后备。

按严重度排序的修复要求：

1. **P1，实施 dispatch 前**：把 `store.py:748/765` 加入闭合集合，确定其未知金额语义并添加回归测试。
2. **P1，实施 dispatch 前**：重写 D5 为精确、可探针验证的规则，覆盖 `backend/services/**` 与 SQL/迁移金额默认值。
3. **P1，实施 dispatch 前**：将 D6 更正为只处理现存 M2，明确 table rebuild 残余不能满足“绝不写库”的强表述。
4. **P1，实施 dispatch 前作 Human 范围决定**：明确未知数量是否允许继续投影为 `"0"`。
5. **P2，可随计划修订处理**：更正 D-4 的“技能违规”描述。

应保留、不要削弱的部分：真实交易所 `"0"` 与缺失值的区分；D2 对缺失均价的不完整标记；D4 不改 domain contract 的阻塞规则；M2 默认不运行的方向；以及禁止访问 `data/**`、网络和服务控制的边界。

[TASK_RESULT v2]
任务 ID: task0-plan-review
执行结果: completed（完成）
结果摘要: 计划漏掉 PREPARED 腿写入未知金额为“0”的站点；D5 不能覆盖历史层与 SQL 默认值；D6 仍引用已删除 M1。实施前需修订闭合集合、守卫、迁移事实及数量范围决定。
产物: [none（只读审查，结论在终端输出）]
检查结果: [任务包/状态一致, 独立 rg 源码扫描, S4 漏点确认, M1 历史与现状核对, D4/D5/D6 设计核验, 角色隔离与技能规则核对, 未运行写入型测试/未读 data/**]
阻塞项: [计划修订与 Human 对未知数量范围的决定]
评审结论: REWORK（返工）
问题记录: none（结论在终端输出）
修复要求: none（要求在终端输出）
本地北京时间: 2026-07-30 13:01:27 CST
下一步模型: opus5（记账人，Human 转交结果）
下一步任务: 记账人依据本终端结论修订计划与 implementation dispatch；Human 先决定未知数量是否属于本阶段，再由 Human 启动修订后的实现任务。
[/TASK_RESULT]
