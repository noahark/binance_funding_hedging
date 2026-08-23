# Task Handoff: hyperliquid-funding-compare-review-1-grok

## Source Report (author-only; immutable after task end)

- task_id: `hyperliquid-funding-compare-review-1-grok`
- role: `Reviewer / Review-1`
- target model: `grok`（provider `xai`）
- stage_id: `2026-08-23-hyperliquid-funding-compare-v1`
- created_at（本地北京时间）：2026-08-23 16:40:00 CST
- base_sha: `25cc8fe4e31194261dd48415f085bc6f9fda062d`
- delivery_sha: `6922bcebb4f18ba824125c46774fc5ad22bab806`
- 固定实现 diff: `dc76e0c..6922bcebb4f18ba824125c46774fc5ad22bab806`
- status_revision（核对时）：`6`，`current_task.id` 与本 task_id 一致，`current_task.state = dispatched`
- 设计权威：`docs/planning/hyperliquid-funding-compare-v1.md` rev3，固定于 `fe91abb69e236e9ef110ca354b8773dfcb042773`。设计本身记范围外。

### 1. 任务背景与只读评审范围

对 claude_glm / 智谱（provider `zhipu`）的「Hyperliquid 费率对比行 v1」交付做 `HIGH_RISK` 独立只读 Review-1。受审范围固定为已提交实现区间 `dc76e0c..6922bce`（13 文件中的产品/测试/契约；`status.json` 与实现者 handoff 记范围外）。评审时仓库 `HEAD` 为 `905d14898f8b7daceffd2576f5d3f848254ab82f`（晚于 delivery 的控制提交，范围外）。本评审未以 `HEAD` 或未提交工作树为范围。

**隔离披露**：实现作者 claude_glm / 智谱（`zhipu`）；设计作者 Opus 5 / Anthropic；本 Reviewer grok / xai。与实现作者跨 provider，隔离成立。Review-1 与 Review-2（kimi）本轮并行，本 verdict 未读取、不知悉对方结论。

**未获授权**：全程未启停服务、未下单、未访问私有 API、未使用凭证、未 merge/push/部署。

### 2. 先验门

| 先验门 | 结果 | 证据 |
|---|---|---|
| `git rev-parse` 与 `status.json` base/delivery 一致 | 通过 | 两值与 `status.json` 逐字相同；`design_sha=fe91abb` 可解析 |
| 固定实现 diff 为 `dc76e0c..6922bce` 单提交 | 通过 | `6922bce feat: Hyperliquid 费率对比行 v1…` |
| `HEAD=905d148` 为控制提交、范围外 | 通过 | `chore(stage): 封存 delivery_sha 6922bce，并行派发 Review-1/Review-2` |
| 实现作者 zhipu / Reviewer xai | 通过 | dispatch 隔离披露 |
| 唯一 handoff 开始前不存在 | 通过 | `test ! -e <本文件路径>` → ABSENT |
| 设计已定案，本轮不评设计 | 通过 | 只判断实现是否忠实、安全、可恢复 |

实现 diff 文件（范围外两份已标注）：

- `backend/adapters/hyperliquid_public.py`（新）
- `backend/config.py`
- `backend/domain/normalize.py`（仅追加 `HL_SYMBOL_DENY`；`SPOT_SYMBOL_MAP` sha256 与 `dc76e0c` 相同）
- `backend/domain/snapshot.py`
- `backend/services/snapshot_service.py`
- `backend/tests/test_hyperliquid_compare.py`（新）
- `backend/tests/test_private_client.py`（urlopen 允许集加 `hyperliquid_public.py`）
- `docs/api/public-market-contract.md`（v0.22 追加）
- `frontend/index.html`
- `frontend/self-check.js`
- `schemas/api/public-market/snapshot.schema.json`
- `reports/.../evidence/hyperliquid-funding-compare-impl-claude-glm.handoff.md`（范围外，仅参考）
- `reports/.../status.json`（范围外）

### 3. 独立复跑

