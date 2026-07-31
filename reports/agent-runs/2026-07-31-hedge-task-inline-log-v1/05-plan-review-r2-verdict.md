# 05：计划评审 round 2 verdict（grok / xai，2026-07-31 15:11:58 CST）

`评审结论: REWORK`。本轮回执携带完整正文、发现清单（R2-F1..F5）与可执行修订要求
（5 条），符合 `AGENTS.md` §7，**已封存**。披露：计划评审与 review-1 同为 grok / xai。

不计入 `rework_count`（计划评审 verdict，`AGENTS.md` §8）。

## 两条阻塞发现（Bookkeeper 已逐条复核代码，均属实）

### R2-F1 —— 自动删除会把已成交腿从持仓里抹掉（资金洞）

`store.aggregate_positions`（`store.py:1934-1951`）的两条查询都带 `WHERE t.status != ?`
（`STATUS_DELETED`）。任务一旦被删，它已经成交的腿就从 `GET /api/hedge-open-positions`
消失，**而账户上的敞口仍然存在**。

配套现状：默认任务筛选是 `running`（`index.html:1330`），删掉的卡默认列表看不见；卡上的
`leg_exposure` 文案（`index.html:4171+`）只有切到「已删除 / 全部」才看得到。

关键判断（Bookkeeper 认同）：手动软删除本来就有这个洞，属偶发；Goal 3 把它从「偶发手动」
放大成「常态自动」——尤其单腿敞口本身就计入失败刹车，等于**攒够单腿敞口就自动把敞口
藏起来**。必须在本 stage 一并钉死。

原 AC5 写「敞口告警 / 持仓视图 / 已删除筛选**至少其一**」判据过宽：实现方只要证明「已删除
筛选里还能看到」就能过关，钱照样从持仓表丢。已按修订要求收紧。

### R2-F2 —— 51169 冻结文案与「六条中文全改写」冲突

`COLLATERAL_CAP_FULL_REASON_ZH_TEMPLATE`（`domain.py:1315-1324`）是 10-design §2(d) /
ADR-T3 的逐字冻结契约，注释明写 `must NOT be reworded`，并明确禁止被换成「保证金不足」
话术——因为平台级抵押上限是全平台共享、追加资金无效，「保证金不足」是它要否认的假事实。

原 Goal 3 写「六条中文文案改写为删除语义」直接撞上该冻结。修法（采纳 grok 建议）：
**正文一字不改，只在其后追加固定删除后缀**；其余五条可改。

## 三条建议 + 两条观察（全部采纳）

- R2-F3：Goal 1 的进度口径交叉引用误指 Goal 3（应为 Goal 4）；Goal 4 文首仍用 COOKIEUSDT
  「卡在 running」作动机，与后文「诊断过时」并列易混。→ 均已改。
- R2-F4：AC4 应点名搜索符号（`pause_task` / `_pause_task_local` / `_pause_from_signal` /
  `STATUS_PAUSED` 赋值点 / `resolve_status_after_attempt` 返回值），避免只搜字符串
  `paused` 漏站点；Stop 补持仓与 51169 两条；事件 kind payload / `reason_zh` 与
  `_entry_next_action` 对 `paused` 的映射（`service.py:366-367`）须与删除语义对齐。→ 均已加。
- R2-F5（观察）：① 429 限频窗口内可能连环删多张卡，恢复只能手动重建——产品已接受，
  不加防抖，但已在 packet 中写明该运维后果；② 既有大量 `STATUS_PAUSED` 断言会转红，
  属预期，已写入 AC12 并要求说明改动，禁止为了让测试变绿而弱化 Goal 3 语义。

## 已确认通过的部分（不再重评）

Goal 3 与 Goal 4 正交、AC2 用人工暂停构造残留死锁成立、根因家族清单（scheduled 四站 +
三个再武装入口 + `stopped`）完整、自动暂停站点清单够用、文件边界够用不过宽、
`server.py` 可选 `task_id` 过滤仍有必要、drain 约束（AC6）足够、r1 的五条修订已正确落盘。

## Bookkeeper 处置

`00-task.md` 升 `status_revision: 5`，按修订要求 1-4 全部落实（第 5 条「不改」的内容原样
保持）。核心变化：

1. AC5 由「三选一」改为**硬性要求已成交腿仍计入持仓 API**，`aggregate_positions` 修复
   写入 Goal 3 与 Allowed Files，「已删除筛选可见」降为附加验收。
2. 51169 正文冻结写入 Goal 3 例外条款与 Stop，AC3 增加「冻结正文逐字未变」的断言要求。
3. Goal 1 交叉引用改指 Goal 4；Goal 4 的 COOKIEUSDT 动机句降级为历史注记。
4. AC4 点名搜索符号；AC12 说明 `paused` 断言转红属预期；Stop 增四条；Allowed Files 的
   `service.py` / `store.py` / `domain.py` 说明从「F10 only」扩写为实际范围。

### 需要 Human 知道的范围变化

R2-F1 的修复（持仓聚合不再因 `deleted` 丢掉已成交腿）**改变了 `GET /api/hedge-open-positions`
的输出**，属契约变更，会由 review-1 审。这是 Human 需求变更（六种自动暂停全改删除）
引出的必要配套修复，不做就会造成「攒够单腿敞口 → 自动删卡 → 敞口在账户里但持仓表看不到」
的资金可见性缺口。Bookkeeper 判定必须做，已写为不可协商的阻塞级验收。
