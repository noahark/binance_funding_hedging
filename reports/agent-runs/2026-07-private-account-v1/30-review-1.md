# Review-1 汇总 — 2026-07-private-account-v1

> 本文件为 stage-delivery required-file（`scripts/validate-stage.py`
> `validate_required_files` pre-accept 硬要求）。聚合两份任务级 first_reviewer
> 评审；任务级权威 raw output 见各自文件。

## 评审分配（cross-review pool，AGENTS.md line 141-149）

| 任务 | implementer（owner） | first_reviewer | 依据 |
|---|---|---|---|
| A（backend） | claude_glm (zhipu_glm) | **Kimi (moonshot_kimi)** fresh 只读 | implementer=claude_glm → reviewer=Kimi |
| B（frontend） | kimi (moonshot_kimi) | **Claude-GLM (zhipu_glm)** fresh 只读 | implementer=Kimi → reviewer=Claude-GLM |

两份 first_reviewer 与各自 implementer provider identity 不同（cross-review
isolation，`validate_tasks` line 550-553 PASS）。

## 结论：双 ACCEPT

| 任务 | verdict | json_schema_valid | diff_fingerprint（reviewer 重算） | raw output |
|---|---|---|---|---|
| A | **ACCEPT** | true | `6ca6ee1db61952c10d547aa73a79e0711b2ae64b:fdfba177950b8872b386d07c1ee02ddfff7eaa0b044307691ebbb40235b8a252` | `review-1-task-a-round1.raw-output.md` |
| B | **ACCEPT** | true | `6c1e992c4628c0d8e369ba648b0403f341037849:50998c3a60afbae089f3e370e7ecbdd869256c70ff0cc1ae888b3f3abd6da2a2` | `review-1-task-b-round1.raw-output.md` |

两份 committed 指纹均由 reviewer 独立重算并与 dispatch 记录逐字一致（review-1
committed 指纹独立重算门禁 PASS）。

## Task A（Kimi fresh）要点

- base `fce1452` → head `6ca6ee1`（H_A backend），scope = `backend/**`/`schemas/**`/`docs/api/**`。
- 10 项核查全 PASS：白名单 12 项 deny-by-default / 单一 HMAC 出口 / 四级成本腿链
  （E1·E1b 仅登记不被 fetcher 调用）/ net_daily_yield 六向量（Decimal 禁 float）/
  排序双向量（net 反超 + abs Phase2 全序回归）/ coverage 截断+warnings / 防重复计算
  / private_account 三态（classic_ref 门控，round1 blocker B 已修）/ 数值卫生+
  落档脱敏 / 零改动红线（classify/normalize 未改，无 websocket 铺垫）。
- 测试独立复现：`pytest backend/tests/ -q` → 147 passed；`test_private_account_v1.py` → 48 passed。
- 额外核查：discovery 证据 sha256 抽验一致、冻结预算表 vs 实测 weight 头一致。
- findings（3 项 P3，required_fixes=[]）：E2b tier② 仅 top candidate（R3 升级口）、
  E4 position_side 推断（真实持仓实测）、ADR-11 文件未建（scope 外）。

## Task B（Claude-GLM fresh）要点

- base `6ca6ee1`（H_A，串行链）→ head `6c1e992`（H_B frontend），scope = `frontend/index.html` + `frontend/self-check.js`。
- 8 项核查全 PASS：净收益列（string-shift 复用，格式化函数体零改动）/ sort_basis
  标注+零排序（`filteredRows()` 纯 filter）/ 私有面板三态 / 隐私开关（默认隐藏，
  localStorage 仅布尔，无 console.log）/ 行联动方向标（不带数量）/ 旧后端降级 /
  self-check §4.7 全集 / 越界干净。
- self-check 独立复现：`node frontend/self-check.js` → 29/29 PASS，exit 0。
- 隐私默认态实证：fixture 渲染下默认隐藏态 DOM 含 `****`、localStorage `'true'`。
- findings（2 项 P3，required_fixes=[]）：设计期 fixture 行序非严格 net 降序（ADR-8，
  合成数据，运行时后端排序保证）/ formatPrice·maskAmount 经 innerHTML 未显式 escape（沿用既有模式）。

## ⚠️ 升级 review-2 的项：Task A 隔离偏差（方案 A）

Task A 的 Kimi 在 `reviewed_artifacts[]` 列入了 `embedded-review-a-round2.raw-output.md`
（嵌入预审 round2 的 PASS 输出），违反 T1 dispatch「嵌入预审结论对你不可见」的
fresh 隔离契约。

- **实质评估**：Kimi 核心校验（指纹重算 / 147 passed 复现 / discovery sha256 / 预算表
  抽验）均独立完成；3 项 findings 带独立代码行号证据（`private_client.py:326` /
  `snapshot.py:446`），非 round2 fix（§1.5 截断 + §1.4 disabled 三态）复述。
  anchor bias 风险存在但无法证实/证伪。
- **处理（用户 2026-07-06 裁定方案 A）**：接受 ACCEPT；`tasks[A].review_1
  .json_schema_valid=true`（JSON 结构合规事实，与独立性维度分开）；verbatim 落档 +
  bookkeeper 标注小节；升级为 review-2 必查项①，由 final_reviewer 独立判定。
- **review-2 判定**：Codex 独立核查后判定「存在但未实质推翻 ACCEPT」（见
  `50-review-2.md` + `review-2-round1.raw-output.md` finding #3），本 stage 维持双 ACCEPT。

## 绑定关系（交 review-2 核对）

- Task A fp 对应 `fce1452..6ca6ee1`（backend scope）；Task B fp 对应 `6ca6ee1..6c1e992`
  （frontend scope，串行链 base=H_A）。
- stage 级聚合 fp `fce1452..6c1e992` = `6c1e992…:a2140b…`（bookkeeper 算，review-2 独立重算一致）。

---

本地北京时间: 2026-07-06（bookkeeper 续任会话聚合）
作者: bookkeeper (claude_glm)