```text
$ .venv/bin/python -m pytest backend/tests/test_hyperliquid_compare.py -q
22 passed in 1.33s
exit=0

$ .venv/bin/python -m pytest backend/tests/ -q
1 failed, 2023 passed in 157.89s
FAILED backend/tests/test_private_client.py::test_urlopen_only_in_designated_http_clients
  urlopen found outside the designated HTTP clients: ['backend/services/public_ip_service.py']
exit=1（基线，dispatch 已声明不必重复报告）

$ node frontend/self-check.js
… [PASS] HL 对比行：默认开/标签/—/每小时/独立 span 三态/开关恢复 …
全部自检通过
exit=0

$ git diff --check dc76e0c 6922bce
（无输出）exit=0
```

### 4. 必查项 M1–M7

#### M1 失败语义（设计 §6.1，D6）—— 通过

HL 是独立 `source_id`，60s 组，与 `premium_index` 同频但独立失败。`_refresh_due_sources` 在 `URLError/OSError/ValueError` 时把 `hl=None`，随后 **`pop("hyperliquid")`**，与 Group A/B「只在成功时推进时间戳、保留 last-good」相反。`_source_due` 在条目缺失时为真，下一 tick 会重试，不会把失败伪装成新鲜。

`_run_refresh_cycle` 在刷新后仍 compose / validate / publish：A7 冷启动失败仍发布 4 行币安数据且 `hyperliquid_data_time is None`；A8 success→failure 后旧值与旧时间戳均消失，恢复后整组回来。`force_account_panels=True` 不刷新 HL（`test_cache_refresh_button_does_not_force_hl`：第二次调用计数仍为 1）。

适配器 `fetch_funding_compare` 先 main 后 xyz，main 失败则 xyz 不发（A13 短路）。任一 `funding` 非有限 Decimal 字符串 → `ValueError` → 整源失败（A9）。offline `get_snapshot` 走 `build_snapshot()`，不经 `_refresh_due_sources`，零 HL 调用（A9c）。

结论：没有让 HL 复用 Group A/B success-only 语义而静默展示旧值。

#### M2 匹配 fail-closed（设计 §3）—— 通过

`build_hyperliquid_matches` 顺序：

1. 完整 key 命中 `HL_SYMBOL_DENY`（`xyz:BB` / `xyz:QNT`）→ 丢弃
2. `is_delisted` 为真 → 丢弃
3. raw name（适配器已剥 dex 前缀）与币安 `baseAsset` exact
4. 类别：main 只配 `PERPETUAL`，xyz 只配 `TRADIFI_PERPETUAL`

无第二套匹配入口（全库 `hyperliquid`/`HL_SYMBOL` 仅此投影）。A1 把 BB/QNT 合成 TRADIFI 以证明 **DENY 在类别本会放行时仍拦住**；A2 用 DENY 表外的 `main:TSLA` / `xyz:DOGE` 证明类别门不依赖 BB/QNT 枚举。同类别同名不受保护——与设计 §8 收窄一致，不是缺陷。

#### M3 IC-1 schema —— 通过

顶层 `additionalProperties: false`。`hyperliquid_data_time` 在 `properties`，**不在**顶层 `required`（required 仍为 schema_version / generated_at / data_time / source_sample_id / summary / rows / warnings）。行内 `hyperliquid` 在 `$defs/row.properties`，**不在** row `required`。`test_schema_accepts_pre_v0_22_snapshot_without_hl_keys` 剥掉两键后仍校验通过；既有 `test_negative_schema.BASE_ROW`（无 HL 键）仍有效。producer `assemble_snapshot` / `build_rows` 恒显式输出（string|null / block|null）。

#### M4 IC-2 前端标红 —— 通过

`isStaleTime(NaN)` 确为 false（`Number.isFinite(ms) && now-ms > 90000`）。实现：

```javascript
const hlMs = (缺失/null/'') ? NaN : Date.parse(...)
const hlStale = !Number.isFinite(hlMs) || isStaleTime(hlMs)
```

unavailable 显式并入条件。父节点 `className` 只由币安 `generated_at`/`data_time` 决定；HL 红色加在独立 `#hl-data-time` span。CSS `.stale-time { color: var(--danger); font-weight: 700 }` 是通用类，作用在 span 上只染 HL 片段。self-check 33c-hl：null → `HL 数据时间: —` 且 span 带 `stale-time`；新鲜 → `id="hl-data-time">` 无 class；陈旧 → span 标红；父 `className` 不含 `stale-time`。

