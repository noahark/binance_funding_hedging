# Task Handoff: hyperliquid-funding-compare-review-2-kimi

## Source Report (author-only; immutable after task end)
- task_id: `hyperliquid-funding-compare-review-2-kimi`
- role / target model: Reviewer / Review-2，kimi（moonshot）
- stage_id: `2026-08-23-hyperliquid-funding-compare-v1`
- created_at: 2026-08-23 16:34:28 CST
- base_sha: `25cc8fe4e31194261dd48415f085bc6f9fda062d`
- delivery_sha: `6922bcebb4f18ba824125c46774fc5ad22bab806`（status.json revision 6 同值，已核对）

### 评审范围与方法

现实性复评（HIGH_RISK，只读）。以固定 `git diff dc76e0c..6922bce` 为受审交付，
设计权威 `docs/planning/hyperliquid-funding-compare-v1.md` rev3（固定于 `fe91abb`，
已过三轮设计评审，设计本身不在本轮范围内）。逐条核对 dispatch 必查项 M1–M7，
并实际重跑全部三条复现命令。与 Review-1（grok）并行、互不知悉对方结论。

### 复现命令实测（本Reviewer独立重跑）

- `.venv/bin/python -m pytest backend/tests/test_hyperliquid_compare.py -q` → **22 passed**（1.37s）
- `.venv/bin/python -m pytest backend/tests/ -q` → **2023 passed, 1 failed**；
  唯一失败为 `test_private_client.py::test_urlopen_only_in_designated_http_clients`，
  即 dispatch 声明的已知基线问题（`public_ip_service.py` 未登记白名单，基线 `dd12833` 即存在），
  与本次交付无关；新增的 `hyperliquid_public.py` 已正确登记白名单（diff 可见）。
- `node frontend/self-check.js` → **全部自检通过**（含新增 33c-hl 块）。

### M1–M7 逐条结论

**M1 失败语义（§6.1/D6）— 通过。**
`backend/services/snapshot_service.py:1425-1442`（delivery_sha 下）：HL 为独立 source_id、
60s 组；任一失败（`URLError/OSError/ValueError`，覆盖 `json.JSONDecodeError`、
`gzip.BadGzipFile`、`http.client.RemoteDisconnected`——已用 MRO 实测确认均为
`OSError`/`ValueError` 子类）→ 不缓存且 **`pop` 掉既有条目**，无 warm last-good，
与 Group A/B 的 success-only 语义（"Timestamps advance only on success"）明确不同，
未复用其投影。冷启动门 `_compose_base_raw` 只等 `premium_index` + `group_b_public`，
HL 不进发布门，失败不阻断快照。`test_service_a7`（冷启动失败照发）、`test_service_a8`
（success→failure 跨 60s due 窗口后值与时间戳同清、恢复后整组回来）均为真实断言。

**M2 匹配 fail-closed（§3）— 通过。**
`build_hyperliquid_matches`（`backend/domain/snapshot.py`）顺序：完整 key 查
`HL_SYMBOL_DENY` → `is_delisted` → raw name exact（`by_base`）→ 类别校验
（`_HL_DEX_ALLOWED_CONTRACT_TYPE`：main→`PERPETUAL`、xyz→`TRADIFI_PERPETUAL`）。
顺序与设计一致，匹配唯一入口，无绕过路径。`test_a1` 把币安 BB/QNT 构造成
`TRADIFI_PERPETUAL`（类别一致），证明拦下它们的只有 DENY——oracle 真实；
`test_a2` 用两个不在 DENY 的 synthetic 撞名（main:TSLA vs 币安 TRADIFI、
xyz:DOGE vs 币安 PERPETUAL）证明类别校验不依赖枚举。

**M3 IC-1 schema — 通过。**
`snapshot.schema.json` 顶层 `additionalProperties: false` 未动（实测），
`hyperliquid_data_time` 注册进顶层 `properties` 但**不在**顶层 `required`（实测）；
`$defs/row` 中 `hyperliquid` 同理（不在 row required，块自身 `additionalProperties:
false` + 内部四字段 required + decimal_string $ref）。
`test_schema_accepts_pre_v0_22_snapshot_without_hl_keys` 显式剥掉新键后仍过校验，
既有 offline fixture 未打挂（全量 2023 passed 旁证）。

