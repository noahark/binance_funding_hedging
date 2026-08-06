# 计划评审 r2 — 持仓周期三功能（返工核验）

被审对象：
- `docs/planning/hedge-open-position-cycle-v1.md`（设计权威，返工版）
- `docs/planning/hedge-open-cycle-stage2-cycle-dev.md`（功能①：周期表，返工版）
- `docs/planning/hedge-open-cycle-stage3-stats-dev.md`（功能②：费率/利息统计，返工版）
- 前一轮：`docs/planning/hedge-open-position-cycle-v1.review-sonnet5.md`（R1，REWORK：P0-1 merge_positions、P1-1 归零观察宽限期、P1-2 覆盖率判定）

评审角色：独立计划评审（`AGENTS.md` §8），只读，sonnet5 本人执行。
评审基线：`main @ 08127aa`（三份文稿仍为工作树内未跟踪文件）。
只读了源码与 `data/hedge-open-tasks.sqlite3`/`data/ledger-flow.sqlite3` 的行计数与 schema；未使用凭证、未发单、未改 Start gate。

**评审结论：REWORK（返工，范围小于 R1）**

R1 的 P0-1（merge_positions 不改的错误断言）**已完全修复且与 `domain.py` 现状逐行吻合**，不再是阻塞项。本轮剩两处需要收紧的地方，都在 R1 已经改对方向的基础上——不是新缺陷类别，是同一处修复里两个还没钉死的细节。verdict 返回 Planner，不触碰 `rework_count`。

---

## 核验点 ① §5.4 merge 匹配规则是否与 `domain.py` 现状吻合

**吻合，逐行核实无误。**

设计 v1 §5.4 现在写的现状缺陷描述——`bucket_by_key` 用 `(coin, direction)` 二元组 `setdefault`（`domain.py:1783/1785`）、`matched_buckets` 同样按二元组记账、检查点在 `:1814`（`if key in matched_buckets:`）——我对照 `domain.py` 逐行核实，行号与代码内容完全一致：

```
1783   bucket_by_key = {}
1785       bucket_by_key.setdefault((p.get("coin"), p.get("direction")), p)
1788   matched_buckets = set()
1799       bucket = bucket_by_key.get(key)
1801       matched_buckets.add(key)
1814       if key in matched_buckets:
```

返工后的匹配规则（v1 §5.4 步骤 1-4：桶键与 matched 集合都改成周期粒度、UM 骨架只匹配活跃周期、未匹配周期各自独立 `no_um` 输出）是对症的正确修法，且 stage2 §3.5 已同步引用「匹配规则权威在设计 v1 §5.4，实现时照此」，两份文档之间不再有矛盾表述。§8 用例 2b 的验收断言（同键下一活跃一已平仓 → 输出两行）与修法直接对应。**这一项无需再改。**

---

## 核验点 ② 宽限期 180s 的取值是否合理

**方向对，但取值的推导依据不准确，且用错了时间戳字段。建议收紧，非阻塞级但应在本轮一并改。**

### a. 用来判断"快照够不够新"的字段选错了

stage2 §3.6 用 `private_account` 的顶层 `checked_at` 与 `opened_at_us + 180s` 比较。我查了这个字段的来源：`checked_at` 是一个**混合时间戳**——无论是 click 强制刷新路径（`snapshot_service.py:809-822`，四个私有面板一次性拉取、共用一个 `datetime.now()`）还是后台定时路径，它反映的是"这次组装 private_account 用的是哪次整体运行"，**不是**"`um_positions` 这个面板本身最后一次成功拉取是什么时候"。

而代码里已经有专门为这个问题准备好的字段：`source_checked_at`（`domain/snapshot.py:1267/1382`，docstring 原话「the fixed five-key per-source success-time object」）。它在后台定时刷新循环里逐面板独立维护（`snapshot_service.py:1414-1436`，`price_map`/`unified_balances`/`um_positions`/`spot_balances`/`pm_account` 各自有自己的到期检查、各自在成功时才推进自己的时间戳），并且在 `_assemble_snapshot_pipeline`（`snapshot_service.py:625-634`）统一挂到 `private_account.source_checked_at` 上，**发布时机覆盖离线构建 + 定时循环 + click 三条路径**。这个字段存在的目的就是「按来源精确知道这个面板最后一次成功是什么时候」——这正是宽限期判定需要的东西。

用混合的顶层 `checked_at` 有一个具体的失效场景：如果 `um_positions` 这一个面板连续拉取失败（网络抖动、限频），而 `unified_balances`/`spot_balances`/`pm_account` 仍在正常刷新，顶层 `checked_at`（依赖具体实现，可能随任一面板的活动而推进）可能看起来「新鲜」，但 `um_positions` 本身用的还是几分钟前的旧数据——这时候宽限期判定会误以为「快照够新，可以信」，而实际上看到的仓位数据是过期的。这恰好是宽限期机制本来要防的那类误判，只是换了个字段名字重新发生一次。