#### M5 零回归 —— 通过

`build_rows` 只新增 `hyperliquid` 键，币安四列赋值未改。`compute_daily_from_hourly` / `compute_annualized_funding_24h` / interval 分支无 diff。A4：同一 `build_rows` 有无 HL 投影，四列逐格相等、行序稳定。A5：4h ×6 → `0.00060000` / `0.21900000`，8h ×3 → `0.00030000` / `0.10950000`，未统一成 8h。全量 2023 passed（唯一失败为声明的基线）。

#### M6 边界 —— 通过

diff 未触碰 hedge/borrow/repay/close/transfer 路径。`SPOT_SYMBOL_MAP` 内容 sha256 与 `dc76e0c` 相同。HL 不在 `force_account_panels` 集合。前端零 `api.hyperliquid.xyz`；`row.hyperliquid` 只进 `hlSublines`（渲染），不进筛选/排序/借币/开单。`server.py` 未改：客户端在 `start_worker` 惰性构造，符合「非 DI 则不必改 server」的边界。

#### M7 验收真实性 —— 通过（未见 CONTRACT_WARNINGS 式假绿）

逐条对照设计 §9。审查重点：断言是否可被一个真实缺陷打红、oracle 是否唯一、是否 mock 掉被测逻辑。

| # | 覆盖 | 真实性判断 |
|---|---|---|
| A1 | `test_a1_deny_blocks_even_when_category_would_match` | 合成 TRADIFI 使类别本会匹配；去掉 DENY 会红。真 |
| A2 | `test_a2_synthetic_cross_category_collision_is_blocked` | DENY 表外撞名；类别门失效会红。真 |
| A3 | `test_a3_hype_row…` + service 层 HYPE `dex=="main"` | 精确 block 相等。真 |
| A4 | 有无 HL 投影四列相等 | 相对回归；M5 由 diff+A5 绝对值补齐。真 |
| A5 | 4h/8h 精确期望串 | 统一成 8h 会红。真 |
| A6 | ZKUSDT `hyperliquid is None` 且时间戳非 null | 与源失败可区分。真 |
| A7 | 冷启动 fail → 发布、全 null、时间戳 null；前端 span 标红 | 阻断发布或留下时间戳会红。真 |
| A8 | success→failure 丢值丢时间戳，再成功恢复 | 保留 last-good 会红。真 |
| A9 | 适配器对 `abc/None/NaN/Infinity/0.0001` 抛 ValueError；service 层 ValueError 与 A7 同一 oracle | 非法值放行会红。真 |
| A9b | 部分无匹配时时间戳有值；前端新鲜不红 | 误报失败会红。真 |
| A9c | offline 注入客户端仍 `calls==0`、全 null；`get_snapshot` 内 schema 校验 | 离线发网或非 null 会红。真 |
| A10 | 精确 decimal 串 + schema `$ref` | 出 JSON number 会红。真 |
| A11 | 结算时间第二行 `HL 每小时` 且片段无数字 | 写出时刻会红。真 |
| A12 | GOLD/kPEPE exact 失败（14 个是采样时点，不作常量） | 代表 exact 机制；与设计时点声明一致。真 |
| A13 | 成功恰好 `dex=""/"xyz"` 两次；首 POST 失败 calls==1；60s 内 due 不重取；源码无 `predictedFundings` | POST 次数在适配器层实计 `_http_post_json`，不是 stub 注释。真 |
| A14 | HTML `checked` + `showHl:true`；关开关零 `hl-subline` | 关不掉会红。真 |
| A15 | `HL` / `HL·xyz` 标签；近 24h 无第二行；搜 BUSDT 仍可见 | 标签错或筛掉无 HL 行会红。真 |
| A16 | self-check 全过，含 33c-hl | 15 列断言仍在。真 |

**与 rev2 假绿的对比**：A7/A8/A9 断言的是 `hyperliquid_data_time is None` 以及旧值消失，不是「warnings 非空」。`CONTRACT_WARNINGS` 三条固定文本不会让这些断言恒真。