**M4 IC-2 前端标红 — 通过。**
`isStaleTime` 源码实测 `Number.isFinite(ms) && now-ms > STALE_TIME_MS`，
`isStaleTime(NaN)` 恒 false——dispatch 的前提成立。实现
（`renderMarketSnapshotMeta`，frontend/index.html）显式把 unavailable 并入：
`hlStale = !Number.isFinite(hlMs) || isStaleTime(hlMs)`。红色只加在
`<span id="hl-data-time">` 上，meta 整行 className 仍只由币安 generated/data
时间决定；self-check 33c-hl 块断言了三态（null→`—`+红、新鲜→不红、陈旧→红）
以及"HL 失败不染红整行"。

**M5 零回归 — 通过。**
`snapshot.py` 的 diff 为纯增量（新增 helper + `build_rows` 一个可选入参 + 每行一个
新键），币安四列计算未触。`test_a4` 有无 HL 两次 `build_rows` 逐格对比 +
行序稳定；`test_a5` 一个 4h（×6）一个 8h（×3）各自断言显式期望值，未统一成 8h；
全量套件 2023 passed 为系统级旁证。

**M6 边界 — 通过。**
diff 只触及 dispatch §7 清单内文件；`SPOT_SYMBOL_MAP` 零改动（normalize.py 仅新增
`HL_SYMBOL_DENY`）；未碰下单/保证金/借币/平仓任何文件。「更新缓存」按钮
（`force_account_panels=True`）只放宽账户面板组，HL due 检查不吃 force，
`test_cache_refresh_button_does_not_force_hl` 实测。前端无新增网络代码
（grep `api.hyperliquid` / HL fetch 均为 0 命中），无直连、无按需拉取。

**M7 验收真实性（18 条）— 通过（重点怀疑后未发现假绿）。**
以 rev2「断言 warnings 非空」假绿同标准逐条审视：

- A1/A2/A2b：oracle 唯一且构造对抗性 fixture（见 M2），非恒真。
- A3/A10：断言整个 block 的**精确相等**（含 ×24、×365 的显式十进制字符串结果），
  外加负值、科学计数法（`1e-5`→`0.00001`）、零三向量；`isinstance(v, str)` 逐字段。
- A4/A5：差分对比 + 显式期望值，非自证。
- A6/A9b：反向 oracle 成立——源成功且部分无匹配时时间戳**有值**、前端**不红**
  （断言 `id="hl-data-time">HL 数据时间: ` 无 class 属性）。
- A7/A8/A9：共享同一 oracle（时间戳 null + 全行 null + 照发），A8 用 monkeypatch
  时钟跨过 60s due 窗口驱动**真实第二次刷新尝试**，断言旧值与旧时间戳同清，
  并补恢复路径。A9 的适配器层向量含 float `0.0001`（JSON number 被拒，
  Decimal 纪律真实执行）与 `"NaN"`/`"Infinity"`。
- A9c：offline 下 stub `calls == 0`、全行 null、schema 校验通过；
  实现层双保险——`_hl_client` 只在 `start_worker` 懒构造，offline 提前 return。
- A11：断言「HL 每小时」且第二行片段正则无数字。
- A12：GOLD→XAUUSDT、kPEPE→1000PEPEUSDT 无 exact 同名，源成功下仍为 null。
- A13：适配器层记录请求体，断言恰好两次 POST 且 dex 顺序 `""`,`"xyz"`，
  首次失败短路（`len(calls)==1`）；服务层断言 60s 内二次 tick 不重取；
  `predictedFundings` 零调用用源码 grep 断言——属静态守卫但对"零调用某端点"
  这一命题是有效 oracle，且端点确实不存在于适配器。
- A14/A15/A16：self-check 33c-hl 在真实 `renderRowHtml` 渲染产物上断言开关
  默认开/关闭后无残留/重开恢复、HL 与 HL·xyz 标签、近 24h 列无第二行、
  无 HL 数据的 BUSDT 搜索仍可见；`node frontend/self-check.js` 全绿。