**要求：** `_hedge_open_positions`（`server.py:737`）在归零观察这一步（stage2 §3.6）能直接拿到完整的 `private_account` 字典（`source_checked_at` 已经是它的一个键，不需要额外查询），把比较对象从 `private_account.get("checked_at")` 换成 `private_account.get("source_checked_at", {}).get("um_positions")`。

### b. 180s 这个数字的推导依据本身站不住，但换算下来大致够用

设计 v1 §4.2 把 180s 写成「2～3 个快照刷新周期（约 60s）」。我查了实际支撑这句话的两个配置常量：

- `cache_ttl_seconds = 60`（`backend/config.py:35`，`um_positions` 所在 Group A 的刷新 TTL）；
- `background_tick_seconds = 30`（`backend/config.py:76`，后台 worker 的轮询粒度——`_source_due` 只在每次 tick 时才被检查一次）。

也就是说，一个 Group A 源从「变成到期」到「真正被重新拉取」，最坏情况不是 60s，是 `60 + 30 = 90s`（到期后还要等下一次 tick 才会被检查到）。这还是**假设一次就拉取成功**的情况；代码注释里明确写着拉取失败「不缓存，下一 tick 重试」（`snapshot_service.py` 面板拉取块），连续失败时旧数据会被更久地沿用，没有上限保证。

按修正后的单周期最坏值（约 90s）折算，180s 大约是 2 倍，比文档自称的「2～3×60s」实际给出的余量更薄，而且完全没有为「下单到成交」这一段链路延迟单独留量——我查了 `LEG_QUERY_MAX_RETRIES = 10`（`domain.py:575`）配合 `DEFAULT_INTERVAL_SECONDS = "0.5"`（`domain.py:558`），单条腿的查单确认预算大约 5s，这部分不是主要瓶颈，但连续两次面板拉取失败（约 150-180s）就足以把 180s 的余量吃光。

**要求：** 把宽限期的推导写成直接引用配置常量的表达式（例如 `2~3 × (cache_ttl_seconds + background_tick_seconds)`，对应 180～270s），而不是手写的「约 60s」近似值；这样常量变了宽限期会跟着变，不会再对不上。给定这项改动的代价极低（无非是新建的周期在归零判定上多等几十秒，设计本身已经接受「宁可延续，不误拆」的粗颗粒原则），建议直接取上限附近（如 240～300s），不必卡在最省的下限。

以上两点（a 换字段、b 调数值/写成表达式）都不改变整体机制，属于同一处修复里的收尾，不是新的设计方向。

---

## 核验点 ③ `_build_coverage` 的调用方式：公开包装的落点

**尚未钉死，需要在本轮定下来（低风险，但计划文档不该把这种选择留给实现者临场决定）。**

stage3 §3.3 现在的写法是「调用 `_build_coverage`（或为其做按窗口调用的公开包装）……实现时若直接调用需先确认其签名可用或补公开包装」——这仍然是把「要不要包装、包装放哪」这个决定留到实现阶段，不是一个已经定案的计划。

我查了：`_build_coverage`（`backend/ledger_flow/service.py:375`）是 `LedgerFlowService` 类的实例方法（`class LedgerFlowService:` 在 `:90`，`coverage_exists`/`get_flow_log`/`_build_coverage` 都在同一个类体内）。stage3 §3.1 要新增的 `sum_funding_by_symbol`/`sum_interest_by_asset` 也计划加在这同一个类上。既然都在同一个类里，「公开包装」不存在跨模块封装被打破的问题——直接在 `LedgerFlowService` 上新增一个公开方法、内部转调 `self._build_coverage(...)`，是最省事也最安全的落点，没有第二个合理选项需要比较。

**要求：** 直接把这条定成计划的一部分，不要留"实现时确认"的活口。建议：`LedgerFlowService` 新增 `window_coverage(start_ms, end_ms) -> dict`（或类似命名），内部为 `self._build_coverage(start_ms, end_ms, self._store.get_coverage())`，返回值直接透出 `complete`/`gaps`/`cov_start`/`cov_end`；stage3 §3.2 的组合根接线改成调用这个新公开方法，不直接碰 `_build_coverage`。这一项不阻塞返工提交，但应在这轮一并写进文档，避免留下一个「实现时再说」的悬空决定。

---

## 返工要求（可执行）

1. 归零观察判定改用 `private_account.get("source_checked_at", {}).get("um_positions")`，不用顶层 `checked_at`。—— 核验点 ②a
2. 宽限期从手写近似值改成对配置常量的表达式（`cache_ttl_seconds` + `background_tick_seconds`），建议取值上调到 240～300s 区间。—— 核验点 ②b
3. stage3 §3.3 明确写死 `LedgerFlowService` 新增公开方法包装 `_build_coverage` 的方案（方法名、签名、返回形状），去掉「实现时确认」的表述。—— 核验点 ③

核验点 ① 无需改动。修订后可再提交一轮独立计划评审，或视 Human 判断该轮收尾是否已足够充分直接授权实现——这个判断本身不属于计划评审范围。