service 层 A13 的 `hl.calls==1` 计的是 `fetch_funding_compare` 次数（due 门），POST 次数由适配器测试承担——两层合读，不是单一恒真断言。

### 5. 非阻塞观察（不进 Human 摘要，不构成 REWORK）

1. N3 曾写「成功 / 第一 POST 失败 / 第二 POST 失败」三个 adapter 夹具；交付缺「main 成功、xyz 失败」。代码是线性两次调用、失败即抛，service A8/A9 已覆盖 fetch 抛错 → pop。不构成假绿。
2. IC-2 父级 `className` 断言落在「HL 时间戳陈旧」态，而非 null 态。当前父 `className` 只由币安时间决定、与 `hlStale` 无关，代码审查等价。
3. 入站拒绝 JSON number 严于设计「无法转 Decimal」。Hyperliquid 官方 `metaAndAssetCtxs` 文档 `funding` 为 string（如 `"0.0000125"`），与项目 Decimal 纪律同向。
4. `URLError/OSError/ValueError` 未覆盖 `UnicodeDecodeError`。非 UTF-8 响应会让本轮 compose 被 worker `except: pass` 跳过，页面暂留上一份已发布快照（时间戳也旧，90s 后标红）。这不是 success-only 缓存投影。无当前实盘证据。重开条件：出现非 UTF-8 的 HL `/info` 响应。

基线 `public_ip_service.py` 未入 urlopen 允许集：按 dispatch 不重复报告。

### 6. Verdict

**ACCEPT**。实现以最小、安全、可恢复的方式落实 rev3。M1–M7 均成立。无 in-range REWORK 发现。

本 ACCEPT 不授权合并、部署、实盘或风险参数调整。

### Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-review-1-grok.handoff.md`；`reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/status.json`
- 执行：Bookkeeper 按 Task Handoff Evidence Contract 核验本文件：`TASK_RESULT v2` 结构、`评审结论: ACCEPT`、固定 `base_sha`/`delivery_sha`/`revision 6`、复跑命令与本报告一致
- 关卡：本 Review-1 封存为 `verified` 后，待并行 Review-2（kimi）回执一并核验；双评审均 `ACCEPT` 后交 Human 决定是否合并。合并、部署、实盘仍须 Human 另行授权
- 不能假设的事实：设计已定案，本轮未改设计；`HEAD=905d148` 是控制提交不是 delivery；基线 urlopen 白名单失败不是本次引入；Review-2 与本轮并行、结论独立

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: hyperliquid-funding-compare-review-1-grok
执行结果: completed（完成）
结果摘要: Review-1 ACCEPT。失败丢缓存、不展示旧HL值、不阻断快照；匹配DENY→下架→同名→类别；新字段已登记但非必填；取不到单独标红；币安四列与4h/8h折算未改；未碰下单路径。18条验收有真oracle，未见假绿。基线urlopen失败不重复报告。
产物: [reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-review-1-grok.handoff.md]
检查结果: [pass：M1 失败丢缓存且不阻断发布；pass：M2 匹配 DENY→下架→同名→类别无绕过；pass：M3 新字段登记且非 required；pass：M4 取不到显式标红且只染 HL 片段；pass：M5 币安四列与 4h/8h 折算未改；pass：M6 未碰下单/SPOT_SYMBOL_MAP/强制刷新/前端直连；pass：M7 18 条有可反例 oracle 未见假绿；pass：复现 22 passed / 2023 passed+1 基线失败 / self-check 全过]
阻塞项: [none]
评审结论: ACCEPT（接受）
问题记录: reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-review-1-grok.handoff.md
修复要求: none
本地北京时间: 2026-08-23 16:40:00 CST
下一步模型: Opus 5 / Claude（当前 Bookkeeper）
下一步任务: 读取：reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-review-1-grok.handoff.md、reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/status.json；执行：核验本 Review-1 ACCEPT、固定 SHA 与 revision 6；关卡：封存后待并行 Review-2 回执一并核验，双 ACCEPT 后交 Human 决定是否合并（合并/部署/实盘仍须 Human 授权）
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->