未发现恒真断言、oracle 不唯一或 mock 掉被测逻辑的情形：stub 只替换网络边界
（`_StubPublic`/`_StubHL` 注入在客户端接缝），匹配、失败语义、schema、渲染
全走真实代码路径。

### 观察（不阻塞，非发现）

HL 块的异常捕获元组 `(URLError, OSError, ValueError)` 与 premium/group_b/
book_ticker 等所有既有源**完全同一形制**（`_refresh_due_sources` 原文可证）。
理论上 `http.client.BadStatusLine`（非 OSError 子类）会逃逸该元组；此时 worker
循环外层 `except Exception` 兜底（实测存在），本轮 tick 中止、HL 旧条目多存活
一个周期，但时间戳真实、90s 后前端 stale 标红仍会信号化。要求 HL 比全部既有源
更严不符合最小改动原则，记为观察；若未来 HL 侧出现病态响应再重开。

### 结论

**ACCEPT。** M1–M7 全部通过；交付真实做到其声称的事，无假绿；唯一测试失败为
dispatch 已声明的基线问题。

### Required Reading for the Next Task
- 读取路径及顺序：reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-review-2-kimi.handoff.md；reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-review-1-grok.handoff.md（若已存在）；reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/status.json
- 执行：Bookkeeper 同文件核验本评审与并行的 Review-1 结论，两份均 ACCEPT 后按 §6 流程推进 Human 业务预决策
- 关卡：Review-1（grok）结论汇合；两份 ACCEPT 后进入 §6-7 中文解释与 Human 决策
- 不能假设的事实：评审锚定固定 `base_sha..delivery_sha`（`25cc8fe..6922bce`），HEAD 后的控制提交不在受审范围；`test_urlopen_only_in_designated_http_clients` 失败为基线既有问题，不得计给本交付

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: hyperliquid-funding-compare-review-2-kimi
执行结果: completed（完成）
结果摘要: Review-2 现实性复评完成，结论 ACCEPT。M1-M7 逐项过原始 diff 与源码并独立重跑三条复现命令：新增测试 22 过、全量 2023 过（唯一失败为已知基线问题）、前端自检全绿。失败语义、fail-closed 匹配、schema 注册非必填、前端三态标红均与设计 rev3 一致；18 条验收逐条审视未发现恒真断言或假绿。
产物: [reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-review-2-kimi.handoff.md]
检查结果: [pass: pytest test_hyperliquid_compare.py 22 passed；pass: 全量 backend/tests 2023 passed + 1 failed（dispatch 声明的基线问题，非本次引入）；pass: node frontend/self-check.js 全部通过；pass: M1 失败语义（原子组/失败弃缓存/无 last-good/不阻断发布，A7/A8 真实断言）；pass: M2 匹配顺序 DENY→delisted→exact→类别校验，A1/A2 对抗性 fixture 证明 oracle 唯一；pass: M3 顶层 additionalProperties:false 且新字段注册但非 required，旧 fixture 兼容；pass: M4 isStaleTime(NaN)===false 已实测，unavailable 显式入标红条件且红色只作用 HL span；pass: M5/M6 币安四列零回归、边界未越（无下单/保证金/借币路径改动，更新缓存按钮不含 HL，前端零新增网络）；pass: M7 十八项验收逐条审视无假绿]
阻塞项: [none]
评审结论: ACCEPT（接受）
问题记录: none
修复要求: none
本地北京时间: 2026-08-23 16:34:28 CST
下一步模型: opus5（Bookkeeper，status.json.bookkeeper；评审结论经本交接件到达）
下一步任务: 读取：reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-review-2-kimi.handoff.md；执行：Bookkeeper 同文件核验本 Review-2 结论，并与并行的 Review-1（grok）结论汇合；关卡：两份评审均 ACCEPT 后进入中文解释与 Human 业务预决策，任一 REWORK 则回对应评审轮
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

（留空，由 Bookkeeper 追加。）

## Errata (append-only)

（无。）
